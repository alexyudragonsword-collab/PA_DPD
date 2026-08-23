package com.padpd.chart

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * The chart schema emitted by `padpd_mobile/chart_spec.py`, typed.
 *
 * The Python side ports all fifteen of `gui_qt/figs.py`'s figure builders
 * into this one shape, so this file plus [ChartCanvas] replaces fifteen
 * bespoke drawing routines with one renderer. Field names must match the
 * Python keys exactly; `tests/test_mobile_api.py` pins the Python half and
 * `ChartSpecParseTest` parses a spec produced by it, so a rename on either
 * side fails a test rather than silently drawing an empty chart.
 *
 * Numeric arrays are not here. They are referenced by blob key and fetched
 * as float32 through [PyBridge.blob] - a 4096-point curve is 16 KB of
 * binary against ~80 KB of JSON text.
 */
@Serializable
data class ChartSpec(
    val panels: List<Panel>,
)

@Serializable
data class Panel(
    val kind: String,                       // line | scatter | bar
    val title: String? = null,
    val xlabel: String = "",
    val ylabel: String = "",
    val y2label: String? = null,
    val xscale: String = "linear",          // linear | log
    val yscale: String = "linear",
    val xlim: List<Double>? = null,
    val ylim: List<Double>? = null,
    @SerialName("aspect_equal") val aspectEqual: Boolean = false,
    @SerialName("x_ticks") val xTicks: List<TickLabel>? = null,
    val series: List<Series> = emptyList(),
    val hlines: List<HLine> = emptyList(),
    val vspans: List<VSpan> = emptyList(),
    // Present only on bar panels. Group offsets are computed in Python so
    // the grouping matches figs.py exactly rather than being re-derived.
    @SerialName("bar_width") val barWidth: Double = 0.8,
) {
    val hasRightAxis: Boolean get() = series.any { it.axis == "right" }
}

@Serializable
data class TickLabel(val pos: Double, val label: String)

@Serializable
data class Series(
    val label: String,
    val x: String,                          // blob key
    val y: String,                          // blob key
    val axis: String = "left",              // left | right
    val style: String = "solid",            // solid | dashed | dotted
    val marker: String = "",                // "" | o | s | d | .
    @SerialName("color_role") val colorRole: String = "seq",
    val width: Double = 1.2,
)

@Serializable
data class HLine(
    val y: Double,
    val axis: String = "left",
    @SerialName("color_role") val colorRole: String = "muted",
)

@Serializable
data class VSpan(
    val x0: Double,
    val x1: Double,
    @SerialName("color_role") val colorRole: String = "warn",
)

/**
 * Lenient about unknown keys on purpose: the Python side may grow a field
 * before the renderer learns to use it, and an app that refuses to draw
 * anything because of one unread key would be worse than one that ignores
 * it. Missing *known* keys still fail, which is the direction that matters.
 */
val ChartJson: Json = Json { ignoreUnknownKeys = true }
