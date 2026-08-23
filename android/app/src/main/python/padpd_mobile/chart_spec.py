"""Chart specifications: what ``gui_qt/figs.py`` draws, as data.

``figs.py`` has fifteen figure builders, but they rest on four primitives -
multi-series XY lines, scatter, bars, and band/threshold overlays. Porting
the *specs* rather than the drawing lets the Android side implement one
renderer instead of fifteen, while the axis ranges, labels, legends, mask
placement and decimation steps that were tuned there carry over unchanged.

A spec is plain JSON except for the numeric arrays, which are referenced
by key and transported separately as float32 blobs (see ``api.blob``).
Keeping numbers out of the JSON matters: a constellation is ~15k points,
and rendering it through a JSON array of Python floats would cost more
than the fit that produced it.

Nothing here imports matplotlib, and nothing here imports a GUI. The
functions mirror ``figs.py`` name for name (``psd_fig`` -> ``psd_spec``)
so the two stay comparable - ``tests/test_mobile_api.py`` asserts they
produce the same curve data.
"""

from __future__ import annotations

import numpy as np

from gui_core.i18n import tr

# Semantic colour roles rather than hex. figs.py hardcodes a dark palette;
# the Android renderer has its own themes (and a light mode figs.py never
# had), so it maps roles to colours itself.
PRIMARY = "primary"      # figs.py #4f8ff7
ACCENT = "accent"        # figs.py #e4574c
MUTED = "muted"          # figs.py #9aa4bd
WARN = "warn"            # figs.py #5a2430 (infeasible spans)
SEQ = "seq"              # cycle by series index

# Scatter plots decimate to at most this many points. Inherited from
# figs.py, where it was a rendering concern; here it also bounds what
# crosses the language boundary.
#
# One deliberate difference: figs.py uses `len // MAX` for the step, which
# overshoots the cap by up to a step's worth (200k points come out as
# 15,385). Rendering does not care; a transport bound that can be exceeded
# is not a bound, so this rounds up instead. The visual result is
# indistinguishable - a slightly coarser sample of an already-dense cloud.
MAX_SCATTER_POINTS = 15000


