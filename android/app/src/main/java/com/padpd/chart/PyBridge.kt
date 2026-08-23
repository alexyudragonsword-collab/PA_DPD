package com.padpd.chart

import android.content.Context
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.MapSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/**
 * The Kotlin half of the bridge to `padpd_mobile.api`.
 *
 * Every method here blocks - Python calls run a real fit, and the
 * interpreter is single-threaded under one GIL. None of them may be
 * called from the UI thread; [PadpdViewModel] keeps them on
 * `Dispatchers.Default`, one at a time. This mirrors the rule the desktop
 * Qt GUI follows with FnWorker.
 */
object PyBridge {

    private var api: PyObject? = null

    /** Capabilities as reported by the Python side after boot. */
    @Serializable
    data class Capabilities(
        val version: String = "",
        val lang: String = "zh",
        val torch: Boolean = false,
        val onnx: Boolean = false,
        val unavailable: List<String> = emptyList(),
        val charts: List<String> = emptyList(),
    )

    @Serializable
    data class GalleryEntry(
        val id: String,
        val title: String,
        val primitive: String,
        val provenance: String,     // "computed" | "sampled"
    )

    @Serializable
    private data class GalleryListing(
        val ok: Boolean, val entries: List<GalleryEntry> = emptyList(),
    )

    /** One metric card. Values arrive already formatted - see pages.py. */
    @Serializable
    data class Metric(
        val label: String,
        val value: String,
        val note: String = "",
    )

    /** One assembled screen: what [page] returns. */
    data class Screen(
        val handle: String,
        val metrics: List<Metric>,
        val charts: Map<String, ChartSpec>,
    )

    @Serializable
    private data class PageReply(
        val ok: Boolean,
        val handle: String = "",
        val metrics: List<Metric> = emptyList(),
        val charts: Map<String, ChartSpec> = emptyMap(),
        val error: String = "",
        val traceback: String = "",
    )

    @Serializable
    private data class ChartReply(
        val ok: Boolean,
        val id: String = "",
        val spec: ChartSpec? = null,
        val error: String = "",
        val traceback: String = "",
    )

    /**
     * Start the interpreter and hand Python its writable directory.
     *
     * filesDir rather than a discovered path: `gui_core/paths.py` already
     * honours PADPD_DATA_DIR, so the app needs no change on the Python
     * side - but the variable must be set before anything under padpd is
     * imported, and Java cannot portably set environment variables. So
     * the directory travels as an argument and Python sets it.
     */
    fun boot(context: Context, lang: String = "zh"): Capabilities {
        if (!Python.isStarted()) Python.start(AndroidPlatform(context))
        val module = Python.getInstance().getModule("padpd_mobile.api")
        api = module
        // Re-callable: switching language boots again, and the Python
        // side treats that as setting the language, not as restarting.
        // Python.start would throw on a second call, hence the guard.
        val json = module
            .callAttr("boot", context.filesDir.absolutePath, lang).toString()
        return ChartJson.decodeFromString(Capabilities.serializer(), json)
    }

    fun galleryList(): List<GalleryEntry> {
        val json = requireApi().callAttr("gallery_list").toString()
        return ChartJson.decodeFromString(GalleryListing.serializer(), json).entries
    }

    /** Build one gallery chart. Returns the spec, or throws with the
     * Python traceback attached - a failure here is a bug worth reading,
     * not something to swallow into an empty chart. */
    fun galleryChart(entryId: String, lang: String = "zh"): ChartSpec {
        val json = requireApi().callAttr("gallery_chart", entryId, lang).toString()
        val reply = ChartJson.decodeFromString(ChartReply.serializer(), json)
        if (!reply.ok || reply.spec == null) {
            throw IllegalStateException("${reply.error}\n${reply.traceback}")
        }
        return reply.spec
    }

    /**
     * Assemble one screen: metrics and every chart, in a single call.
     *
     * The screen is composed on the Python side (`padpd_mobile/pages.py`)
     * for two reasons that both bite here. Metrics are read off live
     * objects - `wf.config.fft_size` and the like - which cannot cross
     * the bridge without opening a general attribute reader. And their
     * formatting is the desktop's, to the digit; duplicating "%.2f dB"
     * in Kotlin would let the two front ends drift in a way that looks
     * like a rounding difference rather than a bug.
     */
    fun page(
        name: String,
        args: List<JsonElement> = emptyList(),
        kwargs: Map<String, JsonElement> = emptyMap(),
    ): Screen {
        val payload = buildJsonObject {
            put("args", JsonArray(args))
            put("kwargs", JsonObject(kwargs))
        }
        val json = requireApi().callAttr("page", name, payload.toString())
            .toString()
        val reply = ChartJson.decodeFromString(PageReply.serializer(), json)
        if (!reply.ok) throw IllegalStateException(
            "${reply.error}\n${reply.traceback}")
        return Screen(reply.handle, reply.metrics, reply.charts)
    }

    /**
     * The Chinese-to-target-language table, fetched once per language.
     *
     * Empty for zh, where the keys are already the displayed strings.
     */
    fun i18nMap(lang: String): Map<String, String> {
        val json = requireApi().callAttr("i18n_map", lang).toString()
        return ChartJson.decodeFromString(
            MapSerializer(String.serializer(), String.serializer()), json)
    }

    /** Raw float32 bytes for one blob key. */
    fun blob(key: String): ByteArray =
        requireApi().callAttr("blob", key).toJava(ByteArray::class.java)

    fun newBlobStore(): BlobStore = BlobStore(::blob)

    fun release(vararg keys: String) {
        requireApi().callAttr("release", *keys)
    }

    private fun requireApi(): PyObject =
        api ?: error("PyBridge.boot() has not been called")
}
