"""Experiments: the shared screen layer, as a workbench sees it.

``gui_core.screens`` turns a service result into what a screen shows -
formatted metrics, chart specs, verdict prose - and both front ends render
that. A workbench needs three more things on top, and they live here so
every front end gets them the same way:

1. **A parameter schema.** Each experiment declares its inputs - type,
   range, unit, group, and *when the input matters* - so a front end
   generates the form instead of hand-laying it out. The old desktop put
   every input of a page in one row, relevant or not, which made two
   pages wider than any laptop screen; a schema makes "only show what
   applies" a property of the data.
2. **Verdicts against the project spec.** A result is read against limits
   (EVM, ACLR, emission mask). The limit, the margin and pass/fail are
   computed here once, so no front end can colour a FAIL green.
3. **Provenance.** Every run is registered with the source and model it
   used, so a result on screen can say where it came from.

The run/present split matters for one more reason: ``present`` is cheap
and language-dependent, ``run`` is expensive and not. Switching language
re-presents the stored result instead of recomputing it - or, as the old
desktop did, throwing it away.

Strings here are Chinese keys translated through ``gui_core.i18n.tr`` at
presentation time; ``tests/test_experiments.py`` checks every one has an
English entry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from gui_core import screens
from gui_core.i18n import tr

# ---------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class Param:
    """One input of an experiment.

    ``kind``: choice | int | float | bool | multi | model | models | file
    ``show``: optional predicate ``(values, ctx) -> bool``; the input is
    hidden (and ignored) when it returns False.
    ``warn``: optional ``(values, ctx) -> str | None``; a live warning
    shown under the input (a Chinese key, translated by the front end).
    """

    key: str
    label: str
    kind: str
    default: Any = None
    choices: tuple = ()
    lo: float = 0.0
    hi: float = 0.0
    step: float = 1.0
    decimals: int = 0
    unit: str = ""
    group: str = ""
    help: str = ""
    advanced: bool = False
    show: Callable | None = None
    warn: Callable | None = None
    # model / models pickers: which families are offered
    families: tuple = ("classical", "neural")
    optional: bool = False          # a model picker that may be left empty


@dataclass
class Context:
    """What an experiment runs against: the active source and the
    workspace's models and spec."""

    workspace: Any
    source_name: str = ""

    @property
    def source(self) -> dict:
        return self.workspace.source(self.source_name or None)

    @property
    def spec(self) -> dict:
        return self.workspace.spec

    @property
    def synthetic(self) -> bool:
        e = self.workspace.sources.get(self.source_name
                                       or self.workspace.active_source)
        return bool(e and e.synthetic)


@dataclass
class Experiment:
    id: str
    title: str
    group: str                      # "flow" | "study"
    summary: str
    params: list
    run: Callable                   # (values, ctx, progress) -> raw
    present: Callable               # (raw, values, ctx, lang) -> dict
    record: Callable | None = None  # (raw, values, ctx) -> (name, kind,
    #                                  config, metrics)
    after: Callable | None = None   # (raw, values, ctx, run_id) -> None
    uses_source: bool = False
    needs_torch: bool = False
    chart_titles: dict = field(default_factory=dict)
    actions: tuple = ()             # (action_id, label) pairs

    def defaults(self) -> dict:
        return {p.key: p.default for p in self.params}

    def visible(self, values: dict, ctx) -> list:
        return [p for p in self.params
                if p.show is None or p.show(values, ctx)]


# ---------------------------------------------------------------------
# verdicts
# ---------------------------------------------------------------------


def mask_margin_db(y, fs: float, mask) -> float | None:
    """Worst out-of-band distance below the emission mask, in dB.

    Positive passes. Only the region from the first mask break outward
    counts: the PSD is normalised to its own peak, which sits exactly on
    the mask's in-band 0 dB, so including the channel would report every
    capture as 0.0 dB - which ``check_mask`` does, and which is how a
    clean 18.7 dB margin read as zero.
    """
    if mask is None:
        return None
    from padpd.metrics import psd
    mask = np.asarray(mask, dtype=float)
    f, p = psd(np.asarray(y), fs)
    af = np.abs(f)
    sel = af >= mask[min(2, len(mask) - 1), 0]
    if not np.any(sel):
        return None
    lim = np.interp(af[sel], mask[:, 0], mask[:, 1])
    return float(np.min(lim - p[sel]))


def _verdict(label: str, value, unit: str, limit=None, *, was=None,
             lower_is_better: bool = True, note: str = "") -> dict:
    """One verdict tile. ``ok`` is None when there is no limit to judge
    against - a reading, not a pass."""
    # plain Python numbers out: numpy scalars would make `ok is True`
    # false for a passing check and leak np types into a run record
    value = None if value is None else float(value)
    was = None if was is None else float(was)
    limit = None if limit is None else float(limit)
    ok = was_ok = margin = None
    if value is not None and limit is not None:
        margin = (limit - value) if lower_is_better else (value - limit)
        ok = bool(margin >= 0)
        if was is not None:
            was_ok = bool(((limit - was) if lower_is_better
                           else (was - limit)) >= 0)
    return {"label": label, "value": value, "unit": unit, "limit": limit,
            "margin": margin, "ok": ok, "was": was, "was_ok": was_ok,
            "lower_is_better": lower_is_better, "note": note}


