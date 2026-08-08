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

NOT corrected: in-band FIR ripple (needs an equalizer stage) and RX
nonlinearity — keep those inside the loopback budget instead.

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

    # ---- main entry --------------------------------------------------
    def process(self, tx_ref: np.ndarray, obs: np.ndarray):
        """Estimate and invert the observation path for one capture.

        Order matters: integer delay first (CFO-robust), then CFO (so
        the spectra line up), then the fractional-delay refinement,
        then phase drift and the widely-linear stage.
        """
        ref = np.asarray(tx_ref, dtype=complex)
        y = np.asarray(obs, dtype=complex)
        info: dict = {}
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
        if self.correct_iq:
            y = self._invert_iq(ref, y, info)
        else:
            g = complex(np.vdot(ref, y) / np.vdot(ref, ref))
            y = y / g
            info["gain"] = g
        return ref, y, info

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
