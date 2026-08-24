package com.padpd.screens

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
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
import com.padpd.chart.ChartView
import com.padpd.i18n.tr
import kotlinx.serialization.json.JsonPrimitive

/**
 * Co-Design, the mobile port of gui_qt/pages/codesign.py.
 *
 * The desktop has two tabs; only the discrete Pareto sweep is here. The
 * gradient tab needs padpd.codesign_torch, and torch has no Android
 * wheel. The sweep is pure numpy and is the half that carries the
 * argument anyway: it shows a sequential design - chase efficiency, then
 * ask DPD to rescue it - hitting a wall that a joint design walks around.
 *
 * Measured at 80 MHz with a 90-coefficient budget: sequential reaches
 * PAE 43.3% and is infeasible (149 coefficients, EVM -20.1 dB); joint
 * takes 28.2% at drive 0.14 with 23 coefficients and EVM -50.0 dB.
 */
@Composable
fun CodesignScreen(lang: String, torchAvailable: Boolean,
                   modifier: Modifier = Modifier) {
    var specDb by remember { mutableIntStateOf(-40) }
    var budget by remember { mutableIntStateOf(90) }
    var bandwidth by remember { mutableIntStateOf(80) }
    var run by remember { mutableStateOf<ScreenRun>(ScreenRun.Idle) }
    var generation by remember { mutableIntStateOf(0) }

    LaunchedEffect(generation, lang) {
        if (generation == 0) return@LaunchedEffect
        run = ScreenRun.Busy
        run = loadScreen("codesign", lang,
            JsonPrimitive(specDb), JsonPrimitive(budget),
            JsonPrimitive(bandwidth))
    }

    Column(modifier.fillMaxSize().padding(12.dp)
        .verticalScroll(rememberScrollState())) {
        Text(tr("联合设计"), fontSize = 18.sp,
             fontWeight = FontWeight.SemiBold)
        Text(tr("离散 Pareto 扫描"), fontSize = 13.sp,
             fontWeight = FontWeight.Medium,
             modifier = Modifier.padding(top = 4.dp))

        Row(Modifier.fillMaxWidth().padding(vertical = 4.dp)
            .horizontalScroll(rememberScrollState()),
            verticalAlignment = Alignment.CenterVertically) {
            IntStepper("EVM spec (dB)", "spec", specDb, -50, -30, 1) {
                specDb = it
            }
            IntStepper(tr("DPD 系数预算"), "budget", budget, 20, 200, 10) {
                budget = it
            }
            OptionRow(tr("带宽 (MHz)"), "cdBw", listOf(20, 80, 160),
                      bandwidth) { bandwidth = it }
        }

        Button({ generation++ }, enabled = run !is ScreenRun.Busy,
               modifier = Modifier.testTag("runSweep")) {
            Text(tr("运行扫描"))
        }

        when (val state = run) {
            is ScreenRun.Idle -> Unit
            is ScreenRun.Busy -> Text(
                tr("计算中…"), fontSize = 12.sp,
                modifier = Modifier.padding(top = 8.dp)
                    .testTag("cd:busy"),
            )
            is ScreenRun.Failed -> Text(
                state.message, fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 8.dp).testTag("cd:error"),
            )
            is ScreenRun.Ready -> {
                MetricRow(state.screen.metrics)
                for (note in state.screen.notes) {
                    Text(note, fontSize = 11.sp,
                         modifier = Modifier.testTag("cd:note"))
                }
                state.screen.charts["codesign"]?.let { spec ->
                    ChartView(spec, state.blobs,
                              Modifier.padding(vertical = 8.dp)
                                  .testTag("chart:codesign"))
                }
                RowTable(state.screen.rows, "cd:table")
            }
        }

        if (!torchAvailable) {
            Text(
                tr("可微梯度寻优页签需要 torch,在 Android 上不可用;此处只有离散扫描。"),
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 20.dp)
                    .testTag("gradUnavailable"),
            )
        }
    }
}