def _aclr_worse(row: dict):
    vals = [v for v in (row.get("aclr_low"), row.get("aclr_high"))
            if isinstance(v, (int, float))]
    return max(vals) if vals else None


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------

def _is(key, *values):
    return lambda v, ctx: v.get(key) in values


def _neural_available() -> bool:
    try:
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------
# workflow: waveform
# ---------------------------------------------------------------------

def _run_waveform(v, ctx, progress):
    from gui_core import services
    return services.make_waveform(
        v["bw"] * 1e6, v["qam"], v["symbols"], v["seed"],
        v["papr"] if v["cfr"] else None)


def _present_waveform(raw, v, ctx, lang):
    shown = screens.present_waveform(raw, lang)
    return {**shown, "verdicts": []}


WAVEFORM = Experiment(
    id="waveform", title="波形", group="flow",
    summary="生成 802.11be 风格 OFDM 基带波形，看 PSD、CCDF、星座与削峰代价；"
            "可导出为 IQDataset。",
    params=[
        Param("bw", "带宽", "choice", 80, (20, 40, 80, 160, 320), unit="MHz",
              group="波形"),
        Param("qam", "调制", "choice", 1024, (256, 1024, 4096), unit="QAM",
              group="波形"),
        Param("symbols", "OFDM 符号数", "int", 8, lo=2, hi=64, group="波形"),
        Param("seed", "随机种子", "int", 0, lo=0, hi=9999, group="波形",
              advanced=True),
        Param("cfr", "CFR 削峰", "bool", False, group="削峰"),
        Param("papr", "目标 PAPR", "float", 8.0, lo=5.0, hi=10.0, step=0.5,
              decimals=1, unit="dB", group="削峰", show=_is("cfr", True)),
    ],
    run=_run_waveform, present=_present_waveform,
    chart_titles={"psd": "频谱", "ccdf": "CCDF", "constellation": "星座",
                  "time": "时域"},
    actions=(("export_npz", "导出 .npz"),),
)

# ---------------------------------------------------------------------
# workflow: PA model
# ---------------------------------------------------------------------


def _run_pa_model(v, ctx, progress):
    from gui_core import services
    src = ctx.source
    if v["family"] == "neural":
        res = services.fit_neural(src, backbone=v["backbone"],
                                  hidden=v["hidden"], epochs=v["epochs"],
                                  on_epoch=progress)
        label = f"{v['backbone'].upper()}-H{v['hidden']}"
        cfg = {"family": "neural", "backbone": v["backbone"],
               "hidden": v["hidden"], "epochs": v["epochs"]}
    else:
        res = services.fit_classical(src, v["type"],
                                     {"order": v["order"],
                                      "memory": v["memory"]})
        label = v["type"]
        cfg = {"family": "classical", "type": v["type"],
               "order": v["order"], "memory": v["memory"]}
    return {"res": res, "label": label, "config": cfg,
            "source": src["name"], "fs": src["fs"]}


def _present_pa_model(raw, v, ctx, lang):
    shown = screens.present_modeling(raw["res"], raw["source"], raw["fs"],
                                     lang)
    out = {**shown, "verdicts": [
        _verdict(tr("测试 NMSE", lang), raw["res"]["metrics"]["nmse_db"],
                 "dB"),
    ]}
    hist = raw["res"].get("history")
    if hist:
        out["charts"]["train"] = ("train", (hist, "val_nmse_db"), {})
    return out


def _record_pa_model(raw, v, ctx):
    name = f"{raw['label']} @ {raw['source']}"
    return name, "pa_model", {**raw["config"], "source": raw["source"]}, \
        raw["res"]["metrics"]


def _after_pa_model(raw, v, ctx, run_id):
    ctx.workspace.add_model(raw["res"]["model"],
                            family=raw["config"]["family"],
                            label=raw["label"], config=raw["config"],
                            source=raw["source"],
                            metrics=raw["res"]["metrics"], run_id=run_id)


def _classical_types():
    from gui_core import services
    return tuple(services.CLASSICAL_MODELS)


PA_MODEL = Experiment(
    id="pa_model", title="PA 模型", group="flow",
    summary="在当前数据源上拟合 PA 行为模型。拟合结果保存进工作区，"
            "可作为 DPD 的评估代理，也是部署页的输入。",
    params=[
        Param("family", "模型族", "choice", "classical",
              ("classical", "neural"), group="模型"),
        Param("type", "类型", "choice", "GMP", _classical_types(),
              group="模型", show=_is("family", "classical")),
        Param("order", "非线性阶数", "int", 5, lo=1, hi=13, group="模型",
              show=_is("family", "classical"),
              help="OpenDPD 预设与样条类型忽略此项"),
        Param("memory", "记忆深度", "int", 4, lo=1, hi=12, group="模型",
              show=_is("family", "classical")),
        Param("backbone", "网络结构", "choice", "dgru",
              ("dgru", "gru", "tcn"), group="神经网络",
              show=_is("family", "neural")),
        Param("hidden", "隐藏单元", "int", 8, lo=4, hi=32, group="神经网络",
              show=_is("family", "neural")),
        Param("epochs", "训练轮数", "int", 20, lo=5, hi=200,
              group="神经网络", show=_is("family", "neural")),
    ],
    run=_run_pa_model, present=_present_pa_model, record=_record_pa_model,
    after=_after_pa_model, uses_source=True,
    chart_titles={"psd": "频谱:实测 vs 预测", "amam": "AM-AM / AM-PM",
                  "train": "训练曲线"},
)

