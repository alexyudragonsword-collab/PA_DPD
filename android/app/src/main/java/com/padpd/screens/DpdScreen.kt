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
import androidx.compose.material3.Switch
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.padpd.i18n.tr
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive

/**
 * DPD Lab, the mobile port of gui_qt/pages/dpd.py.
 *
 * Three independent experiments on one page, matching the desktop:
 * indirect learning against the live PA, an adaptive DPD tracking a
 * drifting one, and the three-loop front-end demo. Each keeps its own
 * button, result and error - they answer different questions and the
 * desktop deliberately does not run them together.
 *
 * The DLA branch is absent for the same reason the neural model family
 * is disabled on the modeling page: it needs torch, which has no Android
 * wheel. Here the whole algorithm choice would be a control with one
 * usable option, so the section says so in a line instead of offering a
 * picker that cannot pick.
 */

private val ILA_BASES = listOf(
    "GMP-510 (OpenDPD)", "MP-500 (OpenDPD)", "GMP", "MP", "Spline-MP (K8,M4)",
)
private val BANDWIDTHS = listOf(20, 40, 80, 160, 320)
private val ADAPTIVE_METHODS = listOf("rls", "whitened", "apa")
private val ADAPTIVE_BASES = listOf("gmp", "spline")
private val ADAPTIVE_DUTS = listOf("drift", "thermal")
private val ILA_TABS = listOf("psd" to "PSD", "constellation" to "星座")

@Composable
fun DpdScreen(lang: String, torchAvailable: Boolean,
              modifier: Modifier = Modifier) {
    Column(modifier.fillMaxSize().padding(12.dp)
        .verticalScroll(rememberScrollState())) {
        Text(tr("DPD 实验室"), fontSize = 18.sp,
             fontWeight = FontWeight.SemiBold)

        IlaSection(lang, torchAvailable)

        SectionTitle(tr("自适应 DPD(漂移跟踪)"))
        AdaptiveSection(lang)

        SectionTitle(tr("前端三环演示"))
        ThreeLoopSection(lang)
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(text, fontSize = 14.sp, fontWeight = FontWeight.Medium,
         modifier = Modifier.padding(top = 20.dp))
}

@Composable
private fun IlaSection(lang: String, torchAvailable: Boolean) {
    var basis by remember { mutableStateOf("GMP-510 (OpenDPD)") }
    var bandwidth by remember { mutableIntStateOf(80) }
    var driveHundredths by remember { mutableIntStateOf(13) }
    var cfrOn by remember { mutableStateOf(false) }
    var run by remember { mutableStateOf<ScreenRun>(ScreenRun.Idle) }
    var generation by remember { mutableIntStateOf(0) }
    var tab by remember { mutableIntStateOf(0) }

    LaunchedEffect(generation, lang) {
        if (generation == 0) return@LaunchedEffect
        run = ScreenRun.Busy
        run = loadScreen("dpd_ila", lang,
            JsonPrimitive(basis), JsonPrimitive(bandwidth),
            JsonPrimitive(driveHundredths / 100.0),
            if (cfrOn) JsonPrimitive(CFR_PAPR_DB) else JsonNull)
    }

    Scrollable { OptionRow(tr("基函数"), "ilaBasis", ILA_BASES, basis) { basis = it } }
    Scrollable {
        OptionRow(tr("带宽(MHz)"), "ilaBw", BANDWIDTHS, bandwidth) { bandwidth = it }
    }
    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
        verticalAlignment = Alignment.CenterVertically) {
        IntStepper("drive", "ilaDrive", driveHundredths, 6, 24, 1,
                   display = { "0.%02d".format(it) }) { driveHundredths = it }
        Text(tr("CFR 削峰"), fontSize = 12.sp)
        Switch(cfrOn, { cfrOn = it }, Modifier.testTag("dpdCfr"))
    }

    if (!torchAvailable) {
        Text(
            tr("DLA(神经 DPD)需要 torch,在 Android 上不可用;此处只有 ILA。"),
            fontSize = 11.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.testTag("dlaUnavailable"),
        )
    }

    Button({ generation++ }, enabled = run !is ScreenRun.Busy,
           modifier = Modifier.testTag("runIla")) { Text(tr("运行 DPD")) }
    RunResult(run, "ila", ILA_TABS, tab) { tab = it }
}

