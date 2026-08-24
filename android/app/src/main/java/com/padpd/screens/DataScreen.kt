package com.padpd.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.padpd.data.SafImport
import com.padpd.i18n.tr
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonPrimitive

/**
 * Data Manager, the mobile port of gui_qt/pages/data.py.
 *
 * Two panels, as on the desktop: registered sources with their preview,
 * and the two-tone IM3 diagnostic. They read different files and answer
 * different questions, so on this side each is its own Python screen -
 * the desktop puts them on one page only because a desktop page is
 * large enough to hold both.
 *
 * **Importing.** The picker returns a `content://` URI, which Python
 * cannot open; [SafImport.copyToCache] copies the bytes out while the
 * grant is live and hands over a real path. The copy happens off the UI
 * thread with the load that follows it - a 40 MB capture read through a
 * ContentResolver is not instant, and it is the same rule the desktop
 * follows with FnWorker.
 *
 * **OpenDPD dataset directories are not offered.** They are directory
 * trees keyed by a spec.json, and a tree import means walking a document
 * tree and copying every member out through SAF. The screen says so
 * rather than showing a directory field that cannot be filled; the
 * single-file importers cover .npz, .csv and .mat.
 */
@Composable
fun DataScreen(lang: String, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxSize().padding(12.dp)
        .verticalScroll(rememberScrollState())) {
        Text(tr("数据管理"), fontSize = 18.sp,
             fontWeight = FontWeight.SemiBold)
        Text(
            tr("加载实测/仿真 PA 数据并注册为数据源。"),
            fontSize = 11.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        SourcesPanel(lang)
        TwoTonePanel(lang)
    }
}

@Composable
private fun SourcesPanel(lang: String) {
    val context = LocalContext.current
    // The action is part of the load key rather than a side effect, so
    // that a recomposition cannot replay an import: every request is a
    // new generation, and the generation is what LaunchedEffect keys on.
    var action by remember { mutableStateOf("") }
    var path by remember { mutableStateOf("") }
    var selected by remember { mutableStateOf("") }
    var autoAlign by remember { mutableStateOf(false) }
    var generation by remember { mutableIntStateOf(0) }
    var run by remember { mutableStateOf<ScreenRun>(ScreenRun.Idle) }
    var importError by remember { mutableStateOf<String?>(null) }
    var tab by remember { mutableIntStateOf(0) }

    val picker = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri ->
        if (uri != null) {
            // Only the URI is captured here; the copy runs in the load
            // below, where it is already off the UI thread.
            path = uri.toString()
            action = "pick"
            generation++
        }
    }

    // generation 0 still loads: the screen must show what is already
    // registered, the same reason the Deployment screen loads its model
    // list before anything is selected.
    LaunchedEffect(generation, lang) {
        run = ScreenRun.Busy
        // A failed copy is reported rather than folded into "nothing was
        // picked": the user chose a document and is owed the reason it
        // did not arrive - a revoked grant reads exactly like a no-op
        // otherwise.
        val copied = if (action == "pick") runCatching {
            withContext(Dispatchers.Default) {
                SafImport.copyToCache(context, Uri.parse(path))
            }
        } else null
        val failure = copied?.exceptionOrNull()
        importError = failure?.let { it.message ?: it.toString() }
        // The screen still loads on a failed copy. Reporting the failure
        // as the whole screen's state would empty the source list, which
        // says the registered sources are gone when only the import
        // failed.
        val act = if (failure == null && copied != null) "load" else action
        val arg = if (failure == null) copied?.getOrThrow() ?: path else ""
        run = loadScreen("data", lang,
                         JsonPrimitive(if (act == "pick") "" else act),
                         JsonPrimitive(arg), JsonPrimitive(selected),
                         JsonPrimitive(autoAlign))
        // Python returns the source it previewed first, so this follows
        // the selection it actually made rather than the one that was
        // asked for - a removed source leaves neither.
        selected = (run as? ScreenRun.Ready)?.screen?.options
            .orEmpty().firstOrNull().orEmpty()
        action = ""
        path = ""
    }

    val names = (run as? ScreenRun.Ready)?.screen?.options.orEmpty()

    Row(Modifier.fillMaxWidth().padding(top = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Button({ action = "example"; generation++ },
               enabled = run !is ScreenRun.Busy,
               modifier = Modifier.testTag("loadExample")) {
            Text(tr("载入完整源示例"))
        }
        OutlinedButton({ picker.launch(SafImport.SOURCE_TYPES) },
                       enabled = run !is ScreenRun.Busy,
                       modifier = Modifier.testTag("importFile")) {
            Text(tr("打开文件 (CSV/.mat/.npz)…"))
        }
    }
    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState())) {
        MultiOptionRow(tr("自动延迟对齐"), "align", listOf("on"),
                       if (autoAlign) listOf("on") else emptyList()) {
            autoAlign = !autoAlign
        }
    }

    if (names.size > 1) {
        Row(Modifier.fillMaxWidth()
            .horizontalScroll(rememberScrollState())) {
            OptionRow(tr("已注册数据源"), "source", names, selected) {
                selected = it
                generation++
            }
        }
    }
    if (names.isNotEmpty()) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton({ action = "consume"; generation++ },
                           enabled = run !is ScreenRun.Busy,
                           modifier = Modifier.testTag("consumeExtras")) {
                Text(tr("运行完整源工具"))
            }
            OutlinedButton({ action = "remove"; generation++ },
                           enabled = run !is ScreenRun.Busy,
                           modifier = Modifier.testTag("removeSource")) {
                Text(tr("移除"))
            }
        }
    }

    importError?.let { message ->
        Text(tr("❌ 加载失败:{e}").replace("{e}", message), fontSize = 11.sp,
             color = MaterialTheme.colorScheme.error,
             modifier = Modifier.padding(top = 8.dp)
                 .testTag("data:importError"))
    }

    RunResult(run, "data",
              listOf("psd" to "PSD", "amam" to "AM-AM / AM-PM"),
              tab) { tab = it }
    (run as? ScreenRun.Ready)?.let { RowTable(it.screen.rows, "data:table") }

    Text(
        // One literal, not two concatenated - see the note in
        // DeployScreen: the i18n guard reads Kotlin string literals.
        tr("OpenDPD 数据集是目录树,SAF 只按文件授权,故此处不提供目录扫描;请用单文件导入(.npz/.csv/.mat)。"),
        fontSize = 11.sp,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = 12.dp)
            .testTag("opendpdUnavailable"),
    )
}

