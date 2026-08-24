"""One function per screen, the mobile counterpart of ``gui_qt/pages/``.

A screen is more than a service call. ``gui_qt/pages/waveform.py`` calls
``services.make_waveform`` once and then does four more things with the
result: reads fields off live objects, formats numbers to fixed
precision, picks which curves to plot, and builds four figures. That work
is presentation, not domain logic - it has no business in
``gui_core/services.py`` - but it is also not something to reimplement in
Kotlin.

Reimplementing it there would cost twice. Live objects cannot cross the
bridge, so ``wf.config.fft_size`` would need a general attribute reader
on the Python side, which turns a narrow allow-list into arbitrary
reflection. And every format string ("%.2f dB") would exist in two
languages, free to drift, with the drift showing up as a number that
merely looks slightly different rather than as a failure.

So each screen is assembled here and crosses once: formatted metrics,
chart specifications, and a handle for whatever the next action needs.
Kotlin lays out the result; it does not compute it.

The split against ``api.py`` is deliberate: that module is the transport
(handles, blobs, dispatch, capability) and knows nothing about screens;
this one knows about screens and nothing about transport.
"""

from __future__ import annotations

from pathlib import Path

from gui_core.i18n import tr


_RUNSTORE = None


def _runstore():
    """The same run store the desktop GUIs write to.

    Lazily built because gui_core.paths resolves the data directory at
    call time from PADPD_DATA_DIR, which api.boot sets to the app's
    private files directory. Registering here rather than skipping it:
    the screens tell the user a run was recorded, and the Compare page
    will read these back when it is ported. A message that says a run was
    saved must be backed by a saved run.
    """
    global _RUNSTORE
    if _RUNSTORE is None:
        from gui_core.paths import user_data_dir
        from gui_core.runstore import RunStore
        _RUNSTORE = RunStore(user_data_dir() / "gui_runs")
    return _RUNSTORE


def _record(name: str, kind: str, config: dict, metrics: dict) -> None:
    from gui_core.runstore import Run
    _runstore().add(Run(name=name, kind=kind, config=config,
                        metrics=metrics))


# Fitted models, by the name the Modeling screen gave them. The desktop
# keeps this in gui_qt's shared state; the Deployment screen sweeps over
# whatever is in it, so without it that screen has nothing to act on.
#
# Process-lifetime only, exactly as on the desktop: a model is a live
# object, and the run store holds the metrics rather than the object. Kill
# the app and the sweep list is empty again, which is the same behaviour
# as closing the desktop GUI.
_MODELS: dict = {}


def _metric(label: str, value: str, note: str = "") -> dict:
    """A metric card. Values arrive pre-formatted, for the reason above."""
    return {"label": label, "value": value, "note": note}


def waveform(bandwidth_mhz: float, qam: int, symbols: int, seed: int,
             cfr_papr_db: float | None = None, *, lang: str = "zh") -> dict:
    """Waveform Studio: generate a baseband OFDM waveform and describe it.

    Mirrors ``gui_qt/pages/waveform.py``'s generate(), including its
    metric wording and precision. The CFR card reads "—" when clipping is
    off, matching the desktop rather than hiding the card, so the screen
    does not change shape when the checkbox moves.
    """
    import gui_core.services as services

    w = services.make_waveform(bandwidth_mhz * 1e6, qam, symbols, seed,
                               cfr_papr_db)
    wf, cfg = w["wf"], w["wf"].config

    curves = {tr("原始波形", lang): w["x"]}
    if w["x_cfr"] is not None:
        curves[tr("CFR 后", lang)] = w["x_cfr"]

    metrics = [
        _metric(tr("采样率", lang), f"{w['fs'] / 1e6:.0f} MSPS",
                tr("{n}× 过采样", lang).format(n=cfg.oversampling)),
        _metric(tr("FFT / 有效子载波", lang),
                f"{cfg.fft_size} / {cfg.n_active}"),
        _metric("PAPR", f"{w['papr_db']:.2f} dB"),
        _metric(tr("CFR 后 PAPR / EVM 代价", lang),
                f"{w['papr_cfr_db']:.2f} dB / {w['cfr_evm_db']:.1f} dB"
                if w["papr_cfr_db"] is not None else "—"),
    ]

    charts = {
        "psd": ("psd", (curves, w["fs"]), {}),
        "ccdf": ("ccdf", (curves,), {}),
        "constellation": ("constellation",
                          ({tr("发送星座", lang): wf.tx_symbols.ravel()},), {}),
        "time": ("time", (curves, w["fs"]), {}),
    }
    return {"result": w, "metrics": metrics, "charts": charts, "lang": lang}


