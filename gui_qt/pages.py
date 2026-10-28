"""The pages that are not experiments: overview, sources, compare, manual,
and the workspace-models panel under the PA model page."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from gui_core import experiments, manual
from gui_qt import common
from gui_qt.common import FnWorker, tr
from gui_qt.experiment_page import (
    SETUP_WIDTH,
    ResultsView,
    clear_layout,
    label,
    make_table,
)
from gui_qt.form import ParamForm
from gui_qt.theme import SERIES, TOKENS


def _scroll(w: QWidget) -> QScrollArea:
    s = QScrollArea()
    s.setWidgetResizable(True)
    s.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    s.setFrameShape(QFrame.Shape.NoFrame)
    s.setWidget(w)
    return s


class _Page(QWidget):
    """Title, summary, and a setup | content body."""

    workspace_edited = Signal()

    def __init__(self, title: str, summary: str, setup: bool = True):
        super().__init__()
        self.setObjectName("page")
        self._title_key, self._summary_key = title, summary
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 18, 24, 12)
        outer.setSpacing(4)
        self.title = label("", "pageTitle", wrap=False)
        self.summary = label("", "summary")
        outer.addWidget(self.title)
        outer.addWidget(self.summary)
        outer.addSpacing(8)
        body = QHBoxLayout()
        body.setSpacing(16)
        outer.addLayout(body, 1)
        if setup:
            self.setup = QFrame()
            self.setup.setObjectName("setup")
            self.setup.setFixedWidth(SETUP_WIDTH)
            self.setup_lay = QVBoxLayout(self.setup)
            self.setup_lay.setContentsMargins(14, 12, 14, 12)
            self.setup_lay.setSpacing(8)
            body.addWidget(self.setup, 0)
        self.content = QWidget()
        self.content_lay = QVBoxLayout(self.content)
        self.content_lay.setContentsMargins(0, 0, 6, 0)
        self.content_lay.setSpacing(12)
        body.addWidget(_scroll(self.content), 1)

    def retranslate(self):
        self.title.setText(tr(self._title_key))
        self.summary.setText(tr(self._summary_key))

    def restyle(self):
        pass

    def workspace_changed(self):
        pass


# ---------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------


class SourcesPage(_Page):
    """The workspace's sources: add, pick the active one, inspect."""

    def __init__(self):
        super().__init__("数据源",
                         "工作区里的数据源。每个实验都在当前数据源上运行;"
                         "数据源以引用保存(合成参数或文件路径),重启后仍在。")
        sl = self.setup_lay
        self.h_list = label("", "groupHead")
        sl.addWidget(self.h_list)
        self.list = QListWidget()
        self.list.setMinimumHeight(120)
        self.list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.list.currentRowChanged.connect(lambda _r: self.preview())
        self.list.itemDoubleClicked.connect(lambda _i: self.activate())
        sl.addWidget(self.list)
        row = QHBoxLayout()
        self.btn_active = QPushButton()
        self.btn_active.clicked.connect(self.activate)
        self.btn_rm = QPushButton()
        self.btn_rm.clicked.connect(self.remove)
        row.addWidget(self.btn_active, 1)
        row.addWidget(self.btn_rm)
        sl.addLayout(row)

        more = QWidget()
        ml = QVBoxLayout(more)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(8)
        self.h_synth = label("", "groupHead")
        ml.addWidget(self.h_synth)
        self.synth = ParamForm(experiments.SYNTHETIC_SOURCE,
                               lambda: experiments.Context(
                                   common.state().workspace))
        ml.addWidget(self.synth)
        self.btn_synth = QPushButton()
        self.btn_synth.clicked.connect(self.add_synthetic)
        ml.addWidget(self.btn_synth)

        self.h_file = label("", "groupHead")
        ml.addWidget(self.h_file)
        self.btn_file = QPushButton()
        self.btn_file.clicked.connect(self.add_file)
        ml.addWidget(self.btn_file)
        self.align = QCheckBox()
        ml.addWidget(self.align)
        self.btn_example = QPushButton()
        self.btn_example.clicked.connect(self.add_example)
        ml.addWidget(self.btn_example)
        self.l_od = label("", "fieldLabel")
        ml.addWidget(self.l_od)
        odr = QHBoxLayout()
        from gui_core import services
        self.od_root = QLineEdit(services.default_opendpd_dir())
        self.btn_od_browse = QPushButton()
        self.btn_od_browse.clicked.connect(self.browse_opendpd)
        odr.addWidget(self.od_root, 1)
        odr.addWidget(self.btn_od_browse)
        ml.addLayout(odr)
        odr2 = QHBoxLayout()
        self.od_ds = QComboBox()
        self.btn_od_load = QPushButton()
        self.btn_od_load.clicked.connect(self.add_opendpd)
        odr2.addWidget(self.od_ds, 1)
        odr2.addWidget(self.btn_od_load)
        ml.addLayout(odr2)
        ml.addStretch(1)
        sl.addWidget(_scroll(more), 1)
        self.msg = label("", "help")
        sl.addWidget(self.msg)

        self.view = ResultsView()
        self.content_lay.addWidget(self.view)
        self.consume_row = QHBoxLayout()
        self.btn_consume = QPushButton()
        self.btn_consume.clicked.connect(self.consume)
        self.consume_msg = label("", "note")
        self.consume_row.addWidget(self.btn_consume)
        self.consume_row.addWidget(self.consume_msg, 1)
        self.content_lay.addLayout(self.consume_row)
        self.content_lay.addStretch(1)
        self._worker = None
        self.retranslate()
        self.refresh_list()
        self.scan_opendpd()

    # ---- list --------------------------------------------------------
    def refresh_list(self):
        ws = common.state().workspace
        cur = self._selected() or ws.active_source
        self.list.blockSignals(True)
        self.list.clear()
        for name, e in ws.sources.items():
            kind = tr("合成") if e.synthetic else tr("实测")
            mark = "● " if name == ws.active_source else "   "
            it = QListWidgetItem(f"{mark}{name}  · {kind}")
            it.setData(Qt.ItemDataRole.UserRole, name)
            it.setToolTip(name if e.synthetic else e.ref.get("path", ""))
            self.list.addItem(it)
            if name == cur:
                self.list.setCurrentItem(it)
        self.list.blockSignals(False)
        self.preview()

    def _selected(self) -> str:
        it = self.list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else ""

    def activate(self):
        name = self._selected()
        if name:
            common.state().workspace.set_active(name)
            self.refresh_list()
            self.workspace_edited.emit()

    def remove(self):
        name = self._selected()
        ws = common.state().workspace
        if name and len(ws.sources) > 1:
            ws.remove_source(name)
            self.refresh_list()
            self.workspace_edited.emit()
        elif name:
            self.msg.setText(tr("至少保留一个数据源"))

    # ---- adding ------------------------------------------------------
    def _add(self, fn, *args):
        if self._worker is not None:
            return
        self.msg.setText(tr("载入中…"))
        for b in (self.btn_synth, self.btn_file, self.btn_example,
                  self.btn_od_load):
            b.setEnabled(False)

        def job(on_progress=None):
            return fn(*args)

        self._worker = FnWorker(job)
        self._worker.done.connect(self._added)
        self._worker.failed.connect(self._add_failed)
        self._worker.start()

    def _settle(self):
        self._worker = None
        for b in (self.btn_synth, self.btn_file, self.btn_example,
                  self.btn_od_load):
            b.setEnabled(True)

    def _added(self, name):
        self._settle()
        self.msg.setText(tr("✅ 已注册:{name}").format(name=name))
        self.list.blockSignals(True)
        self.list.clearSelection()
        self.list.setCurrentRow(-1)
        self.list.blockSignals(False)
        self.refresh_list()
        self.workspace_edited.emit()

    def _add_failed(self, e):
        self._settle()
        self.msg.setText(tr("❌ 加载失败:{e}").format(e=e))

    def wait(self, timeout_ms: int = 120000) -> bool:
        w = self._worker
        return True if w is None else w.wait(timeout_ms)

    def add_synthetic(self):
        params = experiments.synthetic_source_params(self.synth.values())
        self._add(common.state().workspace.add_synthetic, params)

    def add_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("打开数据文件"), "",
            tr("数据 (*.csv *.mat *.npz);;全部 (*)"))
        if path:
            self.add_path(path)

    def add_path(self, path: str):
        from gui_core.screens import SOURCE_KINDS
        kind = SOURCE_KINDS.get(Path(path).suffix.lower())
        if kind is None:
            self.msg.setText(tr("不支持的文件类型:{suffix}").format(
                suffix=Path(path).suffix or "?"))
            return
        self._add(common.state().workspace.add_file, kind, path,
                  self.align.isChecked())

    def add_example(self):
        from gui_core import services
        self._add(common.state().workspace.add_file, "npz",
                  services.EXAMPLE_COMPLETE_NPZ)

    def browse_opendpd(self):
        path = QFileDialog.getExistingDirectory(
            self, tr("选择 OpenDPD 的 datasets 目录"), self.od_root.text())
        if path:
            self.od_root.setText(path)
            self.scan_opendpd()

    def scan_opendpd(self):
        self.od_ds.clear()
        root = Path(self.od_root.text())
        names = sorted(p.name for p in root.iterdir()
                       if (p / "spec.json").exists()) if root.is_dir() else []
        self.od_ds.addItems(names)
        self.od_ds.setEnabled(bool(names))
        self.btn_od_load.setEnabled(bool(names))
        self.od_ds.setPlaceholderText(tr("未找到数据集"))

    def add_opendpd(self):
        name = self.od_ds.currentText()
        if name:
            self._add(common.state().workspace.add_file, "opendpd",
                      str(Path(self.od_root.text()) / name))

    # ---- preview -----------------------------------------------------
    def preview(self):
        from gui_core import screens
        name = self._selected()
        ws = common.state().workspace
        if not name or name not in ws.sources:
            self.view.show_empty(tr("选择左侧的数据源查看"))
            self.btn_consume.hide()
            self.consume_msg.setText("")
            return
        try:
            src = ws.source(name)
        except Exception as e:                           # noqa: BLE001
            self.view.show_empty(tr("❌ 加载失败:{e}").format(e=e))
            self.btn_consume.hide()
            return
        lang = common.PREFS["lang"]
        metrics, charts, rows, notes = screens.present_source(src, lang)
        shown = {"verdicts": [], "metrics": metrics, "charts": charts,
                 "rows": [{tr("采集组"): r["group"], tr("存在"): r["present"],
                           tr("样本数"): r["n"]} for r in rows],
                 "notes": notes, "callout": ""}
        if name == ws.active_source:
            shown["notes"] = [tr("这是当前数据源。")] + notes
        self.view.render(shown, {"psd": "频谱:输入 vs 输出",
                                 "amam": "AM-AM / AM-PM"},
                         lang, common.PREFS["theme"])
        self.btn_consume.setVisible(bool(src.get("extras")))

    def consume(self):
        from gui_core import screens, services
        name = self._selected()
        src = common.state().workspace.source(name)
        lang = common.PREFS["lang"]
        self.btn_consume.setEnabled(False)
        self.consume_msg.setText(tr("完整源工具运行中…"))

        def job(on_progress=None):
            return screens.consume_summary(
                services.consume_source_extras(src), lang)

        self._cw = FnWorker(job)
        self._cw.done.connect(lambda s: (self.consume_msg.setText(s),
                                         self.btn_consume.setEnabled(True)))
        self._cw.failed.connect(lambda e: (self.consume_msg.setText(
            "✗ " + e), self.btn_consume.setEnabled(True)))
        self._cw.start()

    # ---- switches ----------------------------------------------------
    def retranslate(self):
        super().retranslate()
        self.h_list.setText(tr("工作区数据源").upper())
        self.btn_active.setText(tr("设为当前"))
        self.btn_rm.setText(tr("移除"))
        self.h_synth.setText(tr("新建合成源").upper())
        self.synth.retranslate()
        self.btn_synth.setText(tr("添加合成源"))
        self.h_file.setText(tr("导入实测").upper())
        self.btn_file.setText(tr("打开文件 (CSV/.mat/.npz)…"))
        self.align.setText(tr("自动延迟对齐"))
        self.btn_example.setText(tr("载入完整源示例"))
        self.btn_example.setToolTip(
            tr("examples/complete_source_demo.npz:含 burst/step/cal_rx/"
               "atten/operating_points 五个采集组"))
        self.l_od.setText(tr("OpenDPD 目录"))
        self.btn_od_browse.setText(tr("浏览…"))
        self.btn_od_load.setText(tr("加载数据集"))
        self.btn_consume.setText(tr("运行完整源工具"))
        if hasattr(self, "view"):
            self.refresh_list()

    def restyle(self):
        self.preview()

    def workspace_changed(self):
        self.refresh_list()