@Composable
private fun TwoTonePanel(lang: String) {
    val context = LocalContext.current
    var path by remember { mutableStateOf("") }
    var generation by remember { mutableIntStateOf(0) }
    var run by remember { mutableStateOf<ScreenRun>(ScreenRun.Idle) }

    val picker = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri ->
        if (uri != null) {
            path = uri.toString()
            generation++
        }
    }

    LaunchedEffect(generation, lang) {
        if (generation == 0) return@LaunchedEffect
        run = ScreenRun.Busy
        val arg = if (path.isEmpty()) "" else runCatching {
            withContext(Dispatchers.Default) {
                SafImport.copyToCache(context, Uri.parse(path))
            }
        }.getOrDefault("")
        run = loadScreen("two_tone", lang, JsonPrimitive(arg))
        path = ""
    }

    Text(tr("双音记忆诊断"), fontSize = 14.sp,
         fontWeight = FontWeight.Medium,
         modifier = Modifier.padding(top = 24.dp))
    Text(
        tr("载入双音扫音间距的 IM3 表,用记忆强度预判 DPD 该预留多少记忆。"),
        fontSize = 11.sp,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Row(Modifier.fillMaxWidth().padding(top = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Button({ path = ""; generation++ },
               enabled = run !is ScreenRun.Busy,
               modifier = Modifier.testTag("twoToneExample")) {
            Text(tr("载入示例"))
        }
        OutlinedButton({ picker.launch(SafImport.SOURCE_TYPES) },
                       enabled = run !is ScreenRun.Busy,
                       modifier = Modifier.testTag("twoToneImport")) {
            Text(tr("载入双音 IM3 表 (CSV)…"))
        }
    }
    RunResult(run, "twoTone", listOf("two_tone" to "双音 IM3"), 0) {}
}