# ---------------------------------------------------------------------
# workflow: DPD
# ---------------------------------------------------------------------


def _needs_surrogate(v, ctx):
    return v.get("algo") == "DLA" or not ctx.synthetic


def _run_dpd(v, ctx, progress):
    from gui_core import services
    src = ctx.source
    ws = ctx.workspace
    sur_name = v.get("surrogate") or ""
    surrogate = ws.model(sur_name) if sur_name in ws.models else None
    if v["algo"] == "DLA":
        if surrogate is None:
            raise ValueError(tr("DLA 需要先在「PA 模型」页训练一个神经代理"))
        out = services.run_dpd_dla(src, surrogate, hidden=v["hidden"],
                                   epochs=v["epochs"], on_epoch=progress)
        label = "DLA"
    else:
        if not ctx.synthetic and surrogate is None:
            raise ValueError(tr("实测源需要一个评估代理:先在「PA 模型」页"
                                "拟合一个模型"))
        out = services.run_dpd_ila(src, basis=v["basis"],
                                   surrogate=surrogate)
        label = f"ILA-{v['basis']}"
    out["_margin_before"] = mask_margin_db(out["y_before"], out["fs"],
                                           out.get("mask"))
    out["_margin_after"] = mask_margin_db(out["y_after"], out["fs"],
                                          out.get("mask"))
    return {"out": out, "label": label, "source": src["name"],
            "surrogate": sur_name if surrogate is not None else ""}


def _present_dpd(raw, v, ctx, lang):
    out = raw["out"]
    shown = screens.present_dpd(out, lang)
    m = out["metrics"]
    b, a = m.get("no DPD", {}), m.get("DPD", {})
    spec = ctx.spec
    verdicts = [
        _verdict("EVM", a.get("evm_db"), "dB", spec["evm_db"],
                 was=b.get("evm_db")),
    ]
    if _aclr_worse(a) is not None:
        verdicts.append(_verdict(tr("ACLR · 较差一侧", lang), _aclr_worse(a),
                                 "dBc", spec["aclr_dbc"],
                                 was=_aclr_worse(b)))
    if out.get("_margin_after") is not None:
        verdicts.append(_verdict(
            tr("发射 Mask · 带外余量", lang), out["_margin_after"], "dB", 0.0,
            was=out["_margin_before"], lower_is_better=False,
            note=tr("802.11 发射模板", lang)))
    rows = []
    for key, zh in (("evm_db", "EVM (dB)"), ("aclr_low", "ACLR 下邻道 (dBc)"),
                    ("aclr_high", "ACLR 上邻道 (dBc)")):
        if isinstance(b.get(key), (int, float)) and \
                isinstance(a.get(key), (int, float)):
            rows.append({tr("指标", lang): tr(zh, lang),
                         tr("无 DPD", lang): f"{b[key]:.1f}",
                         tr("DPD 后", lang): f"{a[key]:.1f}",
                         tr("改善", lang): f"{b[key] - a[key]:+.1f} dB"})
    if out.get("_margin_after") is not None:
        rows.append({tr("指标", lang): tr("Mask 带外余量 (dB)", lang),
                     tr("无 DPD", lang): f"{out['_margin_before']:+.1f}",
                     tr("DPD 后", lang): f"{out['_margin_after']:+.1f}",
                     tr("改善", lang):
                         f"{out['_margin_after'] - out['_margin_before']:+.1f}"
                         + " dB"})
    notes = [tr("评估口径:{conv}", lang).format(conv=out["convention"])]
    return {**shown, "verdicts": verdicts, "rows": rows, "notes": notes}


def _record_dpd(raw, v, ctx):
    m = raw["out"]["metrics"]
    cfg = {"algo": v["algo"], "source": raw["source"]}
    if v["algo"] == "ILA":
        cfg["basis"] = v["basis"]
    else:
        cfg.update(hidden=v["hidden"], epochs=v["epochs"])
    if raw["surrogate"]:
        cfg["surrogate"] = raw["surrogate"]
    metrics = {"evm_db": m["DPD"]["evm_db"],
               "evm_before_db": m["no DPD"]["evm_db"],
               "aclr_high_dbc": m["DPD"].get("aclr_high"),
               "aclr_before_dbc": m["no DPD"].get("aclr_high"),
               "convention": raw["out"]["convention"]}
    if raw["out"].get("_margin_after") is not None:
        metrics["mask_margin_db"] = raw["out"]["_margin_after"]
    return f"{raw['label']} @ {raw['source']}", "dpd", cfg, metrics