def modeling(model_type: str, order: int, memory: int, drive: float,
             frontend: str, *, lang: str = "zh") -> dict:
    """PA Modeling, classical branch: fit a model and show the residual.

    Mirrors the classical half of gui_qt/pages/modeling.py. The neural
    branch is absent rather than stubbed - torch has no Android wheel, so
    `fit_neural` cannot run here at all, and capabilities() already says
    so. The UI greys that family out; there is nothing for this module to
    assemble for it.

    The source is always the synthetic ReferencePA for now. The desktop
    page also offers whatever the Data page has loaded, and that page is
    not ported yet, so offering a picker with one entry would imply a
    choice that does not exist.
    """
    import gui_core.services as services

    src = services.cached_synthetic_source(drive=drive, frontend=frontend)
    res = services.fit_classical(src, model_type,
                                 {"order": order, "memory": memory})

    # The desktop caps the plotted span at 40k samples; the arrays behind
    # it are the full evaluation split, and plotting all of it would move
    # megabytes across the bridge to draw the same line.
    n = min(len(res["x_eval"]), 40000)

    metrics = [
        _metric(tr("测试 NMSE", lang), f"{res['metrics']['nmse_db']:.2f} dB"),
        _metric(tr("参数量", lang), f"{res['metrics']['n_coeffs']:,}"),
        _metric(tr("数据源", lang), src["name"][:28]),
    ]
    charts = {
        "psd": ("psd", ({tr("实测输出", lang): res["y_eval"][:n],
                         tr("模型预测", lang): res["pred"][:n]}, src["fs"]), {}),
        "amam": ("amam", (res["x_eval"][:n], res["pred"][:n]), {}),
    }
    name = f"{model_type} @ {src['name']}"
    _MODELS[name] = {"model": res["model"],
                     "meta": {"source": src["name"]}}
    _record(name, "pa_model",
            {"family": "classical", "type": model_type,
             "order": order, "memory": memory,
             "drive": drive, "frontend": frontend},
            res["metrics"])

    return {"result": res, "metrics": metrics, "charts": charts, "lang": lang,
            "notes": [tr("✅ {name} 已注册", lang).format(name=name)]}


def gain_modulation(dut: str, drive: float, fit_state: bool, *,
                    lang: str = "zh") -> dict:
    """Gain-modulation identification: step response, then time constants.

    The desktop page turns this result into a paragraph whose wording
    depends on what was found - whether the modulation is significant at
    all, whether the hysteresis ratio can be trusted given the observation
    window, whether a state spline was fitted and what it bought. That
    prose is presentation and belongs on this side; reimplementing its
    branches in Kotlin would be three chances to describe a measurement
    differently from the desktop.
    """
    import gui_core.services as services

    res = services.run_gain_modulation(dut=dut, drive=drive,
                                       fit_state_model=fit_state)
    name, config, metrics = services.gain_mod_run_record(res)
    _record(name, "pa_model", config, metrics)

    if not res["significant"]:
        notes = [tr("无增益调制(垂降 {d:+.3f} dB / {p:+.2f}°)——纯 SMP/"
                    "SplineGMP 即可;已注册为 run。", lang).format(
                        d=res["droop_db"], p=res["phase_drift_deg"])]
    else:
        taus = ", ".join(
            tr("{t:.1f}µs(权重 {w:.2f})", lang).format(t=t, w=w)
            for t, w in zip(res["taus_heat_us"], res["weights_heat"]))
        extra = ""
        if res["state_gain_db"] is not None:
            extra = tr(";状态样条 vs 纯 SMP:{a:.1f} → {b:.1f} dB"
                       "(+{g:.1f} dB)", lang).format(
                           a=res["nmse_plain_db"], b=res["nmse_state_db"],
                           g=res["state_gain_db"])
        hyst = (tr("迟滞比 {h:.2f}", lang).format(h=res["hysteresis_ratio"])
                if res["hysteresis_reliable"] else
                tr("迟滞比 {h:.2f}(观测窗仅 {o:.0f} µs,不足以判定,"
                   "加长 t_obs 再看)", lang).format(
                       h=res["hysteresis_ratio"], o=res["observation_us"]))
        notes = [tr("垂降 {d:+.2f} dB / {p:+.1f}°;加热 τ:{taus};{hyst}"
                    "{extra};已注册为 run。", lang).format(
                        d=res["droop_db"], p=res["phase_drift_deg"],
                        taus=taus, hyst=hyst, extra=extra)]

    metrics = [
        _metric(tr("垂降", lang), f"{res['droop_db']:+.2f} dB"),
        _metric(tr("相位漂移", lang), f"{res['phase_drift_deg']:+.2f}°"),
        _metric(tr("观测窗", lang), f"{res['observation_us']:.0f} µs"),
    ]
    return {"result": res, "metrics": metrics, "lang": lang, "notes": notes,
            "charts": {"gain_modulation": ("gain_modulation", (res,), {})}}


