"""padpd 桌面工作台入口: python -m gui_qt.main"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui_qt import common  # noqa: E402
from gui_qt.common import apply_theme, set_pref, tr  # noqa: E402
from gui_qt.themes import render_qss  # noqa: E402


def app_icon() -> QIcon:
    """The app icon, resolvable both in-repo and inside a PyInstaller
    bundle (datas map it under ``gui_qt/assets``)."""
    for base in (Path(getattr(sys, "_MEIPASS", ROOT)), ROOT):
        p = base / "gui_qt" / "assets" / "padpd.png"
        if p.exists():
            return QIcon(str(p))
    return QIcon()

PAGES = [
    ("🏠", "总览", "home", "HomePage"),
    ("🌊", "波形工作台", "waveform", "WaveformPage"),
    ("🗂️", "数据管理", "data", "DataPage"),
    ("📈", "PA 建模", "modeling", "ModelingPage"),
    ("🎛️", "DPD 实验室", "dpd", "DpdPage"),
    ("⚖️", "结果比较", "compare", "ComparePage"),
    ("🚀", "部署", "deploy", "DeployPage"),
    ("🧭", "联合设计", "codesign", "CodesignPage"),
    ("📖", "用户手册", "manual", "ManualPage"),
]

LANG_ITEMS = [("zh", "中文"), ("en", "English")]
THEME_ITEMS = [("dark", "深色"), ("light", "浅色")]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1280, 860)

        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        side = QWidget()
        side.setObjectName("sidePanel")
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 8)
        sv.setSpacing(0)
        self.brand = QLabel("📡 padpd")
        self.brand.setObjectName("brand")
        self.sub = QLabel()
        self.sub.setObjectName("brandSub")
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lab_lang = QLabel()
        self.cmb_lang = QComboBox()
        self.lab_theme = QLabel()
        self.cmb_theme = QComboBox()
        sv.addWidget(self.brand)
        sv.addWidget(self.sub)
        sv.addWidget(self.nav, 1)
        sv.addWidget(self.lab_lang)
        sv.addWidget(self.cmb_lang)
        sv.addWidget(self.lab_theme)
        sv.addWidget(self.cmb_theme)

        self.stack = QStackedWidget()
        lay.addWidget(side)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.nav.currentRowChanged.connect(self._switch)
        self.cmb_lang.activated.connect(self._on_lang)
        self.cmb_theme.activated.connect(self._on_theme)
        self._rebuild()

    # ---- language / theme switching --------------------------------
    def _busy_guard(self, cmb, items, pref_key) -> bool:
        """Refuse a page rebuild while worker threads run (rebuilding
        deletes the pages owning them -> hard crash); revert the combo."""
        if common.live_worker_count() == 0:
            return False
        cmb.blockSignals(True)
        cmb.setCurrentIndex(
            [c for c, _ in items].index(common.PREFS[pref_key]))
        cmb.blockSignals(False)
        QMessageBox.information(
            self, "padpd",
            tr("有任务正在运行,请等待完成后再切换语言/主题。"))
        return True

    def _on_lang(self, idx: int):
        code = LANG_ITEMS[idx][0]
        if code != common.PREFS["lang"]:
            if self._busy_guard(self.cmb_lang, LANG_ITEMS, "lang"):
                return
            set_pref("lang", code)
            self._rebuild()

    def _on_theme(self, idx: int):
        code = THEME_ITEMS[idx][0]
        if code != common.PREFS["theme"]:
            if self._busy_guard(self.cmb_theme, THEME_ITEMS, "theme"):
                return
            set_pref("theme", code)
            self._rebuild()

    def closeEvent(self, event):
        if common.live_worker_count() > 0:
            ans = QMessageBox.question(
                self, "padpd",
                tr("有任务正在运行,确定要退出吗?"))
            if ans != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            for w in list(common._LIVE_WORKERS):
                w.terminate()          # app is exiting; abort is worse
                w.wait(2000)
        super().closeEvent(event)

    def _rebuild(self):
        """(Re)build all pages and chrome for the current lang/theme.

        Page texts are fixed at construction, so switching language or
        theme recreates the page instances; data lives in the
        get_state() singleton and survives.
        """
        apply_theme()
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(render_qss(common.PREFS["theme"]))

        self.setWindowTitle(tr("padpd — WiFi 7 PA + DPD 工作台"))
        self.sub.setText(tr("WiFi 7 PA + DPD 工作台"))
        self.lab_lang.setText("Language" if common.PREFS["lang"] == "en"
                              else "语言 / Language")
        self.lab_theme.setText(tr("主题"))
        for cmb, items, cur in ((self.cmb_lang, LANG_ITEMS, "lang"),
                                (self.cmb_theme, THEME_ITEMS, "theme")):
            cmb.blockSignals(True)
            cmb.clear()
            for _code, label in items:
                cmb.addItem(tr(label) if cur == "theme" else label)
            cmb.setCurrentIndex(
                [c for c, _ in items].index(common.PREFS[cur]))
            cmb.blockSignals(False)

        row = max(self.nav.currentRow(), 0)
        self.nav.blockSignals(True)
        self.nav.clear()
        for icon, title, *_ in PAGES:
            self.nav.addItem(f"{icon}  {tr(title)}")
        self.nav.blockSignals(False)

        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
        self._pages = {}
        for _, _, mod, cls in PAGES:
            m = importlib.import_module(f"gui_qt.pages.{mod}")
            page = getattr(m, cls)()
            self._pages[mod] = page
            self.stack.addWidget(page)
        self.nav.setCurrentRow(row)
        self._switch(row)

    def _switch(self, row: int):
        self.stack.setCurrentIndex(row)
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("padpd")
    app.setWindowIcon(app_icon())
    win = MainWindow()
    win.setWindowIcon(app_icon())
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