# The ILA basis families a DPD can be built from: the classical model
# registry minus the widely-linear and C-IM3 variants, which model a TX
# front end rather than a predistorter. Ordered as the old DPD page was.
DPD_BASES = ("GMP-510 (OpenDPD)", "DDR-140 (preset)", "MP-500 (OpenDPD)",
             "GMP", "DDR", "MP", "Spline-MP (K8,M4)", "Spline-GMP (K8)",
             "Spline-MP")


DPD = Experiment(
    id="dpd", title="DPD", group="flow",
    summary="在当前数据源上辨识预失真器，按项目 spec 判定；"
            "结果和产生它的参数绑在一起。",
    params=[
        Param("algo", "算法", "choice", "ILA", ("ILA", "DLA"), group="算法"),
        Param("basis", "基函数", "choice", "GMP-510 (OpenDPD)", DPD_BASES,
              group="算法", show=_is("algo", "ILA")),
        Param("surrogate", "PA 代理", "model", "", group="算法",
              show=_needs_surrogate,
              families=("classical", "neural"),
              help="实测源用它评估 DPD 后的输出;DLA 通过它反传梯度"),
        Param("hidden", "隐藏单元", "int", 8, lo=4, hi=24, group="神经网络",
              show=_is("algo", "DLA")),
        Param("epochs", "训练轮数", "int", 20, lo=5, hi=100,
              group="神经网络", show=_is("algo", "DLA")),
    ],
    run=_run_dpd, present=_present_dpd, record=_record_dpd,
    uses_source=True,
    chart_titles={"psd": "频谱与 Mask", "constellation": "星座"},
)

# ---------------------------------------------------------------------
# workflow: deployment
# ---------------------------------------------------------------------


def _run_deploy(v, ctx, progress):
    from gui_core import services
    ws = ctx.workspace
    names = [n for n in v["models"] if n in ws.models]
    if not names:
        raise ValueError(tr("先在「PA 模型」页拟合模型,再勾选要扫描的模型"))
    bits = sorted({int(b) for b in v["bits"]}, reverse=True) or [16, 12, 8]
    sweeps, luts = {}, {}
    for i, n in enumerate(names):
        model, src = ws.model(n), ws.eval_source_for(n)
        sweeps[n] = services.bitwidth_sweep(model, src, bits=tuple(bits))
        if v["lut"] and hasattr(model, "gain_curve"):
            luts[n] = services.lut_sweep(model, src)
        if progress:
            progress({"epoch": i, "of": len(names)})
    return {"sweeps": sweeps, "luts": luts, "bits": bits}


def _present_deploy(raw, v, ctx, lang):
    short = {n: n.split(" @")[0] for n in raw["sweeps"]}
    rows = []
    for n, s in raw["sweeps"].items():
        row = {tr("模型", lang): short[n], "float": f"{s['float']:.2f}"}
        row.update({f"W{b}": f"{s['bits'][b]:.2f}" for b in raw["bits"]})
        if s.get("macs"):
            row[tr("MAC/样本", lang)] = str(s["macs"]["real_macs_per_sample"])
            row["GMAC/s"] = f"{s['macs']['real_gmac_per_s']:.0f}"
        rows.append(row)
    for n, res in raw["luts"].items():
        rows.append({tr("模型", lang): short[n] + " · LUT",
                     "float": f"{res['float']:.2f}",
                     **{f"LUT{k}": f"{val:.2f}"
                        for k, val in res["entries"].items()}})
    # the verdict a deployment needs: the narrowest word that still holds
    # the float accuracy within 1 dB
    verdicts = []
    for n, s in raw["sweeps"].items():
        ok_bits = [b for b in raw["bits"] if s["bits"][b] <= s["float"] + 1]
        best = min(ok_bits) if ok_bits else None
        verdicts.append(_verdict(
            short[n] + " · " + tr("最窄可用位宽", lang),
            best, "bit", note=tr("NMSE 损失 ≤ 1 dB", lang)))
    charts = {"bitwidth": ("bitwidth",
                           ({short[n]: s for n, s in raw["sweeps"].items()},),
                           {})}
    return {"verdicts": verdicts, "metrics": [], "rows": rows,
            "charts": charts, "notes": []}


def _record_deploy(raw, v, ctx):
    n0 = next(iter(raw["sweeps"]))
    s = raw["sweeps"][n0]
    return (f"deploy {n0.split(' @')[0]}", "deploy",
            {"bits": raw["bits"], "models": list(raw["sweeps"])},
            {"float_nmse_db": s["float"],
             **{f"w{b}_nmse_db": val for b, val in s["bits"].items()}})


DEPLOY = Experiment(
    id="deploy", title="部署", group="flow",
    summary="定点位宽扫描(bit-true)与硬件代价估计;样条/MP 模型可再扫 LUT 深度,"
            "并导出 FPGA/ASIC 交接产物。",
    params=[
        Param("models", "模型", "models", (), group="模型"),
        Param("bits", "位宽", "multi", (16, 12, 8), (16, 14, 12, 10, 8),
              group="定点"),
        Param("lut", "同时扫描 LUT 深度", "bool", False, group="定点",
              help="只对带增益曲线的样条/MP 模型生效"),
    ],
    run=_run_deploy, present=_present_deploy, record=_record_deploy,
    chart_titles={"bitwidth": "位宽 vs NMSE"},
    actions=(("export_artifacts", "导出交接产物…"),),
)