def dpd_ila(basis: str, bandwidth_mhz: float, drive: float,
            cfr_papr_db: float | None = None, *, lang: str = "zh") -> dict:
    """DPD Lab, ILA branch: closed-loop indirect learning on the PA.

    The DLA branch is not here for the same reason the neural model
    family is not: it needs torch, which has no Android wheel. Both are
    named in capabilities() and greyed out in the UI.

    Constellation points are computed here rather than shipped raw. The
    desktop calls services.constellation_points to demodulate before and
    after; doing that in Kotlin would mean porting an OFDM demodulator to
    draw a scatter plot.
    """
    import gui_core.services as services

    src = services.cached_synthetic_source(
        bandwidth_hz=bandwidth_mhz * 1e6, drive=drive,
        cfr_papr_db=cfr_papr_db)
    out = services.run_dpd_ila(src, basis=basis)
    m = out["metrics"]

    def _aclr(row):
        return (f"{row['aclr_high']:.1f} dBc" if row["aclr_high"] is not None
                else "—")

    metrics = [
        _metric(tr("无 DPD", lang) + " EVM", f"{m['no DPD']['evm_db']:.1f} dB"),
        _metric(tr("DPD 后", lang) + " EVM", f"{m['DPD']['evm_db']:.1f} dB",
                f"{m['DPD']['evm_db'] - m['no DPD']['evm_db']:+.1f} dB"),
        _metric(tr("无 DPD", lang) + " ACLR", _aclr(m["no DPD"]),
                f"Mask {m['no DPD']['mask']}"),
        _metric(tr("DPD 后", lang) + " ACLR", _aclr(m["DPD"]),
                f"Mask {m['DPD']['mask']}"),
    ]

    charts = {"psd": ("psd", ({tr("无 DPD", lang): out["y_before"],
                               tr("DPD 后", lang): out["y_after"]},
                              out["fs"]),
                      {"mask": out.get("mask")})}
    if out.get("wf") is not None:
        charts["constellation"] = ("constellation", ({
            tr("无 DPD", lang): services.constellation_points(
                out["y_before"], out["wf"], out["gain"]),
            tr("DPD 后", lang): services.constellation_points(
                out["y_after"], out["wf"], out["gain"]),
        },), {})

    label = f"ILA-{basis}"
    _record(f"{label} @ {src['name']}", "dpd",
            {"algo": "ILA", "basis": basis, "source": src["name"]},
            {"evm_db": m["DPD"]["evm_db"],
             "evm_before_db": m["no DPD"]["evm_db"],
             "aclr_high_dbc": m["DPD"]["aclr_high"],
             "aclr_before_dbc": m["no DPD"]["aclr_high"],
             "convention": out["convention"]})

    return {"result": out, "metrics": metrics, "charts": charts, "lang": lang,
            "notes": [tr("✅ {label} 完成({conv} 口径),已注册 run",
                         lang).format(label=label,
                                      conv=out["convention"])]}


