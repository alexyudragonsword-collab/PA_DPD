"""A form generated from an experiment's parameter schema.

The old pages laid every input out by hand, one row per page, relevant
or not; two pages ended up wider than a laptop screen and the same input
drifted between the desktop and the web GUI. Here the schema
(``gui_core.experiments.Param``) is the layout: inputs stack in one
column under their group heading, an input whose ``show`` predicate is
false is hidden (and ``effective_values`` drops it from the run), and
advanced inputs fold away.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QBoxLayout,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui_core.experiments import CHOICE_LABELS
from gui_qt.common import tr

# width two segmented buttons may take side by side in the setup column
SEG_FIT = 248


def choice_text(value, unit: str = "") -> str:
    if value in CHOICE_LABELS:
        return tr(CHOICE_LABELS[value])
    return f"{value} {unit}".strip() if unit else str(value)


class _NoWheel:
    """Spin boxes and combos ignore the wheel unless focused, so scrolling
    the setup column does not silently change an input under the cursor."""

    def wheelEvent(self, e):
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()


class _Spin(_NoWheel, QSpinBox):
    pass


class _DSpin(_NoWheel, QDoubleSpinBox):
    pass


class _Combo(_NoWheel, QComboBox):
    pass


class _Field:
    """One input: its row widget, its value accessors, its texts."""

    def __init__(self, param, form):
        self.p, self.form = param, form
        self.row = QWidget()
        lay = QVBoxLayout(self.row)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(3)
        self.label = QLabel()
        self.label.setObjectName("fieldLabel")
        self.label.setWordWrap(True)
        self.help = QLabel()
        self.help.setObjectName("help")
        self.help.setWordWrap(True)
        self.warn = QLabel()
        self.warn.setObjectName("warn")
        self.warn.setWordWrap(True)
        self.warn.hide()
        self.widget = self._build()
        if param.kind != "bool":
            lay.addWidget(self.label)
        lay.addWidget(self.widget)
        lay.addWidget(self.help)
        lay.addWidget(self.warn)
        self.retranslate()

    # ---- construction --------------------------------------------
    def _build(self) -> QWidget:
        p, changed = self.p, self.form.changed.emit
        k = p.kind
        if k == "choice" and len(p.choices) == 2:
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(0)
            self.group = QButtonGroup(w)
            self.group.setExclusive(True)
            self.buttons = []
            for i, c in enumerate(p.choices):
                b = QPushButton()
                b.setObjectName("seg")
                b.setCheckable(True)
                b.setChecked(c == p.default)
                self.group.addButton(b, i)
                h.addWidget(b, 1)
                self.buttons.append(b)
            self.group.idClicked.connect(lambda _i: changed())
            return w
        if k == "choice":
            w = _Combo()
            for c in p.choices:
                w.addItem("", c)
            w.setCurrentIndex(max(0, list(p.choices).index(p.default)
                                  if p.default in p.choices else 0))
            w.currentIndexChanged.connect(lambda _i: changed())
            return w
        if k == "int":
            w = _Spin()
            w.setRange(int(p.lo), int(p.hi))
            w.setSingleStep(max(1, int(p.step)))
            w.setValue(int(p.default))
            w.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            w.valueChanged.connect(lambda _v: changed())
            return w
        if k == "float":
            w = _DSpin()
            w.setDecimals(p.decimals)
            w.setRange(p.lo, p.hi)
            w.setSingleStep(p.step)
            w.setValue(float(p.default))
            w.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            w.setStepType(QAbstractSpinBox.StepType.DefaultStepType)
            w.valueChanged.connect(lambda _v: changed())
            return w
        if k == "bool":
            w = QCheckBox()
            w.setChecked(bool(p.default))
            w.toggled.connect(lambda _v: changed())
            return w
        if k == "multi":
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(0)
            self.buttons = []
            for c in p.choices:
                b = QPushButton(str(c))
                b.setObjectName("seg")
                b.setCheckable(True)
                b.setChecked(c in tuple(p.default))
                b.toggled.connect(lambda _v: changed())
                h.addWidget(b, 1)
                self.buttons.append(b)
            return w
        if k == "model":
            w = _Combo()
            w.currentIndexChanged.connect(lambda _i: changed())
            return w
        if k == "models":
            w = QListWidget()
            w.setMaximumHeight(130)
            w.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            w.setTextElideMode(Qt.TextElideMode.ElideMiddle)
            w.itemChanged.connect(lambda _it: changed())
            return w
        if k == "file":
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            self.path = QLineEdit(str(p.default or ""))
            self.path.textChanged.connect(lambda _t: changed())
            self.browse = QPushButton()
            self.browse.clicked.connect(self._pick_file)
            h.addWidget(self.path, 1)
            h.addWidget(self.browse)
            return w
        raise ValueError(f"unknown param kind {k!r}")

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self.row, tr(self.p.label), "", tr("CSV (*.csv);;全部 (*)"))
        if path:
            self.path.setText(path)

    # ---- models ----------------------------------------------------
    def reload_models(self, ws):
        p = self.p
        names = [n for n, e in ws.models.items() if e.family in p.families]
        if p.kind == "model":
            cur = self.widget.currentData()
            self.widget.blockSignals(True)
            self.widget.clear()
            self.widget.addItem("—", "")
            for n in names:
                self.widget.addItem(n, n)
            i = self.widget.findData(cur)
            # default to the newest model rather than none: a surrogate
            # picker that opens empty reads as "none needed"
            self.widget.setCurrentIndex(i if i > 0 else
                                        (len(names) if names else 0))
            self.widget.blockSignals(False)
        elif p.kind == "models":
            was = {self.widget.item(i).data(Qt.ItemDataRole.UserRole)
                   for i in range(self.widget.count())
                   if self.widget.item(i).checkState()
                   == Qt.CheckState.Checked}
            fresh = not self.widget.count()
            self.widget.blockSignals(True)
            self.widget.clear()
            for n in names:
                it = QListWidgetItem(n)
                it.setData(Qt.ItemDataRole.UserRole, n)
                it.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                            | Qt.ItemFlag.ItemIsEnabled)
                on = n in was or (fresh and n == names[-1])
                it.setCheckState(Qt.CheckState.Checked if on
                                 else Qt.CheckState.Unchecked)
                self.widget.addItem(it)
            self.widget.blockSignals(False)

    # ---- values ----------------------------------------------------
    def value(self):
        p, w = self.p, self.widget
        if p.kind == "choice":
            if hasattr(self, "group"):
                return p.choices[max(0, self.group.checkedId())]
            return w.currentData()
        if p.kind in ("int", "float"):
            return w.value()
        if p.kind == "bool":
            return w.isChecked()
        if p.kind == "multi":
            return tuple(c for c, b in zip(p.choices, self.buttons,
                                           strict=True)
                         if b.isChecked())
        if p.kind == "model":
            return w.currentData() or ""
        if p.kind == "models":
            return tuple(w.item(i).data(Qt.ItemDataRole.UserRole)
                         for i in range(w.count())
                         if w.item(i).checkState() == Qt.CheckState.Checked)
        if p.kind == "file":
            return self.path.text().strip()
        return None

    def set_value(self, v):
        p, w = self.p, self.widget
        if p.kind == "choice":
            if hasattr(self, "group"):
                if v in p.choices:
                    self.buttons[list(p.choices).index(v)].setChecked(True)
            else:
                i = w.findData(v)
                if i >= 0:
                    w.setCurrentIndex(i)
        elif p.kind == "int":
            w.setValue(int(v))
        elif p.kind == "float":
            w.setValue(float(v))
        elif p.kind == "bool":
            w.setChecked(bool(v))
        elif p.kind == "multi":
            for c, b in zip(p.choices, self.buttons, strict=True):
                b.setChecked(c in tuple(v))
        elif p.kind == "model":
            i = w.findData(v)
            if i >= 0:
                w.setCurrentIndex(i)
        elif p.kind == "models":
            for i in range(w.count()):
                it = w.item(i)
                it.setCheckState(
                    Qt.CheckState.Checked
                    if it.data(Qt.ItemDataRole.UserRole) in tuple(v)
                    else Qt.CheckState.Unchecked)
        elif p.kind == "file":
            self.path.setText(str(v or ""))

    # ---- texts -----------------------------------------------------
    def retranslate(self):
        p = self.p
        unit = f"  ({p.unit})" if p.unit and p.kind not in ("choice",) \
            else ""
        self.label.setText(tr(p.label) + unit)
        self.help.setText(tr(p.help) if p.help else "")
        self.help.setVisible(bool(p.help))
        if p.kind == "choice":
            if hasattr(self, "group"):
                for c, b in zip(p.choices, self.buttons, strict=True):
                    b.setText(choice_text(c, p.unit))
                # side by side when both labels fit the setup column,
                # stacked when a translation makes them too long
                need = sum(b.fontMetrics().horizontalAdvance(b.text()) + 30
                           for b in self.buttons)
                self.widget.layout().setDirection(
                    QBoxLayout.Direction.LeftToRight if need <= SEG_FIT
                    else QBoxLayout.Direction.TopToBottom)
            else:
                for i, c in enumerate(p.choices):
                    self.widget.setItemText(i, choice_text(c, p.unit))
        elif p.kind == "bool":
            self.widget.setText(tr(p.label))
        elif p.kind == "file":
            self.browse.setText(tr("浏览…"))
            self.path.setPlaceholderText(tr("留空用内置示例"))


class ParamForm(QWidget):
    """Inputs for one experiment. ``values()`` reads them on the GUI
    thread; ``changed`` fires on any edit."""

    changed = Signal()

    def __init__(self, params, ctx_fn, parent=None):
        super().__init__(parent)
        self._ctx_fn = ctx_fn
        self.fields: dict[str, _Field] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._heads: list[tuple[QLabel, str, list]] = []
        basic = [p for p in params if not p.advanced]
        adv = [p for p in params if p.advanced]
        self._add_groups(lay, basic)
        self.adv_toggle = None
        if adv:
            self.adv_toggle = QPushButton()
            self.adv_toggle.setObjectName("link")
            self.adv_toggle.setCheckable(True)
            self.adv_toggle.toggled.connect(self._sync)
            lay.addWidget(self.adv_toggle, 0, Qt.AlignmentFlag.AlignLeft)
            self.adv_box = QWidget()
            al = QVBoxLayout(self.adv_box)
            al.setContentsMargins(0, 0, 0, 0)
            al.setSpacing(6)
            self._add_groups(al, adv, heads=False)
            lay.addWidget(self.adv_box)
        lay.addStretch(1)
        self.changed.connect(self._sync)
        self.retranslate()

    def _add_groups(self, lay, params, heads=True):
        group = None
        for p in params:
            if heads and p.group and p.group != group:
                group = p.group
                h = QLabel()
                h.setObjectName("groupHead")
                lay.addWidget(h)
                self._heads.append((h, group, []))
            f = _Field(p, self)
            self.fields[p.key] = f
            if heads and self._heads and self._heads[-1][1] == p.group:
                self._heads[-1][2].append(p.key)
            lay.addWidget(f.row)

    # ---- state -------------------------------------------------------
    def values(self) -> dict:
        """Every input's value, visible or not; effective_values() drops
        the ones that do not apply."""
        return {k: f.value() for k, f in self.fields.items()}

    def set_values(self, values: dict):
        for k, v in values.items():
            if k in self.fields:
                self.fields[k].widget.blockSignals(True)
                try:
                    self.fields[k].set_value(v)
                finally:
                    self.fields[k].widget.blockSignals(False)
        self._sync()

    def reload_models(self):
        ws = self._ctx_fn().workspace
        for f in self.fields.values():
            if f.p.kind in ("model", "models"):
                f.reload_models(ws)
        self._sync()

    def _sync(self, *_):
        ctx = self._ctx_fn()
        v = self.values()
        shown = set()
        for k, f in self.fields.items():
            vis = f.p.show is None or bool(f.p.show(v, ctx))
            if f.p.advanced and self.adv_toggle is not None \
                    and not self.adv_toggle.isChecked():
                vis = False
            f.row.setVisible(vis)
            if vis:
                shown.add(k)
            msg = f.p.warn(v, ctx) if (f.p.warn and vis) else None
            f.warn.setText(tr(msg) if msg else "")
            f.warn.setVisible(bool(msg))
        for h, _g, keys in self._heads:
            h.setVisible(any(k in shown for k in keys))
        if self.adv_toggle is not None:
            self.adv_box.setVisible(self.adv_toggle.isChecked())
            self.adv_toggle.setText(
                ("▾ " if self.adv_toggle.isChecked() else "▸ ")
                + tr("高级设置"))

    def retranslate(self):
        for f in self.fields.values():
            f.retranslate()
        for h, g, _keys in self._heads:
            h.setText(tr(g).upper())
        self._sync()