# ---------------------------------------------------------------------
# studies
# ---------------------------------------------------------------------


def _run_gain_mod(v, ctx, progress):
    from gui_core import services
    return services.run_gain_modulation(dut=v["dut"], drive=v["drive"],
                                        fit_state_model=v["fit_state"])


def _present_gain_mod(raw, v, ctx, lang):
    shown = screens.present_gain_modulation(raw, lang)
    verdicts = [_verdict(tr("增益垂降", lang), raw["droop_db"], "dB")]
    if raw.get("state_gain_db") is not None:
        verdicts.append(_verdict(tr("状态样条增益", lang),
                                 raw["state_gain_db"], "dB",
                                 lower_is_better=False))
    if raw["significant"]:
        verdicts.append(_verdict(
            tr("迟滞比", lang), raw["hysteresis_ratio"], "",
            note=(tr("线性热网络约为 1", lang) if raw["hysteresis_reliable"]
                  else tr("观测窗太短,不足以判定", lang))))
    return {**shown, "verdicts": verdicts}


def _record_gain_mod(raw, v, ctx):
    from gui_core import services
    name, config, metrics = services.gain_mod_run_record(raw)
    return name, "pa_model", config, metrics


GAIN_MOD = Experiment(
    id="gain_modulation", title="增益调制", group="study",
    summary="恒包络阶跃探针:辨识热/陷阱时间常数,并用辨识出的 α 配置"
            "状态条件化样条。",
    params=[
        Param("dut", "虚拟 DUT", "choice", "thermal", ("thermal", "static"),
              group="探针"),
        Param("drive", "PA 驱动 drive", "float", 0.13, lo=0.08, hi=0.2,
              step=0.01, decimals=2, group="探针"),
        Param("fit_state", "拟合状态样条", "bool", True, group="探针"),
    ],
    run=_run_gain_mod, present=_present_gain_mod, record=_record_gain_mod,
    chart_titles={"gain_modulation": "增益与相位轨迹"},
)


def _run_adaptive(v, ctx, progress):
    from gui_core import services
    return services.run_adaptive_dpd(
        method=v["method"], n_blocks=v["blocks"], drift_span=v["drift"],
        forget=v["forget"], apa_k=v["apa_k"], bw=v["bw"] * 1e6,
        basis=v["basis"], dut=v["dut"])


def _present_adaptive(raw, v, ctx, lang):
    shown = screens.present_adaptive(raw, lang)
    return {**shown, "verdicts": [
        _verdict(tr("自适应 · 满漂移 EVM", lang), raw["final_adaptive"], "dB",
                 ctx.spec["evm_db"], was=raw["final_frozen"]),
        _verdict(tr("冻结批处理 · 满漂移 EVM", lang), raw["final_frozen"],
                 "dB", ctx.spec["evm_db"]),
    ]}


def _record_adaptive(raw, v, ctx):
    from gui_core import services
    name, config, metrics = services.adaptive_run_record(raw)
    return name, "dpd", config, metrics


def _adaptive_options(name):
    from gui_core import services
    return tuple(getattr(services, name))


ADAPTIVE = Experiment(
    id="adaptive", title="自适应跟踪", group="study",
    summary="在会漂移的合成 PA 上比较自适应 DPD 与冻结批处理 DPD 的逐块 EVM。",
    params=[
        Param("method", "方法", "choice", "rls",
              _adaptive_options("ADAPTIVE_METHODS"), group="算法"),
        Param("basis", "基底", "choice", "gmp",
              _adaptive_options("ADAPTIVE_BASES"), group="算法"),
        Param("forget", "遗忘因子", "float", 0.6, lo=0.5, hi=0.99, step=0.01,
              decimals=2, group="算法", advanced=True),
        Param("apa_k", "APA 投影阶", "int", 4, lo=1, hi=8, group="算法",
              show=_is("method", "apa"),
              help="K=1 即 NLMS,K 越大越接近 RLS"),
        Param("dut", "虚拟 DUT", "choice", "drift",
              _adaptive_options("ADAPTIVE_DUTS"), group="场景"),
        Param("blocks", "块数(冷到热)", "int", 10, lo=4, hi=16, group="场景"),
        Param("drift", "漂移幅度", "float", 0.02, lo=0.01, hi=0.05,
              step=0.005, decimals=3, group="场景"),
        Param("bw", "带宽", "choice", 80, (20, 40, 80, 160, 320), unit="MHz",
              group="场景",
              help="带宽越大采样率越高,每块越慢(80 MHz 为演示默认)"),
    ],
    run=_run_adaptive, present=_present_adaptive, record=_record_adaptive,
    chart_titles={"adaptive_evm": "逐块 EVM"},
)


def _run_three_loop(v, ctx, progress):
    from gui_core import services
    return services.run_three_loop_demo(
        n_blocks=v["blocks"], drift_span=v["drift"], gain_db=v["iq"],
        phase_deg=10.0 * v["iq"], lo_leakage_dbc=v["lo"])


