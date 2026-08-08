"""Observation-path de-embedding: clean the loopback before DPD learns it.

DPD adapts from a TX -> coupler -> RX loopback capture; every
observation impairment (delay, CFO, phase drift, RX I/Q imbalance, LO
leakage, noise) that is not removed gets *learned into the DPD
coefficients* — the identification effectively appends the RX inverse
to the predistorter, and the on-air signal pays for it
(:mod:`padpd.loopback` quantifies the budget). This module closes that
loop: estimate and invert the observation path per capture, using the
known transmitted drive as the reference, so the DPD adapts against
something close to the true PA output.

Corrected (in inverse order of how the path applies them):

- bulk + fractional delay (reuses :func:`padpd.data.align.align_delay`);
- CFO — weighted LS phase-ramp fit on segment correlations — and slow
  common-phase drift (CPE-style per-segment phase, tracks the low-
  frequency part of phase noise);
- RX I/Q imbalance + LO leakage + complex gain in one widely-linear
  inverse, iterated twice (the second pass removes the image-rotation
  residual left by estimating against the drive instead of the true PA
  output).

Two further impairments are NOT blindly estimable from a single PA
capture and use dedicated calibration captures instead — exactly how
products handle them:

- in-band FIR ripple and the RX's own I/Q imbalance:
  :meth:`ObservationDeembedder.calibrate_rx_path` takes a **PA-bypass**
  capture (known cal signal routed through the observation receiver
  only) and stores a widely-linear inverse plus an LS inverse-FIR
  equalizer. From a PA capture alone, the PA's linear response and the
  RX's are indistinguishable — and a blind equalizer would strip the
  PA's linear memory out of the observation, hiding it from the DPD.
  The bypass capture breaks that ambiguity. Calibrating the RX I/Q
  here (instead of per capture) also keeps the *TX* image visible in
  the corrected observation, which is what a QMC loop needs to see.
- RX third-order nonlinearity:
  :meth:`ObservationDeembedder.calibrate_rx_im3` takes two captures of
  the same drive at a known RX attenuator step. The PA's distortion is
  identical in both; the RX cubic scales with the attenuation, so the
  difference isolates it (a blind single-capture fit cannot separate
  PA-cubic from RX-cubic — the regressors are nearly collinear).

The PA's own distortion is phase-equivariant, so it projects onto none
of the estimated correction terms; what the DPD needs to learn passes
through untouched.
"""

from __future__ import annotations

import numpy as np

from .align import align_delay


def _integer_align(ref: np.ndarray, obs: np.ndarray, max_lag: int = 4096):
    """Integer-only bulk alignment (robust under CFO, unlike the
    fractional cross-spectrum refinement in align_delay: a CFO shifts
    the observation spectrum by a fraction of a bin and biases the
    phase-slope delay estimate by over a sample)."""
    from scipy import signal as sig
    corr = sig.correlate(obs, ref, mode="full", method="fft")
    lags = sig.correlation_lags(len(obs), len(ref), mode="full")
    window = np.where(np.abs(lags) <= max_lag)[0]
    lag = int(lags[window[np.argmax(np.abs(corr[window]))]])
    if lag >= 0:
        obs = obs[lag:]
        ref = ref[: len(obs)]
    else:
        ref = ref[-lag:]
        obs = obs[: len(ref)]
    n = min(len(ref), len(obs))
    return ref[:n], obs[:n], lag


def _segment_phases(ref: np.ndarray, obs: np.ndarray, n_seg: int):
    """Per-segment correlation phase and weights (robust CPE tracker)."""
    n = len(ref)
    edges = np.linspace(0, n, n_seg + 1).astype(int)
    t_c = np.empty(n_seg)
    ph = np.empty(n_seg)
    w = np.empty(n_seg)
    for k in range(n_seg):
        s = slice(edges[k], edges[k + 1])
        c = np.vdot(ref[s], obs[s])
        t_c[k] = 0.5 * (edges[k] + edges[k + 1])
        ph[k] = np.angle(c)
        w[k] = np.abs(c)
    return t_c, np.unwrap(ph), w


