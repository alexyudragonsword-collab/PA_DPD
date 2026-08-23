package com.padpd.chart

import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.Canvas
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/**
 * One renderer for every chart the app draws.
 *
 * `gui_qt/figs.py` needed fifteen functions because matplotlib was being
 * driven directly; here the Python side emits a [ChartSpec] and this walks
 * it. Adding a chart in Phase 3 means adding a spec builder, not touching
 * this file - which is the point of having a spec layer at all.
 */

private val LABEL_SP = 10.sp
private val TICK_SP = 9.sp

@Composable
fun ChartView(
    spec: ChartSpec,
    blobs: BlobStore,
    modifier: Modifier = Modifier,
    panelHeight: androidx.compose.ui.unit.Dp = 260.dp,
) {
    Column(modifier) {
        for ((i, panel) in spec.panels.withIndex()) {
            PanelView(
                panel, blobs,
                Modifier.fillMaxWidth().height(panelHeight)
                    .padding(top = if (i == 0) 0.dp else 8.dp),
            )
        }
    }
}

/** Data-space window currently shown. Gestures move this, not the pixels,
 * so axis ticks stay correct as the user zooms instead of scaling into
 * blurry labels. */
private data class Viewport(val x: Range, val yL: Range, val yR: Range?)

@Composable
fun PanelView(panel: Panel, blobs: BlobStore, modifier: Modifier = Modifier) {
    val palette = chartPalette()
    val measurer = rememberTextMeasurer()
    val base = remember(panel) { basePorts(panel, blobs) }
    var view by remember(panel) { mutableStateOf(base) }

    Canvas(
        modifier.pointerInput(panel) {
            detectTransformGestures { centroid, pan, zoom, _ ->
                val plot = plotRect(size.width.toFloat(), size.height.toFloat(),
                                    panel, measurer)
                if (plot.width <= 0f || plot.height <= 0f) return@detectTransformGestures
                val fx = ((centroid.x - plot.left) / plot.width).coerceIn(0f, 1f)
                val fy = ((centroid.y - plot.top) / plot.height).coerceIn(0f, 1f)
                view = Viewport(
                    view.x.transform(pan.x, plot.width, zoom, fx, invert = false),
                    view.yL.transform(pan.y, plot.height, zoom, fy, invert = true),
                    view.yR?.transform(pan.y, plot.height, zoom, fy, invert = true),
                )
            }
        },
    ) {
        val plot = plotRect(size.width, size.height, panel, measurer)
        drawRect(palette.panel, Offset.Zero, size)
        if (plot.width <= 1f || plot.height <= 1f) return@Canvas

        val v = if (panel.aspectEqual) view.equalised(plot) else view
        val sx = Scale(v.x, plot.left, plot.right, panel.xscale == "log")
        val syL = Scale(v.yL, plot.bottom, plot.top, panel.yscale == "log")
        val syR = v.yR?.let { Scale(it, plot.bottom, plot.top, false) }

        drawSpans(panel, sx, plot, palette)
        drawGridAndTicks(panel, sx, syL, syR, plot, palette, measurer)
        clipRect(plot.left, plot.top, plot.right, plot.bottom) {
            drawHLines(panel, syL, syR, plot, palette)
            drawSeries(panel, blobs, sx, syL, syR, palette)
        }
        drawAxisLabels(panel, plot, palette, measurer)
        drawLegend(panel, plot, palette, measurer)
    }
}

// ---------------------------------------------------------------- ranges

private fun basePorts(panel: Panel, blobs: BlobStore): Viewport {
    var x: Range? = null
    var yL: Range? = null
    var yR: Range? = null
    for (s in panel.series) {
        x = Range.union(x, Range.of(blobs[s.x]))
        val r = Range.of(blobs[s.y])
        if (s.axis == "right") yR = Range.union(yR, r) else yL = Range.union(yL, r)
    }
    // Categorical axes get their extent from the tick positions, not from
    // the bar offsets, so the outermost bars are not clipped in half.
    panel.xTicks?.takeIf { it.isNotEmpty() }?.let { t ->
        x = Range(t.minOf { it.pos } - 0.6, t.maxOf { it.pos } + 0.6)
    }
    // hlines belong inside the visible range or they are invisible advice.
    for (h in panel.hlines) {
        val r = Range(h.y, h.y)
        if (h.axis == "right") yR = Range.union(yR, r) else yL = Range.union(yL, r)
    }
    // Bars read as magnitudes, so their axis must include zero; a bar chart
    // whose baseline is off-screen exaggerates every difference.
    if (panel.kind == "bar") yL = Range.union(yL, Range(0.0, 0.0))

    val padX = if (panel.xTicks != null) 0.0 else 0.02
    return Viewport(
        panel.xlim?.let { Range(it[0], it[1]) } ?: (x ?: Range(0.0, 1.0)).padded(padX),
        panel.ylim?.let { Range(it[0], it[1]) } ?: (yL ?: Range(0.0, 1.0)).padded(0.05),
        yR?.padded(0.05),
    )
}