def adaptive_dpd(method: str, basis: str, dut: str, n_blocks: int,
                 bandwidth_mhz: float, *, lang: str = "zh") -> dict:
    """Drift tracking: an adaptive DPD against a frozen batch one."""
    import gui_core.services as services

    res = services.run_adaptive_dpd(method=method, basis=basis, dut=dut,
                                    n_blocks=n_blocks,
                                    bw=bandwidth_mhz * 1e6)
    name, config, metrics = services.adaptive_run_record(res)
    _record(name, "dpd", config, metrics)

    return {
        "result": res, "lang": lang,
        "metrics": [
            _metric(tr("冻结", lang), f"{res['final_frozen']:.1f} dB"),
            _metric(res["method"].upper(), f"{res['final_adaptive']:.1f} dB"),
            _metric(tr("领先", lang), f"{res['gap_db']:.1f} dB"),
        ],
        "charts": {"adaptive_evm": ("adaptive_evm", (res,), {})},
        "notes": [tr("满漂移 EVM:冻结 {f:.1f} dB → 自适应 {m} {a:.1f} dB"
                     "(领先 {g:.1f} dB);已注册为 run。", lang).format(
                         f=res["final_frozen"], m=res["method"].upper(),
                         a=res["final_adaptive"], g=res["gap_db"])],
    }


def three_loop(n_blocks: int, drift_span: float, lo_leakage_dbc: float,
               iq_gain_db: float, *, lang: str = "zh") -> dict:
    """QMC, observation de-embedding and adaptive DPD, all at once.

    phase_deg tracks gain_db at ten times its value, exactly as the
    desktop page does - one control drives both halves of the IQ
    imbalance so the two cannot be set to an inconsistent pair.
    """
    import gui_core.services as services

    res = services.run_three_loop_demo(
        n_blocks=n_blocks, drift_span=drift_span, gain_db=iq_gain_db,
        phase_deg=10.0 * iq_gain_db, lo_leakage_dbc=lo_leakage_dbc)
    name, config, metrics = services.three_loop_run_record(res)
    _record(name, "dpd", config, metrics)

    return {
        "result": res, "lang": lang,
        "metrics": [
            _metric(tr("原始环回", lang), f"{res['final_raw']:.1f} dB"),
            _metric(tr("仅去嵌", lang), f"{res['final_deembed']:.1f} dB"),
            _metric(tr("三环", lang), f"{res['final_full']:.1f} dB"),
            _metric(tr("镜像残差", lang), f"{res['final_image_dbc']:.1f} dBc"),
        ],
        "charts": {"three_loop": ("three_loop", (res,), {})},
        "notes": [tr("满漂移在空口 EVM:原始环回 {r:.1f} dB(失效)→ 仅去嵌 "
                     "{d:.1f} dB(钉在 IRR)→ 三环 {f:.1f} dB;镜像残差 "
                     "{i:.1f} dBc;已注册为 run。", lang).format(
                         r=res["final_raw"], d=res["final_deembed"],
                         f=res["final_full"], i=res["final_image_dbc"])],
    }


def compare(selected_ids: list | None = None, *,
            lang: str = "zh") -> dict:
    """Compare Runs: the registry every other screen writes to.

    Returns rows rather than metrics - this screen is a table, not a
    reading. Values are pre-formatted here for the same reason metrics
    are: the desktop prints two decimals and Kotlin should not get a
    second opinion about that.

    Export to JSON is absent. On Android that needs the Storage Access
    Framework, which is not wired up yet; offering a button that cannot
    write anywhere would be worse than not offering one.
    """
    runs = _runstore().list()
    rows = [{
        "id": r.run_id,
        "when": r.when,
        "name": r.name,
        "kind": r.kind,
        **{k: (f"{v:.2f}" if isinstance(v, (int, float)) else "")
           for k, v in ((k, r.metrics.get(k)) for k in _COMPARE_KEYS)},
    } for r in runs]

    picked = [r for r in runs if r.run_id in set(selected_ids or ())]
    charts, notes = {}, []
    if len(picked) < 2:
        notes.append(tr("至少勾选 2 项", lang))
    else:
        # Only metrics at least one selected run actually carries: a bar
        # group of empty values reads as "measured zero" rather than "not
        # applicable to this kind of run".
        keys = [k for k in _COMPARE_KEYS
                if any(isinstance(r.metrics.get(k), (int, float))
                       for r in picked)]
        charts["bars"] = ("bars", ([r.name for r in picked],
                                   {k: [r.metrics.get(k) for r in picked]
                                    for k in keys}), {})
        notes.append(tr("对比 {n} 项", lang).format(n=len(picked)))

    return {"result": runs, "rows": rows, "metrics": [], "charts": charts,
            "lang": lang, "notes": notes}


_COMPARE_KEYS = ("nmse_db", "evm_db", "aclr_high_dbc")


