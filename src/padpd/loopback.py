"""Loopback (observation-path) impairment model for DPD budget studies.

In a product, DPD adapts from a TX -> coupler -> RX loopback capture.
Every impairment of that observation path is "learned" into the DPD
coefficients (the identification effectively appends the RX inverse to
the predistorter), so each impairment needs a budget. This module
injects configurable, individually-calibrated impairments into a clean
PA output so the resulting DPD degradation can be quantified *before*
the receiver is designed:

- IQ gain/phase imbalance (finite image rejection) and LO leakage (DC)
- carrier frequency offset (independent-LO case) and phase noise
- in-band amplitude ripple and group-delay ripple (frequency response)
- receiver third-order nonlinearity (calibrated IM3 level)
- fractional delay plus slow delay drift over the capture
- additive noise floor (finite SNR)

All levels are specified relative to the signal so the model is
scale-invariant, matching how RF budgets are written (dBc / dB).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class LoopbackChannel:
    """Configurable observation-path impairments; all disabled by default.

    Apply with ``y_obs = channel(y, fs)``. A fresh ``numpy`` RNG seeded
    from ``seed`` is used per call, so captures are reproducible.
    """

    # IQ imbalance / LO
    iq_gain_imbalance_db: float = 0.0
    iq_phase_imbalance_deg: float = 0.0
    lo_leakage_dbc: float | None = None       # DC offset relative to rms
    cfo_hz: float = 0.0                       # independent-LO case
    phase_noise_rms_deg: float = 0.0
    phase_noise_bw_hz: float = 100e3          # one-pole shaping bandwidth
    # frequency response (in-band ripple)
    ripple_db: float = 0.0                    # peak-to-peak magnitude ripple
    gd_ripple_ns: float = 0.0                 # peak-to-peak group-delay ripple
    ripple_period_hz: float = 40e6            # ripple period across the band
    n_fir_taps: int = 33
    # receiver nonlinearity
    rx_im3_dbc: float | None = None           # cubic product level vs signal
    rx_im3_freeze: bool = False               # calibrate kappa once, then
    #                                           behave physically (level-
    #                                           dependent dBc on later calls)
    # timing
    delay_samples: float = 0.0                # fixed integer+fractional delay
    delay_drift_samples: float = 0.0          # linear drift across the capture
    # noise
    snr_db: float | None = None
    seed: int = 0

    _extra: dict = field(default_factory=dict, repr=False)

    # ---- derived figures of merit -----------------------------------
    def irr_db(self) -> float:
        """Image rejection ratio implied by the IQ imbalance settings."""
        g = 10 ** (self.iq_gain_imbalance_db / 20)
        phi = np.deg2rad(self.iq_phase_imbalance_deg)
        a = 0.5 * (1 + g * np.exp(1j * phi))
        b = 0.5 * (1 - g * np.exp(1j * phi))
        if abs(b) == 0:
            return np.inf
        return 20 * np.log10(abs(a) / abs(b))

    def reset(self) -> None:
        """Drop frozen calibrations (rx_im3_freeze kappa)."""
        self._extra.clear()

    # ---- pieces -----------------------------------------------------
    def _fir(self, fs: float) -> np.ndarray | None:
        if self.ripple_db == 0.0 and self.gd_ripple_ns == 0.0:
            return None
        n = 1024
        f = np.fft.fftfreq(n, d=1 / fs)
        mag_db = 0.5 * self.ripple_db * np.cos(
            2 * np.pi * f / self.ripple_period_hz)
        # group delay tau(f) = d(-phase)/d(2*pi*f); a sinusoidal gd ripple
        # integrates to a sinusoidal phase term
        gd = 0.5 * self.gd_ripple_ns * 1e-9 * np.sin(
            2 * np.pi * f / self.ripple_period_hz)
        phase = -2 * np.pi * np.cumsum(gd) * (fs / n)
        h_f = 10 ** (mag_db / 20) * np.exp(1j * phase)
        h_t = np.fft.ifft(h_f)
        m = self.n_fir_taps
        taps = np.concatenate([h_t[-(m // 2):], h_t[: m - m // 2]])
        taps = taps * np.hanning(m)
        return taps / np.abs(taps.sum())  # unit DC gain; rms fixed later

    @staticmethod
    def _frac_delay(y: np.ndarray, delay: float) -> np.ndarray:
        n = len(y)
        f = np.fft.fftfreq(n)
        return np.fft.ifft(np.fft.fft(y) * np.exp(-2j * np.pi * f * delay))

    # ---- main entry -------------------------------------------------
    def __call__(self, y: np.ndarray, fs: float) -> np.ndarray:
        y = np.asarray(y, dtype=complex)
        rng = np.random.default_rng(self.seed)
        n = len(y)
        t = np.arange(n) / fs
        rms = np.sqrt(np.mean(np.abs(y) ** 2))

        # timing: fixed fractional delay, then slow linear drift
        if self.delay_samples:
            y = self._frac_delay(y, self.delay_samples)
        if self.delay_drift_samples:
            idx = np.arange(n) + self.delay_drift_samples * np.arange(n) / n
            idx = np.clip(idx, 0, n - 1)
            y = np.interp(idx, np.arange(n), y.real) + \
                1j * np.interp(idx, np.arange(n), y.imag)

        # frequency response ripple
        taps = self._fir(fs)
        if taps is not None:
            y = np.convolve(y, taps)[taps.size // 2:
                                     taps.size // 2 + n]
            y *= rms / np.sqrt(np.mean(np.abs(y) ** 2))

        # receiver third-order nonlinearity at a calibrated IM3 level.
        # Default: re-calibrated every call (constant dBc — a *budget*
        # model). With rx_im3_freeze the cubic coefficient kappa is
        # calibrated on the FIRST call and then held, so the IM3 level
        # scales 2:1 with input power like a physical receiver — required
        # for attenuator-step identification (deembed.calibrate_rx_im3).
        if self.rx_im3_dbc is not None:
            d = y * np.abs(y) ** 2
            if self.rx_im3_freeze:
                kappa = self._extra.get("rx_im3_kappa")
                if kappa is None:
                    kappa = rms * 10 ** (self.rx_im3_dbc / 20) / \
                        np.sqrt(np.mean(np.abs(d) ** 2))
                    self._extra["rx_im3_kappa"] = float(kappa)
                y = y + kappa * d
            else:
                d *= rms * 10 ** (self.rx_im3_dbc / 20) / \
                    np.sqrt(np.mean(np.abs(d) ** 2))
                y = y + d

        # IQ imbalance
        if self.iq_gain_imbalance_db or self.iq_phase_imbalance_deg:
            g = 10 ** (self.iq_gain_imbalance_db / 20)
            phi = np.deg2rad(self.iq_phase_imbalance_deg)
            a = 0.5 * (1 + g * np.exp(1j * phi))
            b = 0.5 * (1 - g * np.exp(1j * phi))
            y = a * y + b * np.conj(y)

        # CFO + phase noise (shaped Gaussian phase process)
        if self.cfo_hz:
            y = y * np.exp(2j * np.pi * self.cfo_hz * t)
        if self.phase_noise_rms_deg:
            from scipy.signal import lfilter
            w = rng.standard_normal(n)
            alpha = np.exp(-2 * np.pi * self.phase_noise_bw_hz / fs)
            # one-pole shaping p[i] = a*p[i-1] + (1-a)*w[i], vectorized
            # (bit-identical to the former per-sample loop, which had
            # p[0]=0 and started at i=1 — hence w[0]=0)
            w[0] = 0.0
            p = lfilter([1 - alpha], [1, -alpha], w)
            p *= np.deg2rad(self.phase_noise_rms_deg) / max(np.std(p), 1e-30)
            y = y * np.exp(1j * p)

        # LO leakage (DC offset)
        if self.lo_leakage_dbc is not None:
            theta = rng.uniform(0, 2 * np.pi)
            y = y + rms * 10 ** (self.lo_leakage_dbc / 20) * \
                np.exp(1j * theta)

        # noise floor
        if self.snr_db is not None:
            npow = rms ** 2 * 10 ** (-self.snr_db / 10)
            y = y + np.sqrt(npow / 2) * (rng.standard_normal(n)
                                         + 1j * rng.standard_normal(n))
        return y
