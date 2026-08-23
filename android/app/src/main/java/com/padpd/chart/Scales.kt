package com.padpd.chart

import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow

/**
 * Value-to-pixel mapping and tick selection.
 *
 * Deliberately free of any Android or Compose import: this is the part of
 * the renderer that is easy to get subtly wrong (log axes, degenerate
 * ranges, tick counts) and it runs as a JVM unit test in seconds rather
 * than behind an emulator boot. [ChartCanvas] holds the drawing; this
 * holds the arithmetic.
 */

/** A tick position in data space with the label to draw at it. */
data class Tick(val value: Double, val label: String)

data class Range(val min: Double, val max: Double) {
    val span: Double get() = max - min

    /** Widen a degenerate range so a flat series still gets an axis.
     *
     * A constant curve, a single point, or an all-NaN blob would otherwise
     * produce span == 0 and divide the whole chart by zero. */
    fun sane(): Range {
        if (!min.isFinite() || !max.isFinite()) return Range(0.0, 1.0)
        if (span > 0.0) return this
        val pad = if (abs(min) > 0) abs(min) * 0.05 else 0.5
        return Range(min - pad, max + pad)
    }

    fun padded(fraction: Double): Range {
        val s = sane()
        val pad = s.span * fraction
        return Range(s.min - pad, s.max + pad)
    }

    companion object {
        /** Range over finite values only. NaN is meaningful in this data -
         * bars use it for "this run has no such metric" - so it must be
         * skipped rather than poisoning the bounds. */
        fun of(values: FloatArray): Range {
            var lo = Double.POSITIVE_INFINITY
            var hi = Double.NEGATIVE_INFINITY
            for (v in values) {
                if (v.isNaN() || v.isInfinite()) continue
                val d = v.toDouble()
                lo = min(lo, d); hi = max(hi, d)
            }
            return if (lo > hi) Range(0.0, 1.0) else Range(lo, hi)
        }

        fun union(a: Range?, b: Range): Range =
            if (a == null) b else Range(min(a.min, b.min), max(a.max, b.max))
    }
}

/**
 * Maps data values onto a pixel span.
 *
 * @param log log10 axis. Non-positive values have no place on one, so they
 *   are dropped by [project] rather than clamped: clamping would draw a
 *   point at the axis edge that no measurement supports.
 */
class Scale(
    val range: Range,
    private val pxLow: Float,
    private val pxHigh: Float,
    val log: Boolean = false,
) {
    private val lo = if (log) log10(max(range.min, MIN_LOG)) else range.min
    private val hi = if (log) log10(max(range.max, MIN_LOG * 10)) else range.max
    private val denom = (hi - lo).takeIf { it != 0.0 } ?: 1.0

    /** Pixel position, or null when the value cannot sit on this axis. */
    fun project(v: Double): Float? {
        if (!v.isFinite()) return null
        val t = if (log) {
            if (v <= 0.0) return null
            (log10(v) - lo) / denom
        } else {
            (v - lo) / denom
        }
        return (pxLow + (pxHigh - pxLow) * t).toFloat()
    }

    fun ticks(target: Int = 5): List<Tick> =
        if (log) logTicks() else linearTicks(target)

    private fun linearTicks(target: Int): List<Tick> {
        val step = niceStep(hi - lo, target)
        if (step <= 0.0) return emptyList()
        val first = ceil(lo / step) * step
        val out = ArrayList<Tick>()
        var v = first
        // Guard the loop count as well as the bound: a pathological range
        // with a tiny step would otherwise spin.
        while (v <= hi + step * 1e-6 && out.size < 64) {
            out.add(Tick(v, formatTick(v, step)))
            v += step
        }
        return out
    }

    private fun logTicks(): List<Tick> {
        val out = ArrayList<Tick>()
        var d = floor(lo)
        while (d <= ceil(hi) && out.size < 32) {
            val v = 10.0.pow(d)
            if (log10(v) in lo..hi) out.add(Tick(v, formatLog(d)))
            d += 1.0
        }
        return out
    }

    companion object {
        private const val MIN_LOG = 1e-12

        /** 1-2-5 step at or just above the size implied by [target]. */
        fun niceStep(span: Double, target: Int): Double {
            if (span <= 0.0 || target <= 0) return 0.0
            val raw = span / target
            val mag = 10.0.pow(floor(log10(raw)))
            val norm = raw / mag
            val mult = when {
                norm <= 1.0 -> 1.0
                norm <= 2.0 -> 2.0
                norm <= 5.0 -> 5.0
                else -> 10.0
            }
            return mult * mag
        }

        /** Enough decimals for the step, and no more - "-30" not
         * "-30.000000001", which is what naive formatting of an
         * accumulated float step produces.
         *
         * Note the rounding: toLong() truncates towards zero, so a tick
         * that accumulated to -29.999999999999996 came out labelled "-29"
         * - every negative gridline off by one step, with the line drawn
         * in the right place. Caught by ScaleTest, which is what it is
         * for. */
        fun formatTick(v: Double, step: Double): String {
            val decimals = max(0, -floor(log10(step)).toInt())
            val snapped = if (abs(v) < step * 1e-6) 0.0 else v
            return if (decimals == 0) Math.round(snapped).toString()
            else String.format("%.${min(decimals, 6)}f", snapped)
        }

        fun formatLog(decade: Double): String {
            val d = decade.toInt()
            return when {
                d >= 0 && d <= 4 -> 10.0.pow(d).toLong().toString()
                else -> "1e$d"
            }
        }
    }
}