def _present_three_loop(raw, v, ctx, lang):
    shown = screens.present_three_loop(raw, lang)
    # The raw loopback fails by tens of dB; drawn on the same axis it
    # flattens the two curves that differ by the 3 dB this study is about.
    # It goes into the callout instead of the chart.
    shown["charts"] = {"three_loop": ("three_loop", (raw,),
                                      {"include_raw": False})}
    verdicts = [
        _verdict(tr("三环联合 · 满漂移 EVM", lang), raw["final_full"], "dB",
                 ctx.spec["evm_db"], was=raw["final_deembed"]),
        _verdict(tr("仅去嵌 · 满漂移 EVM", lang), raw["final_deembed"], "dB",
                 ctx.spec["evm_db"], note=tr("被 IRR 钉住", lang)),
        _verdict(tr("镜像残差 · 满漂移", lang), raw["final_image_dbc"], "dBc",
                 note=tr("QMC 估计 IRR {irr:.1f} dB", lang).format(
                     irr=raw["qmc_irr_db"])),
    ]
    callout = tr("原始环回已失效:满漂移时在空口 EVM 为 {raw:+.1f} dB,"
                 "比信号本身还大,所以没有画进图里,否则会把另外两条压扁。",
                 lang).format(raw=raw["final_raw"])
    return {**shown, "verdicts": verdicts, "callout": callout}


def _record_three_loop(raw, v, ctx):
    from gui_core import services
    name, config, metrics = services.three_loop_run_record(raw)
    return name, "dpd", config, metrics


THREE_LOOP = Experiment(
    id="three_loop", title="前端三环", group="study",
    summary="漂移 PA + TX 前端镜像与 LO 泄漏 + 被污染的观测环回:比较原始环回、"
            "仅去嵌与三环联合(QMC + 去嵌 + 自适应 DPD)。",
    params=[
        Param("blocks", "块数(冷到热)", "int", 10, lo=4, hi=16, group="场景"),
        Param("drift", "漂移幅度", "float", 0.02, lo=0.0, hi=0.05, step=0.005,
              decimals=3, group="场景"),
        Param("lo", "LO 泄漏", "float", -35.0, lo=-60.0, hi=-20.0, step=1.0,
              decimals=0, unit="dBc", group="TX 前端损伤"),
        Param("iq", "IQ 增益失衡", "float", 0.3, lo=0.0, hi=1.0, step=0.1,
              decimals=1, unit="dB", group="TX 前端损伤",
              help="相位失衡按 10 倍联动:0.3 dB 约等于 3°,IRR 约 30 dB"),
    ],
    run=_run_three_loop, present=_present_three_loop,
    record=_record_three_loop,
    chart_titles={"three_loop": "逐块 EVM 与镜像残差"},
)


def _run_codesign(v, ctx, progress):
    return screens.codesign(v["spec"], v["budget"], v["bw"])["result"]


def _present_codesign(raw, v, ctx, lang):
    shown = screens.present_codesign(raw, v["budget"], lang)
    seq = max(raw, key=lambda r: r["pae"])
    feasible = [r for r in raw
                if r["feasible"] and r["dpd_cost"] <= v["budget"]]
    verdicts = [_verdict(tr("顺序设计(先冲效率)", lang), 100 * seq["pae"],
                         "% PAE", note=(tr("可行", lang)
                                        if seq in feasible else
                                        tr("撞墙:不可逆/超预算", lang)))]
    verdicts[0]["ok"] = seq in feasible
    if feasible:
        joint = max(feasible, key=lambda r: r["pae"])
        verdicts.append(_verdict(
            tr("联合设计(预算内最高效率)", lang), 100 * joint["pae"], "% PAE",
            note=tr("drive {drive:.2f} · {cost} 系数", lang).format(
                drive=joint["drive"], cost=joint["dpd_cost"])))
        verdicts[-1]["ok"] = True
    return {**shown, "verdicts": verdicts}


CODESIGN = Experiment(
    id="codesign", title="联合设计", group="study",
    summary="PA 工作点与 DPD 复杂度联合权衡:离散 Pareto 扫描 drive,"
            "看先冲效率的顺序设计在哪里撞墙。约 1 分钟。",
    params=[
        Param("spec", "EVM 目标", "float", -40.0, lo=-50.0, hi=-25.0,
              step=1.0, decimals=0, unit="dB", group="目标"),
        Param("budget", "DPD 系数预算", "int", 90, lo=10, hi=300,
              group="目标"),
        Param("bw", "带宽", "choice", 80, (20, 40, 80, 160), unit="MHz",
              group="目标"),
    ],
    run=_run_codesign, present=_present_codesign,
    chart_titles={"codesign": "PAE 与 DPD 系数 vs drive"},
)


def _run_codesign_grad(v, ctx, progress):
    from padpd.codesign_torch import joint_codesign
    from padpd.waveform import OFDMConfig, generate_ofdm
    x = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=256,
                                 n_symbols=4, seed=0)).x
    base = joint_codesign(x, drive_init=v["drive0"], evm_spec_db=v["spec"],
                          learnable_drive=False)
    co = joint_codesign(x, drive_init=v["drive0"], evm_spec_db=v["spec"],
                        lambda_eff=3.0, steps=v["steps"])
    return {"base": base, "co": co}


