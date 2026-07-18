from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                               QGroupBox, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QSpinBox, QTabWidget,
                               QVBoxLayout, QWidget)

from gui_core import Run, services
from gui_qt import figs
from gui_qt.common import (FigurePane, FnWorker, MetricCard, card_row,
                           get_state, page_scaffold)


class DpdPage(QWidget):
    def __init__(self):
        super().__init__()
        page, lay = page_scaffold(
            "DPD 实验室",
            "ILA(经典 LS,基函数 GMP/DDR/MP)或 DLA(神经直接学习,需神经"
            "代理);合成源用星座 EVM+Mask,OpenDPD 源自动用其口径;"
            "实测源评估需选 PA 代理。")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        self.state = get_state()

        grp = QGroupBox("配置")
        gl = QHBoxLayout(grp)
        self.src = QComboBox()
        self.drive = QDoubleSpinBox()
        self.drive.setRange(0.08, 0.24)
        self.drive.setSingleStep(0.01)
        self.drive.setValue(0.14)
        self.cfr_on = QCheckBox("CFR")
        self.cfr = QDoubleSpinBox()
        self.cfr.setRange(5.0, 10.0)
        self.cfr.setValue(8.0)
        self.algo = QComboBox()
        self.algo.addItems(["ILA(经典)", "DLA(神经)"])
        self.basis = QComboBox()
        self.basis.addItems(["GMP-510 (OpenDPD)", "DDR-140 (preset)",
                             "MP-500 (OpenDPD)", "GMP", "DDR", "MP"])
        self.surrogate = QComboBox()
        self.epochs = QSpinBox()
        self.epochs.setRange(5, 100)
        self.epochs.setValue(20)
        self.run_btn = QPushButton("运行 DPD")
        self.run_btn.setObjectName("primary")
        for lbl, w in [("数据源", self.src), ("drive", self.drive)]:
            gl.addWidget(QLabel(lbl))
            gl.addWidget(w)
        gl.addWidget(self.cfr_on)
        gl.addWidget(self.cfr)
        for lbl, w in [("算法", self.algo), ("基函数", self.basis),
                       ("代理", self.surrogate), ("epochs", self.epochs)]:
            gl.addWidget(QLabel(lbl))
            gl.addWidget(w)
        gl.addStretch(1)
        gl.addWidget(self.run_btn)
        lay.addWidget(grp)

        self.prog = QProgressBar()
        self.prog.hide()
        lay.addWidget(self.prog)

        self.c_e0 = MetricCard("EVM(无 DPD)")
        self.c_e1 = MetricCard("EVM(DPD 后)")
        self.c_a0 = MetricCard("ACLR(无 DPD)")
        self.c_a1 = MetricCard("ACLR(DPD 后)")
        lay.addWidget(card_row([self.c_e0, self.c_e1, self.c_a0, self.c_a1]))

        self.tabs = QTabWidget()
        self.p_psd, self.p_const = FigurePane(), FigurePane()
        self.tabs.addTab(self.p_psd, "PSD 前后对比")
        self.tabs.addTab(self.p_const, "星座前后对比")
        lay.addWidget(self.tabs, 1)
        self.msg = QLabel("")
        lay.addWidget(self.msg)

        self.algo.currentTextChanged.connect(self._toggle)
        self.run_btn.clicked.connect(self.run)
        self.refresh()
        self._toggle(self.algo.currentText())

    def refresh(self):
        self.src.blockSignals(True)
        cur = self.src.currentText()
        self.src.clear()
        self.src.addItems(["合成 ReferencePA"] + list(self.state.sources))
        if cur:
            self.src.setCurrentText(cur)
        self.src.blockSignals(False)
        self.surrogate.clear()
        self.surrogate.addItems(list(self.state.models) or ["<无模型>"])

    def _toggle(self, algo):
        ila = algo.startswith("ILA")
        self.basis.setEnabled(ila)
        self.epochs.setEnabled(not ila)

    def _get_source(self):
        name = self.src.currentText()
        if name == "合成 ReferencePA":
            cfr = self.cfr.value() if self.cfr_on.isChecked() else None
            key = f"_dpdsynth_{self.drive.value():.2f}_{cfr}"
            if not hasattr(self.state, key):
                setattr(self.state, key, services.make_synthetic_source(
                    bandwidth_hz=160e6, drive=self.drive.value(),
                    cfr_papr_db=cfr))
            return getattr(self.state, key)
        return self.state.sources[name]

    def run(self):
        src = self._get_source()
        models = self.state.models
        sname = self.surrogate.currentText()
        try:
            if self.algo.currentText().startswith("ILA"):
                surrogate = (models[sname]["model"] if sname in models
                             else None)
                out = services.run_dpd_ila(src,
                                           basis=self.basis.currentText(),
                                           surrogate=surrogate)
                label = f"ILA-{self.basis.currentText()}"
                cfg = {"algo": "ILA", "basis": self.basis.currentText()}
                self._finish(out, label, cfg, src)
            else:
                if sname not in models:
                    self.msg.setText("❌ DLA 需要先在建模页训练神经代理")
                    return
                self.run_btn.setEnabled(False)
                self.prog.setRange(0, self.epochs.value())
                self.prog.show()

                def job(on_progress=None):
                    return services.run_dpd_dla(
                        src, models[sname]["model"],
                        epochs=self.epochs.value(), on_epoch=on_progress)

                self._worker = FnWorker(job)
                self._worker.progress.connect(
                    lambda h: self.prog.setValue(h["epoch"] + 1))
                cfg = {"algo": "DLA", "surrogate": sname,
                       "epochs": self.epochs.value()}
                self._worker.done.connect(
                    lambda out: self._finish(out, "DLA-DGRU", cfg, src))
                self._worker.failed.connect(
                    lambda e: (self.msg.setText(f"❌ {e}"),
                               self.prog.hide(),
                               self.run_btn.setEnabled(True)))
                self._worker.start()
        except Exception as e:
            self.msg.setText(f"❌ {e}")

    def _finish(self, out, label, cfg, src):
        self.prog.hide()
        self.run_btn.setEnabled(True)
        m = out["metrics"]
        self.c_e0.set(f"{m['no DPD']['evm_db']:.1f} dB")
        self.c_e1.set(f"{m['DPD']['evm_db']:.1f} dB",
                      f"{m['DPD']['evm_db']-m['no DPD']['evm_db']:+.1f} dB")
        if m["DPD"]["aclr_high"] is not None:
            self.c_a0.set(f"{m['no DPD']['aclr_high']:.1f} dBc",
                          f"Mask {m['no DPD']['mask']}")
            self.c_a1.set(f"{m['DPD']['aclr_high']:.1f} dBc",
                          f"Mask {m['DPD']['mask']}")
        else:
            self.c_a0.set("—")
            self.c_a1.set("—")
        self.p_psd.set_figure(figs.psd_fig(
            {"无 DPD": out["y_before"], "DPD 后": out["y_after"]},
            out["fs"], mask=out.get("mask")))
        if out.get("wf") is not None:
            self.p_const.set_figure(figs.constellation_fig({
                "无 DPD": services.constellation_points(
                    out["y_before"], out["wf"], out["gain"]),
                "DPD 后": services.constellation_points(
                    out["y_after"], out["wf"], out["gain"])}))
        cfg["source"] = src["name"]
        self.state.runstore.add(Run(
            name=f"{label} @ {src['name']}", kind="dpd", config=cfg,
            metrics={"evm_db": m["DPD"]["evm_db"],
                     "evm_before_db": m["no DPD"]["evm_db"],
                     "aclr_high_dbc": m["DPD"]["aclr_high"],
                     "convention": out["convention"]}))
        self.msg.setText(f"✅ {label} 完成({out['convention']} 口径),"
                         "已注册 run")
