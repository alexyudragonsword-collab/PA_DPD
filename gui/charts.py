"""Plotly chart builders with a consistent engineering template (dark/light)."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from gui.ui import cur_theme, tr

_THEMES = {
    "dark": dict(
        template="plotly_dark", plot_bg="#121828", font="#dfe4ef",
        grid="#232c42", vrect="#5a2430", mask="#9aa4bd",
        palette=["#4f8ff7", "#e4574c", "#37c978", "#e5b567", "#b07cf7",
                 "#5ad0d0"],
    ),
    "light": dict(
        template="plotly_white", plot_bg="#ffffff", font="#1c2333",
        grid="#e3e8f2", vrect="#f3c9c4", mask="#7d879e",
        palette=["#2f6fe0", "#d3402f", "#1f9d57", "#b98a2f", "#8a55e0",
                 "#1e9e9e"],
    ),
}

# backward-compatible module constant (dark palette)
PALETTE = _THEMES["dark"]["palette"]


def palette() -> list:
    return _THEMES[cur_theme()]["palette"]


def _t() -> dict:
    return _THEMES[cur_theme()]


def _layout() -> dict:
    t = _t()
    return dict(
        template=t["template"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=t["plot_bg"],
        font=dict(family="Inter, 'Segoe UI', sans-serif", size=12,
                  color=t["font"]),
        margin=dict(l=50, r=20, t=42, b=42),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h",
                    yanchor="bottom", y=1.02, x=0),
        colorway=t["palette"],
    )


def _grid() -> dict:
    g = _t()["grid"]
    return dict(gridcolor=g, zerolinecolor=g)


def _fig(title: str = "") -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=dict(text=title, font=dict(size=14)),
                      **_layout())
    fig.update_xaxes(**_grid())
    fig.update_yaxes(**_grid())
    return fig


def fig_psd(curves: dict, mask: np.ndarray | None = None,
            title: str | None = None) -> go.Figure:
    """curves: label -> (freqs_hz, psd_db)."""
    fig = _fig(tr("功率谱密度 (PSD)") if title is None else title)
    for label, (f, p) in curves.items():
        fig.add_trace(go.Scattergl(x=np.asarray(f) / 1e6, y=p, name=label,
                                   mode="lines", line=dict(width=1.4)))
    if mask is not None:
        f_m = np.concatenate([-mask[::-1, 0], mask[:, 0]]) / 1e6
        v_m = np.concatenate([mask[::-1, 1], mask[:, 1]])
        fig.add_trace(go.Scatter(x=f_m, y=v_m, name=tr("发射 Mask"),
                                 mode="lines",
                                 line=dict(dash="dash", color=_t()["mask"])))
    fig.update_xaxes(title=tr("频率 (MHz)"))
    fig.update_yaxes(title="PSD (dBr)", range=[-90, 5])
    return fig


def fig_constellation(points_by_label: dict,
                      title: str | None = None) -> go.Figure:
    fig = _fig(tr("星座图") if title is None else title)
    pal = palette()
    for i, (label, pts) in enumerate(points_by_label.items()):
        pts = np.asarray(pts).ravel()
        step = max(1, len(pts) // 15000)
        fig.add_trace(go.Scattergl(
            x=pts.real[::step], y=pts.imag[::step], name=label,
            mode="markers",
            marker=dict(size=3, opacity=0.55, color=pal[i % 6])))
    fig.update_xaxes(title="I", scaleanchor="y", scaleratio=1)
    fig.update_yaxes(title="Q")
    return fig


def fig_amam(am: dict, title: str = "AM-AM / AM-PM") -> go.Figure:
    from plotly.subplots import make_subplots
    fig = make_subplots(rows=1, cols=2, subplot_titles=("AM-AM", "AM-PM"))
    pal = palette()
    step = max(1, len(am["r_in"]) // 15000)
    fig.add_trace(go.Scattergl(x=am["r_in"][::step], y=am["gain"][::step],
                               mode="markers",
                               marker=dict(size=2.5, opacity=0.4,
                                           color=pal[0]),
                               name=tr("增益")), row=1, col=1)
    fig.add_trace(go.Scattergl(x=am["r_in"][::step],
                               y=am["phase_deg"][::step], mode="markers",
                               marker=dict(size=2.5, opacity=0.4,
                                           color=pal[1]),
                               name=tr("相移")), row=1, col=2)
    fig.update_layout(title=dict(text=title, font=dict(size=14)),
                      **_layout())
    fig.update_xaxes(title="|x|", **_grid())
    fig.update_yaxes(title="|y|/|x|", row=1, col=1, **_grid())
    fig.update_yaxes(title=tr("相移 (°)"), row=1, col=2, **_grid())
    return fig


def fig_adaptive_evm(res: dict, title: str | None = None) -> go.Figure:
    """Per-block EVM: frozen batch DPD vs the adaptive method, as the PA
    drifts cold->hot. ``res`` is ``services.run_adaptive_dpd`` output."""
    fig = _fig(tr("漂移跟踪:每块 EVM") if title is None else title)
    pal = palette()
    b = res["blocks"]
    fig.add_trace(go.Scatter(x=b, y=res["evm_frozen"], mode="lines+markers",
                             name=tr("冻结批处理 DPD"),
                             line=dict(width=1.8, color=pal[1])))
    fig.add_trace(go.Scatter(
        x=b, y=res["evm_adaptive"], mode="lines+markers",
        name=tr("自适应 {m}").format(m=res["method"].upper()),
        line=dict(width=1.8, color=pal[0])))
    fig.update_xaxes(title=tr("块(冷 → 热)"))
    fig.update_yaxes(title="EVM (dB)")
    return fig


def fig_three_loop(res: dict, title: str | None = None) -> go.Figure:
    """Per-block on-air EVM for the three loopback configurations plus
    the QMC image residual (right axis). ``res`` is
    ``services.run_three_loop_demo`` output."""
    fig = _fig(tr("前端三环:每块在空口 EVM") if title is None else title)
    pal = palette()
    b = res["blocks"]
    fig.add_trace(go.Scatter(x=b, y=res["evm_raw"], mode="lines+markers",
                             name=tr("原始环回(无环)"),
                             line=dict(width=1.8, color=pal[1])))
    fig.add_trace(go.Scatter(x=b, y=res["evm_deembed"],
                             mode="lines+markers",
                             name=tr("仅去嵌(无 QMC)"),
                             line=dict(width=1.8, color=pal[3])))
    fig.add_trace(go.Scatter(x=b, y=res["evm_full"], mode="lines+markers",
                             name=tr("三环(去嵌+QMC+DPD)"),
                             line=dict(width=2.0, color=pal[0])))
    fig.add_trace(go.Scatter(x=b, y=res["image_dbc"], mode="lines",
                             name=tr("镜像残差 (dBc)"), yaxis="y2",
                             line=dict(width=1.4, dash="dot",
                                       color=pal[4])))
    fig.update_xaxes(title=tr("块(冷 → 热)"))
    fig.update_yaxes(title=tr("在空口 EVM (dB)"))
    fig.update_layout(yaxis2=dict(title=tr("镜像残差 (dBc)"),
                                  overlaying="y", side="right",
                                  showgrid=False))
    return fig


def fig_two_tone(res: dict, title: str | None = None) -> go.Figure:
    """IM3 lower/upper (dBc) vs tone spacing on a log-x axis.

    ``res`` is the dict from ``services.analyze_two_tone_csv``. Spacing
    dependence (spread) and upper/lower gap (asymmetry) are the visible
    memory signatures.
    """
    fig = _fig(tr("双音 IM3 vs 音间距") if title is None else title)
    pal = palette()
    s = np.asarray(res["spacings_hz"]) / 1e6
    fig.add_trace(go.Scatter(x=s, y=res["im3_lower_dbc"], name=tr("下边带 IM3"),
                             mode="lines+markers", line=dict(width=1.8,
                             color=pal[0])))
    fig.add_trace(go.Scatter(x=s, y=res["im3_upper_dbc"], name=tr("上边带 IM3"),
                             mode="lines+markers", line=dict(width=1.8,
                             color=pal[1])))
    fig.update_xaxes(title=tr("音间距 (MHz)"), type="log")
    fig.update_yaxes(title="IM3 (dBc)")
    return fig


def fig_ccdf(curves: dict, title: str | None = None) -> go.Figure:
    fig = _fig(tr("CCDF 峰值统计") if title is None else title)
    for label, (level, prob) in curves.items():
        fig.add_trace(go.Scatter(x=level, y=np.maximum(prob, 1e-7),
                                 name=label, mode="lines"))
    fig.update_xaxes(title=tr("高于平均功率 (dB)"))
    fig.update_yaxes(title="P(power > level)", type="log")
    return fig


def fig_metric_bars(names: list, series: dict,
                    title: str | None = None) -> go.Figure:
    """series: metric_label -> list of values aligned with names."""
    fig = _fig(tr("指标对比") if title is None else title)
    for label, vals in series.items():
        fig.add_trace(go.Bar(x=names, y=vals, name=label,
                             text=[f"{v:.1f}" if v is not None else ""
                                   for v in vals], textposition="outside"))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="dB")
    return fig


def fig_bitwidth(sweeps: dict, title: str | None = None) -> go.Figure:
    """sweeps: model_label -> {"float": v, "bits": {b: v}}."""
    fig = _fig(tr("定点位宽 vs 精度") if title is None else title)
    for label, s in sweeps.items():
        bits = sorted(s["bits"], reverse=True)
        fig.add_trace(go.Scatter(
            x=[f"W{b}" for b in bits], y=[s["bits"][b] for b in bits],
            name=label, mode="lines+markers"))
        fig.add_hline(y=s["float"], line=dict(dash="dot", width=1),
                      annotation_text=f"{label} float",
                      annotation_font_size=10)
    fig.update_yaxes(title="test NMSE (dB)")
    return fig


def fig_train_curve(history: list, metric_key: str = "val_nmse_db",
                    title: str | None = None) -> go.Figure:
    fig = _fig(tr("训练曲线") if title is None else title)
    fig.add_trace(go.Scatter(y=[h[metric_key] for h in history],
                             mode="lines", name=metric_key))
    fig.update_xaxes(title="epoch")
    fig.update_yaxes(title="dB")
    return fig


def fig_codesign(rows: list, budget: int | None = None,
                 title: str | None = None) -> go.Figure:
    from plotly.subplots import make_subplots
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    pal = palette()
    d = [r["drive"] for r in rows]
    fig.add_trace(go.Scatter(x=d, y=[100 * r["pae"] for r in rows],
                             name=tr("漏极效率 (%)"), mode="lines+markers",
                             line=dict(color=pal[1])), secondary_y=False)
    fig.add_trace(go.Scatter(x=d, y=[r["dpd_cost"] for r in rows],
                             name=tr("DPD 达标代价 (系数)"),
                             mode="lines+markers",
                             line=dict(color=pal[0], dash="dash")),
                  secondary_y=True)
    for r in rows:
        if not r["feasible"]:
            fig.add_vrect(x0=r["drive"] - 0.004, x1=r["drive"] + 0.004,
                          fillcolor=_t()["vrect"], opacity=0.35,
                          line_width=0)
    if budget:
        fig.add_hline(y=budget, line=dict(dash="dot", color=pal[0]),
                      secondary_y=True)
    fig.update_layout(title=dict(
        text=tr("PA/DPD 联合设计权衡") if title is None else title,
        font=dict(size=14)), **_layout())
    fig.update_xaxes(title=tr("PA 工作点 (drive)"), **_grid())
    fig.update_yaxes(title="PAE (%)", secondary_y=False, **_grid())
    fig.update_yaxes(title=tr("DPD 系数"), secondary_y=True, **_grid())
    return fig
