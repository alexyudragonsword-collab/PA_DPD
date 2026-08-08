"""QMC: quadrature-modulator correction loop (image + LO leakage).

The TX front end distorts the drive as ``v = a*z + b*conj(z) + c``
(I/Q gain/phase imbalance -> image term b, LO feed-through -> c). These
are *pre-PA* impairments, so unlike post-PA spurs (C-IM3, see
padpd.dpd.direct) they admit an EXACT algebraic pre-inverse,

    precorrect(w) = (conj(a)*(w - c) - b*conj(w - c)) / (|a|^2 - |b|^2),

with F(precorrect(w)) = w identically — no structural ceiling: the loop
cancels down to its estimation noise floor.

Industry splits this out of the DPD as its own slow loop (QMC / LO-cal)
rather than burdening the DPD basis with conj/dc columns; the DPD then
stays purely phase-equivariant (half the coefficients) and each loop
owns one physical mechanism. :class:`QMCCorrector` implements that
loop: transmit ``u = qmc.precorrect(dpd(x))``, observe ``y``, call
:meth:`update` with the DPD-linearized residual — the image (x*) and
DC projections of the residual, referred through the chain gain, drive
the (b, c) estimates; a couple of iterations converge.
"""

from __future__ import annotations

import numpy as np


class QMCCorrector:
    """Estimate-and-invert loop for TX I/Q imbalance and LO leakage."""

    def __init__(self, mu: float = 1.0):
        self.a: complex = 1.0 + 0j       # direct coeff (fixed reference:
        self.b: complex = 0.0 + 0j       # any |a| != 1 folds into the
        self.c: complex = 0.0 + 0j       # chain gain g)
        self.mu = float(mu)

    @property
    def irr_db(self) -> float:
        """Image rejection implied by the current (a, b) estimate."""
        if abs(self.b) == 0:
            return float("inf")
        return float(20 * np.log10(abs(self.a) / abs(self.b)))

    def precorrect(self, z: np.ndarray) -> np.ndarray:
        """Exact pre-inverse of v = a*z + b*conj(z) + c."""
        z = np.asarray(z, dtype=complex)
        det = abs(self.a) ** 2 - abs(self.b) ** 2
        if det <= 0:
            raise ValueError("degenerate imbalance estimate (|b| >= |a|)")
        return (np.conj(self.a) * (z - self.c)
                - self.b * np.conj(z - self.c)) / det

    def update(self, x: np.ndarray, y: np.ndarray,
               target_gain: complex | None = None) -> dict:
        """One estimation step from a transmit/observe capture.

        ``x`` is the *ideal* baseband reference (before DPD), ``y`` the
        observed output. The residual's conj(x) and DC projections,
        referred through the chain gain, correct (b, c). Returns
        diagnostics: residual image/dc levels (dBc) before this update.
        """
        x = np.asarray(x, dtype=complex)
        y = np.asarray(y, dtype=complex)
        g = (complex(np.vdot(x, y) / np.vdot(x, x))
             if target_gain is None else complex(target_gain))
        e = y - g * x
        beta = complex(np.vdot(np.conj(x), e) / np.vdot(x, x))
        dc = complex(np.mean(e))
        sig = float(np.mean(np.abs(g * x) ** 2))
        self.b += self.mu * beta / g
        self.c += self.mu * dc / g
        return {"image_dbc": 10 * np.log10(
                    abs(beta) ** 2 * float(np.mean(np.abs(x) ** 2)) / sig
                    + 1e-30),
                "dc_dbc": 10 * np.log10(abs(dc) ** 2 / sig + 1e-30),
                "gain": g}

    def calibrate(self, pa, x: np.ndarray, dpd=None,
                  iterations: int = 3) -> list[dict]:
        """Run the closed loop against a PA/front-end callable.

        Each pass transmits ``u = precorrect(dpd(x))`` (identity DPD if
        None), observes ``y = pa(u)`` and refines (b, c) from the
        residual. Returns per-iteration diagnostics; the image/dc levels
        of the LAST entry are the post-convergence residuals.
        """
        history = []
        for _ in range(iterations):
            z = dpd(x) if dpd is not None else np.asarray(x, dtype=complex)
            y = pa(self.precorrect(z))
            history.append(self.update(x, y))
        return history
