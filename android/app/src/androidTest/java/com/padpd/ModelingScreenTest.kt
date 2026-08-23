package com.padpd

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
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
 * PA Modeling on a device: fit a classical model, and run the
 * gain-modulation probe.
 *
 * The second screen ported, and the first with two independent actions,
 * so it is also where the shared screen scaffolding in Common.kt first
 * gets used by more than one caller.
 *
 * Unmerged queries and performScrollTo throughout - both traps are
 * documented in android/README.md and both present as a tap that
 * silently does nothing.
 */
@RunWith(AndroidJUnit4::class)
class ModelingScreenTest {

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    private fun openModeling() {
        awaitAny(BOOT_TIMEOUT_MS, "caps", "bootError")
        assertFalse("Python failed to start on device", exists("bootError"))
        compose.onNodeWithTag("nav:modeling").performScrollTo().performClick()
        awaitAny(NAV_TIMEOUT_MS, "fit")
    }

    @Test
    fun fitsAClassicalModelAndPlotsTheResidual() {
        openModeling()
        compose.onNodeWithTag("fit", useUnmergedTree = true).performClick()

        val seen = awaitAny(FIT_TIMEOUT_MS, "chart:psd", "fit:error")
        assertFalse("classical fit failed on device", seen == "fit:error")
        // Scroll to it first. The screen is a vertical scroller and the
        // chart sits below the fit controls, the metrics and the tabs, so
        // on this viewport it composes off-screen. Third variant of the
        // same thing in this module: a node existing says nothing about
        // whether it is visible or reachable.
        compose.onNodeWithTag("chart:psd", useUnmergedTree = true)
            .performScrollTo().assertIsDisplayed()

        // The NMSE card is the one that says the fit meant something.
        assertTrue(
            "no NMSE metric; present: ${presentTags()}",
            presentTags().any { it.startsWith("metric:") },
        )
    }

    @Test
    fun theNeuralFamilyIsOfferedButDisabled() {
        openModeling()
        // Shown rather than hidden: the method exists in padpd, it is
        // this platform that cannot host torch, and those are different
        // statements to make to someone choosing a model.
        compose.onNodeWithTag("neural", useUnmergedTree = true)
            .performScrollTo().assertIsNotEnabled()
        assertTrue(
            "no explanation for the disabled control",
            exists("torchUnavailable"),
        )
    }

    @Test
    fun theGainModulationProbeRunsAndReportsAVerdict() {
        openModeling()
        compose.onNodeWithTag("runGainMod", useUnmergedTree = true)
            .performScrollTo().performClick()

        val seen = awaitAny(FIT_TIMEOUT_MS, "chart:gain_modulation", "gm:error")
        assertFalse("gain-modulation probe failed", seen == "gm:error")

        // The verdict sentence is the deliverable here as much as the
        // chart is: the desktop reports what was found in prose, and that
        // wording is built in pages.py so it exists once.
        assertTrue("no verdict note rendered", exists("gm:note"))
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
        // A GMP fit measures 0.27 s on a workstation; the emulator is in
        // the same range, and the first call also pays scipy.signal's
        // import at 1.37 s on device.
        const val FIT_TIMEOUT_MS = 90_000L
        const val POLL_MS = 250L
    }
}