def delete_runs(ids: list) -> int:
    """Delete runs by id, returning how many are left.

    Not a screen, so not routed through page(): it changes the store
    rather than describing it, and giving a mutation the same entry point
    as a read would make "assemble the compare screen" a call that can
    destroy data.
    """
    store = _runstore()
    for run_id in ids:
        store.delete(run_id)
    return len(store.list())


DEPLOY_BITS = (16, 14, 12, 10, 8)


def _eval_source(entry: dict) -> dict:
    """The source a fitted model should be evaluated on.

    services.eval_source_for rebuilds the exact synthetic source from the
    name when it was never registered, which is the only case here: the
    Data screen is not ported, so every source on this side is synthetic.
    """
    import gui_core.services as services
    return services.eval_source_for(entry["meta"], {})


def deploy(model_names: list | None = None, bits: list | None = None, *,
           lang: str = "zh") -> dict:
    """Deployment: fixed-point bit-width sweep over fitted models.

    Lists what the Modeling screen has fitted this session and sweeps the
    selected ones. With nothing fitted it returns an empty table and says
    so - the desktop shows the same empty list rather than an error.

    Export of hand-off artefacts is not offered. It needs a writable
    directory (Storage Access Framework, not wired up), ONNX export
    (torch, no Android wheel) and an iverilog run for the RTL bit-true
    check (no toolchain on a phone). Three independent blockers, so the
    screen states the reason rather than presenting a button.
    """
    import gui_core.services as services

    available = list(_MODELS)
    picked = [n for n in (model_names or []) if n in _MODELS]
    chosen_bits = [b for b in (bits or []) if b in DEPLOY_BITS] or [16, 12, 8]

    rows, charts, notes = [], {}, []
    if not available:
        notes.append(tr("先在建模页拟合模型", lang))
    elif not picked:
        notes.append(tr("请先勾选至少一个模型和位宽", lang))
    else:
        sweeps = {}
        for name in picked:
            entry = _MODELS[name]
            sweeps[name.split(" @")[0]] = services.bitwidth_sweep(
                entry["model"], _eval_source(entry), bits=tuple(chosen_bits))

        charts["bitwidth"] = ("bitwidth", (sweeps,), {})
        for label, sweep in sweeps.items():
            row = {"name": label, "float": f"{sweep['float']:.2f}"}
            row.update({f"W{b}": f"{sweep['bits'][b]:.2f}"
                        for b in chosen_bits})
            if sweep.get("macs"):
                row["macs"] = str(sweep["macs"]["real_macs_per_sample"])
                row["gmac"] = f"{sweep['macs']['real_gmac_per_s']:.0f}"
            rows.append(row)
            _record(f"deploy {label}", "deploy", {"bits": chosen_bits},
                    {"float_nmse_db": sweep["float"],
                     **{f"w{b}_nmse_db": v
                        for b, v in sweep["bits"].items()}})
        notes.append(tr("✅ 扫描完成({n} 模型),已注册 run",
                        lang).format(n=len(sweeps)))

    return {"result": {"available": available}, "rows": rows,
            "metrics": [_metric(tr("已拟合模型", lang), str(len(available)))],
            "charts": charts, "lang": lang, "notes": notes,
            "options": available}


def lut_depth(model_name: str, *, lang: str = "zh") -> dict:
    """LUT-depth axis of the same trade-off.

    Only branch-gain models carry a gain curve to tabulate, so a model
    without one is reported as unsupported rather than raising - picking
    the wrong model from a list is a normal thing to do.
    """
    import gui_core.services as services

    entry = _MODELS.get(model_name)
    if entry is None:
        return {"result": None, "rows": [], "metrics": [], "charts": {},
                "lang": lang, "notes": [tr("先在建模页拟合模型", lang)]}
    if not hasattr(entry["model"], "gain_curve"):
        return {"result": None, "rows": [], "metrics": [], "charts": {},
                "lang": lang,
                "notes": [tr("该模型不支持 LUT 提取(需要样条/MP 增益曲线)",
                             lang)]}

    res = services.lut_sweep(entry["model"], _eval_source(entry))
    rows = [{"depth": "float", "nmse_db": f"{res['float']:.2f}"}]
    rows += [{"depth": str(n), "nmse_db": f"{v:.2f}"}
             for n, v in res["entries"].items()]
    return {
        "result": res, "rows": rows, "charts": {}, "lang": lang,
        "metrics": [_metric(tr("LUT MAC/样本", lang),
                            str(res["macs"]["real_macs_per_sample_lut"]))],
        "notes": [],
    }


