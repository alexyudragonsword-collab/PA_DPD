import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from gui_qt import figs
from gui_qt.common import FigurePane, get_state, page_scaffold, tr


class ComparePage(QWidget):
    def __init__(self):
        super().__init__()
        # instance attr (not class-level) so tr() sees the current language
        self.COLS = ["✓", tr("时间"), tr("名称"), tr("类型"), "nmse_db",
                     "evm_db", "aclr_high_dbc"]
        page, lay = page_scaffold(
            tr("结果比较"),
            tr("勾选 run 进行对比;注册表持久化于 gui_runs/,与 Web 版共享。"))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        self.state = get_state()

        bar = QHBoxLayout()
        self.btn_cmp = QPushButton(tr("对比选中"))
        self.btn_cmp.setObjectName("primary")
        self.btn_del = QPushButton(tr("删除选中"))
        self.btn_exp = QPushButton(tr("导出 JSON…"))
        self.btn_refresh = QPushButton(tr("刷新"))
        for b in (self.btn_cmp, self.btn_del, self.btn_exp,
                  self.btn_refresh):
            bar.addWidget(b)
        bar.addStretch(1)
        w = QWidget()
        w.setLayout(bar)
        lay.addWidget(w)

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.setColumnWidth(2, 360)
        self.table.setAlternatingRowColors(True)
        lay.addWidget(self.table, 1)

        self.pane = FigurePane(320)
        lay.addWidget(self.pane)
        self.msg = QLabel("")
        lay.addWidget(self.msg)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_cmp.clicked.connect(self.compare)
        self.btn_del.clicked.connect(self.delete)
        self.btn_exp.clicked.connect(self.export)
        self.refresh()

    def refresh(self):
        self._runs = self.state.runstore.list()
        self.table.setRowCount(0)
        for r in self._runs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                         | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, chk)
            vals = [r.when, r.name, r.kind,
                    r.metrics.get("nmse_db"), r.metrics.get("evm_db"),
                    r.metrics.get("aclr_high_dbc")]
            for c, v in enumerate(vals, start=1):
                text = f"{v:.2f}" if isinstance(v, float) else \
                    ("" if v is None else str(v))
                self.table.setItem(row, c, QTableWidgetItem(text))

    def _picked(self):
        return [r for i, r in enumerate(self._runs)
                if self.table.item(i, 0).checkState()
                == Qt.CheckState.Checked]

    def compare(self):
        picked = self._picked()
        if len(picked) < 2:
            self.msg.setText(tr("至少勾选 2 项"))
            return
        names = [r.name for r in picked]
        keys = [k for k in ("nmse_db", "evm_db", "aclr_high_dbc")
                if any(isinstance(r.metrics.get(k), (int, float))
                       for r in picked)]
        series = {k: [r.metrics.get(k) for r in picked] for k in keys}
        self.pane.set_figure(figs.bars_fig(names, series))
        self.msg.setText(tr("对比 {n} 项").format(n=len(picked)))

    def delete(self):
        for r in self._picked():
            self.state.runstore.delete(r.run_id)
        self.refresh()

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("导出"),
                                              "padpd_runs.json",
                                              "JSON (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump([{"name": r.name, "kind": r.kind,
                            "config": r.config, "metrics": r.metrics,
                            "time": r.when} for r in self._runs],
                          f, indent=1, ensure_ascii=False, default=str)
            self.msg.setText(f"💾 {path}")
