package com.padpd

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Compare Runs on a device, and with it the loop the other screens
 * promise: they say "registered as a run", this reads those runs back.
 *
 * The test fits a model first rather than assuming the store has
 * anything. Instrumented tests share one app installation but not a
 * guaranteed order, and a compare screen that passes only because an
 * earlier test happened to leave data behind is testing nothing.
 */
@RunWith(AndroidJUnit4::class)
class CompareScreenTest {

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    @Test
    fun listsARunThatTheModelingScreenJustRegistered() {
        awaitAny(BOOT_TIMEOUT_MS, "caps", "bootError")
        assertFalse("Python failed to start on device", exists("bootError"))

        // Produce a run.
        compose.onNodeWithTag("nav:modeling").performScrollTo().performClick()
        awaitAny(NAV_TIMEOUT_MS, "fit")
        compose.onNodeWithTag("fit", useUnmergedTree = true).performClick()
        val fitted = awaitAny(FIT_TIMEOUT_MS, "chart:psd", "fit:error")
        assertFalse("fit failed, so there is no run to compare",
                    fitted == "fit:error")

        // Read it back through the compare screen.
        compose.onNodeWithTag("nav:compare").performScrollTo().performClick()
        awaitAny(NAV_TIMEOUT_MS, "runTable", "noRuns", "compare:error")
        assertFalse("compare screen reported no runs after a fit",
                    exists("noRuns"))
        assertTrue("no run rows listed; present: ${presentTags()}",
                   presentTags().any { it.startsWith("run:") })
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
        const val FIT_TIMEOUT_MS = 90_000L
        const val POLL_MS = 250L
    }
}