def _present_codesign_grad(raw, v, ctx, lang):
    base, co = raw["base"], raw["co"]
    verdicts = [
        _verdict(tr("固定 drive", lang), 100 * base["efficiency"], "% PAE",
                 note=f"EVM {base['evm_db']:.1f} dB"),
        _verdict(tr("梯度联合优化", lang), 100 * co["efficiency"], "% PAE",
                 note=f"drive→{co['drive']:.3f} · EVM {co['evm_db']:.1f} dB"),
    ]
    return {"verdicts": verdicts, "metrics": [], "notes": [],
            "charts": {"grad": ("grad", (co["history"], v["spec"]), {})}}


CODESIGN_GRAD = Experiment(
    id="codesign_grad", title="可微联合寻优", group="study",
    summary="把 drive 当作可学习参数,内层闭式 LS-DPD、外层梯度,"
            "在 EVM 约束下找最高效率。需要 PyTorch。",
    params=[
        Param("spec", "EVM 目标", "float", -38.0, lo=-50.0, hi=-25.0,
              step=1.0, decimals=0, unit="dB", group="目标"),
        Param("drive0", "初始 drive", "float", 0.12, lo=0.06, hi=0.24,
              step=0.01, decimals=2, group="优化"),
        Param("steps", "梯度步数", "int", 60, lo=10, hi=300, group="优化"),
    ],
    run=_run_codesign_grad, present=_present_codesign_grad,
    needs_torch=True, chart_titles={"grad": "寻优轨迹"},
)


def _run_two_tone(v, ctx, progress):
    from gui_core import services
    return services.analyze_two_tone_csv(v["path"] or
                                         services.EXAMPLE_TWO_TONE_CSV)


def _present_two_tone(raw, v, ctx, lang):
    shown = screens.present_two_tone(raw, lang)
    return {**shown, "verdicts": [
        _verdict(tr("记忆强度", lang), raw["memory_strength_db"], "dB",
                 note=tr("建议记忆深度 {d}", lang).format(
                     d=raw["memory_depth"])),
    ]}


TWO_TONE = Experiment(
    id="two_tone", title="双音诊断", group="study",
    summary="读一张 IM3 随音间距变化的表(电路仿真或实测),在训练任何 DPD 之前"
            "预判它该留多少记忆。",
    params=[
        Param("path", "IM3 表 (CSV)", "file", "", group="输入",
              help="留空则用内置示例 examples/two_tone_example.csv"),
    ],
    run=_run_two_tone, present=_present_two_tone,
    chart_titles={"two_tone": "IM3 vs 音间距"},
)


EXPERIMENTS: dict[str, Experiment] = {e.id: e for e in (
    WAVEFORM, PA_MODEL, DPD, DEPLOY,
    GAIN_MOD, ADAPTIVE, THREE_LOOP, CODESIGN, CODESIGN_GRAD, TWO_TONE)}


def available(exp: Experiment) -> bool:
    return not exp.needs_torch or _neural_available()


# choice values that are identifiers, shown through a label
CHOICE_LABELS = {
    "classical": "经典 (LS)", "neural": "神经网络",
    "ILA": "ILA · 经典 LS", "DLA": "DLA · 神经直学",
    "thermal": "自热 (thermal)", "static": "静态对照 (static)",
    "drift": "漂移 (drift)",
    "none": "无", "iq": "IQ 失衡", "iq+lo": "IQ 失衡 + LO 泄漏",
    "iq+lo+cim3": "IQ + LO + C-IM3",
}


# ---------------------------------------------------------------------
# sources and comparison
# ---------------------------------------------------------------------

# The synthetic source form. Not an Experiment - it produces a source,
# not a result - but the same schema, so the same form renders it.
SYNTHETIC_SOURCE = [
    Param("bw", "带宽", "choice", 160, (20, 40, 80, 160, 320), unit="MHz",
          group="激励"),
    Param("qam", "调制", "choice", 1024, (256, 1024, 4096), unit="QAM",
          group="激励"),
    Param("symbols", "OFDM 符号数", "int", 8, lo=2, hi=32, group="激励"),
    Param("cfr", "CFR 削峰", "bool", False, group="激励"),
    Param("papr", "目标 PAPR", "float", 8.0, lo=5.0, hi=10.0, step=0.5,
          decimals=1, unit="dB", group="激励", show=_is("cfr", True)),
    Param("drive", "PA 驱动 drive", "float", 0.14, lo=0.06, hi=0.24,
          step=0.01, decimals=2, group="虚拟 PA"),
    Param("frontend", "TX 前端损伤", "choice", "none",
          ("none", "iq", "iq+lo", "iq+lo+cim3"), group="虚拟 PA"),
]


def synthetic_source_params(v: dict) -> dict:
    """SYNTHETIC_SOURCE form values -> Workspace.add_synthetic params."""
    v = {p.key: p.default for p in SYNTHETIC_SOURCE} | dict(v)
    return {"bandwidth_hz": float(v["bw"]) * 1e6, "qam": int(v["qam"]),
            "symbols": int(v["symbols"]), "drive": float(v["drive"]),
            "cfr_papr_db": float(v["papr"]) if v["cfr"] else None,
            "frontend": v["frontend"]}


