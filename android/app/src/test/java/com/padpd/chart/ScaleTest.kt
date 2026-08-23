package com.padpd.chart

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The arithmetic behind the renderer. Runs on the JVM in milliseconds,
 * which is why it is here and not in an instrumented test: log axes,
 * degenerate ranges and tick formatting are exactly the sort of thing that
 * is wrong in a way you only notice by reading numbers.
 */
class ScaleTest {

    @Test
    fun linearProjectionHitsBothEnds() {
        val s = Scale(Range(0.0, 10.0), 0f, 100f)
        assertEquals(0f, s.project(0.0)!!, 1e-3f)
        assertEquals(50f, s.project(5.0)!!, 1e-3f)
        assertEquals(100f, s.project(10.0)!!, 1e-3f)
    }

    @Test
    fun invertedPixelSpanWorks() {
        // y axes run bottom-to-top: pxLow > pxHigh.
        val s = Scale(Range(0.0, 1.0), 200f, 0f)
        assertEquals(200f, s.project(0.0)!!, 1e-3f)
        assertEquals(0f, s.project(1.0)!!, 1e-3f)
    }

    @Test
    fun logProjectionIsLogarithmic() {
        val s = Scale(Range(1.0, 1000.0), 0f, 300f, log = true)
        assertEquals(0f, s.project(1.0)!!, 1e-2f)
        assertEquals(100f, s.project(10.0)!!, 1e-2f)
        assertEquals(300f, s.project(1000.0)!!, 1e-2f)
    }

    @Test
    fun logAxisRejectsNonPositiveRatherThanClamping() {
        // Clamping would put a point on the axis edge that no measurement
        // supports; the renderer treats null as a gap.
        val s = Scale(Range(1.0, 100.0), 0f, 100f, log = true)
        assertNull(s.project(0.0))
        assertNull(s.project(-5.0))
    }

    @Test
    fun nonFiniteValuesAreGaps() {
        val s = Scale(Range(0.0, 1.0), 0f, 10f)
        assertNull(s.project(Double.NaN))
        assertNull(s.project(Double.POSITIVE_INFINITY))
    }

    @Test
    fun degenerateRangeStillProducesAnAxis() {
        // A constant curve would otherwise divide the chart by zero.
        val flat = Range(3.0, 3.0).sane()
        assertTrue(flat.span > 0.0)
        val s = Scale(flat, 0f, 100f)
        assertNotNull(s.project(3.0))
    }

    @Test
    fun rangeIgnoresNaNBecauseBarsUseItForMissingMetrics() {
        val r = Range.of(floatArrayOf(-45f, Float.NaN, -38f))
        assertEquals(-45.0, r.min, 1e-6)
        assertEquals(-38.0, r.max, 1e-6)
    }

    @Test
    fun allNaNFallsBackInsteadOfInverting() {
        val r = Range.of(floatArrayOf(Float.NaN, Float.NaN))
        assertTrue(r.max > r.min)
    }

    @Test
    fun niceStepPicksOneTwoOrFive() {
        for (span in listOf(1.0, 3.0, 7.0, 45.0, 1234.0, 0.0007)) {
            val step = Scale.niceStep(span, 5)
            val mantissa = step / Math.pow(10.0, Math.floor(Math.log10(step)))
            val nice = listOf(1.0, 2.0, 5.0).any {
                kotlin.math.abs(it - mantissa) < 1e-9
            }
            assertTrue("span=$span step=$step mantissa=$mantissa", nice)
        }
    }

    @Test
    fun linearTicksCoverTheRangeAndAreBounded() {
        val ticks = Scale(Range(-90.0, 5.0), 0f, 100f).ticks(5)
        assertTrue(ticks.size in 3..12)
        assertTrue(ticks.all { it.value >= -90.0 && it.value <= 5.0 })
    }

    @Test
    fun logTicksAreDecades() {
        val ticks = Scale(Range(1e-7, 1.0), 0f, 100f, log = true).ticks()
        assertTrue(ticks.isNotEmpty())
        assertTrue(ticks.all { kotlin.math.abs(
            Math.log10(it.value) - Math.round(Math.log10(it.value))) < 1e-9 })
    }

    @Test
    fun tickLabelsDoNotLeakFloatNoise() {
        // Accumulating a float step and formatting naively yields
        // "-30.000000000000004"; the label must not.
        assertEquals("-30", Scale.formatTick(-29.999999999999996, 10.0))
        assertEquals("0", Scale.formatTick(1e-18, 10.0))
        assertEquals("0.25", Scale.formatTick(0.25, 0.05))
    }

    @Test
    fun pathologicalRangeDoesNotSpin() {
        // A huge span with a tiny target must still terminate.
        val ticks = Scale(Range(-1e12, 1e12), 0f, 100f).ticks(200)
        assertTrue(ticks.size <= 64)
    }
}
