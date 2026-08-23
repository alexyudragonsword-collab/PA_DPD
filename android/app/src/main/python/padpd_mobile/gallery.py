"""The fourteen chart specs, each with something to draw.

This exists to exercise the renderer, not to demonstrate the algorithms.
Phase 3 wires the real pages; until then the gallery is how every spec
shape gets drawn at least once on a real screen - twin axes, log axes,
categorical ticks, masks, NaN gaps, equal aspect.

Each entry says where its data comes from, and the UI shows it:

``computed``  the real service path ran and this is its output;
``sampled``   the real producer is too slow to sit behind a tap, so the
              input is a small representative fixture.

That distinction is the point of labelling it. A gallery of plausible
charts is easy to mistake for evidence that the pipeline works, and for
half of these it would not be evidence of anything of the sort.
"""

from __future__ import annotations

import numpy as np


def _synth():
    """A small synthetic source, shared by the cheap entries."""
    import gui_core.services as services
    return services.cached_synthetic_source(bandwidth_hz=80e6, symbols=4)


# ------------------------------------------------------------------ cheap

def _psd():
    src = _synth()
    return ("psd", [{"PA in": src["x_val"], "PA out": src["y_val"]},
                    src["fs"]], {})


def _ccdf():
    src = _synth()
    return ("ccdf", [{"PA in": src["x_val"], "PA out": src["y_val"]}], {})


def _amam():
    src = _synth()
    return ("amam", [src["x_val"], src["y_val"]], {})


def _time():
    src = _synth()
    return ("time", [{"PA in": src["x_val"], "PA out": src["y_val"]},
                     src["fs"]], {})


def _constellation():
    import gui_core.services as services
    wf = services.make_waveform(80e6, 1024, 4, 0)
    src = _synth()
    y = src["pa"](wf["x"])
    gain = np.vdot(wf["x"], y) / np.vdot(wf["x"], wf["x"])
    pts = services.constellation_points(y, wf["wf"], gain)
    ideal = services.constellation_points(wf["x"], wf["wf"], 1.0)
    return ("constellation", [{"ideal": ideal, "through PA": pts}], {})


def _bitwidth():
    import gui_core.services as services
    src = _synth()
    model = services.fit_classical(src, "GMP")["model"]
    return ("bitwidth", [{"GMP": services.bitwidth_sweep(
        model, src, bits=(16, 12, 10, 8))}], {})


# ------------------------------------------------ real but slower on a phone

def _gain_modulation():
    import gui_core.services as services
    return ("gain_modulation",
            [services.run_gain_modulation(fit_state_model=False,
                                          n_symbols=4)], {})


def _adaptive_evm():
    import gui_core.services as services
    return ("adaptive_evm",
            [services.run_adaptive_dpd(n_blocks=6, n_symbols=4)], {})


def _three_loop():
    import gui_core.services as services
    return ("three_loop",
            [services.run_three_loop_demo(n_blocks=6, n_symbols=3)], {})


# ---------------------------------------------------------------- fixtures
#
# Producers that are minutes of compute (codesign_sweep), or that need
# torch (train history, gradient co-design), or an instrument file that is
# not on the phone (two-tone CSV). Shapes are taken from real runs; the
# numbers are representative, not measured.

def _two_tone():
    s = np.array([1e6, 2e6, 5e6, 10e6, 20e6, 50e6])
    return ("two_tone", [{
        "spacings_hz": s,
        "im3_lower_dbc": [-46.0, -44.2, -41.8, -39.9, -38.1, -36.4],
        "im3_upper_dbc": [-45.1, -43.6, -41.0, -39.2, -37.4, -35.9],
    }], {})


def _bars():
    return ("bars", [
        ["GMP-510 baseline", "Spline-MP", "Spline-GMP conj+dc",
         "a deliberately overlong run name for truncation"],
        {"ACLR": [-44.1, -46.8, -48.2, -45.0],
         "EVM": [-38.2, -40.1, -41.7, None]},
    ], {})


def _train():
    n = 40
    loss = 0.08 * np.exp(-np.arange(n) / 9.0) + 0.004
    return ("train", [[{"loss": float(v)} for v in loss], "loss"], {})


def _codesign():
    drives = np.linspace(0.08, 0.22, 15)
    rows = [{"drive": float(d),
             "pae": float(0.18 + 1.7 * (d - 0.08)),
             "dpd_cost": float(28 + 900 * (d - 0.08) ** 2),
             "feasible": bool(d < 0.185)} for d in drives]
    return ("codesign", [rows], {"budget": 60})


def _grad():
    n = 30
    drive = 0.10 + 0.06 * (1 - np.exp(-np.arange(n) / 7.0))
    evm = -42 + 5 * (1 - np.exp(-np.arange(n) / 5.0))
    return ("grad", [{"drive": drive.tolist(), "evm_db": evm.tolist()},
                     -38.0], {})


ENTRIES = [
    # id, title, primitive exercised, data provenance, builder
    ("psd", "PSD (line + mask band)", "line", "computed", _psd),
    ("ccdf", "CCDF (log y axis)", "line", "computed", _ccdf),
    ("amam", "AM-AM / AM-PM (two panels)", "scatter", "computed", _amam),
    ("constellation", "Constellation (equal aspect)", "scatter",
     "computed", _constellation),
    ("time", "Envelope vs time", "line", "computed", _time),
    ("bitwidth", "Bit-width sweep (categorical x)", "line", "computed",
     _bitwidth),
    ("gain_modulation", "Gain modulation (twin axis)", "line", "computed",
     _gain_modulation),
    ("adaptive_evm", "Adaptive vs frozen DPD", "line", "computed",
     _adaptive_evm),
    ("three_loop", "Three loops (twin axis)", "line", "computed",
     _three_loop),
    ("two_tone", "Two-tone IM3 (log x)", "line", "sampled", _two_tone),
    ("bars", "Run comparison (bars, NaN gap)", "bar", "sampled", _bars),
    ("train", "Training loss", "line", "sampled", _train),
    ("codesign", "Co-design Pareto (spans)", "line", "sampled", _codesign),
    ("grad", "Gradient search (twin axis)", "line", "sampled", _grad),
]

_BY_ID = {e[0]: e for e in ENTRIES}


def listing() -> list:
    """Metadata for the gallery index - no computation."""
    return [{"id": i, "title": t, "primitive": p, "provenance": prov}
            for i, t, p, prov, _ in ENTRIES]


def chart_args(entry_id: str):
    """``(chart_name, args, kwargs)`` for one entry, running whatever
    computation that entry needs."""
    try:
        entry = _BY_ID[entry_id]
    except KeyError:
        raise KeyError(f"unknown gallery entry {entry_id!r}; "
                       f"known: {sorted(_BY_ID)}") from None
    return entry[4]()