@Composable
private fun AdaptiveSection(lang: String) {
    var method by remember { mutableStateOf("rls") }
    var basis by remember { mutableStateOf("gmp") }
    var dut by remember { mutableStateOf("drift") }
    var blocks by remember { mutableIntStateOf(10) }
    var bandwidth by remember { mutableIntStateOf(80) }
    var run by remember { mutableStateOf<ScreenRun>(ScreenRun.Idle) }
    var generation by remember { mutableIntStateOf(0) }

    LaunchedEffect(generation, lang) {
        if (generation == 0) return@LaunchedEffect
        run = ScreenRun.Busy
        run = loadScreen("adaptive_dpd", lang,
            JsonPrimitive(method), JsonPrimitive(basis), JsonPrimitive(dut),
            JsonPrimitive(blocks), JsonPrimitive(bandwidth))
    }

    Scrollable {
        OptionRow(tr("方法"), "adMethod", ADAPTIVE_METHODS, method) { method = it }
    }
    Scrollable {
        OptionRow(tr("基"), "adBasis", ADAPTIVE_BASES, basis) { basis = it }
        OptionRow(tr("虚拟 DUT"), "adDut", ADAPTIVE_DUTS, dut) { dut = it }
    }
    Scrollable {
        IntStepper(tr("块数"), "adBlocks", blocks, 4, 30, 2) { blocks = it }
        OptionRow(tr("带宽(MHz)"), "adBw", BANDWIDTHS, bandwidth) { bandwidth = it }
    }

    Button({ generation++ }, enabled = run !is ScreenRun.Busy,
           modifier = Modifier.testTag("runAdaptive")) {
        Text(tr("运行自适应 DPD"))
    }
    RunResult(run, "adaptive", listOf("adaptive_evm" to "自适应(漂移)"), 0) {}
}

@Composable
private fun ThreeLoopSection(lang: String) {
    var blocks by remember { mutableIntStateOf(10) }
    var spanThousandths by remember { mutableIntStateOf(20) }
    var loDbc by remember { mutableIntStateOf(-35) }
    var iqTenths by remember { mutableIntStateOf(3) }
    var run by remember { mutableStateOf<ScreenRun>(ScreenRun.Idle) }
    var generation by remember { mutableIntStateOf(0) }

    LaunchedEffect(generation, lang) {
        if (generation == 0) return@LaunchedEffect
        run = ScreenRun.Busy
        run = loadScreen("three_loop", lang,
            JsonPrimitive(blocks), JsonPrimitive(spanThousandths / 1000.0),
            JsonPrimitive(loDbc.toDouble()), JsonPrimitive(iqTenths / 10.0))
    }

    Scrollable {
        IntStepper(tr("块数"), "tlBlocks", blocks, 4, 30, 2) { blocks = it }
        IntStepper(tr("漂移幅度"), "tlSpan", spanThousandths, 5, 60, 5,
                   display = { "0.%03d".format(it) }) { spanThousandths = it }
    }
    Scrollable {
        IntStepper(tr("LO 泄漏(dBc)"), "tlLo", loDbc, -50, -20, 5) { loDbc = it }
        // One control drives both halves of the IQ imbalance: pages.py
        // sets phase_deg to ten times gain_db, as the desktop does, so
        // the pair cannot be made inconsistent from the UI.
        IntStepper(tr("IQ 增益失衡(dB)"), "tlIq", iqTenths, 1, 10, 1,
                   display = { "0.%d".format(it) }) { iqTenths = it }
    }

    Button({ generation++ }, enabled = run !is ScreenRun.Busy,
           modifier = Modifier.testTag("runThreeLoop")) {
        Text(tr("运行三环演示"))
    }
    RunResult(run, "tl", listOf("three_loop" to "前端三环"), 0) {}
}

/** A horizontally scrolling row, since the shared controls do not scroll. */
@Composable
private fun Scrollable(content: @Composable () -> Unit) {
    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
        verticalAlignment = Alignment.CenterVertically) { content() }
}

private const val CFR_PAPR_DB = 8.0
