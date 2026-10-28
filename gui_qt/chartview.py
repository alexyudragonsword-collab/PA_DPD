"""Chart-spec renderer for the desktop, on pyqtgraph.

Renders the same specs ``gui_core.chart_spec`` produces for Android, so a
chart is defined once. Three rules the old matplotlib pages did not
follow:

- **One axis per plot.** A spec series on the right axis goes to its own
  plot stacked underneath, sharing the x axis. Two y scales on one plot
  invite reading a crossing as meaningful when it is an accident of
  scaling.
- **The x range follows the data, not the reference lines.** The emission
  mask table runs to 800 MHz; drawn as-is it pushed a 640 MHz-wide
  spectrum into the middle third of the plot. Muted series (masks,
  references) are drawn but do not set the range.
- **Read and zoom.** Hover shows every line's value at the cursor; drag a
  rectangle to zoom, double-click to reset.
"""

from __future__ import annotations

import os

import numpy as np

# pyqtgraph picks a Qt binding at import; name it rather than let it
# guess, so a stray PyQt install can never be the one it finds
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from gui_qt.theme import ROLES, SERIES, TOKENS

_STYLE = {"solid": Qt.PenStyle.SolidLine, "dashed": Qt.PenStyle.DashLine,
          "dotted": Qt.PenStyle.DotLine}
_SYMBOL = {"o": "o", "s": "s", "d": "d", ".": "o", "": None}

pg.setConfigOptions(antialias=True)


class _Hover:
    """Crosshair + readout for one plot's line series."""

    def __init__(self, plot, lines, tokens, xlog=False, ylog=False):
        self.plot, self.lines, self.xlog, self.ylog = plot, lines, xlog, ylog
        self.vline = pg.InfiniteLine(angle=90, movable=False,
                                     pen=pg.mkPen(tokens["muted"], width=1,
                                                  style=Qt.PenStyle.DotLine))
        self.text = pg.TextItem(anchor=(0, 0), color=tokens["ink"],
                                fill=pg.mkBrush(tokens["panel"]),
                                border=pg.mkPen(tokens["line"]))
        self.text.setZValue(100)
        self.vline.hide()
        self.text.hide()
        plot.addItem(self.vline, ignoreBounds=True)
        plot.addItem(self.text, ignoreBounds=True)
        self.proxy = pg.SignalProxy(plot.scene().sigMouseMoved, rateLimit=30,
                                    slot=self.moved)

    def moved(self, evt):
        pos = evt[0]
        vb = self.plot.vb
        if not self.plot.sceneBoundingRect().contains(pos):
            self.vline.hide()
            self.text.hide()
            return
        p = vb.mapSceneToView(pos)
        xv = p.x()
        x = 10 ** xv if self.xlog else xv
        rows = []
        for label, xs, ys in self.lines:
            if len(xs) < 2:
                continue
            i = int(np.clip(np.searchsorted(xs, x), 1, len(xs) - 1))
            j = i if abs(xs[i] - x) < abs(xs[i - 1] - x) else i - 1
            y = ys[j]
            if np.isfinite(y):
                rows.append(f"{label}: {y:.2f}")
        if not rows:
            self.text.hide()
            return
        self.vline.setPos(xv)
        self.vline.show()
        xr = f"{x:.4g}"
        self.text.setText("x = " + xr + "\n" + "\n".join(rows))
        (x0, x1), (y0, y1) = vb.viewRange()
        tx = xv + 0.015 * (x1 - x0)
        if xv > x0 + 0.62 * (x1 - x0):          # flip left near the edge
            tx = xv - 0.35 * (x1 - x0)
        self.text.setPos(tx, y1 - 0.03 * (y1 - y0))
        self.text.show()


