from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QGroupBox,
                               QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QSpinBox, QTabWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from gui_qt import figs
from gui_qt.common import (FigurePane, FnWorker, MetricCard, card_row,
                           page_scaffold, tr)


class CodesignPage(QWidget):
    def __init__(self):
        super().__init__()
        page, lay = page_scaffold(
            tr("PA/DPD 联合设计"),
            tr("AI-Native 流程:PA 工作点与 DPD 复杂度联合优化。离散 Pareto "
               "扫描(稳健)与可微梯度寻优(内层闭式 LS-DPD + 外层梯度)。"))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_sweep_tab(), tr("离散 Pareto 扫描"))
        self.tabs.addTab(self._build_grad_tab(), tr("可微梯度寻优"))
        lay.addWidget(self.tabs, 1)

    # ---------------- discrete sweep ----------------
    def _build_sweep_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        grp = QGroupBox(tr("配置"))
        gl = QHBoxLayout(grp)
        self.spec1 = QSpinBox()
        self.spec1.setRange(-50, -30)
        self.spec1.setValue(-40)
        self.budget = QSpinBox()
        self.budget.setRange(20, 200)
        self.budget.setValue(90)
        self.bw = QComboBox()
        self.bw.addItems(["20", "80", "160"])
        self.bw.setCurrentText("80")
        self.sweep_btn = QPushButton(tr("运行扫描(约 1 分钟)"))
        self.sweep_btn.setObjectName("primary")
        for lbl, w in [("EVM spec (dB)", self.spec1),
                       (tr("DPD 系数预算"), self.budget),
                       (tr("带宽 (MHz)"), self.bw)]:
            gl.addWidget(QLabel(lbl))
            gl.addWidget(w)
        gl.addStretch(1)
        gl.addWidget(self.sweep_btn)
        lay.addWidget(grp)

        self.prog1 = QProgressBar()
        self.prog1.setRange(0, 0)
        self.prog1.hide()
        lay.addWidget(self.prog1)

        self.c_seq = MetricCard(tr("顺序设计(先冲效率)"))
        self.c_co = MetricCard(tr("联合设计(预算内最高效率)"))
        lay.addWidget(card_row([self.c_seq, self.c_co]))

        self.pane1 = FigurePane(300)
        lay.addWidget(self.pane1, 1)
        self.table1 = QTableWidget(0, 6)
        self.table1.setHorizontalHeaderLabels(
            ["drive", "PAE %", tr("EVM 无DPD"), tr("DPD 系数"), "EVM DPD",
             tr("可行")])
        self.table1.setMaximumHeight(210)
        lay.addWidget(self.table1)
        self.msg1 = QLabel("")
        lay.addWidget(self.msg1)
        self.sweep_btn.clicked.connect(self.run_sweep)
        return tab

    def run_sweep(self):
        spec = float(self.spec1.value())
        budget = self.budget.value()
        bw = float(self.bw.currentText()) * 1e6
        self.sweep_btn.setEnabled(False)
        self.prog1.show()

        def job(on_progress=None):
            from padpd.codesign import codesign_sweep
            from padpd.waveform import OFDMConfig, generate_ofdm
            cfg = OFDMConfig(bandwidth_hz=bw, qam_order=1024, n_symbols=6,
                             seed=0)
            trn = generate_ofdm(cfg)
            va = generate_ofdm(OFDMConfig(bandwidth_hz=bw, qam_order=1024,
                                          n_symbols=6, seed=1))
            return codesign_sweep([0.08, 0.10, 0.12, 0.14, 0.17, 0.20, 0.24],
                                  trn.x, va.x, va, spec,
                                  cfg.sample_rate_hz, bw)

        self._worker1 = FnWorker(job)
        self._worker1.done.connect(
            lambda rows: self._finish_sweep(rows, budget))
        self._worker1.failed.connect(
            lambda e: (self.msg1.setText(f"❌ {e}"), self.prog1.hide(),
                       self.sweep_btn.setEnabled(True)))
        self._worker1.start()

    def _finish_sweep(self, rows, budget):
        self.prog1.hide()
        self.sweep_btn.setEnabled(True)
        self.pane1.set_figure(figs.codesign_fig(rows, budget))
        seq = max(rows, key=lambda r: r["pae"])
        seq_ok = seq["feasible"] and seq["dpd_cost"] <= budget
        self.c_seq.set(f"PAE {100*seq['pae']:.1f}%",
                       tr("可行") if seq_ok
                       else tr("撞墙:不可逆/超预算"))
        feasible = [r for r in rows
                    if r["feasible"] and r["dpd_cost"] <= budget]
        if feasible:
            co = max(feasible, key=lambda r: r["pae"])
            self.c_co.set(
                f"PAE {100*co['pae']:.1f}%",
                tr("drive {drive:.2f} · {cost} 系数 · EVM {evm:.1f} dB")
                .format(drive=co["drive"], cost=co["dpd_cost"],
                        evm=co["evm_dpd"]))
        else:
            self.c_co.set("—", tr("预算内无可行点"))
        self.table1.setRowCount(0)
        for r in rows:
            row = self.table1.rowCount()
            self.table1.insertRow(row)
            vals = [f"{r['drive']:.2f}", f"{100*r['pae']:.1f}",
                    f"{r['evm_nodpd']:.1f}", str(r["dpd_cost"]),
                    f"{r['evm_dpd']:.1f}", "✅" if r["feasible"] else "❌"]
            for c, v in enumerate(vals):
                self.table1.setItem(row, c, QTableWidgetItem(v))
        self.msg1.setText(tr("✅ 扫描完成({n} 个工作点)").format(
            n=len(rows)))

    # ---------------- gradient ----------------
    def _build_grad_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        grp = QGroupBox(tr("配置"))
        gl = QHBoxLayout(grp)
        self.spec2 = QSpinBox()
        self.spec2.setRange(-50, -30)
        self.spec2.setValue(-38)
        self.drive0 = QDoubleSpinBox()
        self.drive0.setRange(0.06, 0.14)
        self.drive0.setSingleStep(0.01)
        self.drive0.setValue(0.08)
        self.steps = QSpinBox()
        self.steps.setRange(50, 300)
        self.steps.setValue(150)
        self.grad_btn = QPushButton(tr("运行梯度寻优"))
        self.grad_btn.setObjectName("primary")
        for lbl, w in [("EVM spec (dB)", self.spec2),
                       (tr("初始 drive"), self.drive0),
                       (tr("梯度步数"), self.steps)]:
            gl.addWidget(QLabel(lbl))
            gl.addWidget(w)
        gl.addStretch(1)
        gl.addWidget(self.grad_btn)
        lay.addWidget(grp)

        self.prog2 = QProgressBar()
        self.prog2.setRange(0, 0)
        self.prog2.hide()
        lay.addWidget(self.prog2)

        self.c_base = MetricCard(tr("保守设计(固定 drive)"))
        self.c_grad = MetricCard(tr("梯度联合优化"))
        lay.addWidget(card_row([self.c_base, self.c_grad]))

        self.pane2 = FigurePane(300)
        lay.addWidget(self.pane2, 1)
        self.msg2 = QLabel("")
        lay.addWidget(self.msg2)
        self.grad_btn.clicked.connect(self.run_grad)
        return tab

    def run_grad(self):
        spec = float(self.spec2.value())
        drive0 = self.drive0.value()
        steps = self.steps.value()
        self.grad_btn.setEnabled(False)
        self.prog2.show()

        def job(on_progress=None):
            from padpd.codesign_torch import joint_codesign
            from padpd.waveform import OFDMConfig, generate_ofdm
            x = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=256,
                                         n_symbols=4, seed=0)).x
            base = joint_codesign(x, drive_init=drive0, evm_spec_db=spec,
                                  learnable_drive=False)
            co = joint_codesign(x, drive_init=drive0, evm_spec_db=spec,
                                lambda_eff=3.0, steps=steps)
            return base, co

        self._worker2 = FnWorker(job)
        self._worker2.done.connect(lambda out: self._finish_grad(out, spec))
        self._worker2.failed.connect(
            lambda e: (self.msg2.setText(
                tr("❌ {e}(需要 PyTorch)").format(e=e)),
                self.prog2.hide(), self.grad_btn.setEnabled(True)))
        self._worker2.start()

    def _finish_grad(self, out, spec):
        self.prog2.hide()
        self.grad_btn.setEnabled(True)
        base, co = out
        self.c_base.set(f"PAE {100*base['efficiency']:.1f}%",
                        f"EVM {base['evm_db']:.1f} dB")
        self.c_grad.set(f"PAE {100*co['efficiency']:.1f}%",
                        f"drive→{co['drive']:.3f} · "
                        f"EVM {co['evm_db']:.1f} dB")
        self.pane2.set_figure(figs.grad_fig(co["history"], spec))
        self.msg2.setText(tr("✅ 梯度寻优完成"))
