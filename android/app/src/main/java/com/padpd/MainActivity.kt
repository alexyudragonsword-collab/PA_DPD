package com.padpd

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.padpd.chart.PyBridge
import com.padpd.i18n.Strings
import com.padpd.i18n.tr
import com.padpd.screens.CodesignScreen
import com.padpd.screens.CompareScreen
import com.padpd.screens.DataScreen
import com.padpd.screens.DeployScreen
import com.padpd.screens.DpdScreen
import com.padpd.screens.GalleryScreen
import com.padpd.screens.HomeScreen
import com.padpd.screens.ManualScreen
import com.padpd.screens.ModelingScreen
import com.padpd.screens.Placeholder
import com.padpd.screens.WaveformScreen
import com.padpd.shell.AppShell
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(
                colorScheme = if (isSystemInDarkTheme()) darkColorScheme()
                              else lightColorScheme(),
            ) {
                Surface(Modifier.fillMaxSize()) { PadpdApp() }
            }
        }
    }
}

/**
 * The nine screens of the desktop workbench, plus the chart gallery.
 *
 * All ten were listed from the first commit, while eight were still
 * placeholders: a navigation bar that grows an entry per completed port
 * would have made a half-finished app look finished. All ten are now
 * ported, so the [Placeholder] branch below is unreachable - kept
 * because the `when` is over an enum and a new entry should fail as a
 * placeholder rather than as a missing branch.
 */
// Public because both shells in com.padpd.shell render it.
//
// The emoji are the desktop's, copied from gui_qt/main.py's PAGES, so
// the same page carries the same glyph on a laptop and on a phone. The
// gallery has none there - it is an Android-only screen - so it gets one
// here. They are decoration, never an identifier: the drawer's test tags
// are built from `id`, which is ASCII and fixed.
enum class Destination(val id: String, val zh: String, val emoji: String) {
    HOME("home", "总览", "🏠"),
    WAVEFORM("waveform", "波形工作台", "🌊"),
    MODELING("modeling", "PA 建模", "📈"),
    DPD("dpd", "DPD 实验室", "🎛️"),
    DATA("data", "数据管理", "🗂️"),
    DEPLOY("deploy", "部署", "🚀"),
    COMPARE("compare", "结果比较", "⚖️"),
    CODESIGN("codesign", "联合设计", "🧭"),
    MANUAL("manual", "用户手册", "📖"),
    GALLERY("gallery", "图表画廊", "🖼️"),
}

@Composable
fun PadpdApp() {
    val context = LocalContext.current
    var caps by remember { mutableStateOf<PyBridge.Capabilities?>(null) }
    var bootError by remember { mutableStateOf<String?>(null) }
    var lang by remember { mutableStateOf("zh") }
    var where by remember { mutableStateOf(Destination.WAVEFORM) }

    // The i18n table is refetched on every language change rather than
    // both being cached: it is one call returning a few hundred short
    // strings, and caching two of them would mean holding a copy of the
    // table that Python already owns.
    LaunchedEffect(lang) {
        caps = null
        runCatching {
            withContext(Dispatchers.Default) {
                val c = PyBridge.boot(context, lang)
                Strings.install(PyBridge.i18nMap(lang))
                c
            }
        }.onSuccess { caps = it }
            .onFailure { bootError = it.message ?: it.toString() }
    }

    // This function now owns only what both shells need and neither
    // should own: the boot state, the language, and which destination is
    // current. How those are presented - a nav bar or a drawer - is the
    // shell's business, chosen at build time in AppShell.
    val ready = caps != null && bootError == null
    AppShell(
        current = where,
        onPick = { where = it },
        lang = lang,
        onLang = { lang = it },
        caps = caps,
        navigable = ready,
    ) {
        val error = bootError
        when {
            error != null -> Text(
                tr("Python 启动失败:") + error,
                color = MaterialTheme.colorScheme.error,
                fontSize = 12.sp,
                modifier = Modifier.padding(12.dp).testTag("bootError"),
            )
            caps == null -> Text(
                tr("正在启动 Python…"), fontSize = 12.sp,
                modifier = Modifier.padding(12.dp).testTag("bootPending"),
            )
            else -> when (where) {
                Destination.HOME -> HomeScreen(lang)
                Destination.WAVEFORM -> WaveformScreen(lang)
                Destination.MODELING ->
                    ModelingScreen(lang, torchAvailable = caps!!.torch)
                Destination.DPD ->
                    DpdScreen(lang, torchAvailable = caps!!.torch)
                Destination.DATA -> DataScreen(lang)
                Destination.DEPLOY -> DeployScreen(lang)
                Destination.CODESIGN ->
                    CodesignScreen(lang, torchAvailable = caps!!.torch)
                Destination.COMPARE -> CompareScreen(lang)
                Destination.MANUAL -> ManualScreen(lang)
                Destination.GALLERY -> GalleryScreen()
                else -> Placeholder(tr(where.zh))
            }
        }
    }
}
