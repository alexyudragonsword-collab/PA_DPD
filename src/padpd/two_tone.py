"""Two-tone memory diagnostics and DPD resource budgeting.

A single-tone AM-AM/AM-PM sweep captures the *static* nonlinearity but is
blind to memory: the same static curve fits a memoryless PA and a strongly
dynamic one. A two-tone excitation exposes memory directly, and it is the
one large-signal characterization a pre-tapeout **circuit simulator gives
cheaply** (a harmonic-balance two-tone at a handful of tone spacings), so
it is the natural bridge from Spectre to a DPD complexity estimate.

Two independent memory signatures are read from the third-order
intermodulation (IM3) products:

- **spacing dependence** — sweeping the tone spacing ``df`` sweeps the
  envelope frequency; if IM3 changes with ``df`` the device has memory
  (bias-network / matching electrical memory at MHz spacings, thermal
  memory at kHz spacings). A memoryless nonlinearity gives IM3 flat in
  ``df``.
- **upper/lower asymmetry** — a memoryless nonlinearity produces equal
  lower and upper IM3; any imbalance is a memory (complex/cross-term)
  signature, and its growth toward small spacing points at thermal
  memory.

The magnitude of these two effects is condensed into a scalar
**memory-strength** figure (in dB), which :func:`recommend_dpd_budget`
maps to a *rough* DPD sizing — how much memory depth and whether cross
terms are worth reserving. This sizes the hardware; the coefficients
themselves are still trained on measured data (a static LUT plus this
budget is a plan, not a fitted DPD).

The same analysis runs on any :class:`~padpd.pa.base.PAModel` (the
synthetic ReferencePA, an HB-imported Wiener-Hammerstein PA) via
:func:`sweep_two_tone`, or directly on a measured/simulated IM3-vs-spacing
table via :func:`memory_strength_from_table`, so a circuit two-tone sweep
and a behavioral model can be compared on one axis.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def two_tone_signal(spacing_hz: float, fs: float, n: int = 8192,
                    amp: float = 1.0) -> tuple[np.ndarray, int]:
    """Complex-baseband two-tone at +/-df/2 about DC (equal tones).

    The half-spacing is snapped to an integer number of FFT bins so the
    tones and their IM products land on exact bins (coherent, leakage
    free). Returns the signal and that half-spacing in bins ``k`` (tones
    at +/-k, IM3 at +/-3k, IM5 at +/-5k).
    """
    k = int(round(spacing_hz / fs * n / 2))
    if k < 3:
        raise ValueError("tone spacing too small for this fs/n "
                         "(need >= 3 bins per half-spacing)")
    if 5 * k >= n // 2:
        raise ValueError("tone spacing too large: IM5 exceeds Nyquist")
    t = np.arange(n)
    f = k / n
    x = amp * (np.exp(2j * np.pi * f * t) + np.exp(-2j * np.pi * f * t))
    return x, k


def measure_imd(pa, spacing_hz: float, fs: float, n: int = 8192,
                amp: float = 1.0) -> dict:
    """Drive ``pa`` with a two-tone and read tone/IM3/IM5 levels.

    Returns dBc levels (relative to one fundamental tone) for the lower
    and upper IM3, their average and asymmetry, and the average IM5.
    Each product is integrated over its bin +/-1 to absorb the small
    leakage from a model's convolution start-up transient.
    """
    x, k = two_tone_signal(spacing_hz, fs, n, amp)
    y = np.asarray(pa(x), dtype=complex)
    spec = np.fft.fft(y) / n

    def level(bin_center: int) -> float:
        idx = (np.array([bin_center - 1, bin_center, bin_center + 1]) % n)
        return float(np.sqrt(np.sum(np.abs(spec[idx]) ** 2)))

    tone = 0.5 * (level(k) + level(-k))
    ref = 20 * np.log10(max(tone, 1e-30))
    im3_lo = 20 * np.log10(max(level(-3 * k), 1e-30)) - ref
    im3_hi = 20 * np.log10(max(level(3 * k), 1e-30)) - ref
    im5_lo = 20 * np.log10(max(level(-5 * k), 1e-30)) - ref
    im5_hi = 20 * np.log10(max(level(5 * k), 1e-30)) - ref
    im3_avg = 10 * np.log10(
        (10 ** (im3_lo / 10) + 10 ** (im3_hi / 10)) / 2)
    im5_avg = 10 * np.log10(
        (10 ** (im5_lo / 10) + 10 ** (im5_hi / 10)) / 2)
    return {"spacing_hz": float(spacing_hz),
            "im3_lower_dbc": im3_lo, "im3_upper_dbc": im3_hi,
            "im3_avg_dbc": im3_avg, "im3_asym_db": im3_hi - im3_lo,
            "im5_avg_dbc": im5_avg}


@dataclass
class TwoToneResult:
    """Two-tone IM3/IM5 vs tone spacing plus condensed memory metrics.

    ``memory_strength_db`` is the headline scalar: the larger of the IM3
    spacing spread and the peak IM3 asymmetry, i.e. roughly how many dB
    of IM3 behavior a memoryless (static AM-AM/AM-PM) model cannot
    reproduce.
    """

    spacings_hz: np.ndarray
    im3_lower_dbc: np.ndarray
    im3_upper_dbc: np.ndarray
    im3_avg_dbc: np.ndarray
    im5_avg_dbc: np.ndarray
    # condensed memory metrics
    im3_spread_db: float          # spacing dependence (diagonal memory)
    im3_asym_db: float            # peak upper/lower imbalance (cross memory)
    memory_strength_db: float
    thermal_suspected: bool       # asymmetry peaks at the smallest spacing

    @classmethod
    def from_curves(cls, spacings_hz, im3_lower_dbc, im3_upper_dbc,
                    im5_avg_dbc=None) -> "TwoToneResult":
        s = np.asarray(spacings_hz, dtype=float)
        lo = np.asarray(im3_lower_dbc, dtype=float)
        hi = np.asarray(im3_upper_dbc, dtype=float)
        order = np.argsort(s)
        s, lo, hi = s[order], lo[order], hi[order]
        avg = 10 * np.log10((10 ** (lo / 10) + 10 ** (hi / 10)) / 2)
        im5 = (np.full_like(s, np.nan) if im5_avg_dbc is None
               else np.asarray(im5_avg_dbc, dtype=float)[order])
        asym = np.abs(hi - lo)
        spread = float(np.ptp(avg)) if len(avg) > 1 else 0.0
        asym_peak = float(np.max(asym))
        # thermal memory shows as asymmetry that is largest at the
        # smallest spacing (slowest envelope) and falls off with spacing
        thermal = bool(len(asym) >= 3
                       and np.argmax(asym) == 0
                       and asym[0] > 1.5 * (np.median(asym[1:]) + 1e-9))
        return cls(spacings_hz=s, im3_lower_dbc=lo, im3_upper_dbc=hi,
                   im3_avg_dbc=avg, im5_avg_dbc=im5,
                   im3_spread_db=spread, im3_asym_db=asym_peak,
                   memory_strength_db=max(spread, asym_peak),
                   thermal_suspected=thermal)


def sweep_two_tone(pa, spacings_hz, fs: float, n: int = 8192,
                   amp: float = 1.0) -> TwoToneResult:
    """Measure IM3/IM5 vs tone spacing on a PA model and condense to
    a :class:`TwoToneResult`."""
    rows = [measure_imd(pa, s, fs, n, amp) for s in spacings_hz]
    return TwoToneResult.from_curves(
        [r["spacing_hz"] for r in rows],
        [r["im3_lower_dbc"] for r in rows],
        [r["im3_upper_dbc"] for r in rows],
        [r["im5_avg_dbc"] for r in rows])


def memory_strength_from_table(spacings_hz, im3_lower_dbc, im3_upper_dbc,
                               im5_avg_dbc=None) -> TwoToneResult:
    """Build a :class:`TwoToneResult` from a measured/simulated table.

    Feed a circuit-simulator (or bench) two-tone sweep — lower and upper
    IM3 in dBc at several tone spacings — to get the same memory-strength
    figure and DPD budget as a behavioral model, so simulation and model
    land on one axis.
    """
    return TwoToneResult.from_curves(spacings_hz, im3_lower_dbc,
                                     im3_upper_dbc, im5_avg_dbc)


def load_two_tone_csv(path: str) -> TwoToneResult:
    """Read a two-tone IM3-vs-spacing table (e.g. a Spectre two-tone sweep).

    Columns (header row, case-insensitive; extra columns ignored)::

        spacing_hz,im3_lower_dbc,im3_upper_dbc[,im5_avg_dbc]

    ``spacing_hz`` is the tone spacing (df); the two IM3 columns are the
    lower and upper third-order sideband levels in dBc (relative to one
    fundamental tone). Returns a :class:`TwoToneResult`; pass it to
    :func:`recommend_dpd_budget` for a DPD sizing.
    """
    import csv
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"{path}: empty CSV")
    cols = {k.strip().lower(): k for k in rows[0]}
    need = ("spacing_hz", "im3_lower_dbc", "im3_upper_dbc")
    for key in need:
        if key not in cols:
            raise ValueError(f"{path}: missing column '{key}' "
                             f"(need {', '.join(need)})")

    def column(key):
        return np.array([float(r[cols[key]]) for r in rows])

    im5 = column("im5_avg_dbc") if "im5_avg_dbc" in cols else None
    return TwoToneResult.from_curves(column("spacing_hz"),
                                     column("im3_lower_dbc"),
                                     column("im3_upper_dbc"), im5)


def recommend_dpd_budget(result, order: int = 5) -> dict:
    """Map a memory-strength figure to a rough DPD sizing.

    Accepts a :class:`TwoToneResult` (preferred — the diagonal/cross
    split is used) or a scalar memory-strength in dB. Returns a dict with

    - ``memory_depth`` : diagonal memory taps to reserve (from the IM3
      spacing spread),
    - ``use_cross_terms`` / ``gmp_config`` : whether GMP lag/lead cross
      terms are worth carrying (from the IM3 asymmetry), and a ready
      ``GMPModel(**gmp_config)`` recipe,
    - ``est_coeffs`` : that recipe's coefficient count,
    - ``rationale`` : one-line justification.

    This sizes hardware from a *cheap* characterization; the coefficients
    are still fit on measured data. Treat the depth as a floor to reserve,
    then confirm/trim against a real DPD sweep.
    """
    if isinstance(result, TwoToneResult):
        spread = result.im3_spread_db
        asym = result.im3_asym_db
        thermal = result.thermal_suspected
        strength = result.memory_strength_db
    else:
        spread = asym = strength = float(result)
        thermal = False

    # diagonal memory depth from the (symmetric) spacing spread
    for thr, d in ((0.5, 1), (1.5, 2), (3.0, 3), (6.0, 4)):
        if spread < thr:
            depth = d
            break
    else:
        depth = 5

    # cross (lag/lead) terms from the asymmetry
    use_cross = asym >= 1.0
    if asym >= 4.0:
        lag_memory = lead_memory = 2
        span = 2
    elif use_cross:
        lag_memory = lead_memory = 1
        span = 2
    else:
        lag_memory = lead_memory = 0
        span = 1
    cross_order = 0 if not use_cross else max(1, (order - 1) // 2)

    gmp_config = {"order": order, "memory_depth": depth,
                  "lag_order": cross_order, "lag_memory": lag_memory,
                  "lag_span": span, "lead_order": cross_order,
                  "lead_memory": lead_memory, "lead_span": span}
    est_coeffs = (order * depth
                  + cross_order * lag_memory * span
                  + cross_order * lead_memory * span)

    bits = [f"IM3 varies {spread:.1f} dB across spacing -> "
            f"memory_depth {depth}"]
    if use_cross:
        bits.append(f"IM3 asymmetry {asym:.1f} dB -> GMP cross terms "
                    f"(lag/lead memory {lag_memory})")
        if thermal:
            bits.append("asymmetry peaks at smallest spacing -> thermal "
                        "memory; consider a slow (envelope-LPF) branch")
    else:
        bits.append(f"IM3 asymmetry {asym:.1f} dB -> memoryless-ish, no "
                    "cross terms")

    return {"memory_strength_db": strength, "memory_depth": depth,
            "use_cross_terms": use_cross, "thermal_suspected": thermal,
            "gmp_config": gmp_config, "est_coeffs": est_coeffs,
            "rationale": "; ".join(bits)}