private fun Range.transform(
    panPx: Float, extentPx: Float, zoom: Float, focus: Float, invert: Boolean,
): Range {
    val s = sane()
    val f = if (invert) 1.0 - focus else focus.toDouble()
    val anchor = s.min + s.span * f
    val newSpan = (s.span / zoom).coerceIn(s.span * 1e-4, s.span * 1e4)
    val shift = -panPx / extentPx * newSpan * (if (invert) -1.0 else 1.0)
    val lo = anchor - newSpan * f + shift
    return Range(lo, lo + newSpan)
}

/** Equal data-units-per-pixel on both axes, for constellations - an IQ
 * cloud drawn on unequal axes reads as an ellipse that is not there. */
private fun Viewport.equalised(plot: Rect): Viewport {
    val perPxX = x.sane().span / plot.width
    val perPxY = yL.sane().span / plot.height
    val per = max(perPxX, perPxY)
    fun grow(r: Range, px: Float): Range {
        val c = (r.min + r.max) / 2
        val half = per * px / 2
        return Range(c - half, c + half)
    }
    return Viewport(grow(x, plot.width), grow(yL, plot.height), yR)
}

// ---------------------------------------------------------------- layout

private fun plotRect(
    w: Float, h: Float, panel: Panel, measurer: TextMeasurer,
): Rect {
    val tickW = measurer.measure("-000.0", TextStyle(fontSize = TICK_SP)).size
    val left = tickW.width + 14f
    val right = w - (if (panel.hasRightAxis) tickW.width + 14f else 8f)
    val top = if (panel.title != null) tickW.height + 12f else 8f
    val bottom = h - (tickW.height * 2 + 12f)
    return Rect(left, top, max(left + 1f, right), max(top + 1f, bottom))
}

// ---------------------------------------------------------------- drawing

private fun DrawScope.drawGridAndTicks(
    panel: Panel, sx: Scale, syL: Scale, syR: Scale?, plot: Rect,
    p: ChartPalette, measurer: TextMeasurer,
) {
    val tickStyle = TextStyle(color = p.tick, fontSize = TICK_SP)

    val xt = panel.xTicks?.map { Tick(it.pos, it.label) } ?: sx.ticks(5)
    for (t in xt) {
        val px = sx.project(t.value) ?: continue
        if (px < plot.left - 1 || px > plot.right + 1) continue
        drawLine(p.grid, Offset(px, plot.top), Offset(px, plot.bottom), 1f)
        val m = measurer.measure(t.label, tickStyle)
        drawText(m, topLeft = Offset(px - m.size.width / 2f, plot.bottom + 4f))
    }
    for (t in syL.ticks(5)) {
        val py = syL.project(t.value) ?: continue
        if (py < plot.top - 1 || py > plot.bottom + 1) continue
        drawLine(p.grid, Offset(plot.left, py), Offset(plot.right, py), 1f)
        val m = measurer.measure(t.label, tickStyle)
        drawText(m, topLeft = Offset(plot.left - m.size.width - 6f,
                                     py - m.size.height / 2f))
    }
    syR?.let { s ->
        for (t in s.ticks(5)) {
            val py = s.project(t.value) ?: continue
            if (py < plot.top - 1 || py > plot.bottom + 1) continue
            val m = measurer.measure(t.label, tickStyle)
            drawText(m, topLeft = Offset(plot.right + 6f, py - m.size.height / 2f))
        }
    }
    drawRect(p.axis, Offset(plot.left, plot.top),
             Size(plot.width, plot.height), style = Stroke(1f))
}

private fun DrawScope.drawSpans(
    panel: Panel, sx: Scale, plot: Rect, p: ChartPalette,
) {
    for (v in panel.vspans) {
        val a = sx.project(v.x0) ?: continue
        val b = sx.project(v.x1) ?: continue
        val lo = max(min(a, b), plot.left)
        val hi = min(max(a, b), plot.right)
        if (hi <= lo) continue
        drawRect(p.forRole(v.colorRole, 0).copy(alpha = 0.5f),
                 Offset(lo, plot.top), Size(hi - lo, plot.height))
    }
}

private fun DrawScope.drawHLines(
    panel: Panel, syL: Scale, syR: Scale?, plot: Rect, p: ChartPalette,
) {
    val dotted = PathEffect.dashPathEffect(floatArrayOf(3f, 5f))
    for (h in panel.hlines) {
        val s = if (h.axis == "right") syR else syL
        val py = s?.project(h.y) ?: continue
        drawLine(p.forRole(h.colorRole, 0).copy(alpha = 0.7f),
                 Offset(plot.left, py), Offset(plot.right, py),
                 1f, pathEffect = dotted)
    }
}