# ---------------------------------------------------------------------
# workspace models (footer of the PA model page)
# ---------------------------------------------------------------------


class ModelsPanel(QFrame):
    """The workspace's fitted models with their lineage."""

    edited = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(12, 10, 12, 10)
        head = QHBoxLayout()
        self.head = label("", "groupHead", wrap=False)
        self.btn_rm = QPushButton()
        self.btn_rm.clicked.connect(self.remove)
        head.addWidget(self.head, 1)
        head.addWidget(self.btn_rm)
        self.lay.addLayout(head)
        self.list = QListWidget()
        self.list.setMaximumHeight(170)
        self.lay.addWidget(self.list)
        self.retranslate()

    def refresh(self):
        ws = common.state().workspace
        self.list.clear()
        for name, e in reversed(list(ws.models.items())):
            nmse = e.metrics.get("nmse_db")
            bits = [e.label, e.source]
            if isinstance(nmse, (int, float)):
                bits.append(f"NMSE {nmse:.2f} dB")
            if e.run_id:
                bits.append(f"run {e.run_id}")
            bits.append(tr("已保存") if e.persisted else tr("仅本次会话"))
            it = QListWidgetItem(" · ".join(bits))
            it.setData(Qt.ItemDataRole.UserRole, name)
            self.list.addItem(it)
        if not ws.models:
            self.list.addItem(tr("还没有模型。拟合的模型会保存在这里,"
                                 "供 DPD 评估和部署使用。"))
        self.btn_rm.setEnabled(bool(ws.models))

    def remove(self):
        it = self.list.currentItem()
        name = it.data(Qt.ItemDataRole.UserRole) if it else None
        if name:
            common.state().workspace.remove_model(name)
            self.refresh()
            self.edited.emit()

    def retranslate(self):
        self.head.setText(tr("工作区中的模型").upper())
        self.btn_rm.setText(tr("删除所选"))
        self.refresh()


