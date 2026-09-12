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
    orders_fn = getattr(model, "branch_phase_orders", None)
    if orders_fn is not None:
        orders = [int(o) for o in orders_fn()]
    else:
        conj_fn = getattr(model, "branch_conjugate", None)
        orders = ([-1 if c else 1 for c in conj_fn()]
                  if conj_fn is not None else [1] * gains.shape[0])
    dc_fn = getattr(model, "dc_coefficient", None)
    dc = dc_fn() if dc_fn is not None else None
    return {"r_grid": r_grid, "gains": gains, "r_max": float(r_max),
            "delays": [tuple(d) for d in model.branch_delays()],
            "phase_orders": orders,
            "conjugate": [o < 0 for o in orders],
            "dc": complex(dc) if dc is not None else 0j}


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
                 phase_orders: list[int] | None = None,
                 dc: complex = 0j):
        self.r_grid = np.asarray(r_grid, dtype=float)
        self.gains = np.asarray(gains, dtype=complex)
        if self.gains.ndim != 2 or len(self.r_grid) != self.gains.shape[1]:
            raise ValueError("gains must be (n_branches, len(r_grid))")
        if delays is None:
            delays = [(m, m) for m in range(self.gains.shape[0])]
        if len(delays) != self.gains.shape[0]:
            raise ValueError("one (carrier, envelope) delay pair per branch")
        self.delays = [tuple(d) for d in delays]
        if phase_orders is None:
            phase_orders = [1] * self.gains.shape[0]
        if len(phase_orders) != self.gains.shape[0]:
            raise ValueError("one phase order per branch")
        if any(o not in (1, -1, -3) for o in phase_orders):
            raise ValueError("phase orders must be +1, -1 or -3")
        self.phase_orders = [int(o) for o in phase_orders]
        self.dc = complex(dc)

    @property
    def conjugate(self) -> list[bool]:
        """Back-compat view: phase-conjugated branches (order < 0)."""
        return [o < 0 for o in self.phase_orders]

    @classmethod
    def from_table(cls, lut: dict) -> LUTDPD:
        orders = lut.get("phase_orders")
        if orders is None:
            orders = [-1 if c else 1
                      for c in lut.get("conjugate",
                                       [False] * len(lut["delays"]))]
        return cls(lut["r_grid"], lut["gains"], lut["delays"],
                   orders, lut.get("dc", 0j))

    @property
    def n_entries(self) -> int:
        return len(self.r_grid)

    @property
    def n_branches(self) -> int:
        return self.gains.shape[0]

    def __call__(self, x: np.ndarray) -> np.ndarray:
        from ..pa.spline import _phase_carrier
        x = np.asarray(x, dtype=complex)
        a = np.abs(x)
        out = np.full_like(x, self.dc)
        for (mc, me), g, order in zip(self.delays, self.gains,
                                      self.phase_orders, strict=True):
            env = np.clip(delayed(a, me), self.r_grid[0], self.r_grid[-1])
            gain = (np.interp(env, self.r_grid, g.real)
                    + 1j * np.interp(env, self.r_grid, g.imag))
            out += _phase_carrier(delayed(x, mc), order) * gain
        return out
