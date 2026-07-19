"""Render the two-tone memory -> DPD-budget decision flow as a manual asset.

Produces ``manual/assets/two_tone_budget.png`` (referenced from manual
section 5.8 in both languages). Labels are kept in universal engineering
terms/symbols so the one shared image reads correctly in the zh and en
manuals alike. Re-run after changing the thresholds in
``padpd.two_tone.recommend_dpd_budget`` so the diagram stays in sync.

Usage:  python scripts/make_two_tone_diagram.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "manual" / "assets" \
    / "two_tone_budget.png"

# palette (light, print-friendly, readable in both manual themes)
C_MEASURE = "#3b6fd4"
C_CRIT = "#1f9d57"
C_DECIDE = "#c9721f"
INK = "#1c2333"
FILL = "#f4f7fd"
FILL_C = "#eef8f1"
FILL_D = "#fdf3e7"


def box(ax, x, y, w, h, text, edge, fill, fontsize=9.5, weight="normal"):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
        linewidth=1.4, edgecolor=edge, facecolor=fill, mutation_aspect=1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=INK, weight=weight, linespacing=1.35)


def arrow(ax, x0, y0, x1, y1, color=INK):
    ax.add_patch(FancyArrowPatch(
        (x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=13,
        linewidth=1.4, color=color, shrinkA=2, shrinkB=2))


def header(ax, x, text, color):
    ax.text(x, 0.955, text, ha="center", va="center", fontsize=11.5,
            weight="bold", color=color)


def main() -> None:
    fig = plt.figure(figsize=(11.4, 5.4), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(0.5, 0.995, "Two-tone memory diagnostics  ->  DPD resource "
            "budget", ha="center", va="top", fontsize=13, weight="bold",
            color=INK)

    # ---- stage 1: measure ------------------------------------------
    header(ax, 0.14, "1  MEASURE", C_MEASURE)
    box(ax, 0.02, 0.60, 0.24, 0.24,
        "Two-tone at several\ntone spacings  df\n\n"
        r"$\to$ IM3 lower / upper" "\n(dBc vs one tone)",
        C_MEASURE, FILL)
    box(ax, 0.02, 0.24, 0.24, 0.24,
        "memoryless PA:\nupper = lower,\nflat over df\n\n"
        "memory breaks\nthis symmetry",
        C_MEASURE, FILL, fontsize=9, weight="normal")
    arrow(ax, 0.14, 0.60, 0.14, 0.48, C_MEASURE)

    # ---- stage 2: criteria -----------------------------------------
    header(ax, 0.44, "2  CRITERIA", C_CRIT)
    box(ax, 0.31, 0.70, 0.26, 0.15,
        "spread = ptp( avg IM3 vs df )\n= diagonal (symmetric) memory",
        C_CRIT, FILL_C, fontsize=9)
    box(ax, 0.31, 0.505, 0.26, 0.15,
        "asym = max | upper - lower |\n= cross (complex) memory",
        C_CRIT, FILL_C, fontsize=9)
    box(ax, 0.31, 0.31, 0.26, 0.15,
        "thermal?  asym peaks at the\nsmallest df (slow envelope)",
        C_CRIT, FILL_C, fontsize=9)
    box(ax, 0.31, 0.135, 0.26, 0.115,
        "memory strength = max( spread, asym )",
        C_CRIT, "#dff0e6", fontsize=9.5, weight="bold")

    arrow(ax, 0.26, 0.72, 0.31, 0.775, C_CRIT)
    arrow(ax, 0.26, 0.60, 0.31, 0.58, C_CRIT)
    arrow(ax, 0.26, 0.36, 0.31, 0.385, C_CRIT)

    # ---- stage 3: decide -------------------------------------------
    header(ax, 0.80, "3  DECIDE  (reserve DPD)", C_DECIDE)
    box(ax, 0.62, 0.70, 0.36, 0.15,
        "spread  ->  memory_depth\n"
        "<0.5 : 1    <1.5 : 2    <3 : 3    <6 : 4    >=6 : 5",
        C_DECIDE, FILL_D, fontsize=9)
    box(ax, 0.62, 0.505, 0.36, 0.15,
        "asym >= 1 dB  ->  GMP lag/lead cross terms\n"
        "asym >= 4 dB  ->  deeper cross (memory 2)",
        C_DECIDE, FILL_D, fontsize=9)
    box(ax, 0.62, 0.31, 0.36, 0.15,
        "thermal  ->  add a slow\nenvelope-LPF branch",
        C_DECIDE, FILL_D, fontsize=9)
    box(ax, 0.62, 0.135, 0.36, 0.115,
        "GMP config  +  est_coeffs\n(= GMPModel(**cfg).n_coeffs)",
        C_DECIDE, "#f7e4cc", fontsize=9.5, weight="bold")

    arrow(ax, 0.57, 0.775, 0.62, 0.775, C_DECIDE)
    arrow(ax, 0.57, 0.58, 0.62, 0.58, C_DECIDE)
    arrow(ax, 0.57, 0.385, 0.62, 0.385, C_DECIDE)
    arrow(ax, 0.80, 0.31, 0.80, 0.25, C_DECIDE)
    arrow(ax, 0.44, 0.135, 0.44, 0.10, C_CRIT)
    arrow(ax, 0.44, 0.075, 0.62, 0.075, INK)
    arrow(ax, 0.80, 0.135, 0.80, 0.10, C_DECIDE)

    ax.text(0.5, 0.045,
            "sizes the hardware (a floor to reserve) — the coefficients "
            "themselves are still trained on measured data",
            ha="center", va="center", fontsize=9.5, style="italic",
            color="#55607a")

    fig.savefig(OUT, dpi=100, facecolor="white",
                bbox_inches="tight", pad_inches=0.15)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
