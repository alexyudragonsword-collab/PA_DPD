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


# Screens Kotlin may ask for, by name. Same reasoning as api.DISPATCH:
# the name arrives from outside the process, so it is matched against a
# table rather than looked up on the module.
SCREENS = {
    "waveform": waveform,
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
}