class ChartView(QWidget):
    """Draws one chart spec. ``set_spec(spec, blobs, theme)``."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(300)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.glw = pg.GraphicsLayoutWidget()
        lay.addWidget(self.glw)
        self._hovers = []
        self.plots = []

    def clear(self):
        self.glw.clear()
        self._hovers = []
        self.plots = []

    # ------------------------------------------------------------
    def set_spec(self, spec: dict, blobs: dict, theme: str = "light"):
        self.clear()
        t = TOKENS[theme]
        self.glw.setBackground(t["chart"])
        panels = spec.get("panels", [])
        # side by side when a spec has several panels (AM-AM | AM-PM);
        # a right-axis split stacks underneath its own panel
        for col, panel in enumerate(panels):
            left = [s for s in panel["series"] if s.get("axis") != "right"]
            right = [s for s in panel["series"] if s.get("axis") == "right"]
            top = self._plot(panel, left, blobs, theme, row=0, col=col,
                             ylabel=panel.get("ylabel", ""),
                             hlines=[h for h in panel["hlines"]
                                     if h.get("axis", "left") == "left"],
                             show_x=not right)
            if right:
                bottom = self._plot(panel, right, blobs, theme, row=1,
                                    col=col, ylabel=panel.get("y2label") or "",
                                    hlines=[h for h in panel["hlines"]
                                            if h.get("axis") == "right"],
                                    show_x=True, title=False)
                bottom.setXLink(top)
                self.glw.ci.layout.setRowStretchFactor(0, 3)
                self.glw.ci.layout.setRowStretchFactor(1, 2)

    def _color(self, s, idx, theme):
        role = s.get("color_role", "seq")
        if role == "seq":
            return SERIES[theme][idx % len(SERIES[theme])]
        return ROLES[theme].get(role, SERIES[theme][0])

    def _plot(self, panel, series, blobs, theme, *, row, col, ylabel,
              hlines, show_x, title=True):
        t = TOKENS[theme]
        p = self.glw.addPlot(row=row, col=col)
        self.plots.append(p)
        p.showGrid(x=True, y=True, alpha=0.35)
        for ax in ("left", "bottom"):
            a = p.getAxis(ax)
            a.setPen(pg.mkPen(t["axis"]))
            a.setTextPen(pg.mkPen(t["tick"]))
            # "PA drive (x0.001)" under one panel and 0.10 under the
            # panel it is linked to: the spec's units, not rescaled ones
            a.enableAutoSIPrefix(False)
        if title and panel.get("title"):
            p.setTitle(panel["title"], color=t["ink2"], size="10pt")
        lab = {"color": t["tick"], "font-size": "10pt"}
        p.setLabel("left", ylabel, **lab)
        if show_x:
            p.setLabel("bottom", panel.get("xlabel", ""), **lab)
        xlog = panel.get("xscale") == "log"
        ylog = panel.get("yscale") == "log"
        p.setLogMode(x=xlog, y=ylog)
        legend = p.addLegend(offset=(-8, 8), labelTextColor=t["ink2"],
                             brush=pg.mkBrush(t["panel"]),
                             pen=pg.mkPen(t["line"]))
        kind = panel.get("kind", "line")
        hover_lines, xs_for_range = [], []
        seq = 0
        for s in series:
            x = np.asarray(blobs[s["x"]], dtype=float)
            y = np.asarray(blobs[s["y"]], dtype=float)
            color = self._color(s, seq, theme)
            if s.get("color_role", "seq") == "seq":
                seq += 1
            label = s.get("label") or ""
            if kind == "bar":
                ok = np.isfinite(y)
                item = pg.BarGraphItem(x=x[ok], height=y[ok],
                                       width=panel.get("bar_width", 0.8) * 0.9,
                                       brush=pg.mkBrush(color),
                                       pen=pg.mkPen(t["chart"], width=1))
                p.addItem(item)
                legend.addItem(item, label)
                xs_for_range.append(x)
                continue
            if kind == "scatter":
                item = pg.ScatterPlotItem(x=x, y=y, size=3, pen=None,
                                          brush=pg.mkBrush(color + "B0"),
                                          name=label)
                p.addItem(item)
                xs_for_range.append(x)
                continue
            pen = pg.mkPen(color, width=max(1.4, float(s.get("width", 1.2))
                                            * 1.15),
                           style=_STYLE.get(s.get("style", "solid")))
            sym = _SYMBOL.get(s.get("marker", ""))
            kw = {}
            if sym:
                kw = {"symbol": sym, "symbolSize": 7,
                      "symbolBrush": pg.mkBrush(color),
                      "symbolPen": pg.mkPen(t["chart"], width=1.5)}
            p.plot(x, y, pen=pen, name=label, **kw)
            order = np.argsort(x)
            hover_lines.append((label, x[order], y[order]))
            if s.get("color_role") != "muted":
                xs_for_range.append(x)
        for h in hlines:
            p.addItem(pg.InfiniteLine(
                angle=0, pos=h["y"], movable=False,
                pen=pg.mkPen(ROLES[theme].get(h.get("color_role", "muted")),
                             width=1, style=Qt.PenStyle.DashLine)))
        for v in panel.get("vspans", []):
            r = pg.LinearRegionItem([v["x0"], v["x1"]], movable=False,
                                    brush=pg.mkBrush(t["bad"] + "30"),
                                    pen=pg.mkPen(None))
            p.addItem(r)
        if panel.get("x_ticks"):
            p.getAxis("bottom").setTicks(
                [[(tk["pos"], tk["label"]) for tk in panel["x_ticks"]]])
        if panel.get("aspect_equal"):
            p.setAspectLocked(True)
        # ranges: explicit limits win; otherwise fit the non-reference data
        if panel.get("xlim"):
            p.setXRange(*panel["xlim"], padding=0)
        elif xs_for_range:
            allx = np.concatenate([a[np.isfinite(a)] for a in xs_for_range])
            if allx.size:
                lo, hi = float(allx.min()), float(allx.max())
                if xlog:
                    lo, hi = np.log10(max(lo, 1e-12)), np.log10(max(hi, 1e-12))
                # categorical axes (bars, W16/W12/...) need room for the
                # outermost tick labels, which pyqtgraph drops at the edge
                pad = 0.5 if kind == "bar" or panel.get("x_ticks") else 0.0
                p.setXRange(lo - pad, hi + pad, padding=0.02)
        if panel.get("ylim"):
            p.setYRange(*panel["ylim"], padding=0)
        vb = p.getViewBox()
        vb.setMouseMode(pg.ViewBox.RectMode)
        if kind == "line" and hover_lines:
            self._hovers.append(_Hover(p, hover_lines, t, xlog, ylog))
        return p

    def mouseDoubleClickEvent(self, ev):          # reset zoom
        for p in self.plots:
            p.enableAutoRange()
        super().mouseDoubleClickEvent(ev)
