package com.padpd

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.getBoundsInRoot
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import android.util.Log
import com.padpd.screens.METRIC_MAX_WIDTH
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Measure what translation does to the layout, instead of looking at it.
 *
 * The screenshots exist for a human to eyeball; this is the part of the
 * same question a machine can settle. A metric card's label is
 * translated and English runs about three times the character count of
 * the Chinese it replaces, so without a bound the card grows to fit and,
 * in a horizontally scrolling row, pushes its neighbours out of reach.
 * The bound is [METRIC_MAX_WIDTH]; this asserts the rendered card
 * actually honours it in the language that stresses it.
 *
 * Heights are logged rather than asserted against a tight number. How
 * many lines a label wraps to is a function of font metrics, and
 * guessing that number and calling it a threshold is how a test starts
 * failing for reasons no one intended. The generous ceiling catches
 * unbounded growth - the defect - while the log gives the real figures
 * to tighten against later if it is ever worth it.
 */
@RunWith(AndroidJUnit4::class)
class LayoutBoundsTest {

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    @Test
    fun metricCardsStayWithinTheirBoundInEnglish() {
        awaitAny(BOOT_TIMEOUT_MS, "caps", "bootError")
        assertFalse("Python failed to start on device", exists("bootError"))

        compose.onNodeWithTag("lang:en", useUnmergedTree = true)
            .performClick()
        awaitAny(BOOT_TIMEOUT_MS, "caps", "bootError")
        assertFalse("Python failed to restart in English",
                    exists("bootError"))

        // The Overview's four headline figures carry the longest labels
        // that are on screen without running anything first.
        compose.goTo("home")
        awaitAny(NAV_TIMEOUT_MS, "env", "home:error")
        assertFalse("overview failed to load", exists("home:error"))

        val tags = presentTags().filter { it.startsWith("metric:") }
        assertTrue("no metric cards to measure; present: ${presentTags()}",
                   tags.isNotEmpty())

        for (tag in tags) {
            val bounds = compose.onNodeWithTag(tag, useUnmergedTree = true)
                .getBoundsInRoot()
            // Subtracting the edges rather than reading DpRect.width and
            // .height: those are top-level extension properties in
            // androidx.compose.ui.unit and need their own imports, which
            // is the second import this file cost a CI round trip for.
            // left/top/right/bottom are members and cannot.
            val width = bounds.right - bounds.left
            val height = bounds.bottom - bounds.top
            Log.i("padpd", "padpd-metric-card: $tag $width x $height")
            assertTrue(
                "$tag is $width wide, over the $METRIC_MAX_WIDTH bound " +
                    "- a translated label grew the card",
                width <= METRIC_MAX_WIDTH + SLACK,
            )
            assertTrue(
                "$tag is $height tall, which is unbounded growth " +
                    "rather than a wrapped label",
                height <= HEIGHT_CEILING,
            )
        }
    }

    private fun awaitAny(timeoutMs: Long, vararg tags: String) {
        val deadline = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < deadline) {
            compose.waitForIdle()
            if (tags.any { exists(it) }) return
            Thread.sleep(POLL_MS)
        }
    }

    private fun exists(tag: String): Boolean =
        compose.onAllNodes(hasTestTag(tag), useUnmergedTree = true)
            .fetchSemanticsNodes().isNotEmpty()

    private fun presentTags(): List<String> =
        compose.onAllNodes(SemanticsMatcher("has a test tag") { node ->
            node.config.getOrNull(SemanticsProperties.TestTag) != null
        }, useUnmergedTree = true).fetchSemanticsNodes()
            .mapNotNull { it.config.getOrNull(SemanticsProperties.TestTag) }

    private companion object {
        const val BOOT_TIMEOUT_MS = 120_000L
        const val NAV_TIMEOUT_MS = 20_000L
        const val POLL_MS = 250L
        // Rounding between dp and device pixels, not a tolerance for
        // being over the bound.
        val SLACK = 1.dp
        // Well above any wrapped label; low enough that a card growing
        // without limit trips it.
        val HEIGHT_CEILING = 160.dp
    }
}
