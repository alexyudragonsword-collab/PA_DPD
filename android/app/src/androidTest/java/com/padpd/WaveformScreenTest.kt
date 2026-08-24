package com.padpd

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Waveform Studio end to end on a device: set parameters, generate, get
 * a chart and metrics.
 *
 * This is the first of the nine ported screens, so it is also the first
 * proof that the whole path works on hardware - Compose form to
 * padpd_mobile.pages to gui_core.services to a spec the renderer draws.
 * The eight that follow reuse this shape, so a break here is a break in
 * all of them.
 *
 * Unmerged queries throughout. Modifier.clickable merges its descendants
 * into one semantics node, so a tag inside a tappable row is invisible in
 * the merged tree and a test that searches it silently asserts nothing -
 * which cost seven CI runs to find once already.
 */
@RunWith(AndroidJUnit4::class)
class WaveformScreenTest {

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    @Test
    fun generatesAWaveformAndDrawsIt() {
        awaitAny(BOOT_TIMEOUT_MS, "caps", "bootError")
        assertFalse("Python failed to start on device", exists("bootError"))

        // The app opens here, so no navigation needed - but assert it
        // rather than assume, since the default is a decision that could
        // change without this test noticing it had stopped testing.
        compose.onNodeWithTag("generate", useUnmergedTree = true)
            .assertIsDisplayed()

        compose.onNodeWithTag("generate", useUnmergedTree = true).performClick()
        val seen = awaitAny(RUN_TIMEOUT_MS, "chart:psd", "wf:error")
        assertFalse("waveform run failed on device", seen == "wf:error")

        compose.onNodeWithTag("chart:psd", useUnmergedTree = true)
            .assertIsDisplayed()
        Screenshots.capture(compose, "zh-waveform-result")
    }

    @Test
    fun everyChartTabDraws() {
        awaitAny(BOOT_TIMEOUT_MS, "caps", "bootError")
        compose.onNodeWithTag("generate", useUnmergedTree = true).performClick()
        awaitAny(RUN_TIMEOUT_MS, "chart:psd", "wf:error")

        // All four figures the desktop page shows. They exercise three of
        // the renderer's four primitives on real generated data rather
        // than on a fixture: lines, a log axis, and a scatter.
        for (slot in listOf("psd", "ccdf", "constellation", "time")) {
            compose.onNodeWithTag("tab:$slot", useUnmergedTree = true)
                .performClick()
            awaitAny(RUN_TIMEOUT_MS, "chart:$slot")
            compose.onNodeWithTag("chart:$slot", useUnmergedTree = true)
                .assertIsDisplayed()
        }
    }

    @Test
    fun metricsArriveFormattedFromPython() {
        awaitAny(BOOT_TIMEOUT_MS, "caps", "bootError")
        compose.onNodeWithTag("generate", useUnmergedTree = true).performClick()
        awaitAny(RUN_TIMEOUT_MS, "chart:psd", "wf:error")

        // PAPR is the metric whose label is language-independent, so it
        // can be asserted without deciding what language the app is in.
        assertTrue(
            "no PAPR metric card; present: ${presentTags()}",
            exists("metric:PAPR"),
        )
    }

    private fun awaitAny(timeoutMs: Long, vararg tags: String): String {
        val deadline = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < deadline) {
            compose.waitForIdle()
            tags.firstOrNull { exists(it) }?.let { return it }
            Thread.sleep(POLL_MS)
        }
        fail("none of ${tags.toList()} appeared within ${timeoutMs}ms. " +
             "Tags present: ${presentTags()}")
        error("unreachable")
    }

    private fun exists(tag: String): Boolean =
        compose.onAllNodes(hasTestTag(tag), useUnmergedTree = true)
            .fetchSemanticsNodes().isNotEmpty()

    private fun presentTags(): List<String> =
        compose.onAllNodes(SemanticsMatcher("has a test tag") { node ->
            node.config.getOrNull(SemanticsProperties.TestTag) != null
        }, useUnmergedTree = true).fetchSemanticsNodes()
            .mapNotNull { it.config.getOrNull(SemanticsProperties.TestTag) }
            .sorted()

    private companion object {
        const val BOOT_TIMEOUT_MS = 120_000L
        // 80 MHz / 8 symbols measures 0.02 s on a workstation and the
        // emulator is not far off, but the first run also pays for
        // scipy.signal's import, measured at 1.37 s on device.
        const val RUN_TIMEOUT_MS = 60_000L
        const val POLL_MS = 250L
    }
}
