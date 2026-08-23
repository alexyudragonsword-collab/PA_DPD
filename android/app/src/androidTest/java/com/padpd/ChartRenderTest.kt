package com.padpd

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.padpd.chart.BlobStore
import com.padpd.chart.ChartSpec
import com.padpd.chart.ChartView
import com.padpd.chart.PyBridge
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Draws every chart specification, one at a time, with no list around it.
 *
 * Not a screenshot test: pixel comparison across emulator images and
 * densities costs more to maintain than it would catch here. What
 * regresses in practice is a panel shape the renderer has never seen -
 * a twin axis, a categorical tick set, an all-NaN series - throwing
 * during draw. Composing each spec on its own catches that and says which
 * one.
 */
@RunWith(AndroidJUnit4::class)
class ChartRenderTest {

    @get:Rule
    val compose = createComposeRule()

    // setContent may be called only once per rule, so the content reads a
    // state holder and the test swaps specs through it.
    private val current = mutableStateOf<Pair<ChartSpec, BlobStore>?>(null)

    @Before
    fun boot() {
        PyBridge.boot(InstrumentationRegistry.getInstrumentation().targetContext)
        compose.setContent {
            current.value?.let { (spec, blobs) ->
                ChartView(spec, blobs, Modifier.fillMaxSize().testTag("chart"))
            }
        }
    }

    @Test
    fun everySpecDraws() {
        val entries = PyBridge.galleryList()
        assertTrue(entries.isNotEmpty())
        for (entry in entries) {
            val spec = PyBridge.galleryChart(entry.id)
            val blobs = PyBridge.newBlobStore().apply { preload(spec) }
            current.value = spec to blobs
            compose.waitForIdle()
            // A renderer that throws on this shape fails the composition,
            // so the node is simply not there.
            compose.onNodeWithTag("chart").assertIsDisplayed()
        }
    }

    @Test
    fun twinAxisPanelDraws() {
        // The awkward one: two y scales, a dotted right-axis series and a
        // colour role the palette resolves rather than the spec naming.
        val spec = PyBridge.galleryChart("three_loop")
        val blobs = PyBridge.newBlobStore().apply { preload(spec) }
        assertTrue(spec.panels[0].hasRightAxis)
        current.value = spec to blobs
        compose.waitForIdle()
        compose.onNodeWithTag("chart").assertIsDisplayed()
    }
}
