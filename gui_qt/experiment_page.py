"""One page template for every experiment.

Setup on the left, generated from the schema; results on the right, in
the order an engineer reads them: verdicts against the spec, supporting
numbers, charts, the before/after table, and where the result came from.

Three things the old pages got wrong and this template makes structural:

- **A result stays attached to its inputs.** Editing an input after a run
  marks the result stale instead of leaving it on screen as if it were
  current; "reproduce" puts the inputs that made it back into the form.
- **Pass and fail come from the spec, not the page.** Tiles render the
  verdicts ``gui_core.experiments`` computed; a page cannot colour a fail
  green, and changing the spec re-judges a stored result without
  re-running it.
- **Language and theme switch in place.** The stored outcome is
  re-presented; nothing is recomputed or lost.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui_core import chart_spec, experiments
from gui_qt import common
from gui_qt.chartview import ChartView
from gui_qt.common import FnWorker, tr
from gui_qt.form import ParamForm

SETUP_WIDTH = 296
_NUMERIC = re.compile(r"^[-+−]?[\d.,]+( ?[a-zA-Z%/]+)*( [↑↓])?$")


def clear_layout(lay):
    while lay.count():
        it = lay.takeAt(0)
        w = it.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        elif it.layout() is not None:
            clear_layout(it.layout())


def fmt_value(v, unit: str) -> str:
    if v is None:
        return "—"
    if unit == "bit" or (float(v).is_integer() and abs(v) >= 100):
        return f"{v:.0f}"
    if unit == "":
        return f"{v:.3f}"
    return f"{v:.1f}"


def label(text: str = "", name: str = "", wrap: bool = True) -> QLabel:
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


class VerdictTile(QFrame):
    """One check against the spec: value, limit, margin, pass/fail, and
    the baseline it improved on."""

    def __init__(self, d: dict):
        super().__init__()
        self.setObjectName("tile")
        self.d = d
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        stripe = QFrame()
        stripe.setFixedWidth(4)
        t = common.PREFS["theme"]
        from gui_qt.theme import TOKENS
        color = (TOKENS[t]["good"] if d["ok"] is True else
                 TOKENS[t]["bad"] if d["ok"] is False else
                 TOKENS[t]["neutral_stripe"])
        stripe.setStyleSheet(f"background: {color}; border: 0;"
                             "border-top-left-radius: 8px;"
                             "border-bottom-left-radius: 8px;")
        outer.addWidget(stripe)
        body = QVBoxLayout()
        body.setContentsMargins(12, 10, 12, 10)
        body.setSpacing(2)
        outer.addLayout(body, 1)

        head = QHBoxLayout()
        head.addWidget(label(d["label"], "tileLabel"), 1)
        if d["ok"] is not None:
            head.addWidget(self._pill(d["ok"]), 0, Qt.AlignmentFlag.AlignTop)
        body.addLayout(head)
        val = QHBoxLayout()
        val.setSpacing(4)
        text = fmt_value(d["value"], d["unit"])
        if d["limit"] is not None and not d["lower_is_better"] \
                and d["value"] is not None and d["value"] > 0:
            text = "+" + text            # a margin reads with its sign
        self.value = label(text, "tileValue", wrap=False)
        val.addWidget(self.value)
        val.addWidget(label(d["unit"], "tileUnit", wrap=False), 0,
                      Qt.AlignmentFlag.AlignBottom)
        val.addStretch(1)
        body.addLayout(val)
        meta = []
        if d["limit"] is not None:
            op = "≤" if d["lower_is_better"] else "≥"
            meta.append(tr("限值") + f" {op} {d['limit']:g} {d['unit']}")
            meta.append(tr("余量") + f" {d['margin']:+.1f}")
        if d.get("note"):
            meta.append(d["note"])
        if meta:
            body.addWidget(label(" · ".join(meta), "tileMeta"))
        if d.get("was") is not None:
            row = QHBoxLayout()
            row.setSpacing(6)
            row.addWidget(label(tr("对照") + " "
                                + fmt_value(d["was"], d["unit"]),
                                "tileMeta", wrap=False))
            if d.get("was_ok") is not None:
                row.addWidget(self._pill(d["was_ok"]))
            row.addStretch(1)
            body.addLayout(row)
        body.addStretch(1)

    @staticmethod
    def _pill(ok: bool) -> QLabel:
        p = QLabel(("✓ " + tr("通过")) if ok else ("✗ " + tr("不通过")))
        p.setObjectName("pillPass" if ok else "pillFail")
        return p


class MetricCard(QFrame):
    def __init__(self, m: dict):
        super().__init__()
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(1)
        lay.addWidget(label(m["label"], "tileLabel"))
        self.value = label(m["value"], "metricValue")
        lay.addWidget(self.value)
        if m.get("note"):
            lay.addWidget(label(m["note"], "tileMeta"))


def make_table(rows: list[dict]) -> QTableWidget:
    cols: list[str] = []
    for r in rows:
        cols += [k for k in r if k not in cols]
    t = QTableWidget(len(rows), len(cols))
    t.setHorizontalHeaderLabels(cols)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    t.setAlternatingRowColors(True)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    for i, r in enumerate(rows):
        for j, c in enumerate(cols):
            text = str(r.get(c, ""))
            it = QTableWidgetItem(text)
            if j and _NUMERIC.match(text):
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                    | Qt.AlignmentFlag.AlignVCenter)
            t.setItem(i, j, it)
    hh = t.horizontalHeader()
    hh.setMinimumSectionSize(48)
    if len(cols) <= 6:
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        if cols:
            hh.setSectionResizeMode(0,
                                    QHeaderView.ResizeMode.ResizeToContents)
    else:
        # wide tables scroll sideways rather than squeeze every column
        # into an unreadable stub
        t.setWordWrap(False)
        hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hh.setStretchLastSection(True)
    t.resizeRowsToContents()
    h = hh.height() + sum(t.rowHeight(i) for i in range(len(rows))) + 4
    if len(cols) > 6:
        h += t.horizontalScrollBar().sizeHint().height()
    t.setFixedHeight(min(h, 340))
    return t


class ResultsView(QWidget):
    """Renders a presented outcome. Used by the experiment page and by
    any page that shows a stored result."""

    def __init__(self):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(12)
        self.charts: list[ChartView] = []
        self.tabs: QTabWidget | None = None

    def show_empty(self, text: str):
        clear_layout(self.lay)
        self.charts, self.tabs = [], None
        box = QFrame()
        box.setObjectName("card")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(20, 28, 20, 28)
        bl.addWidget(label(text, "muted"))
        self.lay.addWidget(box)
        self.lay.addStretch(1)

    def render(self, shown: dict, chart_titles: dict, lang: str, theme: str):
        keep_tab = self.tabs.currentIndex() if self.tabs is not None else 0
        clear_layout(self.lay)
        self.charts = []
        if shown["verdicts"]:
            grid = QGridLayout()
            grid.setSpacing(10)
            n = len(shown["verdicts"])
            cols = 3 if n >= 3 else n
            for i, d in enumerate(shown["verdicts"]):
                grid.addWidget(VerdictTile(d), i // cols, i % cols)
            for c in range(cols):
                grid.setColumnStretch(c, 1)
            self.lay.addLayout(grid)
        # a metric that repeats a verdict tile adds nothing
        seen = {d["label"] for d in shown["verdicts"]}
        metrics = [m for m in shown["metrics"] if m["label"] not in seen]
        if metrics:
            grid = QGridLayout()
            grid.setSpacing(8)
            cols = 4
            for i, m in enumerate(metrics):
                grid.addWidget(MetricCard(m), i // cols, i % cols)
            for c in range(cols):
                grid.setColumnStretch(c, 1)
            self.lay.addLayout(grid)
        if shown.get("callout"):
            self.lay.addWidget(label(shown["callout"], "callout"))
        if shown["charts"]:
            self.tabs = QTabWidget()
            self.tabs.setDocumentMode(True)
            for slot, (name, args, kwargs) in shown["charts"].items():
                spec, blobs = chart_spec.build(name, *args, lang=lang,
                                               **kwargs)
                cv = ChartView()
                cv.setMinimumHeight(340)
                cv.set_spec(spec, blobs, theme)
                self.charts.append(cv)
                title = chart_titles.get(slot)
                self.tabs.addTab(cv, tr(title) if title else slot)
            if keep_tab < self.tabs.count():
                self.tabs.setCurrentIndex(keep_tab)
            hint = label(tr("拖选一段放大,双击复原;悬停读数。"), "help")
            box = QFrame()
            box.setObjectName("card")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(10, 6, 10, 8)
            bl.addWidget(self.tabs)
            bl.addWidget(hint)
            self.lay.addWidget(box)
        else:
            self.tabs = None
        if shown["rows"]:
            self.lay.addWidget(make_table(shown["rows"]))
        for n in shown["notes"]:
            self.lay.addWidget(label(n, "note"))


class ExperimentPage(QWidget):
    """Setup | results for one ``gui_core.experiments.Experiment``."""

    ran = Signal(object)                 # Outcome
    open_compare = Signal(str)           # run kind

    def __init__(self, exp: experiments.Experiment):
        super().__init__()
        self.setObjectName("page")
        self.exp = exp
        self.outcome: experiments.Outcome | None = None
        self.error = ""
        self._worker = None
        self.footer_widgets: list[QWidget] = []

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

        # ---- setup column ------------------------------------------
        setup = QFrame()
        setup.setObjectName("setup")
        setup.setFixedWidth(SETUP_WIDTH)
        sl = QVBoxLayout(setup)
        sl.setContentsMargins(14, 12, 14, 12)
        sl.setSpacing(8)
        self.form = ParamForm(exp.params, self.ctx)
        self.form.changed.connect(self._update_stale)
        fscroll = QScrollArea()
        fscroll.setWidgetResizable(True)
        fscroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        fscroll.setWidget(self.form)
        fscroll.setFrameShape(QFrame.Shape.NoFrame)
        sl.addWidget(fscroll, 1)
        self.run_btn = QPushButton()
        self.run_btn.setObjectName("primary")
        self.run_btn.clicked.connect(self.run)
        sl.addWidget(self.run_btn)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()
        sl.addWidget(self.progress)
        self.status = label("", "help")
        sl.addWidget(self.status)
        body.addWidget(setup, 0)

        # ---- results column ----------------------------------------
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        holder = QWidget()
        hl = QVBoxLayout(holder)
        hl.setContentsMargins(0, 0, 6, 0)
        hl.setSpacing(12)
        self.stale = QFrame()
        self.stale.setObjectName("stale")
        stl = QHBoxLayout(self.stale)
        stl.setContentsMargins(12, 8, 12, 8)
        self.stale_text = label("", "")
        self.stale_btn = QPushButton()
        self.stale_btn.clicked.connect(self.run)
        stl.addWidget(self.stale_text, 1)
        stl.addWidget(self.stale_btn)
        self.stale.hide()
        hl.addWidget(self.stale)
        self.err = label("", "error")
        self.err.hide()
        hl.addWidget(self.err)
        self.results = ResultsView()
        hl.addWidget(self.results)
        self.prov = QFrame()
        self.prov.setObjectName("prov")
        pl = QVBoxLayout(self.prov)
        pl.setContentsMargins(0, 8, 0, 0)
        pl.setSpacing(6)
        top = QHBoxLayout()
        self.prov_head = label("", "muted", wrap=False)
        self.prov_id = label("", "runId", wrap=False)
        self.prov_id.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self.prov_text = label("", "muted")
        top.addWidget(self.prov_head)
        top.addWidget(self.prov_id)
        top.addWidget(self.prov_text, 1)
        pl.addLayout(top)
        acts = QHBoxLayout()
        acts.addStretch(1)
        self.btn_repro = QPushButton()
        self.btn_repro.clicked.connect(self.reproduce)
        self.btn_cmp = QPushButton()
        self.btn_cmp.clicked.connect(
            lambda: self.open_compare.emit(self._run_kind()))
        acts.addWidget(self.btn_repro)
        acts.addWidget(self.btn_cmp)
        self.action_btns = []
        for aid, _lab in exp.actions:
            b = QPushButton()
            b.clicked.connect(lambda _c=False, a=aid: ACTIONS[a](self))
            acts.addWidget(b)
            self.action_btns.append(b)
        pl.addLayout(acts)
        self.prov.hide()
        hl.addWidget(self.prov)
        self.footer = QVBoxLayout()
        self.footer.setSpacing(8)
        hl.addLayout(self.footer)
        hl.addStretch(1)
        self.scroll.setWidget(holder)
        body.addWidget(self.scroll, 1)

        self.form.reload_models()
        self.retranslate()

    # ---- context -----------------------------------------------------
    def ctx(self) -> experiments.Context:
        return experiments.Context(common.state().workspace)

    def add_footer(self, w: QWidget):
        self.footer.addWidget(w)
        self.footer_widgets.append(w)

    # ---- run ---------------------------------------------------------
    def run(self):
        if self._worker is not None:
            return
        values = self.form.values()          # snapshot on the GUI thread
        ctx = self.ctx()
        store = common.state().runstore
        exp = self.exp

        def job(on_progress=None):
            return experiments.execute(exp, values, ctx,
                                       progress=on_progress, runstore=store)

        self.run_btn.setEnabled(False)
        self.stale_btn.setEnabled(False)
        self.err.hide()
        self.progress.setRange(0, 0)
        self.progress.show()
        self.status.setText(tr("运行中…"))
        self._worker = FnWorker(job)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, info: dict):
        if "of" in info:
            self.progress.setRange(0, int(info["of"]))
            self.progress.setValue(int(info.get("epoch", 0)) + 1)
            self.status.setText(f"{int(info.get('epoch', 0)) + 1}"
                                f" / {info['of']}")
            return
        bits = []
        if "epoch" in info:
            bits.append(f"epoch {int(info['epoch']) + 1}")
        for k in ("val_nmse_db", "cascade_nmse_db", "nmse_db"):
            if isinstance(info.get(k), (int, float)):
                bits.append(f"{k.split('_')[0]} {info[k]:.1f} dB")
                break
        if bits:
            self.status.setText(" · ".join(bits))

    def _finish(self):
        self._worker = None
        self.run_btn.setEnabled(True)
        self.stale_btn.setEnabled(True)
        self.progress.hide()

    def _on_done(self, out):
        self._finish()
        self.outcome, self.error = out, ""
        self.status.setText(tr("上次用时 {s:.1f} s").format(s=out.seconds))
        self.render()
        self.ran.emit(out)

    def _on_failed(self, msg: str):
        self._finish()
        self.error = msg
        self.status.setText("")
        self.err.setText("✗ " + msg)
        self.err.show()

    def wait(self, timeout_ms: int = 300000) -> bool:
        """Block until the current run finishes (tests)."""
        w = self._worker
        return True if w is None else w.wait(timeout_ms)

    # ---- render ------------------------------------------------------
    def _run_kind(self) -> str:
        if self.outcome is None or not self.outcome.run_id:
            return ""
        run = common.state().runstore.get(self.outcome.run_id)
        return run.kind if run else ""

    def render(self):
        lang, theme = common.PREFS["lang"], common.PREFS["theme"]
        if self.outcome is None:
            self.results.show_empty(
                tr("设定左侧参数后点「运行」。结果会按项目 spec 判定,"
                   "并记下产生它的参数和数据源。"))
            self.prov.hide()
            self._update_stale()
            return
        shown = experiments.present(self.outcome, self.ctx(), lang)
        self.results.render(shown, self.exp.chart_titles, lang, theme)
        o = self.outcome
        self.prov_head.setText(tr("来源"))
        self.prov_id.setText(f"run {o.run_id}" if o.run_id else "—")
        self.prov_id.setVisible(bool(o.run_id))
        parts = [describe_values(self.exp, o.values)]
        if o.source_name:
            parts.append(o.source_name)
        parts.append(tr("用时 {s:.1f} s").format(s=o.seconds))
        self.prov_text.setText(" · ".join(p for p in parts if p))
        self.btn_cmp.setVisible(bool(o.run_id))
        self.prov.show()
        self._update_stale()

    def _update_stale(self):
        o = self.outcome
        if o is None:
            self.stale.hide()
            return
        ctx = self.ctx()
        now = experiments.effective_values(self.exp, self.form.values(), ctx)
        reasons = []
        if _normalise(now) != _normalise(o.values):
            reasons.append(tr("输入已改动"))
        if self.exp.uses_source and o.source_name \
                and o.source_name != ctx.workspace.active_source:
            reasons.append(tr("数据源已切换"))
        self.stale_text.setText(
            "⚠ " + ";".join(reasons) + " — "
            + tr("下面是上一次运行的结果。") if reasons else "")
        self.stale.setVisible(bool(reasons))

    def reproduce(self):
        if self.outcome is not None:
            self.form.set_values(self.outcome.values)
            self._update_stale()

    # ---- in-place switches --------------------------------------------
    def retranslate(self):
        self.title.setText(tr(self.exp.title))
        self.summary.setText(tr(self.exp.summary))
        self.form.retranslate()
        self.run_btn.setText(tr("运行"))
        self.stale_btn.setText(tr("重新运行"))
        self.btn_repro.setText(tr("复现"))
        self.btn_repro.setToolTip(tr("把产生这个结果的参数填回左侧"))
        self.btn_cmp.setText(tr("在结果比较中打开"))
        for (_aid, lab), b in zip(self.exp.actions, self.action_btns):
            b.setText(tr(lab))
        if self.outcome is not None and not self._worker:
            self.status.setText(tr("上次用时 {s:.1f} s").format(
                s=self.outcome.seconds))
        for w in self.footer_widgets:
            if hasattr(w, "retranslate"):
                w.retranslate()
        self.render()

    def restyle(self):
        self.render()

    def workspace_changed(self):
        """Sources, models or spec changed elsewhere: refresh pickers and
        re-judge the stored result against the (maybe new) spec."""
        self.form.reload_models()
        for w in self.footer_widgets:
            if hasattr(w, "refresh"):
                w.refresh()
        if self.outcome is not None:
            self.render()
        else:
            self._update_stale()


def _normalise(v: dict) -> dict:
    out = {}
    for k, x in v.items():
        if isinstance(x, (list, tuple)):
            x = tuple(sorted(x, key=str))
        elif isinstance(x, float):
            x = round(x, 9)
        out[k] = x
    return out


def describe_values(exp, values: dict) -> str:
    """The inputs of a run in one line, in schema order."""
    from gui_qt.form import choice_text
    bits = []
    for p in exp.params:
        if p.key not in values:
            continue
        v = values[p.key]
        if p.kind == "bool":
            if v:
                bits.append(tr(p.label))
            continue
        if p.kind in ("multi", "models"):
            v = "/".join(str(x).split(" @")[0] for x in v)
        elif p.kind == "choice":
            v = choice_text(v, p.unit)
        elif p.kind == "file":
            v = Path(v).name if v else tr("内置示例")
        elif p.kind == "model":
            v = str(v).split(" @")[0] if v else "—"
        elif p.unit:
            v = f"{v} {p.unit}"
        bits.append(f"{tr(p.label)} {v}")
    return " · ".join(bits)


# ---------------------------------------------------------------------
# result actions
# ---------------------------------------------------------------------


def _export_npz(page: ExperimentPage):
    o = page.outcome
    if o is None:
        return
    path, _ = QFileDialog.getSaveFileName(
        page, tr("导出波形"), "waveform.npz", "IQDataset (*.npz)")
    if not path:
        return
    w = o.raw
    x = w["x_cfr"] if w["x_cfr"] is not None else w["x"]
    np.savez_compressed(path, x=x, y=x, sample_rate_hz=w["fs"],
                        meta=np.array(repr({"source": "padpd-desktop",
                                            "values": o.values})))
    page.status.setText("💾 " + path)


def _export_artifacts(page: ExperimentPage):
    o = page.outcome
    if o is None:
        return
    names = list(o.raw["sweeps"])
    if len(names) > 1:
        name, ok = QInputDialog.getItem(page, tr("导出交接产物…"),
                                        tr("模型"), names, 0, False)
        if not ok:
            return
    else:
        name = names[0]
    bits = [str(b) for b in o.raw["bits"]]
    b, ok = QInputDialog.getItem(page, tr("导出交接产物…"), tr("位宽"),
                                 bits, 0, False)
    if not ok:
        return
    out_dir = QFileDialog.getExistingDirectory(page, tr("选择导出目录"),
                                               "deploy_export")
    if not out_dir:
        return
    ws = common.state().workspace
    model, src = ws.model(name), ws.eval_source_for(name)
    dest = str(Path(out_dir) / name.split(" @")[0].replace(" ", "_"))
    w_bits = int(b)

    def job(on_progress=None):
        from gui_core import services
        return services.export_artifacts(model, src, dest, w_bits=w_bits)

    page.status.setText(tr("导出中…"))
    page._export_worker = FnWorker(job)
    page._export_worker.done.connect(
        lambda paths: page.status.setText(_export_summary(paths)))
    page._export_worker.failed.connect(
        lambda e: page.status.setText(tr("❌ 导出失败:{e}").format(e=e)))
    page._export_worker.start()


def _export_summary(paths: dict) -> str:
    lines = [f"{k}: {v}" for k, v in paths.items()
             if not k.endswith("verified")]
    for key, lab in (("onnx_verified", "ONNX 数值验证"),
                     ("rtl_verified", "RTL bit-true 验证")):
        if key in paths:
            lines.append(tr(lab) + " " + (tr("✅ 通过") if paths[key]
                                          else tr("跳过")))
    return "📦 " + "\n".join(lines)


ACTIONS = {"export_npz": _export_npz, "export_artifacts": _export_artifacts}
