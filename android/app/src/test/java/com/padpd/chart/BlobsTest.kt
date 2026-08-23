package com.padpd.chart

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Decoding of what `api.blob` writes with `numpy.astype("<f4")`. */
class BlobsTest {

    private fun encode(values: FloatArray): ByteArray {
        val buf = ByteBuffer.allocate(values.size * 4).order(ByteOrder.LITTLE_ENDIAN)
        values.forEach { buf.putFloat(it) }
        return buf.array()
    }

    @Test
    fun roundTripsLittleEndianFloats() {
        val want = floatArrayOf(0f, -1.5f, 3.25e6f, Float.NaN)
        val got = Blobs.decode(encode(want))
        assertEquals(want.size, got.size)
        assertArrayEquals(want.copyOfRange(0, 3), got.copyOfRange(0, 3), 0f)
        assertEquals(true, got[3].isNaN())
    }

    @Test
    fun emptyPayloadIsAnEmptyCurveNotACrash() {
        // api.blob returns b"" for an unknown key, which the UI should
        // render as nothing rather than fail on.
        assertEquals(0, Blobs.decode(ByteArray(0)).size)
    }

    @Test
    fun truncatedPayloadKeepsWholeSamples() {
        val bytes = encode(floatArrayOf(1f, 2f)).copyOfRange(0, 6)
        assertEquals(1, Blobs.decode(bytes).size)
    }

    @Test
    fun storeFetchesEachKeyOnce() {
        var calls = 0
        val store = BlobStore { calls++; encode(floatArrayOf(1f, 2f, 3f)) }
        repeat(5) { store["k"] }
        assertEquals(1, calls)
        assertEquals(3, store["k"].size)
    }
}
