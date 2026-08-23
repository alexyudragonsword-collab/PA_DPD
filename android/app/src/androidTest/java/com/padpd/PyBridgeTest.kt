package com.padpd

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.padpd.chart.Blobs
import com.padpd.chart.PyBridge
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.BeforeClass
import org.junit.Test
import org.junit.runner.RunWith

/**
 * The bridge, on a device, with no UI involved.
 *
 * Deliberately separate from the render test. An earlier version drove
 * the real gallery list and asserted both "builds" and "draws" through
 * it, which coupled every chart to LazyColumn's virtualisation: entries
 * below the fold are never composed, so the test waited two minutes for a
 * node that could not appear. Splitting the two properties means a
 * failure now says which one broke.
 */
@RunWith(AndroidJUnit4::class)
class PyBridgeTest {

    companion object {
        @BeforeClass
        @JvmStatic
        fun boot() {
            PyBridge.boot(InstrumentationRegistry.getInstrumentation().targetContext)
        }
    }

    @Test
    fun capabilitiesReportTorchUnavailable() {
        val caps = PyBridge.boot(
            InstrumentationRegistry.getInstrumentation().targetContext)
        assertFalse("torch has no Android wheel", caps.torch)
        assertFalse(caps.onnx)
        assertTrue("fit_neural" in caps.unavailable)
        assertEquals(14, caps.charts.size)
    }

    @Test
    fun galleryListsEveryChartType() {
        val entries = PyBridge.galleryList()
        assertEquals(14, entries.size)
        assertTrue("provenance must be labelled",
                   entries.all { it.provenance in setOf("computed", "sampled") })
        // Half of these carry fixtures; the split is the point of the
        // label, so a gallery that quietly became all-fixture should fail.
        assertTrue("some entries must run the real service path",
                   entries.count { it.provenance == "computed" } >= 7)
    }

    @Test
    fun everySpecBuildsAndItsBlobsTransport() {
        for (entry in PyBridge.galleryList()) {
            val spec = PyBridge.galleryChart(entry.id)
            assertTrue("${entry.id}: no panels", spec.panels.isNotEmpty())
            for (panel in spec.panels) {
                assertTrue("${entry.id}: panel with no series",
                           panel.series.isNotEmpty())
                for (s in panel.series) {
                    val xs = Blobs.decode(PyBridge.blob(s.x))
                    val ys = Blobs.decode(PyBridge.blob(s.y))
                    // An empty blob draws an invisible curve and no error,
                    // which is the failure this whole layer is guarding.
                    assertTrue("${entry.id}/${s.label}: empty x blob", xs.isNotEmpty())
                    assertTrue("${entry.id}/${s.label}: empty y blob", ys.isNotEmpty())
                    assertEquals("${entry.id}/${s.label}: x and y differ in length",
                                 xs.size, ys.size)
                }
            }
        }
    }

    @Test
    fun psdCurveIsNormalisedAsFigsProducesIt() {
        val spec = PyBridge.galleryChart("psd")
        val values = Blobs.decode(PyBridge.blob(spec.panels[0].series[0].y))
        assertTrue("psd came back too short", values.size > 1000)
        assertTrue("psd should peak at 0 dBr", values.max() in -1f..1f)
        assertEquals(listOf(-90.0, 5.0), spec.panels[0].ylim)
    }
}
