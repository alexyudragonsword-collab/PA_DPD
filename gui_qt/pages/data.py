from pathlib import Path

from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QTabWidget, QVBoxLayout, QWidget)

from gui_core import services
from gui_qt import figs
from gui_qt.common import (FigurePane, MetricCard, card_row, get_state,
                           page_scaffold, tr)


class DataPage(QWidget):
    def __init__(self):
        super().__init__()
        page, lay = page_scaffold(
            tr("数据管理"),
            tr("加载实测/仿真 PA 数据并注册为数据源:OpenDPD 数据集目录、"
               "Cadence CSV、MATLAB .mat、IQDataset .npz;可选自动延迟对齐。"))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        self.state = get_state()

        grp = QGroupBox(tr("加载"))
        gl = QHBoxLayout(grp)
        self.root = QLineEdit(services.default_opendpd_dir())
        self.root.setPlaceholderText(tr("选择 OpenDPD 的 datasets 目录"))
        self.btn_browse = QPushButton(tr("浏览…"))
        self.ds = QComboBox()
        self.btn_scan = QPushButton(tr("扫描目录"))
        self.btn_load_ds = QPushButton(tr("加载数据集"))
        self.btn_load_ds.setObjectName("primary")
        self.btn_file = QPushButton(tr("打开文件 (CSV/.mat/.npz)…"))
        self.btn_complete_ex = QPushButton(tr("载入完整源示例"))
        self.btn_complete_ex.setToolTip(
            tr("examples/complete_source_demo.npz:含 burst/step/cal_rx/"
               "atten/多工况 五个采集组的完整实测源容器示例"))
        self.align = QCheckBox(tr("自动延迟对齐"))
        gl.addWidget(QLabel(tr("OpenDPD 目录")))
        gl.addWidget(self.root, 2)
        gl.addWidget(self.btn_browse)
        gl.addWidget(self.btn_scan)
        gl.addWidget(self.ds, 1)
        gl.addWidget(self.btn_load_ds)
        gl.addWidget(self.btn_file)
        gl.addWidget(self.btn_complete_ex)
        gl.addWidget(self.align)
        lay.addWidget(grp)

        tt = QGroupBox(tr("双音记忆诊断"))
        ttl = QHBoxLayout(tt)
        self.btn_tt = QPushButton(tr("载入双音 IM3 表 (CSV)…"))
        self.btn_tt_ex = QPushButton(tr("载入示例"))
        self.tt_msg = QLabel(tr("载入双音扫音间距的 IM3 表(电路仿真或实测),"
                                "用记忆强度预判 DPD 该预留多少记忆;系数仍用"
                                "实测训练。"))
        self.tt_msg.setWordWrap(True)
        ttl.addWidget(self.btn_tt)
        ttl.addWidget(self.btn_tt_ex)
        ttl.addWidget(self.tt_msg, 1)
        lay.addWidget(tt)

        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel(tr("已注册数据源")))
        self.sel = QComboBox()
        self.btn_rm = QPushButton(tr("移除"))
        sel_row.addWidget(self.sel, 1)
        sel_row.addWidget(self.btn_rm)
        w = QWidget()
        w.setLayout(sel_row)
        lay.addWidget(w)

        self.c_fs = MetricCard(tr("采样率"))
        self.c_n = MetricCard("train / val / test")
        self.c_bw = MetricCard(tr("主带宽"))
        self.c_mod = MetricCard(tr("调制 / 子信道"))
        lay.addWidget(card_row([self.c_fs, self.c_n, self.c_bw, self.c_mod]))

        ex_row = QHBoxLayout()
        self.extras_lbl = QLabel("")
        self.extras_lbl.setWordWrap(True)
        self.btn_consume = QPushButton(tr("运行完整源工具"))
        self.btn_consume.setToolTip(
            tr("对当前源可用的采集组一键跑:τ 辨识、状态样条对比、"
               "RX 去嵌标定、跨工况调度器"))
        self.btn_consume.hide()
        ex_row.addWidget(self.extras_lbl, 1)
        ex_row.addWidget(self.btn_consume)
        w2 = QWidget()
        w2.setLayout(ex_row)
        lay.addWidget(w2)

        self.tabs = QTabWidget()
        self.p_psd, self.p_amam, self.p_tt = (FigurePane(), FigurePane(),
                                              FigurePane())
        self.tabs.addTab(self.p_psd, "PSD")
        self.tabs.addTab(self.p_amam, "AM-AM / AM-PM")
        self.tabs.addTab(self.p_tt, tr("双音 IM3"))
        lay.addWidget(self.tabs, 1)
        self.msg = QLabel("")
        lay.addWidget(self.msg)

        self.btn_browse.clicked.connect(self.browse)
        self.btn_scan.clicked.connect(self.scan)
        self.btn_load_ds.clicked.connect(self.load_ds)
        self.btn_file.clicked.connect(self.load_file)
        self.btn_tt.clicked.connect(self.load_two_tone)
        self.btn_tt_ex.clicked.connect(
            lambda: self.load_two_tone(services.EXAMPLE_TWO_TONE_CSV))
        self.btn_complete_ex.clicked.connect(self.load_complete_example)
        self.btn_consume.clicked.connect(self.consume_extras)
        self.btn_rm.clicked.connect(self.remove)
        self.sel.currentTextChanged.connect(self.preview)
        self.scan()

    def browse(self):
        start = self.root.text() if Path(self.root.text()).is_dir() else ""
        path = QFileDialog.getExistingDirectory(
            self, tr("选择 OpenDPD 的 datasets 目录"), start)
        if path:
            self.root.setText(path)
            self.scan()

    def scan(self):
        self.ds.clear()
        root = Path(self.root.text())
        if root.is_dir():
            names = sorted(p.name for p in root.iterdir()
                           if (p / "spec.json").exists())
            self.ds.addItems(names)
            self.msg.setText(
                tr("扫描到 {n} 个数据集").format(n=len(names)) if names
                else tr("该目录下没有 OpenDPD 数据集(缺 spec.json)"))
        else:
            self.msg.setText(tr("目录不存在:{path}").format(
                path=self.root.text()))

    def load_ds(self):
        name = self.ds.currentText()
        if not name:
            return
        try:
            src = services.load_source(
                "opendpd", str(Path(self.root.text()) / name))
            self._register(src)
        except Exception as e:
            self.msg.setText(tr("❌ 加载失败:{e}").format(e=e))

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("打开数据文件"), "",
            tr("数据 (*.csv *.mat *.npz);;全部 (*)"))
        if not path:
            return
        kind = {"csv": "cadence", "mat": "mat",
                "npz": "npz"}[Path(path).suffix[1:]]
        try:
            src = services.load_source(kind, path,
                                       auto_align=self.align.isChecked())
            src["name"] = Path(path).name
            self._register(src)
            if src.get("align_info"):
                self.msg.setText(tr("对齐:延迟 {lag:.2f} 采样").format(
                    lag=src["align_info"]["lag_total"]))
        except Exception as e:
            self.msg.setText(tr("❌ 加载失败:{e}").format(e=e))

    def load_complete_example(self):
        try:
            src = services.load_source("npz",
                                       services.EXAMPLE_COMPLETE_NPZ)
            self._register(src)
        except Exception as e:
            self.msg.setText(tr("❌ 加载失败:{e}").format(e=e))

    def consume_extras(self):
        name = self.sel.currentText()
        src = self.state.sources.get(name)
        if not src or not src.get("extras"):
            return
        self.btn_consume.setEnabled(False)
        self.msg.setText(tr("完整源工具运行中…"))
        from gui_qt.common import FnWorker

        def job(on_progress=None):
            return services.consume_source_extras(src)

        self._cx_worker = FnWorker(job)
        self._cx_worker.done.connect(self._finish_consume)
        self._cx_worker.failed.connect(
            lambda e: (self.msg.setText(f"❌ {e}"),
                       self.btn_consume.setEnabled(True)))
        self._cx_worker.start()

    def _finish_consume(self, out):
        self.btn_consume.setEnabled(True)
        bits = []
        gm = out.get("gain_mod")
        if gm and gm["significant"]:
            taus = "/".join(f"{t:.1f}" for t in gm["taus_heat_us"])
            bits.append(tr("τ 辨识 {taus} µs").format(taus=taus))
        st = out.get("state_fit")
        if st:
            bits.append(tr("状态样条 {a:.1f}→{b:.1f} dB(+{g:.1f})").format(
                a=st["nmse_plain_db"], b=st["nmse_state_db"],
                g=st["state_gain_db"]))
        de = out.get("deembed")
        if de:
            bits.append(tr("RX 标定 IRR {irr:.1f} dB · IM3 {im3:.1f} dBc")
                        .format(irr=de["rx_irr_db"] or float("nan"),
                                im3=de["rx_im3_dbc"] or float("nan")))
        sc = out.get("scheduler")
        if sc:
            bits.append(tr("调度器 {n} 工况点").format(
                n=len(sc["conditions"])))
        errs = [v for k, v in out.items() if k.endswith("_error")]
        if errs:
            bits.append("⚠ " + "; ".join(errs))
        self.msg.setText("✅ " + ";".join(bits) if bits
                         else tr("该源没有可消费的采集组"))

    def load_two_tone(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self, tr("载入双音 IM3 表"), "", tr("CSV (*.csv);;全部 (*)"))
            if not path:
                return
        try:
            res = services.analyze_two_tone_csv(path)
        except Exception as e:
            self.tt_msg.setText(tr("❌ 加载失败:{e}").format(e=e))
            return
        self.tt_msg.setText(tr(
            "记忆强度 {ms:.1f} dB → 建议记忆深度 {d}、交叉项 {cx}"
            "(约 {nc} 系数);热记忆 {th}。系数仍用实测训练。").format(
            ms=res["memory_strength_db"], d=res["memory_depth"],
            cx=(tr("需要") if res["use_cross_terms"] else tr("不需要")),
            nc=res["est_coeffs"],
            th=(tr("疑似") if res["thermal_suspected"] else tr("无"))))
        self.p_tt.set_figure(figs.two_tone_fig(res))
        self.tabs.setCurrentWidget(self.p_tt)

    def _register(self, src):
        self.state.sources[src["name"]] = src
        self.sel.blockSignals(True)
        self.sel.clear()
        self.sel.addItems(list(self.state.sources))
        self.sel.setCurrentText(src["name"])
        self.sel.blockSignals(False)
        self.msg.setText(tr("✅ 已注册:{name}").format(name=src["name"]))
        self.preview(src["name"])

    def preview(self, name):
        src = self.state.sources.get(name)
        if not src:
            return
        prev = services.source_preview(src)
        spec = src.get("spec") or {}
        self.c_fs.set(f"{src['fs']/1e6:.2f} MSPS")
        self.c_n.set(f"{prev['n_train']:,} / {prev['n_val']:,} / "
                     f"{prev['n_test']:,}")
        self.c_bw.set(f"{(src.get('bw') or 0)/1e6:.0f} MHz"
                      if src.get("bw") else "—")
        self.c_mod.set(f"{spec.get('modulation','—')} / "
                       f"{spec.get('n_sub_ch','—')}")
        n = min(len(src["x_train"]), 65536)
        self.p_psd.set_figure(figs.psd_fig(
            {tr("PA 输入"): src["x_train"][:n],
             tr("PA 输出"): src["y_train"][:n]},
            src["fs"]))
        self.p_amam.set_figure(figs.amam_fig(src["x_train"][:n],
                                             src["y_train"][:n]))
        if src.get("extras"):
            names = {"burst": tr("突发"), "step": tr("阶跃探针"),
                     "cal_rx": tr("旁路标定"), "atten": tr("衰减步进"),
                     "operating_points": tr("多工况")}
            parts = [("✓ " if r["present"] else "✗ ")
                     + names[r["group"]]
                     for r in services.source_extras_rows(src)]
            self.extras_lbl.setText(tr("完整源采集组:") + " · ".join(parts))
            self.btn_consume.show()
        else:
            self.extras_lbl.setText("")
            self.btn_consume.hide()

    def remove(self):
        name = self.sel.currentText()
        if name in self.state.sources:
            del self.state.sources[name]
            self.sel.clear()
            self.sel.addItems(list(self.state.sources))
