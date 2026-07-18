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


DARK_RC = {
    "font.family": "sans-serif",
    "font.sans-serif": _cjk_fonts() + ["DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.facecolor": "#121828", "axes.facecolor": "#121828",
    "savefig.facecolor": "#121828", "axes.edgecolor": "#232c42",
    "grid.color": "#232c42", "text.color": "#dfe4ef",
    "axes.labelcolor": "#dfe4ef", "xtick.color": "#9aa4bd",
    "ytick.color": "#9aa4bd", "legend.facecolor": "#171e2e",
    "legend.edgecolor": "#26304a",
    "axes.prop_cycle": matplotlib.cycler(
        color=["#4f8ff7", "#e4574c", "#37c978", "#e5b567", "#b07cf7"]),
}

# Text font resolution happens at canvas draw time (outside any rc_context),
# so the theme must also be installed globally for the Qt app.
matplotlib.rcParams.update(DARK_RC)


def get_state():
    """Singleton app state shared by all pages (same stores as web GUI)."""
    global _STATE
    try:
        return _STATE
    except NameError:
        from gui_core import RunStore
        _STATE = type("S", (), {})()
        _STATE.runstore = RunStore(ROOT / "gui_runs")
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


class FnWorker(QThread):
    """Run a callable in a thread; forward progress dicts + result."""

    progress = Signal(dict)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn, self._args, self._kwargs = fn, args, kwargs

    def run(self):
        try:
            self.done.emit(self._fn(*self._args, on_progress=(
                lambda info: self.progress.emit(info)), **self._kwargs))
        except Exception as e:  # surfaced to the UI, not swallowed
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
