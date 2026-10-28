"""Shared desktop state: preferences, the workspace, the worker thread.

Nothing here draws. The window, the pages and the tests all reach the
workspace and the run registry through ``state()``, so a test can point
them at a temporary directory before the window exists.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from PySide6.QtCore import QThread, Signal  # noqa: E402

from gui_core import i18n  # noqa: E402
from gui_core.prefs import load_prefs, save_prefs  # noqa: E402

PREFS = load_prefs()


def tr(s: str) -> str:
    """Translate a UI string to the current language."""
    return i18n.tr(s, PREFS["lang"])


def set_pref(key: str, value: str) -> None:
    PREFS[key] = value
    save_prefs(PREFS)


class _State:
    """The workspace (sources, models, spec) and the run registry."""

    def __init__(self, root: Path | None = None):
        from gui_core.paths import user_data_dir
        from gui_core.runstore import RunStore
        from gui_core.workspace import Workspace
        base = Path(root) if root else user_data_dir()
        self.workspace = Workspace(base / "workspace")
        self.runstore = RunStore(base / "gui_runs")


_STATE: _State | None = None


def state() -> _State:
    global _STATE
    if _STATE is None:
        _STATE = _State()
    return _STATE


def reset_state(root: Path) -> _State:
    """Point the app at another data directory (tests)."""
    global _STATE
    _STATE = _State(root)
    return _STATE


def app_icon():
    """The app icon, resolvable both in-repo and inside a frozen bundle
    (the spec maps it under ``gui_qt/assets``)."""
    from PySide6.QtGui import QIcon
    for base in (Path(getattr(sys, "_MEIPASS", ROOT)), ROOT):
        p = base / "gui_qt" / "assets" / "padpd.png"
        if p.exists():
            return QIcon(str(p))
    return QIcon()


# Live FnWorker registry. Closing the window while a QThread runs aborts
# the process, so closeEvent consults this first. Language and theme
# switches no longer rebuild pages, so they no longer need to.
_LIVE_WORKERS: set = set()


def live_worker_count() -> int:
    return len(_LIVE_WORKERS)


class FnWorker(QThread):
    """Run a callable in a thread; forward progress dicts and the result.

    The callable receives ``on_progress``. Read widget values on the GUI
    thread *before* starting one and close over the snapshot: a widget
    touched from this thread is undefined behaviour in Qt.
    """

    progress = Signal(dict)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn, self._args, self._kwargs = fn, args, kwargs
        self.finished.connect(lambda: _LIVE_WORKERS.discard(self))

    def start(self, *a, **kw):
        _LIVE_WORKERS.add(self)
        super().start(*a, **kw)

    def run(self):
        try:
            self.done.emit(self._fn(*self._args, on_progress=(
                lambda info: self.progress.emit(dict(info))), **self._kwargs))
        # surfaced to the UI, not swallowed
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"{type(e).__name__}: {e}")
