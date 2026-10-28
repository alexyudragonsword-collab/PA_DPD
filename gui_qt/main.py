"""padpd desktop workbench: python -m gui_qt.main

The window is a workflow rail on the left, a context bar on top, and one
page at a time. The context bar is what every result is judged against
and computed on - the active source, the workspace's models, the project
spec - so it stays in view instead of living on a settings page.

Language and theme switch in place: pages re-present what they hold, so
a switch never throws a result away (the old window rebuilt every page
and did).
"""

from __future__ import annotations

import sys

from gui_qt import common  # noqa: F401  (sets sys.path before gui_core)
from gui_qt.common import set_pref, tr

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gui_core import experiments  # noqa: E402
from gui_qt.theme import palette, qss  # noqa: E402

# (page id, rail label, rail group). Experiment pages are built from
# gui_core.experiments; the others from gui_qt.pages.
RAIL = [
    ("overview", "总览", ""),
    ("waveform", "波形", "工作流"),
    ("sources", "数据源", "工作流"),
    ("pa_model", "PA 模型", "工作流"),
    ("dpd", "DPD", "工作流"),
    ("deploy", "部署", "工作流"),
    ("gain_modulation", "增益调制", "专题实验"),
    ("adaptive", "自适应跟踪", "专题实验"),
    ("three_loop", "前端三环", "专题实验"),
    ("codesign", "联合设计", "专题实验"),
    ("codesign_grad", "可微联合寻优", "专题实验"),
    ("two_tone", "双音诊断", "专题实验"),
    ("compare", "结果比较", "分析"),
    ("manual", "用户手册", "分析"),
]
PAGES = [r for r in RAIL
         if r[0] not in experiments.EXPERIMENTS
         or experiments.available(experiments.EXPERIMENTS[r[0]])]


class SpecDialog(QDialog):
    """Edit the project spec every verdict is judged against."""

    def __init__(self, spec: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("项目 Spec"))
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.evm = QDoubleSpinBox()
        self.evm.setRange(-80, 0)
        self.evm.setDecimals(1)
        self.evm.setSuffix(" dB")
        self.evm.setValue(spec["evm_db"])
        self.aclr = QDoubleSpinBox()
        self.aclr.setRange(-90, 0)
        self.aclr.setDecimals(1)
        self.aclr.setSuffix(" dBc")
        self.aclr.setValue(spec["aclr_dbc"])
        form.addRow(tr("EVM 上限"), self.evm)
        form.addRow(tr("ACLR 上限"), self.aclr)
        lay.addLayout(form)
        note = QLabel(tr("发射 Mask 固定用 802.11 模板。改动后,已有结果会按"
                         "新 spec 重新判定,不必重跑。"))
        note.setObjectName("help")
        note.setWordWrap(True)
        lay.addWidget(note)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def values(self) -> dict:
        return {"evm_db": self.evm.value(), "aclr_dbc": self.aclr.value()}