def home(*, lang: str = "zh") -> dict:
    """Overview: what padpd has achieved, what this device can do, and
    what has been run here.

    The headline figures are the project's own measured results, carried
    over from the desktop page verbatim. They are documentation, not
    something this screen computes - and they say so through the note
    rather than by looking like a live reading.
    """
    import gui_core.services as services
    from gui_core.paths import user_data_dir

    metrics = [
        _metric(tr("合成链路 DPD 后 EVM", lang), "-57.4 dB",
                "160 MHz/1024-QAM"),
        _metric(tr("TCN vs GMP(真实数据)", lang), "-34.9 dB",
                tr("超经典基线", lang)),
        _metric("DPA_160 DLA DPD", "-53.1 dBc", tr("过 -52 验收线", lang)),
        _metric(tr("APA 代理重评", lang), "-38.56 dBc",
                tr("≈发表值 -38.80", lang)),
    ]

    # Environment self-check, the desktop's three lines. Two of them are
    # foregone conclusions on Android and are reported as such rather
    # than probed with a try/import that can only fail.
    env = [tr("⚠️ PyTorch 未安装(神经功能不可用)", lang)]
    opendpd = Path(services.default_opendpd_dir())
    env.append(tr("✅ OpenDPD 数据集:{path}", lang).format(path=opendpd)
               if opendpd.is_dir()
               else tr("ℹ️ OpenDPD 未找到(可在数据页指定)", lang))

    model_dir = user_data_dir() / "models"
    n_models = len(list(model_dir.glob("*"))) if model_dir.is_dir() else 0
    runs = _runstore().list()
    env.append("ℹ️ " + tr("模型 checkpoint × {n}", lang).format(n=n_models)
               + " · " + tr("实验 run × {n}", lang).format(n=len(runs)))

    rows = [{
        "when": r.when,
        "name": r.name,
        "kind": r.kind,
        "metrics": " · ".join(f"{k}={v:.1f}" for k, v in r.metrics.items()
                              if isinstance(v, float))[:60],
    } for r in runs[:8]]

    return {"result": None, "metrics": metrics, "rows": rows, "charts": {},
            "lang": lang, "notes": env}


CODESIGN_DRIVES = (0.08, 0.10, 0.12, 0.14, 0.17, 0.20, 0.24)


def codesign(spec_db: float, budget: int, bandwidth_mhz: float, *,
             lang: str = "zh") -> dict:
    """Co-design: the discrete Pareto sweep over PA drive.

    The gradient tab is not here - padpd.codesign_torch needs torch. This
    half is pure numpy and runs on the phone, which is the more
    interesting half anyway: it is the one that shows a sequential design
    hitting a wall a joint design can walk around.

    The desktop labels this "about a minute". It is the slowest thing in
    the app by a wide margin.
    """
    from padpd.codesign import codesign_sweep
    from padpd.waveform import OFDMConfig, generate_ofdm

    bw = bandwidth_mhz * 1e6
    cfg = OFDMConfig(bandwidth_hz=bw, qam_order=1024, n_symbols=6, seed=0)
    train = generate_ofdm(cfg)
    val = generate_ofdm(OFDMConfig(bandwidth_hz=bw, qam_order=1024,
                                   n_symbols=6, seed=1))
    sweep = codesign_sweep(list(CODESIGN_DRIVES), train.x, val.x, val,
                           float(spec_db), cfg.sample_rate_hz, bw)

    # Sequential design: chase efficiency first, then see whether DPD can
    # rescue it. Joint design: the best efficiency that is still feasible
    # inside the coefficient budget. The gap between them is the point of
    # the whole page.
    sequential = max(sweep, key=lambda r: r["pae"])
    seq_ok = sequential["feasible"] and sequential["dpd_cost"] <= budget
    feasible = [r for r in sweep
                if r["feasible"] and r["dpd_cost"] <= budget]

    metrics = [
        _metric(tr("顺序设计(先冲效率)", lang),
                f"PAE {100 * sequential['pae']:.1f}%",
                tr("可行", lang) if seq_ok
                else tr("撞墙:不可逆/超预算", lang)),
    ]
    if feasible:
        joint = max(feasible, key=lambda r: r["pae"])
        metrics.append(_metric(
            tr("联合设计(预算内最高效率)", lang),
            f"PAE {100 * joint['pae']:.1f}%",
            tr("drive {drive:.2f} · {cost} 系数 · EVM {evm:.1f} dB",
               lang).format(drive=joint["drive"], cost=joint["dpd_cost"],
                            evm=joint["evm_dpd"])))
    else:
        metrics.append(_metric(tr("联合设计(预算内最高效率)", lang), "—",
                               tr("预算内无可行点", lang)))

    rows = [{
        "drive": f"{r['drive']:.2f}",
        "PAE %": f"{100 * r['pae']:.1f}",
        "EVM": f"{r['evm_nodpd']:.1f}",
        "coeffs": str(r["dpd_cost"]),
        "EVM DPD": f"{r['evm_dpd']:.1f}",
        "ok": "✅" if r["feasible"] else "❌",
    } for r in sweep]

    return {
        "result": sweep, "metrics": metrics, "rows": rows, "lang": lang,
        "charts": {"codesign": ("codesign", (sweep, budget), {})},
        "notes": [tr("✅ 扫描完成({n} 个工作点)", lang).format(n=len(sweep))],
    }


