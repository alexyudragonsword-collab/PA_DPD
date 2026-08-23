package com.padpd.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.ui.text.font.FontFamily
import com.padpd.chart.ChartView
import com.padpd.i18n.tr
import com.padpd.chart.BlobStore
import com.padpd.chart.PyBridge
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive

/**
 * What every ported screen shares: how a run is represented, how it is
 * fetched, and the two controls that recur on every page.
 *
 * The desktop has gui_qt/common.py for the same reason. Keeping these
 * here rather than copying them per screen matters more than usual on
 * this side, because the Kotlin half can only be checked in CI - a
 * divergence between two copies of a stepper would take a five-minute
 * round trip to notice.
 */

sealed interface ScreenRun {
    data object Idle : ScreenRun
    data object Busy : ScreenRun
    data class Ready(val screen: PyBridge.Screen, val blobs: BlobStore) :
        ScreenRun
    data class Failed(val message: String) : ScreenRun
}

/**
 * Assemble one screen off the UI thread and resolve its blobs.
 *
 * Blobs are preloaded here, before the result is handed to compose, so
 * that panning a chart later never crosses the bridge mid-frame - the
 * interpreter is single-threaded under one GIL and a fetch during a
 * gesture would stutter it.
 *
 * Failures come back as [ScreenRun.Failed] rather than propagating: the
 * Python side already returns errors as data with a traceback attached,
 * and a bad parameter should show on screen, not take the app down.
 */
suspend fun loadScreen(
    name: String,
    lang: String,
    vararg args: JsonElement,
): ScreenRun = runCatching {
    withContext(Dispatchers.Default) {
        val screen = PyBridge.page(
            name, args.toList(), mapOf("lang" to JsonPrimitive(lang)))
        val blobs = PyBridge.newBlobStore()
            .apply { screen.charts.values.forEach { preload(it) } }
        ScreenRun.Ready(screen, blobs)
    }
}.getOrElse { ScreenRun.Failed(it.message ?: it.toString()) }

/**
 * The metric cards. Values arrive already formatted - see pages.py.
 *
 * This one does scroll horizontally, which is safe only because it is
 * always placed directly in a vertical column. Do not nest it in a
 * horizontally scrolling row - see the note on [OptionRow].
 */
@Composable
fun MetricRow(metrics: List<PyBridge.Metric>) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 8.dp)
            .horizontalScroll(rememberScrollState()),
    ) {
        for (m in metrics) {
            Column(
                Modifier.padding(end = 8.dp)
                    .background(
                        MaterialTheme.colorScheme.surfaceVariant,
                        RoundedCornerShape(8.dp),
                    )
                    .padding(10.dp)
                    .width(140.dp)
                    .testTag("metric:${m.label}"),
            ) {
                Text(m.label, fontSize = 11.sp,
                     color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(m.value, fontSize = 15.sp,
                     fontWeight = FontWeight.Medium)
                if (m.note.isNotEmpty()) {
                    Text(m.note, fontSize = 10.sp,
                         color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

/**
 * An integer nudged by fixed steps - the phone form of a QSpinBox.
 *
 * Integer throughout, including for values the service takes as a float:
 * drive is 0.06..0.24 in hundredths, and stepping it as a Double would
 * accumulate representation error into a parameter that names a run.
 * Callers scale on the way out and pass [display] to render it.
 */
@Composable
fun IntStepper(
    label: String,
    value: Int,
    min: Int,
    max: Int,
    step: Int,
    display: (Int) -> String = { it.toString() },
    onSet: (Int) -> Unit,
) {
    Column(Modifier.padding(end = 12.dp)) {
        Text(label, fontSize = 10.sp,
             color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text("−", fontSize = 16.sp,
                 modifier = Modifier.testTag("$label:-")
                     .clickable { onSet((value - step).coerceAtLeast(min)) })
            Text(display(value), fontSize = 13.sp,
                 modifier = Modifier.testTag("$label:value"))
            Text("+", fontSize = 16.sp,
                 modifier = Modifier.testTag("$label:+")
                     .clickable { onSet((value + step).coerceAtMost(max)) })
        }
    }
}

/**
 * A value picked from a fixed set - the phone form of a QComboBox.
 *
 * Deliberately not scrollable itself. A shared control cannot know what
 * it will be nested in, and Compose throws when a horizontally
 * scrollable component is measured with infinite width - which is what
 * a scrolling row inside a scrolling row produces. Callers that need
 * scrolling wrap this; callers already inside a scrolling row do not.
 */
@Composable
fun <T> OptionRow(
    label: String,
    options: List<T>,
    selected: T,
    onPick: (T) -> Unit,
) {
    Column(Modifier.padding(vertical = 4.dp)) {
        Text(label, fontSize = 10.sp,
             color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            for (o in options) {
                val chosen = o == selected
                Text(
                    o.toString(), fontSize = 12.sp,
                    fontWeight = if (chosen) FontWeight.Bold
                                 else FontWeight.Normal,
                    color = if (chosen) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.testTag("opt:$label:$o")
                        .clickable { onPick(o) },
                )
            }
        }
    }
}

/**
 * Metrics, notes and the chart tabs - the bottom half of every screen.
 *
 * Shared rather than written per screen: three copies of this `when`
 * would be three chances for one screen to forget the error branch, or
 * to render a chart while its blobs are still loading.
 *
 * [tagPrefix] namespaces the busy and error tags so a page with several
 * sections can say which one is running, while the chart and tab tags
 * stay keyed by chart slot - a test asking for chart:psd should not have
 * to know which section drew it.
 */
@Composable
fun RunResult(
    run: ScreenRun,
    tagPrefix: String,
    tabs: List<Pair<String, String>>,
    tab: Int,
    onTab: (Int) -> Unit,
) {
    when (run) {
        is ScreenRun.Idle -> Unit
        is ScreenRun.Busy -> Text(
            tr("计算中…"), fontSize = 12.sp,
            modifier = Modifier.padding(top = 8.dp).testTag("$tagPrefix:busy"),
        )
        is ScreenRun.Failed -> Text(
            run.message, fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            color = MaterialTheme.colorScheme.error,
            modifier = Modifier.padding(top = 8.dp).testTag("$tagPrefix:error"),
        )
        is ScreenRun.Ready -> {
            MetricRow(run.screen.metrics)
            for (note in run.screen.notes) {
                Text(note, fontSize = 11.sp,
                     modifier = Modifier.padding(bottom = 6.dp)
                         .testTag("$tagPrefix:note"))
            }
            if (tabs.size > 1) {
                TabRow(tab, Modifier.testTag("$tagPrefix:tabs")) {
                    tabs.forEachIndexed { i, (slot, label) ->
                        Tab(selected = tab == i, onClick = { onTab(i) },
                            modifier = Modifier.testTag("tab:$slot"),
                            text = { Text(tr(label), fontSize = 12.sp) })
                    }
                }
            }
            run.screen.charts[tabs[tab].first]?.let { spec ->
                ChartView(spec, run.blobs,
                          Modifier.padding(top = 8.dp)
                              .testTag("chart:${tabs[tab].first}"))
            }
        }
    }
}
