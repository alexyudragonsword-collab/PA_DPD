package com.padpd

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.padpd.chart.PyBridge
import com.padpd.i18n.Strings
import com.padpd.i18n.tr
import com.padpd.screens.GalleryScreen
import com.padpd.screens.Placeholder
import com.padpd.screens.WaveformScreen
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
 * All ten are listed from the start even though eight are placeholders.
 * A navigation bar that grows an entry per completed port would make a
 * half-finished app look finished; this one shows the shape of the whole
 * and what is still missing.
 */
private enum class Destination(val id: String, val zh: String) {
    HOME("home", "总览"),
    WAVEFORM("waveform", "波形工作台"),
    MODELING("modeling", "PA 建模"),
    DPD("dpd", "DPD 实验室"),
    DATA("data", "数据管理"),
    DEPLOY("deploy", "部署"),
    COMPARE("compare", "结果比较"),
    CODESIGN("codesign", "联合设计"),
    MANUAL("manual", "用户手册"),
    GALLERY("gallery", "图表画廊"),
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

    Column(Modifier.fillMaxSize()) {
        TopBar(lang, onLang = { lang = it })

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
            else -> {
                CapabilityLine(caps!!)
                NavBar(where) { where = it }
                when (where) {
                    Destination.WAVEFORM -> WaveformScreen(lang)
                    Destination.GALLERY -> GalleryScreen()
                    else -> Placeholder(tr(where.zh))
                }
            }
        }
    }
}

/**
 * What this build can and cannot do, stated up front.
 *
 * torch has no Android wheel, so five entry points cannot run at all.
 * Saying so here - rather than only greying controls where they appear -
 * means the limitation is visible before someone plans work around it.
 */
@Composable
private fun CapabilityLine(caps: PyBridge.Capabilities) {
    Text(
        "padpd ${caps.version} · " +
            tr("{n} 种图表", "n" to caps.charts.size) + " · " +
            tr("torch 不可用({n} 个入口)", "n" to caps.unavailable.size),
        fontSize = 11.sp,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(horizontal = 12.dp).testTag("caps"),
    )
}

@Composable
private fun TopBar(lang: String, onLang: (String) -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            tr("WiFi 7 PA + DPD 工作台"),
            fontSize = 15.sp, fontWeight = FontWeight.SemiBold,
            modifier = Modifier.testTag("appTitle"),
        )
        Row(Modifier.fillMaxWidth().padding(start = 12.dp)) {
            for (code in listOf("zh", "en")) {
                Text(
                    code.uppercase(),
                    fontSize = 12.sp,
                    fontWeight = if (code == lang) FontWeight.Bold
                                 else FontWeight.Normal,
                    color = if (code == lang) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(end = 8.dp)
                        .testTag("lang:$code")
                        .clickable { onLang(code) },
                )
            }
        }
    }
}

@Composable
private fun NavBar(current: Destination, onPick: (Destination) -> Unit) {
    Row(
        Modifier.fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 4.dp)
            .horizontalScroll(rememberScrollState())
            .testTag("nav"),
    ) {
        for (d in Destination.entries) {
            val here = d == current
            Text(
                tr(d.zh),
                fontSize = 13.sp,
                fontWeight = if (here) FontWeight.Bold else FontWeight.Normal,
                color = if (here) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(end = 14.dp)
                    .testTag("nav:${d.id}")
                    .clickable { onPick(d) },
            )
        }
    }
}
