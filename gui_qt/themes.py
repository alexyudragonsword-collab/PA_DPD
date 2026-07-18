"""Theme tokens for the Qt GUI: QSS palette + matplotlib rc, dark/light."""

from __future__ import annotations

from pathlib import Path
from string import Template

QT_TOKENS = {
    "dark": {
        "bg": "#0e1320", "fg": "#e7eaf2",
        "nav_bg": "#0a0e18", "nav_sel": "#22304d",
        "nav_hover": "#161e30", "sel_fg": "#ffffff",
        "muted": "#9aa4bd", "muted2": "#8a94ad",
        "note_bg": "#131a2a", "note_fg": "#aeb7cc",
        "card": "#171e2e", "border": "#26304a",
        "panel": "#121828", "grid": "#232c42", "alt_row": "#151c2d",
        "accent": "#e4574c", "accent_hover": "#ef685d",
        "blue": "#4f8ff7", "green": "#37c978",
        "btn_bg": "#22304d", "btn_border": "#31426a",
        "btn_hover": "#2a3a5e",
        "disabled_bg": "#1a2130", "disabled_fg": "#5a6478",
    },
    "light": {
        "bg": "#f4f6fb", "fg": "#1c2333",
        "nav_bg": "#e9edf5", "nav_sel": "#d7e0f2",
        "nav_hover": "#eef1f8", "sel_fg": "#16203a",
        "muted": "#5d6880", "muted2": "#75809a",
        "note_bg": "#e9eef8", "note_fg": "#45516b",
        "card": "#ffffff", "border": "#d8dfec",
        "panel": "#ffffff", "grid": "#e3e8f2", "alt_row": "#f6f8fc",
        "accent": "#e4574c", "accent_hover": "#ef685d",
        "blue": "#2f6fe0", "green": "#1f9d57",
        "btn_bg": "#e6ebf5", "btn_border": "#c9d3e6",
        "btn_hover": "#dbe3f2",
        "disabled_bg": "#eef0f6", "disabled_fg": "#a0a8bb",
    },
}

# matplotlib rc per theme (fonts are appended by gui_qt.common)
MPL_RC = {
    "dark": {
        "figure.facecolor": "#121828", "axes.facecolor": "#121828",
        "savefig.facecolor": "#121828", "axes.edgecolor": "#232c42",
        "grid.color": "#232c42", "text.color": "#dfe4ef",
        "axes.labelcolor": "#dfe4ef", "xtick.color": "#9aa4bd",
        "ytick.color": "#9aa4bd", "legend.facecolor": "#171e2e",
        "legend.edgecolor": "#26304a",
    },
    "light": {
        "figure.facecolor": "#ffffff", "axes.facecolor": "#ffffff",
        "savefig.facecolor": "#ffffff", "axes.edgecolor": "#d8dfec",
        "grid.color": "#e3e8f2", "text.color": "#1c2333",
        "axes.labelcolor": "#1c2333", "xtick.color": "#5d6880",
        "ytick.color": "#5d6880", "legend.facecolor": "#ffffff",
        "legend.edgecolor": "#d8dfec",
    },
}

MPL_CYCLE = {
    "dark": ["#4f8ff7", "#e4574c", "#37c978", "#e5b567", "#b07cf7"],
    "light": ["#2f6fe0", "#d3402f", "#1f9d57", "#b98a2f", "#8a55e0"],
}


def render_qss(theme: str) -> str:
    tmpl = (Path(__file__).with_name("style_template.qss")
            .read_text(encoding="utf-8"))
    return Template(tmpl).safe_substitute(QT_TOKENS[theme])
