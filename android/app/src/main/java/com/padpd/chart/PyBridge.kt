package com.padpd.chart

import android.content.Context
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlinx.serialization.Serializable

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
    fun boot(context: Context): Capabilities {
        if (!Python.isStarted()) Python.start(AndroidPlatform(context))
        val module = Python.getInstance().getModule("padpd_mobile.api")
        api = module
        val json = module.callAttr("boot", context.filesDir.absolutePath).toString()
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
