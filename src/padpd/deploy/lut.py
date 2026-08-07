"""LUT extraction: spline/polynomial DPD -> hardware interpolation tables.

A fitted branch-gain model (SplineMemoryPolynomial / SplineGMP /
MemoryPolynomialModel — anything with ``gain_curve`` + ``branch_delays``)
is compiled into per-branch complex-gain tables on a uniform amplitude
grid. The runtime then is exactly what DPD silicon implements:

    z(n) = sum_b  x(n - mc_b) * interp(LUT_b, |x(n - me_b)|)

with linear interpolation between adjacent entries and clamp beyond the
last entry. :class:`LUTDPD` is the floating-point reference evaluator of
that datapath; :func:`quantize_lut` adds entry quantization, and
:func:`padpd.deploy.rtl.emit_lut_rtl` turns the same tables into
synthesizable Verilog with a bit-true testbench.

The uniform grid is deliberate: hardware address generation reduces to a
shift/multiply of the amplitude word, whereas the *training-side* knot
grid stays free to be quantile/hybrid — knot placement is a fit-time
concern, table addressing a runtime one.
"""

from __future__ import annotations

import numpy as np

from ..pa.memory_polynomial import delayed
from .fixed_point import quantize_symmetric


def lut_from_model(model, n_entries: int = 256,
                   r_max: float | None = None) -> dict:
    """Sample a fitted branch-gain model into per-branch gain tables.

    Returns ``{"r_grid", "gains" (n_branches, n_entries) complex,
    "r_max", "delays"}``. ``r_max`` defaults to the model's top knot
    (spline models); pass it explicitly for polynomial models.
    """
    if n_entries < 2:
        raise ValueError("n_entries must be >= 2")
    gain_curve = getattr(model, "gain_curve", None)
    if gain_curve is None:
        raise TypeError(f"{type(model).__name__} has no gain_curve(); "
                        "LUT extraction needs a branch-gain model "
                        "(spline/MP)")
    if r_max is None:
        knots = getattr(model, "knots", None)
        if knots is None:
            raise ValueError("r_max is required for models without knots")
        r_max = float(knots[-1])
    r_grid = np.linspace(0.0, float(r_max), int(n_entries))
    gains = np.asarray(gain_curve(r_grid))
    conj_fn = getattr(model, "branch_conjugate", None)
    conjugate = ([bool(c) for c in conj_fn()] if conj_fn is not None
                 else [False] * gains.shape[0])
    return {"r_grid": r_grid, "gains": gains, "r_max": float(r_max),
            "delays": [tuple(d) for d in model.branch_delays()],
            "conjugate": conjugate}


def quantize_lut(lut: dict, entry_bits: int) -> dict:
    """Quantize each branch's table entries to ``entry_bits`` (symmetric,
    power-of-two step — per branch, matching per-tap hardware formats)."""
    gains = np.stack([quantize_symmetric(g, entry_bits)
                      for g in lut["gains"]])
    return {**lut, "gains": gains, "entry_bits": int(entry_bits)}


class LUTDPD:
    """Forward-only LUT + linear-interpolation evaluator (no fit/coeffs).

    The software twin of the hardware datapath; build it from
    :func:`lut_from_model` output via :meth:`from_table`.
    """

    def __init__(self, r_grid: np.ndarray, gains: np.ndarray,
                 delays: list[tuple[int, int]] | None = None,
                 conjugate: list[bool] | None = None):
        self.r_grid = np.asarray(r_grid, dtype=float)
        self.gains = np.asarray(gains, dtype=complex)
        if self.gains.ndim != 2 or len(self.r_grid) != self.gains.shape[1]:
            raise ValueError("gains must be (n_branches, len(r_grid))")
        if delays is None:
            delays = [(m, m) for m in range(self.gains.shape[0])]
        if len(delays) != self.gains.shape[0]:
            raise ValueError("one (carrier, envelope) delay pair per branch")
        self.delays = [tuple(d) for d in delays]
        if conjugate is None:
            conjugate = [False] * self.gains.shape[0]
        if len(conjugate) != self.gains.shape[0]:
            raise ValueError("one conjugate flag per branch")
        self.conjugate = [bool(c) for c in conjugate]

    @classmethod
    def from_table(cls, lut: dict) -> "LUTDPD":
        return cls(lut["r_grid"], lut["gains"], lut["delays"],
                   lut.get("conjugate"))

    @property
    def n_entries(self) -> int:
        return len(self.r_grid)

    @property
    def n_branches(self) -> int:
        return self.gains.shape[0]

    def __call__(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=complex)
        a = np.abs(x)
        out = np.zeros_like(x)
        for (mc, me), g, cj in zip(self.delays, self.gains,
                                   self.conjugate):
            env = np.clip(delayed(a, me), self.r_grid[0], self.r_grid[-1])
            gain = (np.interp(env, self.r_grid, g.real)
                    + 1j * np.interp(env, self.r_grid, g.imag))
            carrier = delayed(x, mc)
            out += (np.conj(carrier) if cj else carrier) * gain
        return out
