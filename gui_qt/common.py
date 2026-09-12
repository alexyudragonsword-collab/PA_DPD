"""Shared Qt widgets/helpers: app state, metric cards, figure pane, workers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import matplotlib  # noqa: E402

matplotlib.use("Agg")  # canvases render via FigureCanvasQTAgg explicitly

from matplotlib.backends.backend_qtagg import (  # noqa: E402
    FigureCanvasQTAgg)
from PySide6.QtCore import Qt, QThread, Signal  # noqa: E402
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QScrollArea,  # noqa: E402
                               QVBoxLayout, QWidget)

from gui_core import i18n  # noqa: E402
from gui_core.prefs import load_prefs, save_prefs  # noqa: E402
from gui_qt.themes import MPL_CYCLE, MPL_RC  # noqa: E402

PREFS = load_prefs()


def tr(s: str) -> str:
    """Translate a UI string to the current language."""
    return i18n.tr(s, PREFS["lang"])


def set_pref(key: str, value: str) -> None:
    PREFS[key] = value
    save_prefs(PREFS)


def _cjk_fonts() -> list[str]:
    """CJK-capable fonts installed on this machine, preferred order.

    Listed BEFORE DejaVu: matplotlib's per-glyph fallback does not reach
    fonts inside .ttc collections, so the CJK font must be primary.
    """
    from matplotlib import font_manager
    installed = {f.name for f in font_manager.fontManager.ttflist}
    prefer = ["Microsoft YaHei", "Noto Sans CJK SC", "PingFang SC",
              "WenQuanYi Zen Hei", "Source Han Sans SC", "SimHei"]
    return [n for n in prefer if n in installed]


_FONT_RC = {
    "font.family": "sans-serif",
    "font.sans-serif": _cjk_fonts() + ["DejaVu Sans"],
    "axes.unicode_minus": False,
}


def theme_rc(theme: str) -> dict:
    return {**_FONT_RC, **MPL_RC[theme],
            "axes.prop_cycle": matplotlib.cycler(color=MPL_CYCLE[theme])}


def current_rc() -> dict:
    return theme_rc(PREFS["theme"])


def apply_theme() -> None:
    """Install the current theme's rc globally.

    Text font resolution happens at canvas draw time (outside any
    rc_context), so the theme must live in the global rcParams.
    """
    matplotlib.rcParams.update(current_rc())


# backward-compatible alias (tests and older callers)
DARK_RC = theme_rc("dark")

apply_theme()


def get_state():
    """Singleton app state shared by all pages (same stores as web GUI)."""
    global _STATE
    try:
        return _STATE
    except NameError:
        from gui_core import RunStore
        from gui_core.paths import user_data_dir
        _STATE = type("S", (), {})()
        _STATE.runstore = RunStore(user_data_dir() / "gui_runs")
        _STATE.sources = {}
        _STATE.models = {}
        return _STATE


class MetricCard(QFrame):
    def __init__(self, label: str, value: str = "—", delta: str = ""):
        super().__init__()
        self.setProperty("class", "card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        self.lab = QLabel(label)
        self.lab.setProperty("class", "cardLabel")
        self.val = QLabel(value)
        self.val.setProperty("class", "cardValue")
        self.dlt = QLabel(delta)
        self.dlt.setProperty("class", "cardDelta")
        for w in (self.lab, self.val, self.dlt):
            lay.addWidget(w)

    def set(self, value: str, delta: str = ""):
        self.val.setText(value)
        self.dlt.setText(delta)


def card_row(cards: list[MetricCard]) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    for c in cards:
        lay.addWidget(c)
    return w


class FigurePane(QScrollArea):
    """Swappable matplotlib canvas area."""

    def __init__(self, min_height: int = 380):
        super().__init__()
        self.setWidgetResizable(True)
        self.setMinimumHeight(min_height)
        self._canvas = None
        self._holder = QWidget()
        self._lay = QVBoxLayout(self._holder)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self.setWidget(self._holder)

    def set_figure(self, fig):
        with matplotlib.rc_context(DARK_RC):
            pass  # figures are already styled by caller context
        if self._canvas is not None:
            self._lay.removeWidget(self._canvas)
            self._canvas.deleteLater()
        self._canvas = FigureCanvasQTAgg(fig)
        self._canvas.setMinimumHeight(self.minimumHeight() - 10)
        self._lay.addWidget(self._canvas)
        self._canvas.draw()


# live FnWorker registry: pages get destroyed on language/theme switches,
# and destroying a running QThread aborts the process — the main window
# consults this to refuse a rebuild/close while work is in flight
_LIVE_WORKERS: set = set()


def live_worker_count() -> int:
    return len(_LIVE_WORKERS)


class FnWorker(QThread):
    """Run a callable in a thread; forward progress dicts + result."""

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
                lambda info: self.progress.emit(info)), **self._kwargs))
        # surfaced to the UI, not swallowed
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


def page_scaffold(title: str, note: str) -> tuple[QWidget, QVBoxLayout]:
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(22, 16, 22, 16)
    lay.setSpacing(10)
    t = QLabel(title)
    t.setObjectName("pageTitle")
    n = QLabel(note)
    n.setObjectName("note")
    n.setWordWrap(True)
    lay.addWidget(t)
    lay.addWidget(n)
    return page, lay


def dark_fig(builder, *args, **kwargs):
    """Build a padpd.plotting figure under the dark rc context."""
    with matplotlib.rc_context(DARK_RC):
        return builder(*args, **kwargs)


def hline(items: list[QWidget]) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    for it in items:
        lay.addWidget(it)
    lay.addStretch(1)
    return w


ALIGN_TOP = Qt.AlignmentFlag.AlignTop
