"""padpd 桌面工作台入口: python -m gui_qt.main"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel,  # noqa: E402
                               QListWidget, QMainWindow, QStackedWidget,
                               QVBoxLayout, QWidget)

PAGES = [
    ("🏠  总览", "home", "HomePage"),
    ("🌊  波形工作台", "waveform", "WaveformPage"),
    ("🗂️  数据管理", "data", "DataPage"),
    ("📈  PA 建模", "modeling", "ModelingPage"),
    ("🎛️  DPD 实验室", "dpd", "DpdPage"),
    ("⚖️  结果比较", "compare", "ComparePage"),
    ("🚀  部署", "deploy", "DeployPage"),
    ("🧭  联合设计", "codesign", "CodesignPage"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("padpd — WiFi 7 PA + DPD 工作台")
        self.resize(1280, 860)

        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        side = QWidget()
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(0)
        brand = QLabel("📡 padpd")
        brand.setObjectName("brand")
        sub = QLabel("WiFi 7 PA + DPD 工作台")
        sub.setObjectName("brandSub")
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        for title, *_ in PAGES:
            self.nav.addItem(title)
        sv.addWidget(brand)
        sv.addWidget(sub)
        sv.addWidget(self.nav, 1)
        side.setStyleSheet("background:#0a0e18;")

        self.stack = QStackedWidget()
        self._pages = {}
        import importlib
        for _, mod, cls in PAGES:
            m = importlib.import_module(f"gui_qt.pages.{mod}")
            page = getattr(m, cls)()
            self._pages[mod] = page
            self.stack.addWidget(page)

        self.nav.currentRowChanged.connect(self._switch)
        self.nav.setCurrentRow(0)

        lay.addWidget(side)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(central)

    def _switch(self, row: int):
        self.stack.setCurrentIndex(row)
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    qss = Path(__file__).with_name("style.qss")
    app.setStyleSheet(qss.read_text(encoding="utf-8"))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