class ObservationDeembedder:
    """Per-capture estimator/corrector for the DPD observation path.

    ``process(tx_ref, obs)`` returns ``(ref_trimmed, obs_corrected,
    info)`` — feed the corrected pair to ILA/AdaptiveDPD identification.
    Stateless across captures by default (each capture re-estimates,
    which is what a tracking loop does block by block).
    """

    def __init__(self, correct_delay: bool = True, correct_cfo: bool = True,
                 correct_phase_drift: bool = True, correct_iq: bool = True,
                 n_seg: int = 64):
        self.correct_delay = correct_delay
        self.correct_cfo = correct_cfo
        self.correct_phase_drift = correct_phase_drift
        self.correct_iq = correct_iq
        self.n_seg = int(n_seg)
        self._rx_wl: tuple[complex, complex, complex] | None = None
        self._rx_fir: np.ndarray | None = None
        self._rx_im3: complex | None = None

    # ---- component estimators ---------------------------------------
    def _remove_cfo(self, ref, obs, info):
        t_c, ph, w = _segment_phases(ref, obs, self.n_seg)
        wsum = w.sum()
        if wsum == 0:
            return obs
        t0 = np.average(t_c, weights=w)
        p0 = np.average(ph, weights=w)
        denom = np.sum(w * (t_c - t0) ** 2)
        slope = (np.sum(w * (t_c - t0) * (ph - p0)) / denom
                 if denom > 0 else 0.0)
        info["cfo_cycles_per_sample"] = float(slope / (2 * np.pi))
        return obs * np.exp(-1j * slope * np.arange(len(obs)))

    def _remove_phase_drift(self, ref, obs, info):
        t_c, ph, w = _segment_phases(ref, obs, self.n_seg)
        # keep the mean phase (part of the complex gain, removed by the
        # widely-linear stage); subtract only the drift around it
        drift = ph - np.average(ph, weights=np.maximum(w, 1e-30))
        phase = np.interp(np.arange(len(obs)), t_c, drift)
        info["phase_drift_rms_deg"] = float(np.degrees(
            np.sqrt(np.average(drift ** 2, weights=w))))
        return obs * np.exp(-1j * phase)

    def _invert_iq(self, ref, obs, info):
        for _ in range(2):        # second pass kills the rotation residual
            phi = np.stack([ref, np.conj(ref), np.ones_like(ref)], axis=1)
            alpha, beta, dc = np.linalg.lstsq(phi, obs, rcond=None)[0]
            det = abs(alpha) ** 2 - abs(beta) ** 2
            if det <= 0:
                break
            obs = (np.conj(alpha) * (obs - dc)
                   - beta * np.conj(obs - dc)) / det
        info["rx_irr_db"] = float(20 * np.log10(
            abs(alpha) / max(abs(beta), 1e-15)))
        info["rx_dc"] = complex(dc)
        return obs

    def _apply_rx_wl(self, y, info):
        """Apply the calibrated (PA-bypass) RX widely-linear inverse.

        Unlike the per-capture fit this does NOT normalize the gain to
        the drive and does NOT touch the TX image — a QMC loop running
        on the corrected observation still sees what it must correct.
        """
        alpha, beta, dc = self._rx_wl
        det = abs(alpha) ** 2 - abs(beta) ** 2
        y = (np.conj(alpha) * (y - dc) - beta * np.conj(y - dc)) / det
        info["rx_irr_db"] = float(20 * np.log10(
            abs(alpha) / max(abs(beta), 1e-15)))
        info["rx_dc"] = complex(dc)
        return y

    # ---- main entry --------------------------------------------------
    def _process_linear(self, ref, y, info):
        """Delay / CFO / drift / widely-linear stages (shared by
        process() and the calibration captures)."""
        if self.correct_delay:
            ref, y, lag = _integer_align(ref, y)
            info["delay_int"] = lag
        if self.correct_cfo:
            y = self._remove_cfo(ref, y, info)
        if self.correct_delay:
            ref, y, d = align_delay(ref, y)
            info["delay_samples"] = float(info["delay_int"]
                                          + d["lag_total"])
        if self.correct_phase_drift:
            y = self._remove_phase_drift(ref, y, info)
        if self._rx_wl is not None:
            y = self._apply_rx_wl(y, info)
        elif self.correct_iq:
            y = self._invert_iq(ref, y, info)
        else:
            g = complex(np.vdot(ref, y) / np.vdot(ref, ref))
            y = y / g
            info["gain"] = g
        return ref, y

    def process(self, tx_ref: np.ndarray, obs: np.ndarray):
        """Estimate and invert the observation path for one capture.

        Order matters: integer delay first (CFO-robust), then CFO (so
        the spectra line up), then the fractional-delay refinement,
        then phase drift and the widely-linear stage; finally the
        calibrated RX-IM3 inverse and FIR equalizer, when calibrated
        (the receiver applies ripple before its nonlinearity before
        its I/Q imbalance, so the inverses run in reverse).
        """
        ref = np.asarray(tx_ref, dtype=complex)
        y = np.asarray(obs, dtype=complex)
        info: dict = {}
        ref, y = self._process_linear(ref, y, info)
        if self._rx_im3 is not None:
            y = y - self._rx_im3 * y * np.abs(y) ** 2
            info["rx_im3_kappa"] = complex(self._rx_im3)
        if self._rx_fir is not None:
            y = np.convolve(y, self._rx_fir, mode="same")
        return ref, y, info

    # ---- dedicated-capture calibrations ------------------------------
    def calibrate_rx_path(self, ref_cal: np.ndarray, obs_cal: np.ndarray,
                          n_taps: int = 33, fir_ridge: float = 1e-2) -> dict:
        """Calibrate the RX linear response from a PA-BYPASS capture.

        ``ref_cal`` is the known cal signal, ``obs_cal`` what the
        observation receiver captured with the PA out of the path.
        Stores (a) the RX widely-linear response (I/Q imbalance + DC +
        complex gain) and (b) an ``n_taps`` LS inverse-FIR equalizer
        for the in-band ripple; every later :meth:`process` applies
        both. Only a bypass capture can separate the RX's linear
        response from the PA's — a blind fit on a PA capture would
        equalize the PA's own memory out of the observation and hide
        it from the DPD.
        """
        ref = np.asarray(ref_cal, dtype=complex)
        y = np.asarray(obs_cal, dtype=complex)
        info: dict = {}
        self._rx_wl = None                    # estimate, don't apply
        saved_iq, self.correct_iq = self.correct_iq, False
        try:
            ref, y = self._process_linear(ref, y, info)
        finally:
            self.correct_iq = saved_iq
        phi = np.stack([ref, np.conj(ref), np.ones_like(ref)], axis=1)
        alpha, beta, dc = np.linalg.lstsq(phi, y, rcond=None)[0]
        if abs(alpha) ** 2 - abs(beta) ** 2 <= 0:
            raise ValueError("degenerate RX imbalance estimate")
        self._rx_wl = (complex(alpha), complex(beta), complex(dc))
        y = self._apply_rx_wl(y, info)

        half = n_taps // 2
        cols = np.stack([np.roll(y, k - half) for k in range(n_taps)],
                        axis=1)
        # Ridge toward the pass-through (delta) tap: the cal signal only
        # excites the occupied band, so an unregularized LS inverse is
        # unconstrained out of band and can amplify the PA's distortion
        # shoulders when applied to a PA capture. The delta prior pins
        # the equalizer to unity wherever the data says nothing.
        delta = np.zeros(n_taps, dtype=complex)
        delta[half] = 1.0
        r_mat = cols.conj().T @ cols
        lam = fir_ridge * np.trace(r_mat).real / n_taps
        taps = np.linalg.solve(r_mat + lam * np.eye(n_taps),
                               cols.conj().T @ ref + lam * delta)
        self._rx_fir = taps
        resid = cols @ taps - ref
        info["fir_taps"] = n_taps
        info["fir_fit_nmse_db"] = float(10 * np.log10(
            np.mean(np.abs(resid) ** 2)
            / np.mean(np.abs(ref) ** 2) + 1e-30))
        return info

    def calibrate_rx_im3(self, tx_ref: np.ndarray, obs_hi: np.ndarray,
                         obs_lo: np.ndarray, step_db: float) -> dict:
        """Calibrate the RX cubic nonlinearity from an attenuator step.

        Two captures of the SAME drive, the second with the RX input
        attenuated by ``step_db``. The PA's distortion is common mode;
        the RX cubic term scales with the square of the attenuation,
        so the (scale-aligned) difference isolates it — the separation
        a blind single-capture fit cannot make. Requires a receiver
        whose IM3 level actually moves with input power
        (``LoopbackChannel(rx_im3_freeze=True)`` in simulation).
        Stores kappa; later :meth:`process` calls subtract
        ``kappa * y * |y|^2`` (first-order inverse, valid at the hi
        capture's operating level).
        """
        ref = np.asarray(tx_ref, dtype=complex)
        i1: dict = {}
        i2: dict = {}
        _, y1 = self._process_linear(ref.copy(),
                                     np.asarray(obs_hi, dtype=complex), i1)
        _, y2 = self._process_linear(ref.copy(),
                                     np.asarray(obs_lo, dtype=complex), i2)
        n = min(len(y1), len(y2))
        y1, y2 = y1[:n], y2[:n]
        g_rel = np.vdot(y1, y2) / np.vdot(y1, y1)   # scale alignment
        diff = y1 - y2 / g_rel
        a = 10 ** (-abs(step_db) / 20)
        b = y1 * np.abs(y1) ** 2
        phi = np.stack([y1, np.ones_like(y1)], axis=1)
        b_perp = b - phi @ np.linalg.lstsq(phi, b, rcond=None)[0]
        kappa = complex(np.vdot(b_perp, diff)
                        / ((1 - a ** 2) * np.vdot(b_perp, b_perp)))
        self._rx_im3 = kappa
        level = float(10 * np.log10(
            abs(kappa) ** 2 * np.mean(np.abs(b) ** 2)
            / np.mean(np.abs(y1) ** 2) + 1e-30))
        return {"kappa": kappa, "rx_im3_dbc": level}

    def wrap(self, pa, channel, fs: float):
        """Compose ``u -> deembed(u, channel(pa(u), fs))`` for closed-loop
        identification (drop-in ``pa`` argument for ILA/AdaptiveDPD).

        The corrected observation is re-scaled by the drive's LS gain so
        the wrapped callable still *looks* like a PA (gain included) to
        target-gain estimation.
        """
        def observed(u):
            u = np.asarray(u, dtype=complex)
            ref, y, _ = self.process(u, channel(pa(u), fs))
            if len(ref) < len(u):     # pad the trimmed tail (delay cut)
                y = np.concatenate([y, np.zeros(len(u) - len(ref),
                                                dtype=complex)])
            return y
        return observed