# ---------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------


class ComparePage(_Page):
    """Runs of one kind side by side, with what differs between them."""

    def __init__(self):
        super().__init__("结果比较",
                         "同一类运行并排比较:指标,以及产生差异的输入。"
                         "每次运行都记在这里,重启后仍在。")
        sl = self.setup_lay
        self.h_kind = label("", "groupHead")
        sl.addWidget(self.h_kind)
        kr = QHBoxLayout()
        kr.setSpacing(0)
        self.kind_group = QButtonGroup(self)
        self.kind_btns = {}
        for i, k in enumerate(experiments.KIND_LABELS):
            b = QPushButton()
            b.setObjectName("seg")
            b.setCheckable(True)
            self.kind_group.addButton(b, i)
            self.kind_btns[k] = b
            kr.addWidget(b, 1)
        self.kind_btns["pa_model"].setChecked(True)
        self.kind_group.idClicked.connect(lambda _i: self.refresh())
        sl.addLayout(kr)
        self.h_runs = label("", "groupHead")
        sl.addWidget(self.h_runs)
        self.list = QListWidget()
        self.list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.itemChanged.connect(lambda _i: self.compare())
        sl.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.btn_del = QPushButton()
        self.btn_del.clicked.connect(self.delete)
        self.btn_exp = QPushButton()
        self.btn_exp.clicked.connect(self.export)
        row.addWidget(self.btn_del)
        row.addWidget(self.btn_exp)
        sl.addLayout(row)
        self.msg = label("", "help")
        sl.addWidget(self.msg)
        self.view = ResultsView()
        self.content_lay.addWidget(self.view)
        self.content_lay.addStretch(1)
        self._runs = []
        self.retranslate()

    def kind(self) -> str:
        for k, b in self.kind_btns.items():
            if b.isChecked():
                return k
        return "pa_model"

    def focus(self, kind: str):
        """Open on one kind with its two newest runs picked."""
        if kind in self.kind_btns:
            self.kind_btns[kind].setChecked(True)
        self.refresh(pick_newest=2)

    def refresh(self, pick_newest: int = 0):
        store = common.state().runstore
        was = set(self.picked_ids())
        self._runs = store.list(self.kind())
        self.list.blockSignals(True)
        self.list.clear()
        for i, r in enumerate(self._runs):
            it = QListWidgetItem(f"{r.name}\n{r.when} · {r.run_id}")
            it.setData(Qt.ItemDataRole.UserRole, r.run_id)
            it.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                        | Qt.ItemFlag.ItemIsEnabled
                        | Qt.ItemFlag.ItemIsSelectable)
            on = (r.run_id in was) if not pick_newest else i < pick_newest
            it.setCheckState(Qt.CheckState.Checked if on
                             else Qt.CheckState.Unchecked)
            self.list.addItem(it)
        self.list.blockSignals(False)
        self.compare()

    def picked_ids(self) -> list:
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.CheckState.Checked]

    def picked(self) -> list:
        ids = set(self.picked_ids())
        return [r for r in self._runs if r.run_id in ids]

    def compare(self):
        runs = self.picked()
        lang = common.PREFS["lang"]
        n = len(self._runs)
        self.msg.setText(tr("{n} 次运行").format(n=n))
        if not runs:
            self.view.show_empty(tr("勾选左侧的运行;勾选两个以上即并排比较。")
                                 if n else tr("这一类还没有运行记录。"))
            return
        out = experiments.compare_runs(runs, lang)
        self.view.render(out, {"bars": "指标对比"}, lang,
                         common.PREFS["theme"])
        if out["diff"]:
            self.view.lay.addWidget(label(tr("输入差异").upper(),
                                          "groupHead"))
            self.view.lay.addWidget(make_table(out["diff"]))
        self.last = out

    def delete(self):
        store = common.state().runstore
        for rid in self.picked_ids():
            store.delete(rid)
        self.refresh()

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("导出"),
                                              "padpd_runs.json",
                                              "JSON (*.json)")
        if path:
            runs = self.picked() or self._runs
            with open(path, "w", encoding="utf-8") as f:
                json.dump([{"run_id": r.run_id, "name": r.name,
                            "kind": r.kind, "config": r.config,
                            "metrics": r.metrics, "time": r.when}
                           for r in runs], f, indent=1, ensure_ascii=False,
                          default=str)
            self.msg.setText(f"💾 {path}")

    def retranslate(self):
        super().retranslate()
        self.h_kind.setText(tr("运行类型").upper())
        for k, b in self.kind_btns.items():
            b.setText(tr(experiments.KIND_LABELS[k]))
        self.h_runs.setText(tr("运行").upper())
        self.btn_del.setText(tr("删除所选"))
        self.btn_exp.setText(tr("导出 JSON"))
        self.refresh()

    def restyle(self):
        self.compare()

    def workspace_changed(self):
        self.refresh()


