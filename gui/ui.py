"""Shared UI helpers for the Streamlit workbench: CSS, cards, state."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

ACCENT = "#e4574c"
BLUE = "#4f8ff7"
GREEN = "#37c978"
AMBER = "#e5b567"

_CSS = f"""
<style>
/* layout polish */
.block-container {{ padding-top: 2.2rem; max-width: 1200px; }}
h1, h2, h3 {{ letter-spacing: .3px; }}
h1 {{ font-size: 1.65rem !important; }}
h2 {{ font-size: 1.2rem !important; }}

/* metric cards */
div[data-testid="stMetric"] {{
  background: linear-gradient(160deg, #1a2234 0%, #141a29 100%);
  border: 1px solid #26304a;
  border-radius: 12px;
  padding: 14px 16px 10px 16px;
}}
div[data-testid="stMetric"] label {{ color: #9aa4bd !important; }}
div[data-testid="stMetricValue"] {{
  font-variant-numeric: tabular-nums;
}}

/* badges */
.badge {{
  display: inline-block; padding: 2px 10px; border-radius: 999px;
  font-size: .74rem; font-weight: 600; letter-spacing: .4px;
  margin-right: 6px;
}}
.badge-ok   {{ background: #12351f; color: {GREEN}; border: 1px solid #1d5a33; }}
.badge-fail {{ background: #3a1720; color: {ACCENT}; border: 1px solid #6b2733; }}
.badge-info {{ background: #14263f; color: {BLUE};  border: 1px solid #23446e; }}

/* sidebar brand */
.brand-title {{ font-size: 1.12rem; font-weight: 700; margin-bottom: 0; }}
.brand-sub   {{ font-size: .74rem; color: #8a94ad; margin-top: 2px; }}

/* section divider card */
.section-note {{
  border-left: 3px solid {BLUE}; background: #131a2a;
  padding: 8px 14px; border-radius: 6px; color: #aeb7cc;
  font-size: .86rem; margin: 4px 0 12px 0;
}}
</style>
"""


def page_setup(title: str, icon: str = ""):
    """Per-page boilerplate: CSS + header."""
    st.markdown(_CSS, unsafe_allow_html=True)
    st.title(f"{icon} {title}".strip())


def note(text: str):
    st.markdown(f'<div class="section-note">{text}</div>',
                unsafe_allow_html=True)


def badge(text: str, kind: str = "info") -> str:
    return f'<span class="badge badge-{kind}">{text}</span>'


def get_state():
    """Central session objects (created lazily)."""
    from gui_core import RunStore
    if "runstore" not in st.session_state:
        st.session_state.runstore = RunStore(ROOT / "gui_runs")
    st.session_state.setdefault("sources", {})   # name -> source dict
    st.session_state.setdefault("models", {})    # name -> {"model", "meta"}
    return st.session_state


def register_model(name: str, model, meta: dict):
    st.session_state.models[name] = {"model": model, "meta": meta}


def model_options() -> dict:
    return st.session_state.get("models", {})


def source_options() -> dict:
    return st.session_state.get("sources", {})
