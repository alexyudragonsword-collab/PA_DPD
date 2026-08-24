package com.padpd.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import com.padpd.chart.ChartView
import com.padpd.chart.PyBridge
import com.padpd.i18n.tr
import kotlinx.serialization.json.JsonPrimitive

/**
 * PA Modeling, the mobile port of gui_qt/pages/modeling.py.
 *
 * Two independent actions on one screen, as on the desktop: fit a model,
 * and identify gain modulation by step response. They share nothing but
 * the page, so each has its own button, its own result and its own
 * error - a single combined "run" control would tie two experiments
 * together that the desktop deliberately keeps apart.
 *
 * The neural family is shown and disabled rather than hidden. torch has
 * no Android wheel, so `fit_neural` cannot run here; omitting the option
 * would make the phone look like it offers a smaller method set than it
 * does, when what is actually true is that this platform cannot host it.
 *
 * The source picker is absent for now: the Data page is not ported, so
 * the synthetic ReferencePA is the only source that exists here.
 */

private val MODEL_TYPES = listOf(
    "MP", "GMP", "DDR", "Spline-MP",
    "MP-500 (OpenDPD)", "GMP-510 (OpenDPD)", "DDR-140 (preset)",
    "Spline-MP (K8,M4)", "Spline-GMP (K8)",
    "Spline-MP-WL (conj+dc)", "Spline-MP-CIM3 (conj3+dc)",
)
private val FRONTENDS = listOf("none", "iq", "iq+lo", "iq+lo+cim3")
private val GAIN_MOD_DUTS = listOf("thermal", "static")
private val FIT_TABS = listOf("psd" to "PSD", "amam" to "AM-AM / AM-PM")

@Composable
fun ModelingScreen(lang: String, torchAvailable: Boolean,
                   modifier: Modifier = Modifier) {
    Column(modifier.fillMaxSize().padding(12.dp)
        .verticalScroll(rememberScrollState())) {
        Text(tr("PA 建模"), fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
        FitSection(lang, torchAvailable)
        Text(
            tr("增益调制辨识(τ 表征 → 状态样条)"),
            fontSize = 14.sp, fontWeight = FontWeight.Medium,
            modifier = Modifier.padding(top = 20.dp),
        )
        GainModSection(lang)
    }
}

@Composable
private fun FitSection(lang: String, torchAvailable: Boolean) {
    var modelType by remember { mutableStateOf("GMP") }
    var order by remember { mutableIntStateOf(5) }
    var memory by remember { mutableIntStateOf(4) }
    var driveHundredths by remember { mutableIntStateOf(14) }
    var frontend by remember { mutableStateOf("none") }
    var neural by remember { mutableStateOf(false) }
    var run by remember { mutableStateOf<ScreenRun>(ScreenRun.Idle) }
    var generation by remember { mutableIntStateOf(0) }
    var tab by remember { mutableIntStateOf(0) }

    LaunchedEffect(generation, lang) {
        if (generation == 0) return@LaunchedEffect
        run = ScreenRun.Busy
        run = loadScreen("modeling", lang,
            JsonPrimitive(modelType), JsonPrimitive(order),
            JsonPrimitive(memory), JsonPrimitive(driveHundredths / 100.0),
            JsonPrimitive(frontend))
    }

    Row(Modifier.fillMaxWidth()
        .horizontalScroll(rememberScrollState())) {
        OptionRow(tr("类型"), "modelType", MODEL_TYPES, modelType) { modelType = it }
    }
    Row(Modifier.fillMaxWidth()
        .horizontalScroll(rememberScrollState())) {
        OptionRow(tr("前端"), "frontend", FRONTENDS, frontend) { frontend = it }
    }
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp)
        .horizontalScroll(rememberScrollState())) {
        IntStepper(tr("阶数"), "order", order, 3, 9, 1) { order = it }
        IntStepper(tr("记忆"), "memory", memory, 1, 30, 1) { memory = it }
        // drive is 0.06..0.24 in 0.01 steps; held as hundredths so the
        // stepper stays integer arithmetic and cannot drift.
        IntStepper("drive", "fitDrive", driveHundredths, 6, 24, 1,
                   display = { "0.%02d".format(it) }) { driveHundredths = it }
    }

    Row(verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.padding(vertical = 4.dp)) {
        Text(tr("神经 (SGD)"), fontSize = 12.sp,
             color = if (torchAvailable) MaterialTheme.colorScheme.onSurface
                     else MaterialTheme.colorScheme.onSurfaceVariant)
        Switch(neural, { neural = it }, enabled = torchAvailable,
               modifier = Modifier.testTag("neural"))
    }
    if (!torchAvailable) {
        Text(
            tr("torch 在 Android 上没有可用轮子,神经模型无法在设备上训练。"),
            fontSize = 11.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.testTag("torchUnavailable"),
        )
    }

    Button({ generation++ }, enabled = run !is ScreenRun.Busy && !neural,
           modifier = Modifier.testTag("fit")) { Text(tr("拟合模型")) }

    RunResult(run, "fit", FIT_TABS, tab) { tab = it }
}

@Composable
private fun GainModSection(lang: String) {
    var dut by remember { mutableStateOf("thermal") }
    var driveHundredths by remember { mutableIntStateOf(13) }
    var fitState by remember { mutableStateOf(true) }
    var run by remember { mutableStateOf<ScreenRun>(ScreenRun.Idle) }
    var generation by remember { mutableIntStateOf(0) }

    LaunchedEffect(generation, lang) {
        if (generation == 0) return@LaunchedEffect
        run = ScreenRun.Busy
        run = loadScreen("gain_modulation", lang,
            JsonPrimitive(dut), JsonPrimitive(driveHundredths / 100.0),
            JsonPrimitive(fitState))
    }

    Row(Modifier.fillMaxWidth()
        .horizontalScroll(rememberScrollState())) {
        OptionRow(tr("虚拟 DUT"), "gmDut", GAIN_MOD_DUTS, dut) { dut = it }
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        IntStepper("drive", "gmDrive", driveHundredths, 6, 24, 1,
                   display = { "0.%02d".format(it) }) { driveHundredths = it }
        Text(tr("拟合状态样条"), fontSize = 12.sp)
        Switch(fitState, { fitState = it }, Modifier.testTag("fitState"))
    }
    Button({ generation++ }, enabled = run !is ScreenRun.Busy,
           modifier = Modifier.testTag("runGainMod")) { Text(tr("运行辨识")) }

    RunResult(run, "gm", listOf("gain_modulation" to "增益调制"), 0) {}
}
