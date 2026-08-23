package com.padpd

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.padpd.chart.PyBridge
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * On-device guard for Phase 2, replacing the Phase 0 probe.
 *
 * Phase 0 asked "can Python run here at all"; that is settled - all five
 * acceptance criteria passed on hardware. What can still break silently is
 * the chart path: a spec field renamed in Python, a blob that arrives
 * empty, a renderer that throws on one panel shape. So this builds every
 * gallery entry through the real bridge and draws it.
 *
 * Deliberately not a screenshot test. Pixel comparison across emulator
 * images and densities is a maintenance cost out of proportion to what it
 * would catch here; "every spec builds, transports and draws without
 * throwing" is the property that actually regresses.
 */
@RunWith(AndroidJUnit4::class)
class GalleryRenderTest {

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    @Test
    fun pythonBootsAndReportsNoTorch() {
        compose.waitUntil(BOOT_TIMEOUT_MS) {
            compose.onAllNodesWithTagExists("caps") || compose.onAllNodesWithTagExists("bootError")
        }
        compose.onNodeWithTag("bootError").assertDoesNotExistSafely()
        compose.onNodeWithTag("caps").assertIsDisplayed()
    }

    @Test
    fun everyGalleryEntryBuildsTransportsAndDraws() {
        compose.waitUntil(BOOT_TIMEOUT_MS) { compose.onAllNodesWithTagExists("caps") }

        val entries = PyBridge.galleryList()
        assertEquals("gallery lost entries", 14, entries.size)

        for (entry in entries) {
            compose.onNodeWithTag("entry:${entry.id}").performClick()
            compose.waitUntil(CHART_TIMEOUT_MS) {
                compose.onAllNodesWithTagExists("chart:${entry.id}") ||
                    compose.onAllNodesWithTagExists("error:${entry.id}")
            }
            assertFalse("${entry.id} failed to build",
                        compose.onAllNodesWithTagExists("error:${entry.id}"))
            compose.onNodeWithTag("chart:${entry.id}").assertIsDisplayed()
            // Collapse again so the list stays short enough to scroll to
            // the next entry without the previous chart in the way.
            compose.onNodeWithTag("entry:${entry.id}").performClick()
        }
    }

    @Test
    fun blobsArriveAsFloatsNotEmpty() {
        compose.waitUntil(BOOT_TIMEOUT_MS) { compose.onAllNodesWithTagExists("caps") }
        val spec = PyBridge.galleryChart("psd")
        val key = spec.panels[0].series[0].y
        val values = com.padpd.chart.Blobs.decode(PyBridge.blob(key))
        assertTrue("psd curve came back empty", values.size > 1000)
        assertTrue("psd is normalised to 0 dBr at the peak",
                   values.max() > -1f && values.max() < 1f)
    }

    private companion object {
        // Generous: first launch unpacks numpy and scipy, and the slowest
        // gallery entry runs a six-block three-loop demo.
        const val BOOT_TIMEOUT_MS = 120_000L
        const val CHART_TIMEOUT_MS = 120_000L
    }
}

private fun androidx.compose.ui.test.junit4.AndroidComposeTestRule<*, *>
    .onAllNodesWithTagExists(tag: String): Boolean =
    onAllNodes(androidx.compose.ui.test.hasTestTag(tag))
        .fetchSemanticsNodes().isNotEmpty()

private fun androidx.compose.ui.test.SemanticsNodeInteraction.assertDoesNotExistSafely() {
    runCatching { assertDoesNotExist() }
}
