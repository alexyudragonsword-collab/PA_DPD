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
import org.junit.Assert.fail
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * The screen itself: does the app start, does Python come up, does
 * tapping an entry draw something.
 *
 * Only the first entry is exercised. The gallery is a LazyColumn, so
 * entries below the fold are not composed until scrolled to, and driving
 * all fourteen through the list would be testing scrolling rather than
 * charts - PyBridgeTest and ChartRenderTest cover those without it.
 *
 * Waits are hand-rolled rather than `compose.waitUntil` so that a timeout
 * can say what the semantics tree actually contained. An earlier version
 * timed out with nothing but "condition still not satisfied", which is
 * consistent with a dozen different causes and distinguishes none of them.
 */
@RunWith(AndroidJUnit4::class)
class GalleryScreenTest {

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    @Test
    fun startsAndDrawsTheFirstChart() {
        awaitAny(BOOT_TIMEOUT_MS, "caps", "bootError")
        assertFalse("Python failed to start on device", exists("bootError"))
        compose.onNodeWithTag("caps").assertIsDisplayed()

        compose.onNodeWithTag("entry:psd").performClick()

        // Whether the row ever entered its pending state separates the
        // two failures that otherwise look the same from outside: a tap
        // that never set `open` (no pending, no chart) from a load that
        // never returned (pending, no chart).
        val expanded = await(EXPAND_TIMEOUT_MS, "pending:psd", "chart:psd", "error:psd")

        val seen = awaitAny(CHART_TIMEOUT_MS,
                            "expanded=$expanded", "chart:psd", "error:psd")
        assertFalse("psd failed to build on device: see logcat", seen == "error:psd")
        compose.onNodeWithTag("chart:psd").assertIsDisplayed()
    }

    /** Poll in real time for the first of [tags] to appear, and report
     * what was there instead if none does. The first vararg may be a
     * "note=value" string rather than a tag; it is not polled for, only
     * quoted in the failure. */
    private fun awaitAny(timeoutMs: Long, vararg tags: String): String {
        val notes = tags.filter { it.contains('=') }
        val real = tags.filterNot { it.contains('=') }
        val deadline = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < deadline) {
            compose.waitForIdle()
            real.firstOrNull { exists(it) }?.let { return it }
            Thread.sleep(POLL_MS)
        }
        fail("none of $real appeared within ${timeoutMs}ms. " +
             "Tags present: ${presentTags()}. $notes")
        error("unreachable")
    }

    /** Like [awaitAny] but returns null on timeout instead of failing,
     * for observations that are diagnostic rather than the assertion. */
    private fun await(timeoutMs: Long, vararg tags: String): String? {
        val deadline = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < deadline) {
            compose.waitForIdle()
            tags.firstOrNull { exists(it) }?.let { return it }
            Thread.sleep(POLL_MS)
        }
        return null
    }

    private fun exists(tag: String): Boolean =
        compose.onAllNodes(hasTestTag(tag)).fetchSemanticsNodes().isNotEmpty()

    private fun presentTags(): List<String> =
        compose.onAllNodes(SemanticsMatcher("has a test tag") { node ->
            node.config.getOrNull(SemanticsProperties.TestTag) != null
        }).fetchSemanticsNodes()
            .mapNotNull { it.config.getOrNull(SemanticsProperties.TestTag) }
            .sorted()

    private companion object {
        // First launch unpacks numpy and scipy.
        const val BOOT_TIMEOUT_MS = 120_000L
        const val CHART_TIMEOUT_MS = 60_000L
        const val EXPAND_TIMEOUT_MS = 10_000L
        const val POLL_MS = 250L
    }
}
