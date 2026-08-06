"""Shared GUI preferences (language / theme), persisted next to gui_runs.

Both the Streamlit and the Qt GUI read this at startup and write it on
every switch, so the choice carries across sessions and across GUIs.
"""

from __future__ import annotations

import json
from pathlib import Path

from .paths import user_data_dir

PREFS_PATH = user_data_dir() / "gui_prefs.json"

DEFAULTS = {"lang": "zh", "theme": "dark"}


def load_prefs(path: Path | None = None) -> dict:
    p = Path(path) if path else PREFS_PATH
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    out = dict(DEFAULTS)
    for k in DEFAULTS:
        v = data.get(k)
        if isinstance(v, str):
            out[k] = v
    if out["lang"] not in ("zh", "en"):
        out["lang"] = "zh"
    if out["theme"] not in ("dark", "light"):
        out["theme"] = "dark"
    return out


def save_prefs(prefs: dict, path: Path | None = None) -> None:
    p = Path(path) if path else PREFS_PATH
    keep = {k: prefs.get(k, DEFAULTS[k]) for k in DEFAULTS}
    p.write_text(json.dumps(keep, indent=1), encoding="utf-8")
