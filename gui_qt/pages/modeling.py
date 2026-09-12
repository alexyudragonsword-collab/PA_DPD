from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui_core import Run, services
from gui_qt import figs
from gui_qt.common import (
    FigurePane,
    FnWorker,
    MetricCard,
    card_row,
    get_state,
    page_scaffold,
    tr,
)


class ModelingPage(QWidget):
    def __init__(self):
        super().__init__()
        page, lay = page_scaffold(
            tr("PA 建模"),
            tr("经典(LS 闭式解)或神经(SGD)模型拟合 PA 行为;拟合好的模型"
               "可作为 DPD 评估代理并进入部署页。"))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        self.state = get_state()

        grp = QGroupBox(tr("配置"))
        gl = QHBoxLayout(grp)
        self.src = QComboBox()
        self.family = QComboBox()
        self.family.addItems([tr("经典 (LS)"), tr("神经 (SGD)")])
        self.mtype = QComboBox()
        self.mtype.addItems(list(services.CLASSICAL_MODELS))
        self.order = QSpinBox()
        self.order.setRange(3, 9)
        self.order.setValue(5)
        self.order.setToolTip(tr("Spline-MP:阶数滑条 = 节点数"))
        self.memory = QSpinBox()
        self.memory.setRange(1, 30)
        self.memory.setValue(4)
        self.backbone = QComboBox()
        self.backbone.addItems(["dgru", "gru", "tcn"])
        self.hidden = QSpinBox()
        self.hidden.setRange(4, 32)
        self.hidden.setValue(8)
        self.epochs = QSpinBox()
        self.epochs.setRange(5, 100)
        self.epochs.setValue(20)
        self.drive = QDoubleSpinBox()
        self.drive.setRange(0.06, 0.24)
        self.drive.setSingleStep(0.01)
        self.drive.setValue(0.14)
        self.frontend = QComboBox()
        self.frontend.addItems(list(services.FRONTEND_DUTS))
        self.frontend.setToolTip(
            tr("合成 DUT 的 TX 前端损伤:iq=镜像(0.3 dB/3°,IRR≈30 dB),"
               "+lo=LO 泄漏 -35 dBc,+cim3=counter-IM3 -32 dBc;"
               "配套模型选 Spline-MP-WL / Spline-MP-CIM3"))
        self.fit_btn = QPushButton(tr("拟合模型"))
        self.fit_btn.setObjectName("primary")
        for lbl, w in [(tr("数据源"), self.src), ("drive", self.drive),
                       (tr("前端"), self.frontend),
                       (tr("模型族"), self.family), (tr("类型"), self.mtype),
                       (tr("阶数"), self.order), (tr("记忆"), self.memory),
                       ("backbone", self.backbone), ("hidden", self.hidden),
                       ("epochs", self.epochs)]:
            gl.addWidget(QLabel(lbl))
            gl.addWidget(w)
        gl.addStretch(1)
        gl.addWidget(self.fit_btn)
        lay.addWidget(grp)

        self.prog = QProgressBar()
        self.prog.hide()
        lay.addWidget(self.prog)

        self.c_nmse = MetricCard(tr("测试 NMSE"))
        self.c_np = MetricCard(tr("参数量"))
        self.c_src = MetricCard(tr("数据源"))
        lay.addWidget(card_row([self.c_nmse, self.c_np, self.c_src]))

        self.tabs = QTabWidget()
        self.p_psd, self.p_amam, self.p_gm = (FigurePane(), FigurePane(),
                                              FigurePane())
        self.tabs.addTab(self.p_psd, tr("PSD:实测 vs 预测"))
        self.tabs.addTab(self.p_amam, tr("AM-AM / AM-PM(预测)"))
        self.tabs.addTab(self.p_gm, tr("增益调制"))
        lay.addWidget(self.tabs, 1)

        ggrp = QGroupBox(tr("增益调制辨识(τ 表征 → 状态样条)"))
        gl2 = QHBoxLayout(ggrp)
        self.gm_dut = QComboBox()
        self.gm_dut.addItems(list(services.GAIN_MOD_DUTS))
        self.gm_dut.setToolTip(tr("thermal=自热虚拟 DUT(τ 真值 5/30 µs);"
                                  "static=纯 ReferencePA 对照(应判无调制)"))
        self.gm_drive = QDoubleSpinBox()
        self.gm_drive.setRange(0.06, 0.24)
        self.gm_drive.setSingleStep(0.01)
        self.gm_drive.setValue(0.13)
        self.gm_fit = QCheckBox(tr("拟合状态样条"))
        self.gm_fit.setChecked(True)
        self.gm_fit.setToolTip(tr("用辨识出的 α 配置 StateConditionedSpline,"
                                  "在突发激励上与纯 SMP 对比 NMSE"))
        self.gm_run = QPushButton(tr("运行辨识"))
        self.gm_run.setObjectName("primary")
        for lbl, w in [(tr("虚拟 DUT"), self.gm_dut),
                       ("drive", self.gm_drive)]:
            gl2.addWidget(QLabel(lbl))
            gl2.addWidget(w)
        gl2.addWidget(self.gm_fit)
        gl2.addStretch(1)
        gl2.addWidget(self.gm_run)
        lay.addWidget(ggrp)
        self.gm_msg = QLabel(tr("阶跃响应实验辨识增益调制时常数(手册 5.9):"
                                "恒包络探针,加热/冷却分别多指数拟合。"))
        self.gm_msg.setWordWrap(True)
        lay.addWidget(self.gm_msg)

        bottom = QHBoxLayout()
        self.save_btn = QPushButton(tr("保存 checkpoint…"))
        self.save_btn.setEnabled(False)
        self.msg = QLabel("")
        bottom.addWidget(self.save_btn)
        bottom.addWidget(self.msg, 1)
        w = QWidget()
        w.setLayout(bottom)
        lay.addWidget(w)

        self.family.currentIndexChanged.connect(self._toggle)
        self.fit_btn.clicked.connect(self.fit)
        self.save_btn.clicked.connect(self.save)
        self.gm_run.clicked.connect(self.run_gain_mod)
        self._toggle(self.family.currentIndex())
        self.refresh()
        self._last = None

    def refresh(self):
        cur = self.src.currentText()
        self.src.blockSignals(True)
        self.src.clear()
        self.src.addItems([tr("合成 ReferencePA")] + list(self.state.sources))
        if cur:
            self.src.setCurrentText(cur)
        self.src.blockSignals(False)

    def _toggle(self, idx):
        classical = idx == 0  # index 0 = classical (LS)
        for w in (self.mtype, self.order, self.memory):
            w.setEnabled(classical)
        for w in (self.backbone, self.hidden, self.epochs):
            w.setEnabled(not classical)

    def _get_source(self):
        name = self.src.currentText()
        if name == tr("合成 ReferencePA"):
            return services.cached_synthetic_source(
                drive=self.drive.value(),
                frontend=self.frontend.currentText())
        return self.state.sources[name]

    def fit(self):
        src = self._get_source()
        if self.family.currentIndex() == 0:  # classical (LS)
            # snapshot widget values on the GUI thread; run the LS fit in
            # a worker so a 320 MHz source doesn't freeze the window
            label = self.mtype.currentText()
            params = {"order": self.order.value(),
                      "memory": self.memory.value()}
            cfg = {"family": "classical", "type": label, **params}
            self.fit_btn.setEnabled(False)

            def job(on_progress=None):
                return services.fit_classical(src, label, params)

            self._worker = FnWorker(job)
            self._worker.done.connect(
                lambda res: self._finish(res, label, cfg, src))
            self._worker.failed.connect(
                lambda e: (self.msg.setText(f"❌ {e}"),
                           self.fit_btn.setEnabled(True)))
            self._worker.start()
        else:
            self.fit_btn.setEnabled(False)
            epochs = self.epochs.value()      # snapshot on the GUI thread
            self.prog.setRange(0, epochs)
            self.prog.show()
            backbone, hidden = (self.backbone.currentText(),
                                self.hidden.value())

            def job(on_progress=None):
                return services.fit_neural(
                    src, backbone=backbone, hidden=hidden,
                    epochs=epochs, on_epoch=on_progress)

            self._worker = FnWorker(job)
            self._worker.progress.connect(
                lambda h: (self.prog.setValue(h["epoch"] + 1),
                           self.prog.setFormat(
                               f"epoch {h['epoch']+1} · "
                               f"{h['val_nmse_db']:.2f} dB")))
            label = f"{backbone.upper()}-H{hidden}"
            cfg = {"family": "neural", "backbone": backbone,
                   "hidden": hidden, "epochs": epochs}
            self._worker.done.connect(
                lambda res: self._finish(res, label, cfg, src))
            self._worker.failed.connect(self._fail)
            self._worker.start()

    def _fail(self, err):
        self.msg.setText(f"❌ {err}")
        self.prog.hide()
        self.fit_btn.setEnabled(True)

    def _finish(self, res, label, cfg, src):
        self.prog.hide()
        self.fit_btn.setEnabled(True)
        name = f"{label} @ {src['name']}"
        self.state.models[name] = {"model": res["model"],
                                   "meta": {"config": cfg,
                                            "source": src["name"],
                                            "metrics": res["metrics"]}}
        self.state.runstore.add(Run(name=name, kind="pa_model", config=cfg,
                                    metrics=res["metrics"]))
        self.c_nmse.set(f"{res['metrics']['nmse_db']:.2f} dB")
        self.c_np.set(f"{res['metrics']['n_coeffs']:,}")
        self.c_src.set(src["name"][:28])
        n = min(len(res["x_eval"]), 40000)
        self.p_psd.set_figure(figs.psd_fig(
            {tr("实测输出"): res["y_eval"][:n],
             tr("模型预测"): res["pred"][:n]},
            src["fs"]))
        self.p_amam.set_figure(figs.amam_fig(res["x_eval"][:n],
                                             res["pred"][:n]))
        self._last = (res, cfg, name)
        self.save_btn.setEnabled(True)
        self.msg.setText(tr("✅ {name} 已注册").format(name=name))

    def run_gain_mod(self):
        self.gm_run.setEnabled(False)
        self.gm_msg.setText(tr("阶跃响应实验运行中…"))
        # snapshot widget values on the GUI thread (worker thread below)
        dut = self.gm_dut.currentText()
        drive = self.gm_drive.value()
        fit_state = self.gm_fit.isChecked()

        def job(on_progress=None):
            return services.run_gain_modulation(dut=dut, drive=drive,
                                                fit_state_model=fit_state)

        self._gm_worker = FnWorker(job)
        self._gm_worker.done.connect(self._finish_gain_mod)
        self._gm_worker.failed.connect(
            lambda e: (self.gm_msg.setText(f"❌ {e}"),
                       self.gm_run.setEnabled(True)))
        self._gm_worker.start()

    def _finish_gain_mod(self, res):
        self.gm_run.setEnabled(True)
        self.p_gm.set_figure(figs.gain_modulation_fig(res))
        self.tabs.setCurrentWidget(self.p_gm)
        name, cfg, metrics = services.gain_mod_run_record(res)
        self.state.runstore.add(Run(name=name, kind="pa_model", config=cfg,
                                    metrics=metrics))
        if not res["significant"]:
            self.gm_msg.setText(tr(
                "无增益调制(垂降 {d:+.3f} dB / {p:+.2f}°)——纯 SMP/"
                "SplineGMP 即可;已注册为 run。").format(
                d=res["droop_db"], p=res["phase_drift_deg"]))
            return
        taus = ", ".join(f"{t:.1f}µs(权重 {w:.2f})" for t, w in
                         zip(res["taus_heat_us"], res["weights_heat"],
                             strict=True))
        extra = ""
        if res["state_gain_db"] is not None:
            extra = tr(";状态样条 vs 纯 SMP:{a:.1f} → {b:.1f} dB"
                       "(+{g:.1f} dB)").format(
                a=res["nmse_plain_db"], b=res["nmse_state_db"],
                g=res["state_gain_db"])
        hyst = (tr("迟滞比 {h:.2f}").format(h=res["hysteresis_ratio"])
                if res["hysteresis_reliable"] else
                tr("迟滞比 {h:.2f}(观测窗仅 {o:.0f} µs,不足以判定,"
                   "加长 t_obs 再看)").format(
                    h=res["hysteresis_ratio"], o=res["observation_us"]))
        self.gm_msg.setText(tr(
            "垂降 {d:+.2f} dB / {p:+.1f}°;加热 τ:{taus};{hyst}"
            "{extra};已注册为 run。").format(
            d=res["droop_db"], p=res["phase_drift_deg"], taus=taus,
            hyst=hyst, extra=extra))

    def save(self):
        if not self._last:
            return
        res, cfg, name = self._last
        ext = ".pt" if cfg["family"] == "neural" else ".npz"
        path, _ = QFileDialog.getSaveFileName(
            self, tr("保存模型"), f"models/qt_{name.split(' @')[0]}{ext}",
            f"checkpoint (*{ext})")
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            res["model"].save(path)
            self.msg.setText(tr("💾 已保存 {path}").format(path=path))
