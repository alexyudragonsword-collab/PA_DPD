package com.padpd

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.SemanticsMatcher
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
 * Overview and Co-Design on a device.
 *
 * Two screens in one class because neither needs much: Overview computes
 * nothing beyond reading the run store, and Co-Design has a single
 * button. Splitting them would mean two emulator app launches for four
 * assertions.
 */
@RunWith(AndroidJUnit4::class)
class HomeAndCodesignTest {

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    private fun open(destination: String, vararg landmarks: String) {
        awaitAny(BOOT_TIMEOUT_MS, "caps", "bootError")
        assertFalse("Python failed to start on device", exists("bootError"))
        compose.goTo(destination)
        awaitAny(NAV_TIMEOUT_MS, *landmarks)
    }

    @Test
    fun overviewShowsHeadlineFiguresAndLabelsThemAsPublished() {
        open("home", "env", "home:error")
        assertFalse("overview failed to load", exists("home:error"))

        // The four cards look exactly like the live readings on every
        // other screen, so the screen has to say they are not.
        assertTrue("no provenance note under the headline figures",
                   exists("headlineProvenance"))
        assertTrue("no environment self-check", exists("env"))
    }

    @Test
    fun coDesignSweepsAndDrawsThePareto() {
        open("codesign", "runSweep")
        compose.onNodeWithTag("runSweep", useUnmergedTree = true)
            .performClick()

        val seen = awaitAny(SWEEP_TIMEOUT_MS, "chart:codesign", "cd:error")
        assertFalse("co-design sweep failed on device", seen == "cd:error")
        assertTrue("no sweep table", exists("cd:table"))

        // Two cards: sequential and joint. The gap between them is the
        // page's whole argument.
        assertTrue(
            "expected both design strategies as metrics; present: " +
                "${presentTags()}",
            presentTags().count { it.startsWith("metric:") } >= 2,
        )
        // The widest metric labels in the app land here: 13 Chinese
        // characters become 37 in English. This is the picture that
        // shows whether the card bounds hold.
        Screenshots.capture(compose, "zh-codesign-result")
    }

    @Test
    fun theGradientTabSaysWhyItIsMissing() {
        open("codesign", "runSweep")
        assertTrue("no explanation for the missing gradient tab",
                   exists("gradUnavailable"))
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
        const val NAV_TIMEOUT_MS = 20_000L
        // The sweep measures 4 s on a workstation; the desktop page
        // labels it "about a minute", which is a stale estimate.
        const val SWEEP_TIMEOUT_MS = 180_000L
        const val POLL_MS = 250L
    }
}
