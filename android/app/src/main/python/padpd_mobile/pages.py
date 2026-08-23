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


# Screens Kotlin may ask for, by name. Same reasoning as api.DISPATCH:
# the name arrives from outside the process, so it is matched against a
# table rather than looked up on the module.
SCREENS = {
    "waveform": waveform,
    "modeling": modeling,
    "gain_modulation": gain_modulation,
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
}
