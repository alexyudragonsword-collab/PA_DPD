"""TX-side I/Q imbalance wrapper: the image-distortion virtual DUT.

An imperfect I/Q modulator maps the ideal baseband ``x`` to

    x_iq = a * x + b * conj(x),
    a = (1 + g e^{j phi}) / 2,   b = (1 - g e^{j phi}) / 2,

with ``g`` the linear gain mismatch and ``phi`` the phase mismatch —
the ``b`` term is the image, sitting at mirrored baseband frequency and
suppressed by the image rejection ratio IRR = |a|^2 / |b|^2. Fed through
a nonlinear PA, the image both passes linearly and intermodulates with
the direct signal, producing the x* and x*|x|^2 distortion families
that a phase-equivariant (x-only) model cannot represent by
construction. :class:`IQImbalancePA` chains this modulator error in
front of any PA callable, giving the widely-linear
(``conjugate=True``) spline branches something real to earn their
coefficients on.

(The observation-path counterpart — RX I/Q imbalance in the DPD
feedback — lives in :mod:`padpd.loopback`.)
"""

from __future__ import annotations

from typing import Callable

import numpy as np


def iq_imbalance_coeffs(gain_db: float,
                        phase_deg: float) -> tuple[complex, complex]:
    """Direct/image coefficients (a, b) of an imbalanced I/Q modulator."""
    g = 10 ** (gain_db / 20)
    phi = np.deg2rad(phase_deg)
    a = 0.5 * (1 + g * np.exp(1j * phi))
    b = 0.5 * (1 - g * np.exp(1j * phi))
    return complex(a), complex(b)


def irr_db(gain_db: float, phase_deg: float) -> float:
    """Image rejection ratio implied by an imbalance setting."""
    a, b = iq_imbalance_coeffs(gain_db, phase_deg)
    if abs(b) == 0:
        return float("inf")
    return float(20 * np.log10(abs(a) / abs(b)))


class IQImbalancePA:
    """PA driven through an imbalanced TX I/Q modulator (forward-only).

    Wraps any PA callable; not a fittable model. Typical handset-class
    uncalibrated imbalance is ~0.2-0.5 dB / 2-5 deg (IRR ~25-35 dB).
    """

    def __init__(self, pa: Callable[[np.ndarray], np.ndarray],
                 gain_db: float = 0.3, phase_deg: float = 3.0):
        self.pa = pa
        self.gain_db = float(gain_db)
        self.phase_deg = float(phase_deg)
        self.a, self.b = iq_imbalance_coeffs(gain_db, phase_deg)

    @property
    def irr_db(self) -> float:
        return irr_db(self.gain_db, self.phase_deg)

    def __call__(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=complex)
        return self.pa(self.a * x + self.b * np.conj(x))


class TxFrontEndPA(IQImbalancePA):
    """Direct-conversion TX front end + PA: image, LO leakage, C-IM3.

    Extends the I/Q-imbalance wrapper with the two remaining
    hard-to-filter mixer/PA products of a direct-conversion chain:

    - ``lo_leakage_dbc``: LO feed-through — a constant complex offset at
      the PA input (fixed pseudo-random phase), i.e. energy exactly at
      the LO frequency;
    - ``cim3_dbc``: counter-IM3 at LO-3BB. The switching mixer's 3rd LO
      harmonic converts the baseband to a conj(x) component at 3LO-BB;
      the PA's cubic term intermodulates it with the wanted signal,
      (3LO-BB) - 2(LO+BB) = LO-3BB, with baseband-equivalent envelope
      conj(x)^3 — a phase harmonic exp(-j3*phi) that no x- or
      conj(x)-based basis can represent. (The second C-IM3 mechanism,
      PA IM3 between the image and the wanted signal,
      2(LO-BB) - (LO+BB) = LO-3BB, lands on the SAME conj(x)^3 term
      with coefficient ~b^2 and emerges from the wrapped PA itself.)
      The injected level is calibrated per call relative to the PA
      output rms, so it is scale-invariant like the loopback
      impairments.
    """

    def __init__(self, pa: Callable[[np.ndarray], np.ndarray],
                 gain_db: float = 0.3, phase_deg: float = 3.0,
                 lo_leakage_dbc: float | None = None,
                 cim3_dbc: float | None = None, seed: int = 0):
        super().__init__(pa, gain_db=gain_db, phase_deg=phase_deg)
        self.lo_leakage_dbc = lo_leakage_dbc
        self.cim3_dbc = cim3_dbc
        theta = np.random.default_rng(seed).uniform(0, 2 * np.pi)
        self._dc_phase = complex(np.exp(1j * theta))

    def __call__(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=complex)
        v = self.a * x + self.b * np.conj(x)
        rms_in = float(np.sqrt(np.mean(np.abs(v) ** 2))) or 1.0
        if self.lo_leakage_dbc is not None:
            v = v + (rms_in * 10 ** (self.lo_leakage_dbc / 20)
                     * self._dc_phase)
        y = self.pa(v)
        if self.cim3_dbc is not None:
            d = np.conj(x) ** 3
            rms_y = float(np.sqrt(np.mean(np.abs(y) ** 2))) or 1.0
            rms_d = float(np.sqrt(np.mean(np.abs(d) ** 2))) or 1.0
            y = y + d * (rms_y * 10 ** (self.cim3_dbc / 20) / rms_d)
        return y
