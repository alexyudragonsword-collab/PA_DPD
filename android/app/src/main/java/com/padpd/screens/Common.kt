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
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.style.TextOverflow
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
 * fetched, and the controls that recur on every page.
 *
 * Every control takes an explicit `tag` separate from its `label`. The
 * label is translated, so building a test tag out of it would mean the
 * identifiers change when the user switches language - a device test
 * written against the Chinese UI would stop finding anything in English,
 * and the failure would look like a broken screen rather than a renamed
 * tag. Tags are ASCII and fixed; labels are for people.
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
 *
 * The card sizes to its label rather than being pinned at one width.
 * Labels are translated and English runs about three times the character
 * count of the Chinese it replaces - "联合设计(预算内最高效率)" is 13
 * characters and "Co-design (best efficiency in budget)" is 37. At a
 * fixed width and with no line limit that label simply wrapped to four
 * lines, leaving one card towering over its neighbours. Bounding the
 * width and capping the lines makes the overflow degrade predictably
 * instead of reshaping the row.
 */
@Composable
fun MetricRow(metrics: List<PyBridge.Metric>) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 8.dp)
            .horizontalScroll(rememberScrollState()),
    ) {
        for (m in metrics) {
            Column(
                // widthIn before the background, not after: a bound
                // applied inside the padding constrains the text and
                // leaves the card 20.dp wider than the number says, so
                // the figure a test can assert on would not be the
                // figure written here.
                Modifier.padding(end = 8.dp)
                    .widthIn(min = METRIC_MIN_WIDTH, max = METRIC_MAX_WIDTH)
                    .background(
                        MaterialTheme.colorScheme.surfaceVariant,
                        RoundedCornerShape(8.dp),
                    )
                    .padding(10.dp)
                    .testTag("metric:${m.label}"),
            ) {
                Text(m.label, fontSize = 11.sp,
                     maxLines = 2, overflow = TextOverflow.Ellipsis,
                     color = MaterialTheme.colorScheme.onSurfaceVariant)
                // The value is the reading itself; truncating it would be
                // worse than any layout it breaks, so it gets the width
                // it needs and only a single line to take it on.
                Text(m.value, fontSize = 15.sp, maxLines = 1,
                     overflow = TextOverflow.Ellipsis,
                     fontWeight = FontWeight.Medium)
                if (m.note.isNotEmpty()) {
                    Text(m.note, fontSize = 10.sp,
                         maxLines = 2, overflow = TextOverflow.Ellipsis,
                         color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

/**
 * Metric card bounds, named so the test that measures them and the code
 * that sets them cannot drift apart.
 *
 * The maximum is what stops a translated label growing the card without
 * limit; [MetricRow] scrolls horizontally, so a card wider than the
 * screen would push its neighbours out of reach rather than wrap.
 */
val METRIC_MIN_WIDTH = 140.dp
val METRIC_MAX_WIDTH = 210.dp

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
    tag: String,
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
                 modifier = Modifier.testTag("$tag:-")
                     .clickable { onSet((value - step).coerceAtLeast(min)) })
            Text(display(value), fontSize = 13.sp,
                 modifier = Modifier.testTag("$tag:value"))
            Text("+", fontSize = 16.sp,
                 modifier = Modifier.testTag("$tag:+")
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
    tag: String,
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
                    modifier = Modifier.testTag("opt:$tag:$o")
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

/**
 * A simple key/value table, for screens whose result is rows rather than
 * a reading - deployment sweeps, LUT depths.
 *
 * Columns come from the first row's keys, in insertion order, because
 * pages.py builds those rows in the order the desktop table shows them.
 * Scrolls horizontally, so like [MetricRow] it belongs directly in a
 * column and not inside another horizontal scroller.
 *
 * **One scroll state, shared.** The header and every data row are
 * separate Rows, and each used to call rememberScrollState() for itself -
 * so scrolling the header moved the header alone and the columns stopped
 * lining up with their headings. Sharing one state is what makes this a
 * table rather than a stack of independently scrolling strips.
 *
 * Column width is fixed for the same reason: the rows are measured
 * independently of each other, so intrinsic sizing would give each row
 * its own column widths and nothing would align. What the fixed width
 * costs is that a long cell has to give somewhere, and a single line
 * with an ellipsis is the visible way to give - wrapping made rows
 * different heights, which breaks the alignment the fixed width exists
 * to provide.
 */
@Composable
fun RowTable(rows: List<Map<String, String>>, tag: String) {
    if (rows.isEmpty()) return
    val columns = rows.first().keys.toList()
    val scroll = rememberScrollState()
    Column(Modifier.fillMaxWidth().padding(vertical = 8.dp).testTag(tag)) {
        Row(Modifier.horizontalScroll(scroll)) {
            for (c in columns) {
                Text(c, fontSize = 10.sp,
                     fontWeight = FontWeight.Medium,
                     maxLines = 1, overflow = TextOverflow.Ellipsis,
                     color = MaterialTheme.colorScheme.onSurfaceVariant,
                     modifier = Modifier.width(COLUMN_WIDTH))
            }
        }
        for ((i, row) in rows.withIndex()) {
            Row(Modifier.horizontalScroll(scroll).testTag("$tag:row$i")) {
                for (c in columns) {
                    Text(row[c].orEmpty(), fontSize = 12.sp,
                         maxLines = 1, overflow = TextOverflow.Ellipsis,
                         fontFamily = FontFamily.Monospace,
                         modifier = Modifier.width(COLUMN_WIDTH))
                }
            }
        }
    }
}

/**
 * Table column width, wide enough for the longest translated cell the
 * screens actually produce: "operating points" (16 monospace characters
 * at 12sp) on the Data screen's capture-group checklist.
 */
private val COLUMN_WIDTH = 124.dp

/** Several values picked from a fixed set. Not scrollable - see [OptionRow]. */
@Composable
fun <T> MultiOptionRow(
    label: String,
    tag: String,
    options: List<T>,
    selected: Collection<T>,
    onToggle: (T) -> Unit,
) {
    Column(Modifier.padding(vertical = 4.dp)) {
        Text(label, fontSize = 10.sp,
             color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            for (o in options) {
                val chosen = o in selected
                Text(
                    (if (chosen) "☑ " else "☐ ") + o.toString(),
                    fontSize = 12.sp,
                    color = if (chosen) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.testTag("multi:$tag:$o")
                        .clickable { onToggle(o) },
                )
            }
        }
    }
}
