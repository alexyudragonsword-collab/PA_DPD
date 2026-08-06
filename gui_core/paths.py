"""Where the GUIs persist user data (prefs, run registry).

In a source checkout this is the repo root — unchanged dev behavior.
In a frozen app it must NOT be: PyInstaller's ROOT is the read-only
install dir (PermissionError under Program Files) and a Nuitka onefile
extracts to a fresh %TEMP% dir every launch, silently discarding
anything written there. Frozen builds therefore use a per-user data
directory. PADPD_DATA_DIR overrides everything (tests, portable mode).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)          # PyInstaller
                or globals().get("__compiled__"))      # Nuitka


def user_data_dir() -> Path:
    env = os.environ.get("PADPD_DATA_DIR", "").strip()
    if env:
        p = Path(env)
    elif not _is_frozen():
        p = REPO_ROOT
    elif sys.platform == "win32":
        p = Path(os.environ.get("APPDATA",
                                Path.home() / "AppData" / "Roaming")) / "padpd"
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / "padpd"
    else:
        p = Path(os.environ.get("XDG_DATA_HOME",
                                Path.home() / ".local" / "share")) / "padpd"
    p.mkdir(parents=True, exist_ok=True)
    return p