def _decimation_step(n: int) -> int:
    return max(1, -(-n // MAX_SCATTER_POINTS))


class ChartBlobs:
    """Collects float32 arrays and hands out stable keys.

    float32 rather than float64 throughout: these are display
    coordinates, a phone screen has ~10^3 distinguishable positions per
    axis, and halving the payload is worth more than precision nobody can
    see. Fits and metrics stay float64 - only the plotting path narrows.
    """

    def __init__(self) -> None:
        self._data: dict[str, np.ndarray] = {}
        self._n = 0

    def put(self, arr) -> str:
        key = f"b{self._n}"
        self._n += 1
        self._data[key] = np.ascontiguousarray(
            np.asarray(arr, dtype=np.float64).ravel(), dtype=np.float32)
        return key

    def as_dict(self) -> dict[str, np.ndarray]:
        return dict(self._data)

    def __len__(self) -> int:
        return len(self._data)


def _panel(kind: str, **kw) -> dict:
    """A panel with every optional field present, so the renderer never
    has to distinguish "absent" from "null"."""
    p = {
        "kind": kind,               # line | scatter | bar
        "title": None,
        "xlabel": "", "ylabel": "", "y2label": None,
        "xscale": "linear", "yscale": "linear",
        "xlim": None, "ylim": None,
        "aspect_equal": False,
        "x_ticks": None,            # [{"pos": float, "label": str}]
        "series": [],
        "hlines": [],               # [{"y", "axis", "color_role"}]
        "vspans": [],               # [{"x0", "x1", "color_role"}]
    }
    p.update(kw)
    return p


def _series(label, x_key, y_key, *, axis="left", style="solid",
            marker="", color_role=SEQ, width=1.2) -> dict:
    return {"label": label, "x": x_key, "y": y_key, "axis": axis,
            "style": style, "marker": marker, "color_role": color_role,
            "width": width}


def _decimate(arr) -> np.ndarray:
    arr = np.asarray(arr).ravel()
    return arr[::_decimation_step(len(arr))]


# --------------------------------------------------------------------
# one spec function per figs.py builder, same name with _spec
# --------------------------------------------------------------------

def psd_spec(curves: dict, fs: float, mask=None, *, blobs, lang="zh") -> dict:
    from padpd.metrics import psd
    p = _panel("line", xlabel=tr("频率 (MHz)", lang), ylabel="PSD (dBr)",
               ylim=[-90, 5])
    for label, y in curves.items():
        f, v = psd(np.asarray(y), fs)
        p["series"].append(_series(label, blobs.put(f / 1e6), blobs.put(v)))
    if mask is not None:
        mask = np.asarray(mask)
        # Mirror the one-sided mask about DC, exactly as figs.py does.
        f_m = np.concatenate([-mask[::-1, 0], mask[:, 0]]) / 1e6
        v_m = np.concatenate([mask[::-1, 1], mask[:, 1]])
        p["series"].append(_series(
            tr("发射 Mask", lang), blobs.put(f_m), blobs.put(v_m),
            style="dashed", color_role=MUTED, width=1.1))
    return {"panels": [p]}


def ccdf_spec(curves: dict, *, blobs, lang="zh") -> dict:
    from padpd.metrics import ccdf
    p = _panel("line", xlabel=tr("高于平均功率 (dB)", lang), ylabel="CCDF",
               yscale="log")
    for label, x in curves.items():
        level, prob = ccdf(np.asarray(x))
        # Floor at 1e-7 before the log axis: ccdf's tail reaches exact
        # zero, which a log scale cannot place.
        p["series"].append(_series(
            label, blobs.put(level), blobs.put(np.maximum(prob, 1e-7))))
    return {"panels": [p]}


def adaptive_evm_spec(res: dict, *, blobs, lang="zh") -> dict:
    p = _panel("line", xlabel=tr("块(冷 → 热)", lang), ylabel="EVM (dB)")
    b = blobs.put(res["blocks"])
    p["series"].append(_series(tr("冻结批处理 DPD", lang), b,
                               blobs.put(res["evm_frozen"]), marker="s"))
    p["series"].append(_series(
        tr("自适应 {m}", lang).format(m=res["method"].upper()), b,
        blobs.put(res["evm_adaptive"]), marker="o", width=1.6))
    return {"panels": [p]}


def gain_modulation_spec(res: dict, *, blobs, lang="zh") -> dict:
    taus = ", ".join(f"{v:.1f}µs" for v in res["taus_heat_us"])
    p = _panel("line", xlabel=tr("阶跃后时间 (µs)", lang),
               ylabel=tr("增益变化 (dB)", lang),
               y2label=tr("相位漂移 (°)", lang))
    t = blobs.put(res["t_us"])
    p["series"].append(_series(
        tr("升功率(加热)|G|", lang) + (f" τ=[{taus}]" if taus else ""),
        t, blobs.put(res["heat_db"]), width=1.5))
    p["series"].append(_series(tr("降功率(冷却)|G|", lang), t,
                               blobs.put(res["cool_db"]), width=1.5))
    p["series"].append(_series(tr("加热相位漂移 (°)", lang), t,
                               blobs.put(res["heat_deg"]), axis="right",
                               style="dotted", color_role=MUTED))
    return {"panels": [p]}


def three_loop_spec(res: dict, *, blobs, lang="zh") -> dict:
    p = _panel("line", xlabel=tr("块(冷 → 热)", lang),
               ylabel=tr("在空口 EVM (dB)", lang),
               y2label=tr("镜像残差 (dBc)", lang))
    b = blobs.put(res["blocks"])
    p["series"].append(_series(tr("原始环回(无环)", lang), b,
                               blobs.put(res["evm_raw"]), marker="o"))
    p["series"].append(_series(tr("仅去嵌(无 QMC)", lang), b,
                               blobs.put(res["evm_deembed"]), marker="s"))
    p["series"].append(_series(tr("三环(去嵌+QMC+DPD)", lang), b,
                               blobs.put(res["evm_full"]), marker="d",
                               width=1.6))
    p["series"].append(_series(tr("镜像残差 (dBc)", lang), b,
                               blobs.put(res["image_dbc"]), axis="right",
                               style="dotted", color_role=MUTED))
    return {"panels": [p]}


def two_tone_spec(res: dict, *, blobs, lang="zh") -> dict:
    p = _panel("line", xlabel=tr("音间距 (MHz)", lang), ylabel="IM3 (dBc)",
               xscale="log")
    s = blobs.put(np.asarray(res["spacings_hz"]) / 1e6)
    p["series"].append(_series(tr("下边带 IM3", lang), s,
                               blobs.put(res["im3_lower_dbc"]), marker="o"))
    p["series"].append(_series(tr("上边带 IM3", lang), s,
                               blobs.put(res["im3_upper_dbc"]), marker="s"))
    return {"panels": [p]}


def constellation_spec(points_by_label: dict, *, blobs, lang="zh") -> dict:
    p = _panel("scatter", xlabel="I", ylabel="Q", aspect_equal=True)
    for label, pts in points_by_label.items():
        pts = _decimate(np.asarray(pts))
        p["series"].append(_series(label, blobs.put(pts.real),
                                   blobs.put(pts.imag), marker="."))
    return {"panels": [p]}


def amam_spec(x, y, *, blobs, lang="zh") -> dict:
    """Two panels, as figs.py draws two subplots: AM-AM and AM-PM."""
    from padpd.metrics.amam import am_am_am_pm
    am = am_am_am_pm(np.asarray(x), np.asarray(y))
    # One step for all three arrays - they are parallel samples, so
    # decimating them differently would pair the wrong points together.
    step = _decimation_step(len(am["r_in"]))
    r_key = blobs.put(am["r_in"][::step])
    p1 = _panel("scatter", title="AM-AM", xlabel="|x|", ylabel="|y|/|x|")
    p1["series"].append(_series("AM-AM", r_key,
                                blobs.put(am["gain"][::step]),
                                marker=".", color_role=PRIMARY))
    p2 = _panel("scatter", title="AM-PM", xlabel="|x|",
                ylabel=tr("相移 (°)", lang))
    p2["series"].append(_series("AM-PM", r_key,
                                blobs.put(am["phase_deg"][::step]),
                                marker=".", color_role=ACCENT))
    return {"panels": [p1, p2]}


def time_spec(sig: dict, fs: float, n: int = 2000, *, blobs,
              lang="zh") -> dict:
    p = _panel("line", xlabel=tr("时间 (µs)", lang), ylabel="|x|")
    for label, x in sig.items():
        x = np.asarray(x)[:n]
        p["series"].append(_series(
            label, blobs.put(np.arange(len(x)) / fs * 1e6),
            blobs.put(np.abs(x)), width=0.9))
    return {"panels": [p]}


def bars_spec(names: list, series: dict, *, blobs, lang="zh") -> dict:
    """Grouped bars. Offsets are computed here rather than on the Kotlin
    side so the grouping matches figs.py exactly."""
    n, k = len(names), max(1, len(series))
    width = 0.8 / k
    xs = np.arange(n)
    p = _panel("bar", ylabel="dB",
               x_ticks=[{"pos": float(i),
                         "label": t if len(t) < 26 else t[:23] + "…"}
                        for i, t in enumerate(names)])
    p["bar_width"] = float(width)
    for i, (label, vals) in enumerate(series.items()):
        # None means "this run has no such metric" - NaN so the renderer
        # can leave a gap instead of drawing a zero-height bar, which
        # would read as a real measurement of 0 dB.
        v = [x if x is not None else np.nan for x in vals]
        p["series"].append(_series(
            label, blobs.put(xs + (i - k / 2 + 0.5) * width), blobs.put(v)))
    return {"panels": [p]}


def bitwidth_spec(sweeps: dict, *, blobs, lang="zh") -> dict:
    """NMSE vs word length. x is categorical (W16, W12, ...), so it is
    carried as tick labels with integer positions."""
    p = _panel("line", ylabel="test NMSE (dB)")
    ticks = None
    for label, s in sweeps.items():
        bits = sorted(s["bits"], reverse=True)
        if ticks is None:
            ticks = [{"pos": float(i), "label": f"W{b}"}
                     for i, b in enumerate(bits)]
            p["x_ticks"] = ticks
        p["series"].append(_series(
            label, blobs.put(np.arange(len(bits), dtype=float)),
            blobs.put([s["bits"][b] for b in bits]), marker="o"))
        # The float-precision reference for this model.
        p["hlines"].append({"y": float(s["float"]), "axis": "left",
                            "color_role": MUTED})
    return {"panels": [p]}


def train_spec(history: list, key: str, *, blobs, lang="zh") -> dict:
    p = _panel("line", xlabel="epoch", ylabel=key)
    vals = [h[key] for h in history]
    p["series"].append(_series(
        key, blobs.put(np.arange(len(vals), dtype=float)), blobs.put(vals),
        color_role=PRIMARY, width=1.4))
    return {"panels": [p]}


def codesign_spec(rows: list, budget=None, *, blobs, lang="zh") -> dict:
    p = _panel("line", xlabel="PA drive", ylabel="PAE (%)",
               y2label=tr("DPD 系数", lang))
    d = blobs.put([r["drive"] for r in rows])
    p["series"].append(_series("PAE (%)", d,
                               blobs.put([100 * r["pae"] for r in rows]),
                               marker="o", color_role=ACCENT))
    p["series"].append(_series(tr("DPD 系数", lang), d,
                               blobs.put([r["dpd_cost"] for r in rows]),
                               axis="right", style="dashed", marker="s",
                               color_role=PRIMARY))
    if budget:
        p["hlines"].append({"y": float(budget), "axis": "right",
                            "color_role": PRIMARY})
    # Shade drive points whose EVM misses spec, as figs.py does.
    for r in rows:
        if not r["feasible"]:
            p["vspans"].append({"x0": float(r["drive"]) - 0.004,
                                "x1": float(r["drive"]) + 0.004,
                                "color_role": WARN})
    return {"panels": [p]}


def grad_spec(history: dict, spec: float, *, blobs, lang="zh") -> dict:
    p = _panel("line", xlabel=tr("梯度步", lang), ylabel="drive",
               y2label="EVM (dB)")
    n = len(history["drive"])
    steps = blobs.put(np.arange(n, dtype=float))
    p["series"].append(_series("drive", steps, blobs.put(history["drive"]),
                               color_role=ACCENT))
    p["series"].append(_series("EVM (dB)", steps,
                               blobs.put(history["evm_db"]), axis="right",
                               color_role=PRIMARY))
    p["hlines"].append({"y": float(spec), "axis": "right",
                        "color_role": MUTED})
    return {"panels": [p]}


BUILDERS = {
    "psd": psd_spec,
    "ccdf": ccdf_spec,
    "adaptive_evm": adaptive_evm_spec,
    "gain_modulation": gain_modulation_spec,
    "three_loop": three_loop_spec,
    "two_tone": two_tone_spec,
    "constellation": constellation_spec,
    "amam": amam_spec,
    "time": time_spec,
    "bars": bars_spec,
    "bitwidth": bitwidth_spec,
    "train": train_spec,
    "codesign": codesign_spec,
    "grad": grad_spec,
}


def build(name: str, *args, lang: str = "zh", **kwargs):
    """Build one chart. Returns ``(spec, blobs)``.

    ``spec`` is JSON-serialisable; ``blobs`` maps the keys it references
    to float32 arrays.
    """
    try:
        fn = BUILDERS[name]
    except KeyError:
        raise KeyError(
            f"unknown chart {name!r}; known: {sorted(BUILDERS)}") from None
    blobs = ChartBlobs()
    spec = fn(*args, blobs=blobs, lang=lang, **kwargs)
    return spec, blobs.as_dict()