def _seg(parent, items, current, on_pick):
    w = QWidget(parent)
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(0)
    group = QButtonGroup(w)
    btns = {}
    for code, text in items:
        b = QPushButton(text)
        b.setObjectName("seg")
        b.setCheckable(True)
        b.setChecked(code == current)
        group.addButton(b)
        b.clicked.connect(lambda _c=False, c=code: on_pick(c))
        h.addWidget(b)
        btns[code] = b
    return w, btns


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1280, 860)
        root = QWidget()
        root.setObjectName("appRoot")
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self._build_bar())
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_rail())
        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)
        v.addLayout(body, 1)
        self.setCentralWidget(root)
        self.pages: dict[str, QWidget] = {}
        self.current = ""
        self._apply_theme()
        self.retranslate()
        self.navigate("overview")

    # ---- chrome --------------------------------------------------------
    def _build_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("bar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 8, 16, 8)
        h.setSpacing(8)
        self.brand = QLabel("padpd")
        self.brand.setObjectName("brand")
        self.brand_sub = QLabel()
        self.brand_sub.setObjectName("brandSub")
        h.addWidget(self.brand)
        h.addWidget(self.brand_sub)
        h.addSpacing(12)
        self.chip_source = QToolButton()
        self.chip_source.setObjectName("chip")
        self.chip_source.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_source = QMenu(self.chip_source)
        self.menu_source.aboutToShow.connect(self._fill_source_menu)
        self.chip_source.setMenu(self.menu_source)
        self.chip_models = QToolButton()
        self.chip_models.setObjectName("chip")
        self.chip_models.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_models = QMenu(self.chip_models)
        self.menu_models.aboutToShow.connect(self._fill_model_menu)
        self.chip_models.setMenu(self.menu_models)
        self.chip_spec = QToolButton()
        self.chip_spec.setObjectName("chip")
        self.chip_spec.clicked.connect(self.edit_spec)
        for c in (self.chip_source, self.chip_models, self.chip_spec):
            c.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            h.addWidget(c)
        h.addStretch(1)
        lang_w, self.lang_btns = _seg(bar, [("zh", "中文"), ("en", "EN")],
                                      common.PREFS["lang"], self.set_lang)
        theme_w, self.theme_btns = _seg(bar, [("light", ""), ("dark", "")],
                                        common.PREFS["theme"],
                                        self.set_theme)
        h.addWidget(theme_w)
        h.addSpacing(6)
        h.addWidget(lang_w)
        return bar

    def _build_rail(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("rail")
        rail.setFixedWidth(188)
        lay = QVBoxLayout(rail)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(1)
        self.rail_group = QButtonGroup(rail)
        self.rail_group.setExclusive(True)
        self.rail_btns: dict[str, QPushButton] = {}
        self.rail_heads: list[tuple[QLabel, str]] = []
        group = None
        for pid, _title, g in PAGES:
            if g and g != group:
                group = g
                head = QLabel()
                head.setObjectName("railHead")
                lay.addWidget(head)
                self.rail_heads.append((head, g))
            b = QPushButton()
            b.setObjectName("railItem")
            b.setCheckable(True)
            b.clicked.connect(lambda _c=False, p=pid: self.navigate(p))
            self.rail_group.addButton(b)
            self.rail_btns[pid] = b
            lay.addWidget(b)
        lay.addStretch(1)
        scroll = QScrollArea()
        scroll.setObjectName("rail")
        scroll.setWidget(rail)
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(188)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return scroll

    # ---- pages ---------------------------------------------------------
    def page(self, pid: str) -> QWidget:
        """The page, built on first use."""
        if pid in self.pages:
            return self.pages[pid]
        from gui_qt import pages
        if pid in experiments.EXPERIMENTS:
            from gui_qt.experiment_page import ExperimentPage
            p = ExperimentPage(experiments.EXPERIMENTS[pid])
            p.ran.connect(lambda _o: self.workspace_changed())
            p.open_compare.connect(self.open_compare)
            if pid == "pa_model":
                panel = pages.ModelsPanel()
                panel.edited.connect(self.workspace_changed)
                p.add_footer(panel)
        else:
            p = {"overview": pages.OverviewPage, "sources": pages.SourcesPage,
                 "compare": pages.ComparePage,
                 "manual": pages.ManualPage}[pid]()
            if hasattr(p, "navigate"):
                p.navigate.connect(self.navigate)
            p.workspace_edited.connect(self.workspace_changed)
        self.pages[pid] = p
        self.stack.addWidget(p)
        return p

    def navigate(self, pid: str):
        p = self.page(pid)
        self.stack.setCurrentWidget(p)
        self.rail_btns[pid].setChecked(True)
        self.current = pid

    def open_compare(self, kind: str):
        self.navigate("compare")
        self.pages["compare"].focus(kind)

    def workspace_changed(self):
        """Sources, models or spec changed: refresh the bar and every built
        page (experiment pages re-judge stored results)."""
        self._update_chips()
        for p in self.pages.values():
            p.workspace_changed()

    # ---- context bar ---------------------------------------------------
    def _update_chips(self):
        ws = common.state().workspace
        name = ws.active_source or "—"
        short = name if len(name) <= 46 else name[:44] + "…"
        self.chip_source.setText(f"{tr('数据源')}  {short}")
        self.chip_source.setToolTip(name)
        n = len(ws.models)
        self.chip_models.setText(f"{tr('PA 模型')}  {n}")
        sp = ws.spec
        self.chip_spec.setText(f"Spec  EVM ≤ {sp['evm_db']:g} dB · "
                               f"ACLR ≤ {sp['aclr_dbc']:g} dBc")
        self.chip_spec.setToolTip(tr("点击修改项目 Spec"))

    def _fill_source_menu(self):
        ws = common.state().workspace
        m = self.menu_source
        m.clear()
        for name in ws.sources:
            a = m.addAction(name)
            a.setCheckable(True)
            a.setChecked(name == ws.active_source)
            a.triggered.connect(lambda _c=False, n=name: self.set_source(n))
        m.addSeparator()
        m.addAction(tr("管理数据源…")).triggered.connect(
            lambda: self.navigate("sources"))

    def _fill_model_menu(self):
        ws = common.state().workspace
        m = self.menu_models
        m.clear()
        for name, e in reversed(list(ws.models.items())):
            nm = e.metrics.get("nmse_db")
            a = m.addAction(name + (f"   {nm:.1f} dB"
                                    if isinstance(nm, (int, float)) else ""))
            a.setEnabled(False)
        if not ws.models:
            m.addAction(tr("还没有模型")).setEnabled(False)
        m.addSeparator()
        m.addAction(tr("拟合新模型…")).triggered.connect(
            lambda: self.navigate("pa_model"))

    def set_source(self, name: str):
        common.state().workspace.set_active(name)
        self.workspace_changed()

    def edit_spec(self):
        ws = common.state().workspace
        dlg = SpecDialog(ws.spec, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            ws.set_spec(**dlg.values())
            self.workspace_changed()

    # ---- language / theme ------------------------------------------------
    def set_lang(self, code: str):
        if code == common.PREFS["lang"]:
            return
        set_pref("lang", code)
        self.retranslate()
        for p in self.pages.values():
            p.retranslate()

    def set_theme(self, code: str):
        if code == common.PREFS["theme"]:
            return
        set_pref("theme", code)
        self._apply_theme()
        for p in self.pages.values():
            p.restyle()

    def _apply_theme(self):
        app = QApplication.instance()
        if app is not None:
            app.setPalette(palette(common.PREFS["theme"]))
            app.setStyleSheet(qss(common.PREFS["theme"]))
        self.theme_btns[common.PREFS["theme"]].setChecked(True)

    def retranslate(self):
        self.setWindowTitle(tr("padpd — WiFi 7 PA + DPD 工作台"))
        self.brand_sub.setText(tr("PA + DPD 工作台"))
        self.lang_btns[common.PREFS["lang"]].setChecked(True)
        self.theme_btns["light"].setText(tr("浅色"))
        self.theme_btns["dark"].setText(tr("深色"))
        for head, g in self.rail_heads:
            head.setText(tr(g).upper())
        for pid, title, _g in PAGES:
            self.rail_btns[pid].setText(tr(title))
        self._update_chips()

    def closeEvent(self, event):                         # noqa: N802
        if common.live_worker_count() > 0:
            ans = QMessageBox.question(
                self, "padpd", tr("有任务正在运行,确定要退出吗?"))
            if ans != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            for w in list(common._LIVE_WORKERS):
                w.terminate()          # app is exiting; abort is worse
                w.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("padpd")
    app.setWindowIcon(common.app_icon())
    win = MainWindow()
    win.setWindowIcon(common.app_icon())
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
