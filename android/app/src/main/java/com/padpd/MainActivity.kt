package com.padpd

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.foundation.isSystemInDarkTheme
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
 * Phase 2's deliverable: every chart specification, drawn.
 *
 * There are no product pages yet - Phase 3 builds those. What this proves
 * is that the spec layer plus one renderer covers all fourteen chart
 * shapes `gui_qt/figs.py` produces, including the awkward ones: twin axes,
 * log axes, categorical ticks, equal aspect, NaN gaps and shaded spans.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(
                colorScheme = if (isSystemInDarkTheme()) darkColorScheme()
                              else lightColorScheme(),
            ) {
                Surface(Modifier.fillMaxSize()) { GalleryScreen() }
            }
        }
    }
}

private sealed interface Load {
    data object Pending : Load
    data class Ready(val spec: ChartSpec, val blobs: BlobStore) : Load
    data class Failed(val message: String) : Load
}

@Composable
fun GalleryScreen() {
    val context = androidx.compose.ui.platform.LocalContext.current
    var caps by remember { mutableStateOf<PyBridge.Capabilities?>(null) }
    var entries by remember { mutableStateOf<List<PyBridge.GalleryEntry>>(emptyList()) }
    var bootError by remember { mutableStateOf<String?>(null) }
    val loaded = remember { mutableStateMapOf<String, Load>() }
    var open by remember { mutableStateOf<String?>(null) }
    var clicks by remember { mutableIntStateOf(0) }

    LaunchedEffect(Unit) {
        // Interpreter startup unpacks numpy and scipy; measured at 178 ms
        // on an arm64 device, but never on the UI thread regardless.
        runCatching {
            withContext(Dispatchers.Default) {
                val c = PyBridge.boot(context)
                c to PyBridge.galleryList()
            }
        }.onSuccess { (c, e) -> caps = c; entries = e }
            .onFailure { bootError = it.message ?: it.toString() }
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
        item {
            Header(caps, bootError)
            StateMarkers(open, clicks)
        }
        items(entries, key = { it.id }) { entry ->
            EntryRow(
                entry,
                state = loaded[entry.id],
                expanded = open == entry.id,
                onClick = {
                    clicks++
                    open = if (open == entry.id) null else entry.id
                },
            )
        }
    }
}

/**
 * Zero-size nodes whose test tags carry the screen's own state.
 *
 * Diagnostic scaffolding for a failure that has so far only been
 * observable from outside: a tap that reaches onClick (the semantics
 * action is present and fires) but leaves the row collapsed. Encoding
 * `open` and the click count as tags puts both in the tag list a failing
 * test prints, which separates "onClick never ran" from "it ran and the
 * state change did not reach the row".
 */
@Composable
private fun StateMarkers(open: String?, clicks: Int) {
    Box(Modifier.size(1.dp).testTag("open=${open ?: "none"}"))
    Box(Modifier.size(1.dp).testTag("clicks=$clicks"))
}

@Composable
private fun Header(caps: PyBridge.Capabilities?, error: String?) {
    Column(Modifier.padding(bottom = 12.dp)) {
        Text("padpd chart gallery", fontSize = 20.sp,
             fontWeight = FontWeight.SemiBold)
        when {
            error != null -> Text("Python failed to start: $error",
                                  color = MaterialTheme.colorScheme.error,
                                  fontSize = 12.sp,
                                  modifier = Modifier.testTag("bootError"))
            caps == null -> Text("starting Python…", fontSize = 12.sp)
            else -> Text(
                "padpd ${caps.version} · ${caps.charts.size} chart types · " +
                    "torch unavailable (${caps.unavailable.size} entry points)",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.testTag("caps"),
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
            .clickable(onClick = onClick)
            .padding(10.dp)
            .testTag("entry:${entry.id}"),
    ) {
        // Diagnostic: says what this row was actually handed, so a
        // failure can tell a click that never happened from one whose
        // state change never reached here.
        Box(Modifier.size(1.dp).testTag("expanded:${entry.id}=$expanded"))
        Row(Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically) {
            Text(entry.title, fontSize = 14.sp, fontWeight = FontWeight.Medium)
            ProvenanceChip(entry.provenance)
        }
        Text("${entry.primitive} primitive", fontSize = 11.sp,
             fontFamily = FontFamily.Monospace,
             color = MaterialTheme.colorScheme.onSurfaceVariant)

        if (expanded) {
            when (state) {
                null, is Load.Pending ->
                    // Tagged so a test that sees no chart can tell "the
                    // tap never registered" from "the load never
                    // finished" - the two look identical otherwise.
                    Text("computing…", fontSize = 12.sp,
                         modifier = Modifier.padding(top = 8.dp)
                             .testTag("pending:${entry.id}"))
                is Load.Failed ->
                    Text(state.message, fontSize = 11.sp,
                         fontFamily = FontFamily.Monospace,
                         color = MaterialTheme.colorScheme.error,
                         modifier = Modifier.padding(top = 8.dp)
                             .testTag("error:${entry.id}"))
                is Load.Ready ->
                    ChartView(state.spec, state.blobs,
                              Modifier.padding(top = 8.dp)
                                  .testTag("chart:${entry.id}"))
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
