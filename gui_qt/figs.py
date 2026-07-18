"""Matplotlib figure builders for the Qt GUI (dark-styled)."""

from __future__ import annotations

import matplotlib
import numpy as np
from matplotlib.figure import Figure

from .common import current_rc, tr


def _fig(w=8.2, h=4.2) -> tuple:
    with matplotlib.rc_context(current_rc()):
        fig = Figure(figsize=(w, h), constrained_layout=True)
        ax = fig.add_subplot(111)
        ax.grid(True, alpha=0.5)
        return fig, ax


def psd_fig(curves: dict, fs: float, mask=None) -> Figure:
    from padpd.metrics import psd
    fig, ax = _fig()
    for label, y in curves.items():
        f, p = psd(np.asarray(y), fs)
        ax.plot(f / 1e6, p, lw=1.1, label=label)
    if mask is not None:
        f_m = np.concatenate([-mask[::-1, 0], mask[:, 0]]) / 1e6
        v_m = np.concatenate([mask[::-1, 1], mask[:, 1]])
        ax.plot(f_m, v_m, "--", color="#9aa4bd", lw=1.1, label=tr("发射 Mask"))
    ax.set_xlabel(tr("频率 (MHz)"))
    ax.set_ylabel("PSD (dBr)")
    ax.set_ylim(-90, 5)
    ax.legend(loc="upper right", fontsize=8)
    return fig


def ccdf_fig(curves: dict) -> Figure:
    from padpd.metrics import ccdf
    fig, ax = _fig()
    for label, x in curves.items():
        level, prob = ccdf(np.asarray(x))
        ax.semilogy(level, np.maximum(prob, 1e-7), lw=1.2, label=label)
    ax.set_xlabel(tr("高于平均功率 (dB)"))
    ax.set_ylabel("CCDF")
    ax.legend(fontsize=8)
    return fig


def constellation_fig(points_by_label: dict) -> Figure:
    fig, ax = _fig(5.4, 5.0)
    for label, pts in points_by_label.items():
        pts = np.asarray(pts).ravel()
        step = max(1, len(pts) // 15000)
        ax.plot(pts.real[::step], pts.imag[::step], ".", ms=1.6, alpha=0.5,
                label=label)
    ax.set_xlabel("I")
    ax.set_ylabel("Q")
    ax.set_aspect("equal")
    ax.legend(markerscale=8, fontsize=8)
    return fig


def amam_fig(x, y) -> Figure:
    from padpd.metrics.amam import am_am_am_pm
    am = am_am_am_pm(np.asarray(x), np.asarray(y))
    with matplotlib.rc_context(current_rc()):
        fig = Figure(figsize=(8.2, 3.8), constrained_layout=True)
        ax1, ax2 = fig.subplots(1, 2)
        step = max(1, len(am["r_in"]) // 15000)
        ax1.plot(am["r_in"][::step], am["gain"][::step], ".", ms=1.4,
                 alpha=0.4, color="#4f8ff7")
        ax2.plot(am["r_in"][::step], am["phase_deg"][::step], ".", ms=1.4,
                 alpha=0.4, color="#e4574c")
        for ax, t, yl in ((ax1, "AM-AM", "|y|/|x|"),
                          (ax2, "AM-PM", tr("相移 (°)"))):
            ax.set_title(t, fontsize=10)
            ax.set_xlabel("|x|")
            ax.set_ylabel(yl)
            ax.grid(True, alpha=0.5)
        return fig


def time_fig(sig: dict, fs: float, n: int = 2000) -> Figure:
    fig, ax = _fig()
    for label, x in sig.items():
        x = np.asarray(x)[:n]
        ax.plot(np.arange(len(x)) / fs * 1e6, np.abs(x), lw=0.9, label=label)
    ax.set_xlabel(tr("时间 (µs)"))
    ax.set_ylabel("|x|")
    ax.legend(fontsize=8)
    return fig


def bars_fig(names: list, series: dict) -> Figure:
    fig, ax = _fig()
    n, k = len(names), max(1, len(series))
    width = 0.8 / k
    xs = np.arange(n)
    for i, (label, vals) in enumerate(series.items()):
        v = [x if x is not None else np.nan for x in vals]
        ax.bar(xs + (i - k / 2 + 0.5) * width, v, width, label=label)
    ax.set_xticks(xs, [t if len(t) < 26 else t[:23] + "…" for t in names],
                  rotation=12, fontsize=8)
    ax.set_ylabel("dB")
    ax.legend(fontsize=8)
    return fig


def bitwidth_fig(sweeps: dict) -> Figure:
    fig, ax = _fig()
    for label, s in sweeps.items():
        bits = sorted(s["bits"], reverse=True)
        ax.plot([f"W{b}" for b in bits], [s["bits"][b] for b in bits],
                "o-", label=label)
        ax.axhline(s["float"], ls=":", lw=1, alpha=0.6)
    ax.set_ylabel("test NMSE (dB)")
    ax.legend(fontsize=8)
    return fig


def train_fig(history: list, key: str) -> Figure:
    fig, ax = _fig(8.2, 3.2)
    ax.plot([h[key] for h in history], lw=1.4, color="#4f8ff7")
    ax.set_xlabel("epoch")
    ax.set_ylabel(key)
    return fig


def codesign_fig(rows: list, budget: int | None = None) -> Figure:
    with matplotlib.rc_context(current_rc()):
        fig = Figure(figsize=(8.2, 4.2), constrained_layout=True)
        ax1 = fig.add_subplot(111)
        d = [r["drive"] for r in rows]
        ax1.plot(d, [100 * r["pae"] for r in rows], "o-", color="#e4574c",
                 label="PAE (%)")
        ax1.set_xlabel("PA drive")
        ax1.set_ylabel("PAE (%)", color="#e4574c")
        ax1.grid(True, alpha=0.5)
        ax2 = ax1.twinx()
        ax2.plot(d, [r["dpd_cost"] for r in rows], "s--", color="#4f8ff7",
                 label=tr("DPD 系数"))
        if budget:
            ax2.axhline(budget, ls=":", color="#4f8ff7", alpha=0.6)
        ax2.set_ylabel(tr("DPD 系数"), color="#4f8ff7")
        for r in rows:
            if not r["feasible"]:
                ax1.axvspan(r["drive"] - 0.004, r["drive"] + 0.004,
                            color="#5a2430", alpha=0.5)
        return fig


def grad_fig(history: dict, spec: float) -> Figure:
    with matplotlib.rc_context(current_rc()):
        fig = Figure(figsize=(8.2, 4.0), constrained_layout=True)
        ax1 = fig.add_subplot(111)
        ax1.plot(history["drive"], color="#e4574c")
        ax1.set_xlabel(tr("梯度步"))
        ax1.set_ylabel("drive", color="#e4574c")
        ax1.grid(True, alpha=0.5)
        ax2 = ax1.twinx()
        ax2.plot(history["evm_db"], color="#4f8ff7")
        ax2.axhline(spec, ls=":", color="#9aa4bd")
        ax2.set_ylabel("EVM (dB)", color="#4f8ff7")
        return fig
