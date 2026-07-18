"""Plotly chart builders with a consistent dark engineering template."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

PALETTE = ["#4f8ff7", "#e4574c", "#37c978", "#e5b567", "#b07cf7", "#5ad0d0"]

_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#121828",
    font=dict(family="Inter, 'Segoe UI', sans-serif", size=12,
              color="#dfe4ef"),
    margin=dict(l=50, r=20, t=42, b=42),
    legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h",
                yanchor="bottom", y=1.02, x=0),
    colorway=PALETTE,
)

_GRID = dict(gridcolor="#232c42", zerolinecolor="#232c42")


def _fig(title: str = "") -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=dict(text=title, font=dict(size=14)), **_LAYOUT)
    fig.update_xaxes(**_GRID)
    fig.update_yaxes(**_GRID)
    return fig


def fig_psd(curves: dict, mask: np.ndarray | None = None,
            title: str = "功率谱密度 (PSD)") -> go.Figure:
    """curves: label -> (freqs_hz, psd_db)."""
    fig = _fig(title)
    for label, (f, p) in curves.items():
        fig.add_trace(go.Scattergl(x=np.asarray(f) / 1e6, y=p, name=label,
                                   mode="lines", line=dict(width=1.4)))
    if mask is not None:
        f_m = np.concatenate([-mask[::-1, 0], mask[:, 0]]) / 1e6
        v_m = np.concatenate([mask[::-1, 1], mask[:, 1]])
        fig.add_trace(go.Scatter(x=f_m, y=v_m, name="发射 Mask",
                                 mode="lines",
                                 line=dict(dash="dash", color="#9aa4bd")))
    fig.update_xaxes(title="频率 (MHz)")
    fig.update_yaxes(title="PSD (dBr)", range=[-90, 5])
    return fig


def fig_constellation(points_by_label: dict,
                      title: str = "星座图") -> go.Figure:
    fig = _fig(title)
    for i, (label, pts) in enumerate(points_by_label.items()):
        pts = np.asarray(pts).ravel()
        step = max(1, len(pts) // 15000)
        fig.add_trace(go.Scattergl(
            x=pts.real[::step], y=pts.imag[::step], name=label,
            mode="markers",
            marker=dict(size=3, opacity=0.55, color=PALETTE[i % 6])))
    fig.update_xaxes(title="I", scaleanchor="y", scaleratio=1)
    fig.update_yaxes(title="Q")
    return fig


def fig_amam(am: dict, title: str = "AM-AM / AM-PM") -> go.Figure:
    from plotly.subplots import make_subplots
    fig = make_subplots(rows=1, cols=2, subplot_titles=("AM-AM", "AM-PM"))
    step = max(1, len(am["r_in"]) // 15000)
    fig.add_trace(go.Scattergl(x=am["r_in"][::step], y=am["gain"][::step],
                               mode="markers",
                               marker=dict(size=2.5, opacity=0.4,
                                           color=PALETTE[0]),
                               name="增益"), row=1, col=1)
    fig.add_trace(go.Scattergl(x=am["r_in"][::step],
                               y=am["phase_deg"][::step], mode="markers",
                               marker=dict(size=2.5, opacity=0.4,
                                           color=PALETTE[1]),
                               name="相移"), row=1, col=2)
    fig.update_layout(title=dict(text=title, font=dict(size=14)), **_LAYOUT)
    fig.update_xaxes(title="|x|", **_GRID)
    fig.update_yaxes(title="|y|/|x|", row=1, col=1, **_GRID)
    fig.update_yaxes(title="相移 (°)", row=1, col=2, **_GRID)
    return fig


def fig_ccdf(curves: dict, title: str = "CCDF 峰值统计") -> go.Figure:
    fig = _fig(title)
    for label, (level, prob) in curves.items():
        fig.add_trace(go.Scatter(x=level, y=np.maximum(prob, 1e-7),
                                 name=label, mode="lines"))
    fig.update_xaxes(title="高于平均功率 (dB)")
    fig.update_yaxes(title="P(power > level)", type="log")
    return fig


def fig_metric_bars(names: list, series: dict,
                    title: str = "指标对比") -> go.Figure:
    """series: metric_label -> list of values aligned with names."""
    fig = _fig(title)
    for label, vals in series.items():
        fig.add_trace(go.Bar(x=names, y=vals, name=label,
                             text=[f"{v:.1f}" if v is not None else ""
                                   for v in vals], textposition="outside"))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="dB")
    return fig


def fig_bitwidth(sweeps: dict, title: str = "定点位宽 vs 精度") -> go.Figure:
    """sweeps: model_label -> {"float": v, "bits": {b: v}}."""
    fig = _fig(title)
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
                    title: str = "训练曲线") -> go.Figure:
    fig = _fig(title)
    fig.add_trace(go.Scatter(y=[h[metric_key] for h in history],
                             mode="lines", name=metric_key))
    fig.update_xaxes(title="epoch")
    fig.update_yaxes(title="dB")
    return fig


def fig_codesign(rows: list, budget: int | None = None,
                 title: str = "PA/DPD 联合设计权衡") -> go.Figure:
    from plotly.subplots import make_subplots
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    d = [r["drive"] for r in rows]
    fig.add_trace(go.Scatter(x=d, y=[100 * r["pae"] for r in rows],
                             name="PAE 代理 (%)", mode="lines+markers",
                             line=dict(color=PALETTE[1])), secondary_y=False)
    fig.add_trace(go.Scatter(x=d, y=[r["dpd_cost"] for r in rows],
                             name="DPD 达标代价 (系数)",
                             mode="lines+markers",
                             line=dict(color=PALETTE[0], dash="dash")),
                  secondary_y=True)
    for r in rows:
        if not r["feasible"]:
            fig.add_vrect(x0=r["drive"] - 0.004, x1=r["drive"] + 0.004,
                          fillcolor="#5a2430", opacity=0.35, line_width=0)
    if budget:
        fig.add_hline(y=budget, line=dict(dash="dot", color=PALETTE[0]),
                      secondary_y=True)
    fig.update_layout(title=dict(text=title, font=dict(size=14)), **_LAYOUT)
    fig.update_xaxes(title="PA 工作点 (drive)", **_GRID)
    fig.update_yaxes(title="PAE (%)", secondary_y=False, **_GRID)
    fig.update_yaxes(title="DPD 系数", secondary_y=True, **_GRID)
    return fig
