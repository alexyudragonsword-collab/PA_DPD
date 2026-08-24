package com.padpd.chart

import android.content.res.Configuration
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.util.Base64

/**
 * Golden images of the chart renderer, rendered on the JVM.
 *
 * These are the pixel comparisons the emulator deliberately does not do.
 * The emulator's binary version comes from the GitHub runner image and
 * moves on GitHub's schedule, so a pixel test there goes red for reasons
 * unrelated to the commit. Here the renderer is layoutlib, pinned by the
 * plugin version, so a changed image means changed drawing code.
 *
 * **The data is real.** Each preview loads a fixture produced by
 * chart_spec.py itself - see tests/test_chart_fixtures.py - rather than a
 * ChartSpec written by hand here. A hand-written spec would test the
 * renderer against a fiction and would quietly omit the awkward cases:
 * a log axis, a twin axis, a categorical axis, a NaN gap in a bar
 * series, a shaded mask band. Those are the ones a renderer gets wrong,
 * and the gallery fixtures carry all of them.
 *
 * **Both themes.** Every chart is rendered light and dark. The dark
 * palette exists in ChartTheme.kt and, until these, had never been
 * rendered by anything: the emulator runs light, so a dark-mode series
 * drawn in a colour that vanishes against its own background would have
 * shipped without complaint.
 */

private val json = Json { ignoreUnknownKeys = true }

/**
 * One fixture: the spec, and a BlobStore over its arrays.
 *
 * BlobStore takes a fetch lambda rather than a bridge, which is what
 * makes this possible at all - no Python, no device, just bytes.
 */
private fun fixture(id: String): Pair<ChartSpec, BlobStore> {
    val stream = requireNotNull(
        ChartGoldensMarker::class.java.classLoader
            ?.getResourceAsStream("chart-fixtures/$id.json"),
    ) { "fixture chart-fixtures/$id.json is not on the classpath" }
    val root = json.parseToJsonElement(
        stream.bufferedReader().use { it.readText() },
    ).jsonObject
    val spec = json.decodeFromJsonElement(
        ChartSpec.serializer(), root.getValue("spec"),
    )
    val blobs = (root.getValue("blobs") as JsonObject)
        .mapValues { (_, v) -> Base64.getDecoder().decode(v.jsonPrimitive.content) }
    return spec to BlobStore { key ->
        requireNotNull(blobs[key]) { "fixture $id references unknown blob $key" }
    }
}

/** Only for its class loader - resources resolve relative to a class. */
private class ChartGoldensMarker

/**
 * A fixed-size frame, so a golden's dimensions come from here and not
 * from whatever the preview device defaults to.
 */
@Composable
private fun Framed(id: String) {
    // Read from the composition rather than passed in: @Preview's uiMode
    // is what layoutlib turns into isSystemInDarkTheme(), and ChartTheme
    // reads the same signal, so the frame and the chart cannot disagree
    // about which palette they are in.
    val dark = isSystemInDarkTheme()
    val (spec, blobs) = fixture(id)
    MaterialTheme(
        colorScheme = if (dark) darkColorScheme() else lightColorScheme(),
    ) {
        Column(
            Modifier.width(360.dp)
                .background(MaterialTheme.colorScheme.background)
                .padding(8.dp),
        ) {
            ChartView(spec, blobs, Modifier.fillMaxWidth())
        }
    }
}

// Two annotations per function rather than two functions: the plugin
// emits one image per @Preview, so this is 14 declarations and 28
// goldens. The uiMode is what drives isSystemInDarkTheme() under
// layoutlib, and therefore which ChartTheme palette is chosen.
private const val NIGHT = Configuration.UI_MODE_NIGHT_YES

@Preview(name = "light", widthDp = 380)
@Preview(name = "dark", widthDp = 380, uiMode = NIGHT)
@Composable
fun PsdGolden() = Framed("psd")

@Preview(name = "light", widthDp = 380)
@Preview(name = "dark", widthDp = 380, uiMode = NIGHT)
@Composable
fun CcdfGolden() = Framed("ccdf")

@Preview(name = "light", widthDp = 380)
@Preview(name = "dark", widthDp = 380, uiMode = NIGHT)
@Composable
fun AmAmGolden() = Framed("amam")

@Preview(name = "light", widthDp = 380)
@Preview(name = "dark", widthDp = 380, uiMode = NIGHT)
@Composable
fun ConstellationGolden() = Framed("constellation")

@Preview(name = "light", widthDp = 380)
@Preview(name = "dark", widthDp = 380, uiMode = NIGHT)
@Composable
fun TimeGolden() = Framed("time")

@Preview(name = "light", widthDp = 380)
@Preview(name = "dark", widthDp = 380, uiMode = NIGHT)
@Composable
fun BitwidthGolden() = Framed("bitwidth")

@Preview(name = "light", widthDp = 380)
@Preview(name = "dark", widthDp = 380, uiMode = NIGHT)
@Composable
fun GainModulationGolden() = Framed("gain_modulation")

@Preview(name = "light", widthDp = 380)
@Preview(name = "dark", widthDp = 380, uiMode = NIGHT)
@Composable
fun AdaptiveEvmGolden() = Framed("adaptive_evm")

@Preview(name = "light", widthDp = 380)
@Preview(name = "dark", widthDp = 380, uiMode = NIGHT)
@Composable
fun ThreeLoopGolden() = Framed("three_loop")

@Preview(name = "light", widthDp = 380)
@Preview(name = "dark", widthDp = 380, uiMode = NIGHT)
@Composable
fun TwoToneGolden() = Framed("two_tone")

@Preview(name = "light", widthDp = 380)
@Preview(name = "dark", widthDp = 380, uiMode = NIGHT)
@Composable
fun BarsGolden() = Framed("bars")

@Preview(name = "light", widthDp = 380)
@Preview(name = "dark", widthDp = 380, uiMode = NIGHT)
@Composable
fun TrainGolden() = Framed("train")

@Preview(name = "light", widthDp = 380)
@Preview(name = "dark", widthDp = 380, uiMode = NIGHT)
@Composable
fun CodesignGolden() = Framed("codesign")

@Preview(name = "light", widthDp = 380)
@Preview(name = "dark", widthDp = 380, uiMode = NIGHT)
@Composable
fun GradGolden() = Framed("grad")
