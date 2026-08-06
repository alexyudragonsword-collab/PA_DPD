"""Shared UI helpers for the Streamlit workbench: CSS, cards, state, i18n."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from gui_core import i18n  # noqa: E402
from gui_core.prefs import load_prefs, save_prefs  # noqa: E402

ACCENT = "#e4574c"
BLUE = "#4f8ff7"
GREEN = "#37c978"
AMBER = "#e5b567"

# custom-element palette per theme (Streamlit widgets follow theme.* config)
_TOKENS = {
    "dark": {
        "card_grad_a": "#1a2234", "card_grad_b": "#141a29",
        "border": "#26304a", "muted": "#9aa4bd", "muted2": "#8a94ad",
        "note_bg": "#131a2a", "note_fg": "#aeb7cc",
        "ok_bg": "#12351f", "ok_fg": GREEN, "ok_bd": "#1d5a33",
        "fail_bg": "#3a1720", "fail_fg": ACCENT, "fail_bd": "#6b2733",
        "info_bg": "#14263f", "info_fg": BLUE, "info_bd": "#23446e",
    },
    "light": {
        "card_grad_a": "#ffffff", "card_grad_b": "#f4f6fb",
        "border": "#d8dfec", "muted": "#5d6880", "muted2": "#75809a",
        "note_bg": "#e9eef8", "note_fg": "#45516b",
        "ok_bg": "#e3f6ea", "ok_fg": "#177a43", "ok_bd": "#b5e3c6",
        "fail_bg": "#fbe9e7", "fail_fg": "#c0392e", "fail_bd": "#f0c4be",
        "info_bg": "#e8effc", "info_fg": "#2f5fc0", "info_bd": "#c3d4f2",
    },
}

# Streamlit base theme options per theme (applied via st._config)
_ST_THEME = {
    "dark": {"base": "dark", "primaryColor": ACCENT,
             "backgroundColor": "#0e1320",
             "secondaryBackgroundColor": "#171e2e",
             "textColor": "#e7eaf2"},
    "light": {"base": "light", "primaryColor": ACCENT,
              "backgroundColor": "#f7f9fd",
              "secondaryBackgroundColor": "#eceff7",
              "textColor": "#1c2333"},
}


def _css(theme: str) -> str:
    t = _TOKENS[theme]
    return f"""
<style>
/* layout polish */
.block-container {{ padding-top: 2.2rem; max-width: 1200px; }}
h1, h2, h3 {{ letter-spacing: .3px; }}
h1 {{ font-size: 1.65rem !important; }}
h2 {{ font-size: 1.2rem !important; }}

/* metric cards */
div[data-testid="stMetric"] {{
  background: linear-gradient(160deg, {t["card_grad_a"]} 0%,
              {t["card_grad_b"]} 100%);
  border: 1px solid {t["border"]};
  border-radius: 12px;
  padding: 14px 16px 10px 16px;
}}
div[data-testid="stMetric"] label {{ color: {t["muted"]} !important; }}
div[data-testid="stMetricValue"] {{
  font-variant-numeric: tabular-nums;
}}

/* badges */
.badge {{
  display: inline-block; padding: 2px 10px; border-radius: 999px;
  font-size: .74rem; font-weight: 600; letter-spacing: .4px;
  margin-right: 6px;
}}
.badge-ok   {{ background: {t["ok_bg"]}; color: {t["ok_fg"]};
               border: 1px solid {t["ok_bd"]}; }}
.badge-fail {{ background: {t["fail_bg"]}; color: {t["fail_fg"]};
               border: 1px solid {t["fail_bd"]}; }}
.badge-info {{ background: {t["info_bg"]}; color: {t["info_fg"]};
               border: 1px solid {t["info_bd"]}; }}

/* sidebar brand */
.brand-title {{ font-size: 1.12rem; font-weight: 700; margin-bottom: 0; }}
.brand-sub   {{ font-size: .74rem; color: {t["muted2"]}; margin-top: 2px; }}

/* section divider card */
.section-note {{
  border-left: 3px solid {BLUE}; background: {t["note_bg"]};
  padding: 8px 14px; border-radius: 6px; color: {t["note_fg"]};
  font-size: .86rem; margin: 4px 0 12px 0;
}}
</style>
"""


def get_prefs() -> dict:
    """Session copy of the shared GUI prefs (lang/theme)."""
    if "prefs" not in st.session_state:
        st.session_state.prefs = load_prefs()
    return st.session_state.prefs


def set_pref(key: str, value: str) -> None:
    prefs = get_prefs()
    prefs[key] = value
    save_prefs(prefs)


def cur_lang() -> str:
    return get_prefs()["lang"]


def cur_theme() -> str:
    return get_prefs()["theme"]


def tr(s: str) -> str:
    """Translate a UI string to the current session language."""
    return i18n.tr(s, cur_lang())


def apply_theme() -> None:
    """Point Streamlit's base theme at the current selection.

    Uses the config channel (`st._config`); note this is process-wide,
    so all browser sessions of one server share the choice — fine for a
    single-user workbench.
    """
    for opt, val in _ST_THEME[cur_theme()].items():
        try:
            st._config.set_option(f"theme.{opt}", val)
        except Exception:
            pass


def page_setup(title: str, icon: str = ""):
    """Per-page boilerplate: CSS + header."""
    st.markdown(_css(cur_theme()), unsafe_allow_html=True)
    st.title(f"{icon} {tr(title)}".strip())


def note(text: str):
    st.markdown(f'<div class="section-note">{text}</div>',
                unsafe_allow_html=True)


def badge(text: str, kind: str = "info") -> str:
    return f'<span class="badge badge-{kind}">{text}</span>'


def get_state():
    """Central session objects (created lazily)."""
    from gui_core import RunStore
    from gui_core.paths import user_data_dir
    if "runstore" not in st.session_state:
        st.session_state.runstore = RunStore(user_data_dir() / "gui_runs")
    st.session_state.setdefault("sources", {})   # name -> source dict
    st.session_state.setdefault("models", {})    # name -> {"model", "meta"}
    return st.session_state


def register_model(name: str, model, meta: dict):
    st.session_state.models[name] = {"model": model, "meta": meta}


def model_options() -> dict:
    return st.session_state.get("models", {})


def source_options() -> dict:
    return st.session_state.get("sources", {})
