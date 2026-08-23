package com.padpd.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.padpd.chart.BlobStore
import com.padpd.chart.ChartSpec
import com.padpd.chart.ChartView
import com.padpd.chart.PyBridge
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * The chart gallery: every specification the renderer can draw, with
 * where its data came from.
 *
 * Not one of the nine ported screens - it is the Phase 2 deliverable,
 * kept because it is the only place the provenance distinction is
 * visible. Half these charts are fixtures, and a screen of plausible
 * charts reads as proof that the pipeline works when for those it is
 * proof of nothing. It is also what GalleryScreenTest drives on device.
 */
private sealed interface Load {
    data object Pending : Load
    data class Ready(val spec: ChartSpec, val blobs: BlobStore) : Load
    data class Failed(val message: String) : Load
}

@Composable
fun GalleryScreen() {
    var entries by remember { mutableStateOf<List<PyBridge.GalleryEntry>>(emptyList()) }
    var listError by remember { mutableStateOf<String?>(null) }
    val loaded = remember { mutableStateMapOf<String, Load>() }
    var open by remember { mutableStateOf<String?>(null) }

    // No boot here: PadpdApp starts the interpreter before any screen is
    // shown. This screen used to do it itself, from when it was the whole
    // app, and leaving that in would have put a second node carrying each
    // of the boot test tags into the tree - which reads as a duplicate-node
    // error rather than as the design mistake it is.
    LaunchedEffect(Unit) {
        runCatching { withContext(Dispatchers.Default) { PyBridge.galleryList() } }
            .onSuccess { entries = it }
            .onFailure { listError = it.message ?: it.toString() }
    }

    LaunchedEffect(open) {
        val id = open ?: return@LaunchedEffect
        if (loaded[id] is Load.Ready) return@LaunchedEffect
        loaded[id] = Load.Pending
        loaded[id] = runCatching {
            withContext(Dispatchers.Default) {
                val spec = PyBridge.galleryChart(id)
                // Resolve every blob now, so panning later never crosses
                // the bridge mid-frame.
                val blobs = PyBridge.newBlobStore().apply { preload(spec) }
                Load.Ready(spec, blobs)
            }
        }.getOrElse { Load.Failed(it.message ?: it.toString()) }
    }

    LazyColumn(Modifier.fillMaxSize().padding(12.dp)) {
        listError?.let { message ->
            item {
                Text(message, fontSize = 11.sp,
                     fontFamily = FontFamily.Monospace,
                     color = MaterialTheme.colorScheme.error,
                     modifier = Modifier.testTag("galleryError"))
            }
        }
        items(entries, key = { it.id }) { entry ->
            EntryRow(
                entry,
                state = loaded[entry.id],
                expanded = open == entry.id,
                onClick = { open = if (open == entry.id) null else entry.id },
            )
        }
    }
}

@Composable
private fun EntryRow(
    entry: PyBridge.GalleryEntry,
    state: Load?,
    expanded: Boolean,
    onClick: () -> Unit,
) {
    Column(
        Modifier.fillMaxWidth().padding(vertical = 4.dp)
            .clip(RoundedCornerShape(8.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .testTag("entry:${entry.id}"),
    ) {
        // The tap target is the caption only, deliberately not the whole
        // row. With clickable on the outer column the chart sat inside
        // the click target, so a tap on a chart collapsed its own row and
        // a drag competed with the renderer's pan and zoom.
        Column(
            Modifier.fillMaxWidth()
                .clickable(onClick = onClick)
                .padding(10.dp)
                .testTag("head:${entry.id}"),
        ) {
            Row(Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically) {
                Text(entry.title, fontSize = 14.sp, fontWeight = FontWeight.Medium)
                ProvenanceChip(entry.provenance)
            }
            Text("${entry.primitive} primitive", fontSize = 11.sp,
                 fontFamily = FontFamily.Monospace,
                 color = MaterialTheme.colorScheme.onSurfaceVariant)
        }

        if (expanded) {
            Column(Modifier.padding(start = 10.dp, end = 10.dp, bottom = 10.dp)) {
                when (state) {
                    null, is Load.Pending ->
                        Text("computing…", fontSize = 12.sp,
                             modifier = Modifier.testTag("pending:${entry.id}"))
                    is Load.Failed ->
                        Text(state.message, fontSize = 11.sp,
                             fontFamily = FontFamily.Monospace,
                             color = MaterialTheme.colorScheme.error,
                             modifier = Modifier.testTag("error:${entry.id}"))
                    is Load.Ready ->
                        ChartView(state.spec, state.blobs,
                                  Modifier.testTag("chart:${entry.id}"))
                }
            }
        }
    }
}

/**
 * Says whether the chart is real output or a fixture.
 *
 * Half these entries carry representative inputs because their real
 * producers are minutes of compute or need torch. A gallery of plausible
 * charts is otherwise very easy to read as proof that the pipeline works.
 */
@Composable
private fun ProvenanceChip(provenance: String) {
    val computed = provenance == "computed"
    Text(
        if (computed) "computed" else "fixture",
        fontSize = 10.sp,
        color = if (computed) Color(0xFF37C978) else Color(0xFFE5B567),
        modifier = Modifier
            .clip(RoundedCornerShape(4.dp))
            .background(MaterialTheme.colorScheme.surface)
            .padding(horizontal = 6.dp, vertical = 2.dp),
    )
}
