package com.padpd

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assertIsDisplayed
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
 * DPD Lab on a device: the three experiments the desktop page offers.
 *
 * One test per experiment rather than one covering the page. They run
 * independently in the app, so a failure should name which one broke -
 * and the ILA loop takes seconds while the three-loop demo takes longer,
 * so sharing a timeout would mean sizing it for the slowest.
 */
@RunWith(AndroidJUnit4::class)
class DpdScreenTest {

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    private fun openDpd() {
        awaitAny(BOOT_TIMEOUT_MS, "caps", "bootError")
        assertFalse("Python failed to start on device", exists("bootError"))
        compose.onNodeWithTag("nav:dpd").performScrollTo().performClick()
        awaitAny(NAV_TIMEOUT_MS, "runIla")
    }

    private fun tap(tag: String) {
        compose.onNodeWithTag(tag, useUnmergedTree = true)
            .performScrollTo().performClick()
    }

    @Test
    fun ilaRunsAndPlotsBeforeAndAfter() {
        openDpd()
        tap("runIla")
        val seen = awaitAny(RUN_TIMEOUT_MS, "chart:psd", "ila:error")
        assertFalse("ILA failed on device", seen == "ila:error")
        // Same vertical-scroll reason as ModelingScreenTest.
        compose.onNodeWithTag("chart:psd", useUnmergedTree = true)
            .performScrollTo().assertIsDisplayed()
        // Four metric cards: EVM and ACLR, each before and after.
        assertTrue(
            "expected four metric cards; present: ${presentTags()}",
            presentTags().count { it.startsWith("metric:") } >= 4,
        )
    }

    @Test
    fun theDlaBranchSaysWhyItIsMissing() {
        openDpd()
        // Not silently absent: the algorithm exists in padpd and it is
        // this platform that cannot host torch.
        assertTrue("no explanation for the missing DLA branch",
                   exists("dlaUnavailable"))
    }

    @Test
    fun adaptiveTrackingRuns() {
        openDpd()
        tap("runAdaptive")
        val seen = awaitAny(RUN_TIMEOUT_MS, "chart:adaptive_evm",
                            "adaptive:error")
        assertFalse("adaptive DPD failed on device", seen == "adaptive:error")
        assertTrue("no verdict note", exists("adaptive:note"))
    }

    @Test
    fun theThreeLoopDemoRuns() {
        openDpd()
        tap("runThreeLoop")
        val seen = awaitAny(SLOW_RUN_TIMEOUT_MS, "chart:three_loop",
                            "tl:error")
        assertFalse("three-loop demo failed on device", seen == "tl:error")
        assertTrue("no verdict note", exists("tl:note"))
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
        // Measured on a workstation: ILA 2.4 s, adaptive 1.1 s at six
        // blocks, three-loop 1.8 s. The emulator runs x86_64 natively
        // under KVM so it is in the same range, but the app's defaults
        // are larger than those measurements (ten blocks, not six).
        const val RUN_TIMEOUT_MS = 120_000L
        const val SLOW_RUN_TIMEOUT_MS = 180_000L
        const val POLL_MS = 250L
    }
}
