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
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.padpd.chart.ChartView
import com.padpd.i18n.tr
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonPrimitive

/**
 * Deployment, the mobile port of gui_qt/pages/deploy.py.
 *
 * Sweeps run over models the Modeling screen fitted this session, which
 * is the same coupling the desktop has - a model is a live object, so the
 * run store holds its metrics and not the object itself. With nothing
 * fitted the screen says so, exactly as the desktop's empty list does.
 *
 * Export of hand-off artefacts is stated as unavailable rather than
 * offered. It needs three things this platform does not have: a writable
 * directory through the Storage Access Framework, ONNX export through
 * torch, and an iverilog run for the RTL bit-true check. Any one of them
 * would make the button fail; all three make it dishonest to draw.
 */

private val ALL_BITS = listOf(16, 14, 12, 10, 8)

@Composable
fun DeployScreen(lang: String, modifier: Modifier = Modifier) {
    val models = remember { mutableStateListOf<String>() }
    val bits = remember { mutableStateListOf(16, 12, 8) }
    var run by remember { mutableStateOf<ScreenRun>(ScreenRun.Idle) }
    var generation by remember { mutableIntStateOf(0) }
    var lutFor by remember { mutableStateOf<String?>(null) }
    var lut by remember { mutableStateOf<ScreenRun>(ScreenRun.Idle) }

    // generation 0 still loads: the screen has to list what is fitted
    // before anything can be selected, unlike the compute screens where
    // an idle state means "nothing asked for yet".
    LaunchedEffect(generation, lang) {
        run = ScreenRun.Busy
        run = loadScreen("deploy", lang,
            JsonArray(models.map { JsonPrimitive(it) }),
            JsonArray(bits.map { JsonPrimitive(it) }))
    }

    LaunchedEffect(lutFor, lang) {
        val name = lutFor ?: return@LaunchedEffect
        lut = ScreenRun.Busy
        lut = loadScreen("lut_depth", lang, JsonPrimitive(name))
    }

    val available = (run as? ScreenRun.Ready)?.screen?.options ?: emptyList()

    Column(modifier.fillMaxSize().padding(12.dp)
        .verticalScroll(rememberScrollState())) {
        Text(tr("部署"), fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
        Text(
            tr("定点位宽扫描(bit-true)+ 硬件成本估计。"),
            fontSize = 11.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        if (available.isEmpty()) {
            Text(tr("先在建模页拟合模型"), fontSize = 12.sp,
                 modifier = Modifier.padding(top = 12.dp)
                     .testTag("noModels"))
        } else {
            Row(Modifier.fillMaxWidth()
                .horizontalScroll(rememberScrollState())) {
                MultiOptionRow(tr("模型(勾选)"), "model", available, models) { name ->
                    if (name in models) models.remove(name)
                    else models.add(name)
                }
            }
            Row(Modifier.fillMaxWidth()
                .horizontalScroll(rememberScrollState())) {
                MultiOptionRow(tr("位宽"), "bits", ALL_BITS, bits) { b ->
                    if (b in bits) bits.remove(b) else bits.add(b)
                }
            }
            Button({ generation++ },
                   enabled = run !is ScreenRun.Busy && models.isNotEmpty()
                       && bits.isNotEmpty(),
                   modifier = Modifier.testTag("sweep")) {
                Text(tr("位宽扫描"))
            }
        }

        SweepResult(run, "sweep")

        if (available.isNotEmpty()) {
            Text(tr("LUT 深度扫描"), fontSize = 14.sp,
                 fontWeight = FontWeight.Medium,
                 modifier = Modifier.padding(top = 20.dp))
            Row(Modifier.fillMaxWidth()
                .horizontalScroll(rememberScrollState())) {
                OptionRow(tr("模型"), "lutModel", available, lutFor ?: available.first()) {
                    lutFor = it
                }
            }
            Button({ lutFor = lutFor ?: available.first() },
                   enabled = lut !is ScreenRun.Busy,
                   modifier = Modifier.testTag("lutSweep")) {
                Text(tr("LUT 深度扫描"))
            }
            SweepResult(lut, "lut")
        }

        Text(
            // One literal, not two concatenated: the i18n guard reads
            // Kotlin with a regex over string literals, so a key split
            // across a `+` is two keys that will never be found.
            tr("导出交接产物在 Android 上不可用:需要可写目录(SAF)、ONNX 导出(torch)与 iverilog 做 RTL bit-true 校验。"),
            fontSize = 11.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 20.dp)
                .testTag("exportUnavailable"),
        )
    }
}

@Composable
private fun SweepResult(run: ScreenRun, tagPrefix: String) {
    when (run) {
        is ScreenRun.Idle -> Unit
        is ScreenRun.Busy -> Text(
            tr("计算中…"), fontSize = 12.sp,
            modifier = Modifier.padding(top = 8.dp)
                .testTag("$tagPrefix:busy"),
        )
        is ScreenRun.Failed -> Text(
            run.message, fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            color = MaterialTheme.colorScheme.error,
            modifier = Modifier.padding(top = 8.dp)
                .testTag("$tagPrefix:error"),
        )
        is ScreenRun.Ready -> {
            if (run.screen.metrics.isNotEmpty()) {
                MetricRow(run.screen.metrics)
            }
            for (note in run.screen.notes) {
                Text(note, fontSize = 11.sp,
                     modifier = Modifier.testTag("$tagPrefix:note"))
            }
            run.screen.charts["bitwidth"]?.let { spec ->
                ChartView(spec, run.blobs,
                          Modifier.padding(vertical = 8.dp)
                              .testTag("chart:bitwidth"))
            }
            RowTable(run.screen.rows, "$tagPrefix:table")
        }
    }
}
