from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui_core import Run, services
from gui_qt import figs
from gui_qt.common import FigurePane, FnWorker, get_state, page_scaffold, tr

ALL_BITS = [16, 14, 12, 10, 8]


class DeployPage(QWidget):
    def __init__(self):
        super().__init__()
        page, lay = page_scaffold(
            tr("部署"),
            tr("定点位宽扫描(bit-true)+ 硬件成本估计;导出 FPGA/ASIC 交接"
               "产物:整数系数 JSON、参考向量 CSV、神经模型 ONNX。"))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        self.state = get_state()

        grp = QGroupBox(tr("位宽扫描"))
        gl = QHBoxLayout(grp)
        self.model_list = QListWidget()
        self.model_list.setMaximumHeight(96)
        self.model_list.setMinimumWidth(320)
        self.bits_list = QListWidget()
        self.bits_list.setMaximumHeight(96)
        self.bits_list.setMaximumWidth(90)
        for b in ALL_BITS:
            it = QListWidgetItem(f"W{b}")
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if b in (16, 12, 8)
                             else Qt.CheckState.Unchecked)
            self.bits_list.addItem(it)
        self.sweep_btn = QPushButton(tr("位宽扫描"))
        self.sweep_btn.setObjectName("primary")
        gl.addWidget(QLabel(tr("模型(勾选)")))
        gl.addWidget(self.model_list, 2)
        gl.addWidget(QLabel(tr("位宽")))
        gl.addWidget(self.bits_list)
        gl.addStretch(1)
        gl.addWidget(self.sweep_btn)
        lay.addWidget(grp)

        self.prog = QProgressBar()
        self.prog.hide()
        lay.addWidget(self.prog)

        self.pane = FigurePane(300)
        lay.addWidget(self.pane, 1)
        self.table = QTableWidget(0, 0)
        self.table.setMaximumHeight(150)
        lay.addWidget(self.table)

        lgrp = QGroupBox(tr("LUT 深度扫描"))
        ll = QHBoxLayout(lgrp)
        self.lut_model = QComboBox()
        self.lut_btn = QPushButton(tr("LUT 深度扫描"))
        ll.addWidget(QLabel(tr("模型")))
        ll.addWidget(self.lut_model, 2)
        ll.addStretch(1)
        ll.addWidget(self.lut_btn)
        lay.addWidget(lgrp)
        self.lut_table = QTableWidget(0, 2)
        self.lut_table.setMaximumHeight(120)
        self.lut_table.hide()
        lay.addWidget(self.lut_table)

        exp = QGroupBox(tr("导出交接产物"))
        el = QHBoxLayout(exp)
        self.exp_model = QComboBox()
        self.exp_bits = QComboBox()
        self.exp_bits.addItems([f"W{b}" for b in ALL_BITS])
        self.exp_btn = QPushButton(tr("生成产物到目录…"))
        el.addWidget(QLabel(tr("模型")))
        el.addWidget(self.exp_model, 2)
        el.addWidget(QLabel(tr("系数位宽")))
        el.addWidget(self.exp_bits)
        el.addStretch(1)
        el.addWidget(self.exp_btn)
        lay.addWidget(exp)

        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)

        self.sweep_btn.clicked.connect(self.sweep)
        self.lut_btn.clicked.connect(self.lut_sweep)
        self.exp_btn.clicked.connect(self.export)
        self.refresh()

    def refresh(self):
        names = list(self.state.models)
        self.model_list.clear()
        for n in names:
            it = QListWidgetItem(n)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Unchecked)
            self.model_list.addItem(it)
        if self.model_list.count():
            self.model_list.item(0).setCheckState(Qt.CheckState.Checked)
        self.exp_model.clear()
        self.exp_model.addItems(names or [tr("<先在建模页拟合模型>")])
        self.lut_model.clear()
        self.lut_model.addItems(names or [tr("<先在建模页拟合模型>")])

    def _picked_models(self):
        return [self.model_list.item(i).text()
                for i in range(self.model_list.count())
                if self.model_list.item(i).checkState()
                == Qt.CheckState.Checked]

    def _picked_bits(self):
        return tuple(sorted(
            (ALL_BITS[i] for i in range(self.bits_list.count())
             if self.bits_list.item(i).checkState()
             == Qt.CheckState.Checked), reverse=True))

    def _src_for(self, entry):
        return services.eval_source_for(entry["meta"], self.state.sources)

    def sweep(self):
        picked, bits = self._picked_models(), self._picked_bits()
        if not picked or not bits:
            self.msg.setText(tr("请先勾选至少一个模型和位宽"))
            return
        entries = {n: self.state.models[n] for n in picked}
        self.sweep_btn.setEnabled(False)
        self.prog.setRange(0, len(picked))
        self.prog.setValue(0)
        self.prog.show()

        def job(on_progress=None):
            sweeps = {}
            for i, (name, entry) in enumerate(entries.items()):
                sweeps[name.split(" @")[0]] = services.bitwidth_sweep(
                    entry["model"], self._src_for(entry), bits=bits)
                if on_progress:
                    on_progress({"i": i + 1})
            return sweeps

        self._worker = FnWorker(job)
        self._worker.progress.connect(lambda h: self.prog.setValue(h["i"]))
        self._worker.done.connect(lambda s: self._finish(s, list(bits)))
        self._worker.failed.connect(
            lambda e: (self.msg.setText(f"❌ {e}"), self.prog.hide(),
                       self.sweep_btn.setEnabled(True)))
        self._worker.start()

    def _finish(self, sweeps, bits):
        self.prog.hide()
        self.sweep_btn.setEnabled(True)
        self.pane.set_figure(figs.bitwidth_fig(sweeps))
        cols = [tr("模型"), "float"] + [f"W{b}" for b in bits] + \
            [tr("MAC/样本"), "GMAC/s"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(0)
        self.table.setColumnWidth(0, 300)
        for label, s in sweeps.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            vals = [label, f"{s['float']:.2f}"] + \
                [f"{s['bits'][b]:.2f}" for b in bits]
            if s.get("macs"):
                vals += [str(s["macs"]["real_macs_per_sample"]),
                         f"{s['macs']['real_gmac_per_s']:.0f}"]
            for c, v in enumerate(vals):
                self.table.setItem(row, c, QTableWidgetItem(v))
            self.state.runstore.add(Run(
                name=f"deploy {label}", kind="deploy",
                config={"bits": bits},
                metrics={"float_nmse_db": s["float"],
                         **{f"w{b}_nmse_db": v
                            for b, v in s["bits"].items()}}))
        self.msg.setText(tr("✅ 扫描完成({n} 模型),已注册 run").format(
            n=len(sweeps)))

    def lut_sweep(self):
        name = self.lut_model.currentText()
        if name not in self.state.models:
            self.msg.setText(tr("先在建模页拟合模型"))
            return
        entry = self.state.models[name]
        model = entry["model"]
        if not hasattr(model, "gain_curve"):
            self.msg.setText(
                tr("该模型不支持 LUT 提取(需要样条/MP 增益曲线)"))
            return
        # snapshot on the GUI thread; the closure runs in a worker thread
        src = self._src_for(entry)
        self.lut_btn.setEnabled(False)
        self.msg.setText(tr("LUT 深度扫描中…"))

        def job(on_progress=None):
            return services.lut_sweep(model, src)

        self._lut_worker = FnWorker(job)
        self._lut_worker.done.connect(self._lut_finish)
        self._lut_worker.failed.connect(
            lambda e: (self.msg.setText(f"❌ {e}"),
                       self.lut_btn.setEnabled(True)))
        self._lut_worker.start()

    def _lut_finish(self, res):
        self.lut_btn.setEnabled(True)
        rows = [("float", res["float"])] + \
            [(str(n), v) for n, v in res["entries"].items()]
        self.lut_table.setHorizontalHeaderLabels(
            [tr("LUT 深度 (点数)"), "NMSE (dB)"])
        self.lut_table.setRowCount(0)
        for label, v in rows:
            r = self.lut_table.rowCount()
            self.lut_table.insertRow(r)
            self.lut_table.setItem(r, 0, QTableWidgetItem(label))
            self.lut_table.setItem(r, 1, QTableWidgetItem(f"{v:.2f}"))
        self.lut_table.show()
        self.msg.setText(tr("LUT MAC/样本") + ": "
                         + str(res["macs"]["real_macs_per_sample_lut"]))

    def export(self):
        name = self.exp_model.currentText()
        if name not in self.state.models:
            self.msg.setText(tr("先在建模页拟合模型"))
            return
        out_dir = QFileDialog.getExistingDirectory(
            self, tr("选择导出目录"), "deploy_export")
        if not out_dir:
            return
        entry = self.state.models[name]
        w_bits = int(self.exp_bits.currentText()[1:])
        dest = str(Path(out_dir) / name.split(" @")[0].replace(" ", "_"))
        # ONNX export + RTL emission + an iverilog run — off the UI thread
        self.exp_btn.setEnabled(False)
        self.msg.setText(tr("导出中…"))

        def job(on_progress=None):
            return services.export_artifacts(
                entry["model"], self._src_for(entry), dest, w_bits=w_bits)

        self._exp_worker = FnWorker(job)
        self._exp_worker.done.connect(self._export_done)
        self._exp_worker.failed.connect(
            lambda e: (self.msg.setText(tr("❌ 导出失败:{e}").format(e=e)),
                       self.exp_btn.setEnabled(True)))
        self._exp_worker.start()

    def _export_done(self, paths):
        self.exp_btn.setEnabled(True)
        lines = [f"{k}: {v}" for k, v in paths.items()
                 if not k.endswith("verified")]
        if "onnx_verified" in paths:
            lines.append(tr("ONNX 数值验证") + " "
                         + (tr("✅ 通过") if paths["onnx_verified"]
                            else tr("跳过")))
        if "rtl_verified" in paths:
            lines.append(tr("RTL bit-true 验证") + " "
                         + (tr("✅ 通过") if paths["rtl_verified"]
                            else tr("跳过")))
        self.msg.setText("📦 " + "\n".join(lines))