KIND_LABELS = {"pa_model": "PA 模型", "dpd": "DPD", "deploy": "部署"}

# metric keys that are labels, not numbers to plot
_NOT_PLOTTED = {"convention"}


def compare_runs(runs: list, lang: str = "zh") -> dict:
    """Side by side for runs of one kind: their numbers, and which inputs
    differ between them.

    The old compare page put every run in one table and plotted whatever
    metrics the picked runs carried, so a DPD run's EVM sat next to a PA
    model's NMSE as if one could be traded for the other. Comparing runs
    of one kind makes the columns mean the same thing; the config diff
    says what changed to produce the difference.
    """
    kinds = {r.kind for r in runs}
    if len(kinds) > 1:
        raise ValueError(tr("只能比较同一类运行", lang))
    names = [r.name for r in runs]
    if len(set(names)) < len(names):
        names = [f"{r.name} #{r.run_id[:4]}" for r in runs]
    keys: list[str] = []
    for r in runs:
        keys += [k for k, v in r.metrics.items()
                 if isinstance(v, (int, float)) and not isinstance(v, bool)
                 and k not in _NOT_PLOTTED and k not in keys]
    rows = []
    for n, r in zip(names, runs):
        row = {tr("运行", lang): n, tr("时间", lang): r.when}
        for k in keys:
            v = r.metrics.get(k)
            row[k] = f"{v:.2f}" if isinstance(v, (int, float)) else ""
        rows.append(row)
    ckeys: list[str] = []
    for r in runs:
        ckeys += [k for k in r.config if k not in ckeys]
    diff = []
    for k in ckeys:
        vals = [r.config.get(k) for r in runs]
        if len({repr(v) for v in vals}) > 1:
            diff.append({tr("参数", lang): k,
                         **{n: "—" if v is None else str(v)
                            for n, v in zip(names, vals)}})
    charts = {}
    # dB metrics share an axis; a bit count or a MAC count does not
    plot = [k for k in keys if k.endswith(("_db", "_dbc"))]
    if len(runs) >= 2 and plot:
        charts["bars"] = ("bars", (names, {k: [r.metrics.get(k)
                                                for r in runs]
                                           for k in plot}), {})
    notes = []
    if len(runs) >= 2 and not diff:
        notes.append(tr("这些运行的输入完全相同;差异只来自随机性或数据源"
                        "内容。", lang))
    return {"rows": rows, "diff": diff, "charts": charts, "notes": notes,
            "metrics": [], "verdicts": [], "callout": ""}


# ---------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------


@dataclass
class Outcome:
    """A finished run: everything needed to re-present it later, in any
    language, without recomputing - and to say where it came from."""

    exp_id: str
    values: dict
    raw: Any
    source_name: str = ""
    run_id: str = ""
    run_name: str = ""
    config: dict = field(default_factory=dict)
    seconds: float = 0.0


def effective_values(exp: Experiment, values: dict, ctx) -> dict:
    """Defaults, overlaid with the given values, minus inputs that do not
    apply - a hidden input must not leak into a run or its record."""
    v = {**exp.defaults(), **values}
    keep = {p.key for p in exp.visible(v, ctx)}
    return {k: val for k, val in v.items() if k in keep}


def execute(exp: Experiment, values: dict, ctx, progress=None,
            runstore=None) -> Outcome:
    """Run, register, apply side effects. The one path every front end
    and every test takes, so a run on screen and a run in a test are the
    same thing."""
    import time

    from gui_core.runstore import Run
    t0 = time.perf_counter()
    v = effective_values(exp, values, ctx)
    full = {**exp.defaults(), **v}      # run functions read by key
    raw = exp.run(full, ctx, progress)
    out = Outcome(exp_id=exp.id, values=v, raw=raw,
                  source_name=(ctx.source_name or
                               ctx.workspace.active_source)
                  if exp.uses_source else "")
    if exp.record is not None:
        name, kind, config, metrics = exp.record(raw, full, ctx)
        clean = {k: val for k, val in metrics.items()
                 if isinstance(val, (int, float, str)) or val is None}
        run = Run(name=name, kind=kind, config=config, metrics=clean)
        if runstore is not None:
            runstore.add(run)
        out.run_id, out.run_name, out.config = run.run_id, name, config
    if exp.after is not None:
        exp.after(raw, full, ctx, out.run_id)
    out.seconds = time.perf_counter() - t0
    return out


def present(outcome: Outcome, ctx, lang: str = "zh") -> dict:
    """Re-present a stored outcome. Cheap; called on every language
    switch and every spec change."""
    exp = EXPERIMENTS[outcome.exp_id]
    full = {**exp.defaults(), **outcome.values}
    shown = exp.present(outcome.raw, full, ctx, lang)
    shown.setdefault("verdicts", [])
    shown.setdefault("metrics", [])
    shown.setdefault("charts", {})
    shown.setdefault("rows", [])
    shown.setdefault("notes", [])
    shown.setdefault("callout", "")
    return shown
