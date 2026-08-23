package com.padpd.chart

import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.ui.graphics.Color

/**
 * Colours for charts, keyed by the semantic roles `chart_spec.py` emits.
 *
 * The Python side deliberately sends roles rather than hex: `figs.py`
 * hardcodes one dark palette, while the phone has a light mode the desktop
 * GUI never had. Values here mirror `gui_qt/themes.py` so a chart is
 * recognisably the same chart on both, without the spec having to know
 * which theme is active.
 */
data class ChartPalette(
    val panel: Color,
    val grid: Color,
    val axis: Color,
    val label: Color,
    val tick: Color,
    val primary: Color,
    val accent: Color,
    val muted: Color,
    val warn: Color,
    val cycle: List<Color>,
) {
    /** Colour for a series: an explicit role, or the cycle by index. */
    fun forRole(role: String, index: Int): Color = when (role) {
        "primary" -> primary
        "accent" -> accent
        "muted" -> muted
        "warn" -> warn
        else -> cycle[index % cycle.size]
    }
}

// gui_qt/themes.py MPL_RC["dark"] + MPL_CYCLE["dark"]
val DarkChartPalette = ChartPalette(
    panel = Color(0xFF121828),
    grid = Color(0xFF232C42),
    axis = Color(0xFF232C42),
    label = Color(0xFFDFE4EF),
    tick = Color(0xFF9AA4BD),
    primary = Color(0xFF4F8FF7),
    accent = Color(0xFFE4574C),
    muted = Color(0xFF9AA4BD),
    warn = Color(0xFF5A2430),
    cycle = listOf(
        Color(0xFF4F8FF7), Color(0xFFE4574C), Color(0xFF37C978),
        Color(0xFFE5B567), Color(0xFFB07CF7),
    ),
)

// gui_qt/themes.py MPL_RC["light"] + MPL_CYCLE["light"]
val LightChartPalette = ChartPalette(
    panel = Color(0xFFFFFFFF),
    grid = Color(0xFFE3E8F2),
    axis = Color(0xFFD8DFEC),
    label = Color(0xFF1C2333),
    tick = Color(0xFF5D6880),
    primary = Color(0xFF2F6FE0),
    accent = Color(0xFFD3402F),
    muted = Color(0xFF5D6880),
    warn = Color(0xFFE8C7C7),
    cycle = listOf(
        Color(0xFF2F6FE0), Color(0xFFD3402F), Color(0xFF1F9D57),
        Color(0xFFB98A2F), Color(0xFF8A55E0),
    ),
)

@Composable
@ReadOnlyComposable
fun chartPalette(): ChartPalette =
    if (isSystemInDarkTheme()) DarkChartPalette else LightChartPalette
