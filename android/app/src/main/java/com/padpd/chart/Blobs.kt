package com.padpd.chart

import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Decoding for the float32 blobs `padpd_mobile.api.blob` hands back.
 *
 * Little-endian because that is what `numpy.astype("<f4")` writes and what
 * every ARM and x86 Android device reads natively; the explicit order is
 * there so the contract does not silently depend on the platform default.
 */
object Blobs {

    fun decode(bytes: ByteArray): FloatArray {
        if (bytes.isEmpty()) return FloatArray(0)
        // A truncated payload means the transport lost data. Better to
        // draw the whole samples and be short than to read past the end.
        val n = bytes.size / 4
        val out = FloatArray(n)
        ByteBuffer.wrap(bytes, 0, n * 4)
            .order(ByteOrder.LITTLE_ENDIAN)
            .asFloatBuffer()
            .get(out)
        return out
    }
}

/**
 * A chart's blobs, fetched once and reused across recompositions.
 *
 * Compose redraws on every pan and zoom frame. Pulling a 15k-point
 * constellation across the language boundary at 60 Hz would spend more
 * time in the bridge than in the renderer, so resolution happens once when
 * the spec arrives and the arrays stay on this side afterwards.
 */
class BlobStore(private val fetch: (String) -> ByteArray) {
    private val cache = HashMap<String, FloatArray>()

    operator fun get(key: String): FloatArray =
        cache.getOrPut(key) { Blobs.decode(fetch(key)) }

    /** Resolve every key a spec references, so a later draw never blocks
     * on the bridge. */
    fun preload(spec: ChartSpec) {
        for (panel in spec.panels) {
            for (s in panel.series) { get(s.x); get(s.y) }
        }
    }

    val size: Int get() = cache.size
}