def manual(chapter_id: str = "", *, lang: str = "zh") -> dict:
    """The built-in bilingual manual.

    gui_core/manual.py needs no change for this: MANUAL_DIR resolves as
    gui_core's parent directory, and the Gradle staging task copies
    manual/ there alongside it. The same eight chapters the desktop
    shows, from the same Markdown.

    Images ride the blob channel rather than being inlined as base64.
    They are 162 KB on average and 300 KB at the largest; base64 would
    add a third to that and put the payload inside the screen's own JSON.

    split_segments() exists because Streamlit could not reference local
    image files from Markdown. Compose has the same limitation for a
    different reason - it has no Markdown renderer at all - so the same
    slicing serves here.
    """
    from gui_core import manual as manual_mod

    chapters = [{"id": cid,
                 "title": manual_mod.chapter_title(cid, lang)}
                for cid in manual_mod.chapter_ids()]
    current = chapter_id or chapters[0]["id"]

    segments = []
    for seg in manual_mod.split_segments(manual_mod.load(current, lang)):
        if seg[0] == "md":
            segments.append({"kind": "md", "text": seg[1]})
        else:
            path = Path(seg[1])
            # A missing image is reported in place rather than dropped:
            # silently omitting it would make the chapter look complete
            # while a figure its text refers to is simply gone.
            if path.is_file():
                # Raw bytes; api.page registers them as a blob. This
                # module does not touch the transport, the same way it
                # names a chart builder rather than building the spec.
                segments.append({"kind": "img",
                                 "data": path.read_bytes(),
                                 "caption": seg[2]})
            else:
                segments.append({"kind": "md",
                                 "text": f"*[missing image: {path.name}]*"})

    return {"result": None, "metrics": [], "charts": {}, "lang": lang,
            "notes": [], "rows": chapters, "segments": segments,
            "options": [current]}


# Screens Kotlin may ask for, by name. Same reasoning as api.DISPATCH:
# the name arrives from outside the process, so it is matched against a
# table rather than looked up on the module.
SCREENS = {
    "waveform": waveform,
    "modeling": modeling,
    "gain_modulation": gain_modulation,
    "dpd_ila": dpd_ila,
    "adaptive_dpd": adaptive_dpd,
    "three_loop": three_loop,
    "compare": compare,
    "deploy": deploy,
    "lut_depth": lut_depth,
    "home": home,
    "codesign": codesign,
    "manual": manual,
}


def build(name: str, *args, **kwargs) -> dict:
    if name not in SCREENS:
        raise KeyError(f"no such screen: {name}")
    return SCREENS[name](*args, **kwargs)


def chart_names(name: str) -> list:
    """Chart slots a screen produces, for tests that assert coverage."""
    return list(_SLOTS[name])


_SLOTS = {
    "waveform": ("psd", "ccdf", "constellation", "time"),
    "modeling": ("psd", "amam"),
    "gain_modulation": ("gain_modulation",),
    "dpd_ila": ("psd", "constellation"),
    "adaptive_dpd": ("adaptive_evm",),
    "three_loop": ("three_loop",),
    # Charts appear only once two runs are selected.
    "compare": (),
    "deploy": ("bitwidth",),
    "lut_depth": (),
    "home": (),
    "codesign": ("codesign",),
    "manual": (),
}
