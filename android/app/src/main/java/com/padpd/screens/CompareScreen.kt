package com.padpd.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.padpd.chart.ChartView
import com.padpd.chart.PyBridge
import com.padpd.i18n.tr
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonPrimitive

/**
 * Compare Runs, the mobile port of gui_qt/pages/compare.py.
 *
 * This screen is the reason the other pages register runs: it reads back
 * what they wrote. The store is gui_core's RunStore under the app's
 * private directory, which is the same registry the desktop GUIs use -
 * so a run recorded on the phone has the same shape as one recorded on a
 * workstation, and the file could be carried between them.
 *
 * Export to JSON is deliberately missing rather than stubbed. It needs
 * the Storage Access Framework, which is not wired up yet; a button that
 * cannot write anywhere is worse than no button, and the desktop's other
 * three actions - compare, delete, refresh - all work here.
 */

private val COLUMNS = listOf(
    "when" to "时间",
    "kind" to "类型",
    "nmse_db" to "nmse_db",
    "evm_db" to "evm_db",
    "aclr_high_dbc" to "aclr_high_dbc",
)

@Composable
fun CompareScreen(lang: String, modifier: Modifier = Modifier) {
    val selected = remember { mutableStateListOf<String>() }
    var run by remember { mutableStateOf<ScreenRun>(ScreenRun.Idle) }
    var generation by remember { mutableIntStateOf(0) }
    // A delete is a request the effect below fulfils, rather than work
    // launched from the click handler. Composition has no scope of its
    // own to hand a coroutine, and building one there would outlive the
    // screen.
    var deleteRequest by remember { mutableStateOf<List<String>?>(null) }
    val busy = deleteRequest != null

    LaunchedEffect(generation, lang) {
        run = ScreenRun.Busy
        run = loadScreen("compare", lang, JsonArray(selected.map {
            JsonPrimitive(it)
        }))
    }

    LaunchedEffect(deleteRequest) {
        val ids = deleteRequest ?: return@LaunchedEffect
        runCatching {
            withContext(Dispatchers.Default) { PyBridge.deleteRuns(ids) }
        }
        selected.clear()
        deleteRequest = null
        generation++
    }

    Column(modifier.fillMaxSize().padding(12.dp)) {
        Text(tr("结果比较"), fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
        Text(
            tr("勾选 run 进行对比;注册表持久化于 gui_runs/,与桌面版同一格式。"),
            fontSize = 11.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Row(Modifier.fillMaxWidth().padding(vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button({ generation++ }, enabled = selected.size >= 2 && !busy,
                   modifier = Modifier.testTag("compareSelected")) {
                Text(tr("对比选中"))
            }
            OutlinedButton(
                { deleteRequest = selected.toList() },
                enabled = selected.isNotEmpty() && !busy,
                modifier = Modifier.testTag("deleteSelected"),
            ) { Text(tr("删除选中")) }
            OutlinedButton({ generation++ },
                           modifier = Modifier.testTag("refreshRuns")) {
                Text(tr("刷新"))
            }
        }

        when (val state = run) {
            is ScreenRun.Idle, is ScreenRun.Busy -> Text(
                tr("计算中…"), fontSize = 12.sp,
                modifier = Modifier.testTag("compare:busy"),
            )
            is ScreenRun.Failed -> Text(
                state.message, fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.testTag("compare:error"),
            )
            is ScreenRun.Ready -> {
                for (note in state.screen.notes) {
                    Text(note, fontSize = 11.sp,
                         modifier = Modifier.testTag("compare:note"))
                }
                state.screen.charts["bars"]?.let { spec ->
                    ChartView(spec, state.blobs,
                              Modifier.padding(vertical = 8.dp)
                                  .testTag("chart:bars"))
                }
                if (state.screen.rows.isEmpty()) {
                    Text(tr("还没有 run。先在建模或 DPD 页跑一次。"),
                         fontSize = 12.sp,
                         modifier = Modifier.testTag("noRuns"))
                } else {
                    RunTable(state.screen.rows, selected)
                }
            }
        }
    }
}

@Composable
private fun RunTable(
    rows: List<Map<String, String>>,
    selected: MutableList<String>,
) {
    LazyColumn(Modifier.fillMaxSize().testTag("runTable")) {
        items(rows, key = { it["id"] ?: it.hashCode().toString() }) { row ->
            val id = row["id"].orEmpty()
            val checked = id in selected
            Column(
                Modifier.fillMaxWidth().padding(vertical = 3.dp)
                    .clip(RoundedCornerShape(6.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant)
                    .padding(8.dp)
                    .testTag("run:$id"),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(
                        checked,
                        {
                            if (checked) selected.remove(id)
                            else selected.add(id)
                        },
                        Modifier.testTag("pick:$id"),
                    )
                    Text(row["name"].orEmpty(), fontSize = 13.sp,
                         fontWeight = FontWeight.Medium)
                }
                Row(Modifier.fillMaxWidth()
                    .horizontalScroll(rememberScrollState())) {
                    for ((key, label) in COLUMNS) {
                        val value = row[key].orEmpty()
                        if (value.isEmpty()) continue
                        // 116.dp, not 96: the "when" column carries a
                        // RunStore timestamp - "2026-08-24 01:23", 16
                        // monospace characters at 12sp - which did not
                        // fit and wrapped onto a second line, in Chinese
                        // as much as in English.
                        Column(Modifier.padding(end = 14.dp).width(116.dp)) {
                            Text(tr(label), fontSize = 9.sp,
                                 maxLines = 1,
                                 overflow = TextOverflow.Ellipsis,
                                 color = MaterialTheme.colorScheme
                                     .onSurfaceVariant)
                            Text(value, fontSize = 12.sp, maxLines = 1,
                                 overflow = TextOverflow.Ellipsis,
                                 fontFamily = FontFamily.Monospace)
                        }
                    }
                }
            }
        }
    }
}