private fun DrawScope.drawSeries(
    panel: Panel, blobs: BlobStore, sx: Scale, syL: Scale, syR: Scale?,
    p: ChartPalette,
) {
    for ((i, s) in panel.series.withIndex()) {
        val xs = blobs[s.x]
        val ys = blobs[s.y]
        val sy = if (s.axis == "right") syR ?: syL else syL
        val color = p.forRole(s.colorRole, i)
        when (panel.kind) {
            "bar" -> drawBars(xs, ys, sx, sy, color, panel.barWidth)
            "scatter" -> drawPoints(xs, ys, sx, sy, color, 1.6f)
            else -> {
                drawPolyline(xs, ys, sx, sy, color, s)
                if (s.marker.isNotEmpty() && s.marker != ".") {
                    drawPoints(xs, ys, sx, sy, color, 3f)
                }
            }
        }
    }
}

private fun DrawScope.drawPolyline(
    xs: FloatArray, ys: FloatArray, sx: Scale, sy: Scale, color: Color,
    s: Series,
) {
    val n = min(xs.size, ys.size)
    if (n == 0) return
    val path = Path()
    var open = false
    for (k in 0 until n) {
        val px = sx.project(xs[k].toDouble())
        val py = sy.project(ys[k].toDouble())
        if (px == null || py == null) {
            // A gap, not a jump: NaN and log-axis rejects both mean "no
            // sample here", and joining across would invent data.
            open = false
            continue
        }
        if (!open) { path.moveTo(px, py); open = true } else path.lineTo(px, py)
    }
    val effect = when (s.style) {
        "dashed" -> PathEffect.dashPathEffect(floatArrayOf(9f, 6f))
        "dotted" -> PathEffect.dashPathEffect(floatArrayOf(2f, 5f))
        else -> null
    }
    drawPath(path, color,
             style = Stroke(width = s.width.toFloat() * 1.4f, pathEffect = effect))
}

private fun DrawScope.drawPoints(
    xs: FloatArray, ys: FloatArray, sx: Scale, sy: Scale, color: Color, r: Float,
) {
    val n = min(xs.size, ys.size)
    for (k in 0 until n) {
        val px = sx.project(xs[k].toDouble()) ?: continue
        val py = sy.project(ys[k].toDouble()) ?: continue
        drawCircle(color, r, Offset(px, py), alpha = if (r < 2f) 0.5f else 1f)
    }
}

private fun DrawScope.drawBars(
    xs: FloatArray, ys: FloatArray, sx: Scale, sy: Scale, color: Color,
    widthData: Double,
) {
    val n = min(xs.size, ys.size)
    val zero = sy.project(0.0) ?: return
    for (k in 0 until n) {
        if (ys[k].isNaN()) continue        // missing metric: leave a gap
        val cx = sx.project(xs[k].toDouble()) ?: continue
        val half = abs((sx.project(xs[k] + widthData / 2) ?: cx) - cx)
        val top = sy.project(ys[k].toDouble()) ?: continue
        drawRect(color, Offset(cx - half, min(top, zero)),
                 Size(max(half * 2, 1f), abs(top - zero)))
    }
}

private fun DrawScope.drawAxisLabels(
    panel: Panel, plot: Rect, p: ChartPalette, measurer: TextMeasurer,
) {
    val style = TextStyle(color = p.label, fontSize = LABEL_SP)
    panel.title?.let {
        val m = measurer.measure(it, style)
        drawText(m, topLeft = Offset(plot.center.x - m.size.width / 2f, 2f))
    }
    if (panel.xlabel.isNotEmpty()) {
        val m = measurer.measure(panel.xlabel, style)
        drawText(m, topLeft = Offset(plot.center.x - m.size.width / 2f,
                                     size.height - m.size.height - 1f))
    }
    // y labels sit horizontally at the top of their axis rather than
    // rotated: rotated text on a phone-width chart costs more room than it
    // saves, and a short unit string reads fine there.
    if (panel.ylabel.isNotEmpty()) {
        drawText(measurer.measure(panel.ylabel, style),
                 topLeft = Offset(plot.left + 2f, plot.top - 1f))
    }
    panel.y2label?.let {
        val m = measurer.measure(it, TextStyle(color = p.muted, fontSize = LABEL_SP))
        drawText(m, topLeft = Offset(plot.right - m.size.width - 2f, plot.top - 1f))
    }
}

private fun DrawScope.drawLegend(
    panel: Panel, plot: Rect, p: ChartPalette, measurer: TextMeasurer,
) {
    val labelled = panel.series.filter { it.label.isNotEmpty() }
    if (labelled.isEmpty()) return
    val style = TextStyle(color = p.label, fontSize = TICK_SP)
    var y = plot.top + 4f
    for ((i, s) in panel.series.withIndex()) {
        if (s.label.isEmpty()) continue
        val m = measurer.measure(s.label, style)
        val x = plot.right - m.size.width - 16f
        if (y + m.size.height > plot.bottom) break
        drawLine(p.forRole(s.colorRole, i), Offset(x - 12f, y + m.size.height / 2f),
                 Offset(x - 2f, y + m.size.height / 2f), 2.5f)
        drawText(m, topLeft = Offset(x, y))
        y += m.size.height + 2f
    }
}
