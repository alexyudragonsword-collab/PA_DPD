package com.padpd.screens

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.padpd.chart.BlobStore
import com.padpd.chart.ChartView
import com.padpd.chart.PyBridge
import com.padpd.i18n.tr
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonPrimitive

/**
 * Waveform Studio, the mobile port of `gui_qt/pages/waveform.py`.
 *
 * The parameter set is the desktop's, values included: the same five
 * bandwidths, the same five QAM orders, the same symbol and seed ranges,
 * the same 8 dB default CFR target. They are not arbitrary - 802.11be
 * defines the bandwidths and the constellation set - so diverging here
 * would mean the phone could generate a waveform the desktop cannot
 * reproduce, and a run recorded on one would not replay on the other.
 *
 * Everything numeric is computed and formatted in Python; this file
 * lays out what comes back and owns no arithmetic of its own.
 */

private val BANDWIDTHS = listOf(20, 40, 80, 160, 320)
private val QAM_ORDERS = listOf(16, 64, 256, 1024, 4096)
private val CHART_TABS = listOf(
    "psd" to "PSD",
    "ccdf" to "CCDF",
    "constellation" to "星座",
    "time" to "时域",
)

private sealed interface Run {
    data object Idle : Run
    data object Busy : Run
    data class Ready(val screen: PyBridge.Screen, val blobs: BlobStore) : Run
    data class Failed(val message: String) : Run
}

@Composable
fun WaveformScreen(lang: String, modifier: Modifier = Modifier) {
    var bandwidth by remember { mutableIntStateOf(80) }
    var qam by remember { mutableIntStateOf(1024) }
    var symbols by remember { mutableIntStateOf(8) }
    var seed by remember { mutableIntStateOf(0) }
    var cfrOn by remember { mutableStateOf(false) }
    var run by remember { mutableStateOf<Run>(Run.Idle) }
    var generation by remember { mutableIntStateOf(0) }
    var tab by remember { mutableIntStateOf(0) }

    // Keyed on lang as well as the generate button: chart axis labels and
    // series names are built in Python, so switching language has to
    // rebuild the screen rather than re-render it.
    LaunchedEffect(generation, lang) {
        if (generation == 0) return@LaunchedEffect
        run = Run.Busy
        run = runCatching {
            withContext(Dispatchers.Default) {
                val screen = PyBridge.page(
                    "waveform",
                    args = listOf(
                        JsonPrimitive(bandwidth), JsonPrimitive(qam),
                        JsonPrimitive(symbols), JsonPrimitive(seed),
                        if (cfrOn) JsonPrimitive(CFR_PAPR_DB)
                        else JsonPrimitive(null as String?),
                    ),
                    kwargs = mapOf("lang" to JsonPrimitive(lang)),
                )
                val blobs = PyBridge.newBlobStore()
                    .apply { screen.charts.values.forEach { preload(it) } }
                Run.Ready(screen, blobs)
            }
        }.getOrElse { Run.Failed(it.message ?: it.toString()) }
    }

    Column(modifier.fillMaxSize().padding(12.dp)) {
        Text(tr("波形工作台"), fontSize = 18.sp, fontWeight = FontWeight.SemiBold)

        Row(
            Modifier.fillMaxWidth().padding(vertical = 8.dp)
                .horizontalScroll(rememberScrollState()),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Choice(tr("带宽(MHz)"), BANDWIDTHS, bandwidth) { bandwidth = it }
            Choice("QAM", QAM_ORDERS, qam) { qam = it }
            Stepper(tr("符号数"), symbols, 2, 40, 2) { symbols = it }
            Stepper(tr("种子"), seed, 0, 9999, 1) { seed = it }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(tr("CFR 削峰"), fontSize = 12.sp)
                Switch(cfrOn, { cfrOn = it }, Modifier.testTag("cfr"))
            }
        }

        Button(
            { generation++ },
            enabled = run !is Run.Busy,
            modifier = Modifier.testTag("generate"),
        ) { Text(tr("生成波形")) }

        when (val state = run) {
            is Run.Idle -> Unit
            is Run.Busy -> Text(
                tr("计算中…"), fontSize = 12.sp,
                modifier = Modifier.padding(top = 12.dp).testTag("busy"),
            )
            is Run.Failed -> Text(
                state.message, fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 12.dp).testTag("waveformError"),
            )
            is Run.Ready -> {
                MetricRow(state.screen.metrics)
                TabRow(tab, Modifier.testTag("chartTabs")) {
                    CHART_TABS.forEachIndexed { i, (slot, label) ->
                        Tab(
                            selected = tab == i,
                            onClick = { tab = i },
                            modifier = Modifier.testTag("tab:$slot"),
                            text = { Text(tr(label), fontSize = 12.sp) },
                        )
                    }
                }
                val slot = CHART_TABS[tab].first
                val spec = state.screen.charts[slot]
                if (spec != null) {
                    ChartView(
                        spec, state.blobs,
                        Modifier.padding(top = 8.dp).testTag("chart:$slot"),
                    )
                }
            }
        }
    }
}

@Composable
private fun MetricRow(metrics: List<PyBridge.Metric>) {
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
                Text(
                    m.label, fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(m.value, fontSize = 15.sp, fontWeight = FontWeight.Medium)
                if (m.note.isNotEmpty()) {
                    Text(
                        m.note, fontSize = 10.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

/** A value picked from a fixed set, the phone form of a QComboBox. */
@Composable
private fun Choice(
    label: String,
    options: List<Int>,
    selected: Int,
    onPick: (Int) -> Unit,
) {
    Column(Modifier.padding(end = 12.dp)) {
        Text(label, fontSize = 10.sp,
             color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row {
            for (o in options) {
                val chosen = o == selected
                Text(
                    o.toString(),
                    fontSize = 12.sp,
                    fontWeight = if (chosen) FontWeight.Bold else FontWeight.Normal,
                    color = if (chosen) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier
                        .padding(end = 6.dp)
                        .testTag("$label:$o")
                        .clickable { onPick(o) },
                )
            }
        }
    }
}

/** An integer nudged by fixed steps, the phone form of a QSpinBox. */
@Composable
private fun Stepper(
    label: String,
    value: Int,
    min: Int,
    max: Int,
    step: Int,
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
            Text(value.toString(), fontSize = 13.sp,
                 modifier = Modifier.testTag("$label:value"))
            Text("+", fontSize = 16.sp,
                 modifier = Modifier.testTag("$label:+")
                     .clickable { onSet((value + step).coerceAtMost(max)) })
        }
    }
}

private const val CFR_PAPR_DB = 8.0