# ---------------------------------------------------------------------
# overview
# ---------------------------------------------------------------------


class OverviewPage(_Page):
    navigate = Signal(str)

    FLOW = (("sources", "数据源"), ("pa_model", "PA 模型"),
            ("dpd", "DPD"), ("deploy", "部署"))

    def __init__(self):
        super().__init__("总览",
                         "WiFi 7(802.11be)PA 行为建模与数字预失真工作台。"
                         "按左侧工作流从数据源走到部署;专题实验各自独立。",
                         setup=False)
        self.retranslate()

    def refresh(self):
        clear_layout(self.content_lay)
        st = common.state()
        ws, runs = st.workspace, st.runstore.list()
        lay = self.content_lay

        grid = QGridLayout()
        grid.setSpacing(10)
        counts = {"sources": len(ws.sources), "pa_model": len(ws.models),
                  "dpd": len([r for r in runs if r.kind == "dpd"]),
                  "deploy": len([r for r in runs if r.kind == "deploy"])}
        sub = {"sources": ws.active_source,
               "pa_model": f"{counts['pa_model']} {tr('个模型')}",
               "dpd": f"{counts['dpd']} {tr('次运行')}",
               "deploy": f"{counts['deploy']} {tr('次运行')}"}
        for i, (pid, title) in enumerate(self.FLOW):
            b = QPushButton(f"{i + 1}  {tr(title)}\n{sub[pid]}")
            b.setObjectName("flowStep")
            b.setMinimumHeight(64)
            b.clicked.connect(lambda _c=False, p=pid: self.navigate.emit(p))
            grid.addWidget(b, 0, i)
            grid.setColumnStretch(i, 1)
        lay.addLayout(grid)

        sp = ws.spec
        lay.addWidget(label(tr("项目 Spec").upper(), "groupHead"))
        lay.addWidget(label(
            f"EVM ≤ {sp['evm_db']:g} dB · ACLR ≤ {sp['aclr_dbc']:g} dBc · "
            + tr("802.11 发射模板") + " — "
            + tr("在顶栏的 Spec 处修改;已有结果会按新 spec 重新判定。"),
            "note"))

        lay.addWidget(label(tr("专题实验").upper(), "groupHead"))
        sg = QGridLayout()
        sg.setSpacing(10)
        studies = [e for e in experiments.EXPERIMENTS.values()
                   if e.group == "study" and experiments.available(e)]
        for i, e in enumerate(studies):
            b = QPushButton(tr(e.title))
            b.setObjectName("studyCard")
            b.setToolTip(tr(e.summary))
            b.clicked.connect(lambda _c=False, p=e.id: self.navigate.emit(p))
            sg.addWidget(b, i // 3, i % 3)
        for c in range(3):
            sg.setColumnStretch(c, 1)
        lay.addLayout(sg)

        lay.addWidget(label(tr("环境").upper(), "groupHead"))
        lay.addWidget(label(self._env(), "note"))

        lay.addWidget(label(tr("最近运行").upper(), "groupHead"))
        if runs:
            lay.addWidget(make_table([{
                tr("时间"): r.when, tr("名称"): r.name,
                tr("类型"): tr(experiments.KIND_LABELS.get(r.kind, r.kind)),
                "run": r.run_id} for r in runs[:8]]))
        else:
            lay.addWidget(label(tr("还没有运行记录。"), "muted"))
        lay.addStretch(1)

    def _env(self) -> str:
        from gui_core import services
        parts = []
        try:
            import torch
            parts.append(tr("✅ PyTorch {v}(神经建模可用)").format(
                v=torch.__version__))
        except ImportError:
            parts.append(tr("⚠️ PyTorch 未安装(神经功能不可用)"))
        od = Path(services.default_opendpd_dir())
        parts.append(tr("✅ OpenDPD 数据集:{path}").format(path=od)
                     if od.is_dir()
                     else tr("ℹ️ OpenDPD 未找到(可在数据页指定)"))
        return "   ".join(parts)

    def retranslate(self):
        super().retranslate()
        self.refresh()

    def workspace_changed(self):
        self.refresh()


# ---------------------------------------------------------------------
# manual
# ---------------------------------------------------------------------


def _manual_css(theme: str) -> str:
    t = TOKENS[theme]
    return f"""
    body {{ color: {t['ink']}; font-size: 13.5px; }}
    h1 {{ font-size: 21px; color: {t['ink']}; }}
    h2 {{ font-size: 16px; color: {t['ink']};
          border-bottom: 1px solid {t['line']}; }}
    h3 {{ font-size: 14px; color: {t['ink']}; }}
    p, li {{ line-height: 148%; }}
    a {{ color: {SERIES[theme][0]}; }}
    code {{ background: {t['panel2']}; color: {t['accent']};
            font-family: 'Consolas','DejaVu Sans Mono',monospace; }}
    pre {{ background: {t['panel2']}; border: 1px solid {t['line']};
           padding: 8px; }}
    table {{ border-collapse: collapse; }}
    th {{ background: {t['panel2']}; color: {t['muted']};
          border: 1px solid {t['line']}; padding: 4px 10px; }}
    td {{ border: 1px solid {t['line']}; padding: 4px 10px; }}
    img {{ margin: 8px 0; }}
    blockquote {{ border-left: 3px solid {t['accent']};
                  background: {t['accent_wash']}; padding: 4px 10px;
                  color: {t['ink2']}; }}
    """


def _to_html(md_text: str) -> str | None:
    try:
        import markdown
    except ImportError:
        return None
    body = markdown.markdown(
        md_text, extensions=["tables", "fenced_code", "sane_lists"])
    # scale screenshots to the browser pane
    return body.replace("<img ", '<img width="760" ')


class ManualPage(_Page):
    def __init__(self):
        super().__init__("用户手册",
                         "内置双语用户手册:快速入门、工作流、逐页指南、数据接口、"
                         "算法速览、性能基准、部署打包与 FAQ;语言随顶栏切换,"
                         "工程级细节见仓库 docs/ 目录。", setup=False)
        row = QHBoxLayout()
        self.toc = QListWidget()
        self.toc.setFixedWidth(220)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.view.setSearchPaths([str(manual.MANUAL_DIR)])
        row.addWidget(self.toc)
        row.addWidget(self.view, 1)
        holder = QWidget()
        holder.setLayout(row)
        self.content_lay.addWidget(holder, 1)
        self.view.setMinimumHeight(560)
        self.toc.currentRowChanged.connect(self._show)
        self.retranslate()

    def _show(self, row: int):
        if row < 0:
            return
        cid = manual.chapter_ids()[row]
        md_text = manual.load(cid, common.PREFS["lang"])
        html = _to_html(md_text)
        if html is None:  # graceful fallback without the markdown package
            self.view.setMarkdown(md_text)
            return
        self.view.document().setDefaultStyleSheet(
            _manual_css(common.PREFS["theme"]))
        self.view.setHtml(html)
        self.view.verticalScrollBar().setValue(0)

    def retranslate(self):
        super().retranslate()
        row = max(self.toc.currentRow(), 0)
        self.toc.blockSignals(True)
        self.toc.clear()
        for cid in manual.chapter_ids():
            self.toc.addItem(manual.chapter_title(cid, common.PREFS["lang"]))
        self.toc.blockSignals(False)
        self.toc.setCurrentRow(row)
        self._show(row)

    def restyle(self):
        self._show(max(self.toc.currentRow(), 0))
