from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                               QGroupBox, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QSpinBox, QTabWidget,
                               QVBoxLayout, QWidget)

from gui_core import Run, services
from gui_qt import figs
from gui_qt.common import (FigurePane, FnWorker, MetricCard, card_row,
                           get_state, page_scaffold, tr)


class DpdPage(QWidget):
    def __init__(self):
        super().__init__()
        page, lay = page_scaffold(
            tr("DPD 实验室"),
            tr("ILA(经典 LS,基函数 GMP/DDR/MP)或 DLA(神经直接学习,需神经"
               "代理);合成源用星座 EVM+Mask,OpenDPD 源自动用其口径;"
               "实测源评估需选 PA 代理。"))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        self.state = get_state()

        grp = QGroupBox(tr("配置"))
        gl = QHBoxLayout(grp)
        self.src = QComboBox()
        self.bw = QComboBox()
        self.bw.addItems(["20", "40", "80", "160", "320"])
        self.bw.setCurrentText("160")
        self.drive = QDoubleSpinBox()
        self.drive.setRange(0.08, 0.24)
        self.drive.setSingleStep(0.01)
        self.drive.setValue(0.14)
        self.cfr_on = QCheckBox("CFR")
        self.cfr = QDoubleSpinBox()
        self.cfr.setRange(5.0, 10.0)
        self.cfr.setValue(8.0)
        self.algo = QComboBox()
        self.algo.addItems([tr("ILA(经典)"), tr("DLA(神经)")])
        self.basis = QComboBox()
        self.basis.addItems(["GMP-510 (OpenDPD)", "DDR-140 (preset)",
                             "MP-500 (OpenDPD)", "GMP", "DDR", "MP"])
        self.surrogate = QComboBox()
        self.epochs = QSpinBox()
        self.epochs.setRange(5, 100)
        self.epochs.setValue(20)
        self.run_btn = QPushButton(tr("运行 DPD"))
        self.run_btn.setObjectName("primary")
        for lbl, w in [(tr("数据源"), self.src),
                       (tr("带宽 (MHz)"), self.bw), ("drive", self.drive)]:
            gl.addWidget(QLabel(lbl))
            gl.addWidget(w)
        gl.addWidget(self.cfr_on)
        gl.addWidget(self.cfr)
        for lbl, w in [(tr("算法"), self.algo), (tr("基函数"), self.basis),
                       (tr("代理"), self.surrogate),
                       ("epochs", self.epochs)]:
            gl.addWidget(QLabel(lbl))
            gl.addWidget(w)
        gl.addStretch(1)
        gl.addWidget(self.run_btn)
        lay.addWidget(grp)

        self.prog = QProgressBar()
        self.prog.hide()
        lay.addWidget(self.prog)

        self.c_e0 = MetricCard(tr("EVM(无 DPD)"))
        self.c_e1 = MetricCard(tr("EVM(DPD 后)"))
        self.c_a0 = MetricCard(tr("ACLR(无 DPD)"))
        self.c_a1 = MetricCard(tr("ACLR(DPD 后)"))
        lay.addWidget(card_row([self.c_e0, self.c_e1, self.c_a0, self.c_a1]))

        self.tabs = QTabWidget()
        self.p_psd, self.p_const, self.p_adapt = (FigurePane(), FigurePane(),
                                                 FigurePane())
        self.tabs.addTab(self.p_psd, tr("PSD 前后对比"))
        self.tabs.addTab(self.p_const, tr("星座前后对比"))
        self.tabs.addTab(self.p_adapt, tr("自适应(漂移)"))
        lay.addWidget(self.tabs, 1)
        self.msg = QLabel("")
        lay.addWidget(self.msg)

        agrp = QGroupBox(tr("自适应 / 在线 DPD(漂移跟踪)"))
        al = QHBoxLayout(agrp)
        self.ad_method = QComboBox()
        self.ad_method.addItems(list(services.ADAPTIVE_METHODS))
        self.ad_bw = QComboBox()
        self.ad_bw.addItems(["20", "40", "80", "160", "320"])
        self.ad_bw.setCurrentText("80")
        self.ad_bw.setToolTip(tr("带宽越大采样率越高,自适应每块的计算"
                                 "越慢(80 MHz 为演示默认)"))
        self.ad_blocks = QSpinBox()
        self.ad_blocks.setRange(4, 16)
        self.ad_blocks.setValue(10)
        self.ad_span = QDoubleSpinBox()
        self.ad_span.setRange(0.01, 0.05)
        self.ad_span.setSingleStep(0.005)
        self.ad_span.setValue(0.02)
        self.ad_forget = QDoubleSpinBox()
        self.ad_forget.setRange(0.50, 0.99)
        self.ad_forget.setSingleStep(0.01)
        self.ad_forget.setValue(0.60)
        self.ad_k = QSpinBox()
        self.ad_k.setRange(1, 8)
        self.ad_k.setValue(4)
        self.ad_k.setToolTip(tr("APA 投影阶:K=1 即 NLMS,K 越大越接近 RLS"
                                "(仅 method=apa 生效)"))
        self.ad_run = QPushButton(tr("运行自适应 DPD"))
        self.ad_run.setObjectName("primary")
        for lbl, w in [(tr("方法"), self.ad_method),
                       (tr("带宽 (MHz)"), self.ad_bw),
                       (tr("块数"), self.ad_blocks),
                       (tr("漂移"), self.ad_span),
                       ("forget", self.ad_forget),
                       ("APA K", self.ad_k)]:
            al.addWidget(QLabel(lbl))
            al.addWidget(w)
        al.addStretch(1)
        al.addWidget(self.ad_run)
        lay.addWidget(agrp)
        self.ad_msg = QLabel(tr("在会漂移的合成 PA 上比较自适应 vs 冻结批处理 "
                                "DPD 的逐块 EVM。"))
        self.ad_msg.setWordWrap(True)
        lay.addWidget(self.ad_msg)

        self.algo.currentIndexChanged.connect(self._toggle)
        self.run_btn.clicked.connect(self.run)
        self.ad_run.clicked.connect(self.run_adaptive)
        self.refresh()
        self._toggle(self.algo.currentIndex())

    def refresh(self):
        self.src.blockSignals(True)
        cur = self.src.currentText()
        self.src.clear()
        self.src.addItems([tr("合成 ReferencePA")] + list(self.state.sources))
        if cur:
            self.src.setCurrentText(cur)
        self.src.blockSignals(False)
        self.surrogate.clear()
        self.surrogate.addItems(list(self.state.models) or [tr("<无模型>")])

    def _toggle(self, idx):
        ila = idx == 0  # index 0 = ILA (classical)
        self.basis.setEnabled(ila)
        self.epochs.setEnabled(not ila)

    def _get_source(self):
        name = self.src.currentText()
        if name == tr("合成 ReferencePA"):
            cfr = self.cfr.value() if self.cfr_on.isChecked() else None
            bw = float(self.bw.currentText()) * 1e6
            key = f"_dpdsynth_{bw:.0f}_{self.drive.value():.2f}_{cfr}"
            if not hasattr(self.state, key):
                setattr(self.state, key, services.make_synthetic_source(
                    bandwidth_hz=bw, drive=self.drive.value(),
                    cfr_papr_db=cfr))
            return getattr(self.state, key)
        return self.state.sources[name]

    def run(self):
        src = self._get_source()
        models = self.state.models
        sname = self.surrogate.currentText()
        try:
            if self.algo.currentIndex() == 0:  # ILA (classical)
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
                    self.msg.setText(tr("❌ DLA 需要先在建模页训练神经代理"))
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

    def run_adaptive(self):
        self.ad_run.setEnabled(False)
        self.ad_msg.setText(tr("自适应跟踪中…"))
        method = self.ad_method.currentText()
        bw = float(self.ad_bw.currentText()) * 1e6

        def job(on_progress=None):
            return services.run_adaptive_dpd(
                method=method, n_blocks=self.ad_blocks.value(),
                drift_span=self.ad_span.value(),
                forget=self.ad_forget.value(), apa_k=self.ad_k.value(),
                bw=bw)

        self._ad_worker = FnWorker(job)
        self._ad_worker.done.connect(self._finish_adaptive)
        self._ad_worker.failed.connect(
            lambda e: (self.ad_msg.setText(f"❌ {e}"),
                       self.ad_run.setEnabled(True)))
        self._ad_worker.start()

    def _finish_adaptive(self, res):
        self.ad_run.setEnabled(True)
        self.p_adapt.set_figure(figs.adaptive_evm_fig(res))
        self.tabs.setCurrentWidget(self.p_adapt)
        name, cfg, metrics = services.adaptive_run_record(res)
        self.state.runstore.add(Run(name=name, kind="dpd", config=cfg,
                                    metrics=metrics))
        self.ad_msg.setText(tr(
            "满漂移 EVM:冻结 {f:.1f} dB → 自适应 {m} {a:.1f} dB"
            "(领先 {g:.1f} dB);已注册为 run。").format(
            f=res["final_frozen"], m=res["method"].upper(),
            a=res["final_adaptive"], g=res["gap_db"]))

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
            {tr("无 DPD"): out["y_before"], tr("DPD 后"): out["y_after"]},
            out["fs"], mask=out.get("mask")))
        if out.get("wf") is not None:
            self.p_const.set_figure(figs.constellation_fig({
                tr("无 DPD"): services.constellation_points(
                    out["y_before"], out["wf"], out["gain"]),
                tr("DPD 后"): services.constellation_points(
                    out["y_after"], out["wf"], out["gain"])}))
        cfg["source"] = src["name"]
        self.state.runstore.add(Run(
            name=f"{label} @ {src['name']}", kind="dpd", config=cfg,
            metrics={"evm_db": m["DPD"]["evm_db"],
                     "evm_before_db": m["no DPD"]["evm_db"],
                     "aclr_high_dbc": m["DPD"]["aclr_high"],
                     "convention": out["convention"]}))
        self.msg.setText(tr("✅ {label} 完成({conv} 口径),已注册 run")
                         .format(label=label, conv=out["convention"]))
