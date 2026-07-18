import numpy as np
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                               QFileDialog, QGroupBox, QHBoxLayout, QLabel,
                               QPushButton, QSpinBox, QTabWidget,
                               QVBoxLayout, QWidget)

from gui_core import services
from gui_qt import figs
from gui_qt.common import (FigurePane, MetricCard, card_row, hline,
                           page_scaffold)


class WaveformPage(QWidget):
    def __init__(self):
        super().__init__()
        page, lay = page_scaffold(
            "波形工作台",
            "生成 802.11be 风格 OFDM 基带波形;PSD / CCDF / 星座 / 时域;"
            "可选 CFR 削峰对比;可导出 IQDataset (.npz)。")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        form = QGroupBox("波形参数")
        fl = QHBoxLayout(form)
        self.bw = QComboBox()
        self.bw.addItems(["20", "40", "80", "160", "320"])
        self.bw.setCurrentText("80")
        self.qam = QComboBox()
        self.qam.addItems(["16", "64", "256", "1024", "4096"])
        self.qam.setCurrentText("1024")
        self.sym = QSpinBox()
        self.sym.setRange(2, 40)
        self.sym.setValue(8)
        self.seed = QSpinBox()
        self.seed.setRange(0, 9999)
        self.cfr_on = QCheckBox("CFR 削峰")
        self.cfr = QDoubleSpinBox()
        self.cfr.setRange(5.0, 10.0)
        self.cfr.setValue(8.0)
        self.cfr.setSingleStep(0.5)
        self.gen = QPushButton("生成波形")
        self.gen.setObjectName("primary")
        self.export = QPushButton("导出 .npz")
        self.export.setEnabled(False)
        for lbl, w in [("带宽(MHz)", self.bw), ("QAM", self.qam),
                       ("符号数", self.sym), ("种子", self.seed)]:
            fl.addWidget(QLabel(lbl))
            fl.addWidget(w)
        fl.addWidget(self.cfr_on)
        fl.addWidget(self.cfr)
        fl.addStretch(1)
        fl.addWidget(self.gen)
        fl.addWidget(self.export)
        lay.addWidget(form)

        self.c_fs = MetricCard("采样率")
        self.c_fft = MetricCard("FFT / 有效子载波")
        self.c_papr = MetricCard("PAPR")
        self.c_cfr = MetricCard("CFR 后 PAPR / EVM 代价")
        lay.addWidget(card_row([self.c_fs, self.c_fft, self.c_papr,
                                self.c_cfr]))

        self.tabs = QTabWidget()
        self.p_psd, self.p_ccdf = FigurePane(), FigurePane()
        self.p_const, self.p_time = FigurePane(), FigurePane()
        for pane, name in [(self.p_psd, "PSD"), (self.p_ccdf, "CCDF"),
                           (self.p_const, "星座"), (self.p_time, "时域")]:
            self.tabs.addTab(pane, name)
        lay.addWidget(self.tabs, 1)

        self.gen.clicked.connect(self.generate)
        self.export.clicked.connect(self.do_export)
        self._w = None

    def generate(self):
        cfr = self.cfr.value() if self.cfr_on.isChecked() else None
        self._w = services.make_waveform(
            float(self.bw.currentText()) * 1e6,
            int(self.qam.currentText()), self.sym.value(),
            self.seed.value(), cfr)
        w, wf = self._w, self._w["wf"]
        self.c_fs.set(f"{w['fs']/1e6:.0f} MSPS",
                      f"{wf.config.oversampling}× 过采样")
        self.c_fft.set(f"{wf.config.fft_size} / {wf.config.n_active}")
        self.c_papr.set(f"{w['papr_db']:.2f} dB")
        self.c_cfr.set(f"{w['papr_cfr_db']:.2f} dB /"
                       f" {w['cfr_evm_db']:.1f} dB"
                       if w["papr_cfr_db"] is not None else "—")
        sig = {"原始波形": w["x"]}
        if w["x_cfr"] is not None:
            sig["CFR 后"] = w["x_cfr"]
        self.p_psd.set_figure(figs.psd_fig(sig, w["fs"]))
        self.p_ccdf.set_figure(figs.ccdf_fig(sig))
        self.p_const.set_figure(
            figs.constellation_fig({"发送星座": wf.tx_symbols.ravel()}))
        self.p_time.set_figure(figs.time_fig(sig, w["fs"]))
        self.export.setEnabled(True)

    def do_export(self):
        if not self._w:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出波形", "waveform.npz", "IQDataset (*.npz)")
        if path:
            x = (self._w["x_cfr"] if self._w["x_cfr"] is not None
                 else self._w["x"])
            np.savez_compressed(path, x=x, y=x,
                                sample_rate_hz=self._w["fs"],
                                meta=np.array(repr({"source": "qt-gui"})))
