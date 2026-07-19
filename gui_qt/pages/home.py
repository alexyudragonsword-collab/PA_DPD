from pathlib import Path

from PySide6.QtWidgets import (QLabel, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from gui_core import services
from gui_qt.common import (MetricCard, card_row, get_state, page_scaffold,
                           tr)


class HomePage(QWidget):
    def __init__(self):
        super().__init__()
        page, lay = page_scaffold(
            tr("padpd 工作台总览"),
            tr("WiFi 7(802.11be)PA 行为建模与数字预失真研发平台:经典与神经"
               "模型、ILA/DLA 预失真、CFR、定点部署与 PA/DPD 联合设计。"))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        lay.addWidget(QLabel(tr("代表性成果(实测)")))
        lay.addWidget(card_row([
            MetricCard(tr("合成链路 DPD 后 EVM"), "-57.4 dB",
                       "160 MHz/1024-QAM"),
            MetricCard(tr("TCN vs GMP(真实数据)"), "-34.9 dB",
                       tr("超经典基线")),
            MetricCard("DPA_160 DLA DPD", "-53.1 dBc",
                       tr("过 -52 验收线")),
            MetricCard(tr("APA 代理重评"), "-38.56 dBc",
                       tr("≈发表值 -38.80"))]))

        lay.addWidget(QLabel(tr("环境自检")))
        self.env = QLabel()
        self.env.setWordWrap(True)
        lay.addWidget(self.env)

        lay.addWidget(QLabel(tr("最近实验")))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [tr("时间"), tr("名称"), tr("类型"), tr("指标")])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(1, 380)
        self.table.setAlternatingRowColors(True)
        lay.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
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
        n_models = len(list(Path("models").glob("*"))) \
            if Path("models").is_dir() else 0
        runs = get_state().runstore.list()
        parts.append(f"ℹ️ checkpoint × {n_models} · run × {len(runs)}")
        self.env.setText("   ".join(parts))

        self.table.setRowCount(0)
        for r in runs[:8]:
            row = self.table.rowCount()
            self.table.insertRow(row)
            metr = " · ".join(f"{k}={v:.1f}" for k, v in r.metrics.items()
                              if isinstance(v, float))[:60]
            for c, text in enumerate([r.when, r.name, r.kind, metr]):
                self.table.setItem(row, c, QTableWidgetItem(text))
