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
 * The Data screen on a device.
 *
 * Driven through the bundled examples rather than the file picker: the
 * picker is a system activity an instrumented test cannot operate, and
 * the copy it feeds is covered by [SafImportTest]. What is left is the
 * part that matters here - that a real measured container loads on the
 * phone, that its five capture groups are found, and that the tools
 * those groups unlock actually run.
 *
 * complete_source_demo.npz is a 1.0 MB container carrying 4,352 samples
 * plus burst, step, cal_rx, atten and operating_points capture groups.
 * Its arriving at all proves the Gradle staging task put examples/
 * inside the APK.
 */
@RunWith(AndroidJUnit4::class)
class DataScreenTest {

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    private fun openData() {
        awaitAny(BOOT_TIMEOUT_MS, "caps", "bootError")
        assertFalse("Python failed to start on device", exists("bootError"))
        compose.onNodeWithTag("nav:data").performScrollTo().performClick()
        awaitAny(NAV_TIMEOUT_MS, "loadExample", "data:error")
        assertFalse("data screen failed to load", exists("data:error"))
    }

    private fun loadExample() {
        openData()
        compose.onNodeWithTag("loadExample").performScrollTo().performClick()
        awaitAny(LOAD_TIMEOUT_MS, "data:table", "data:error")
        assertFalse("loading the bundled source failed", exists("data:error"))
    }

    @Test
    fun loadsTheBundledCompleteSourceAndPreviewsIt() {
        loadExample()
        // Four metric cards: sample rate, the three split sizes, main
        // bandwidth, modulation. Their labels are translated, so the
        // assertion is on how many arrived, not on which.
        assertTrue("no metric cards; present: ${presentTags()}",
                   presentTags().count { it.startsWith("metric:") } >= 4)
        compose.onNodeWithTag("chart:psd", useUnmergedTree = true)
            .performScrollTo()
        assertTrue("no PSD chart", exists("chart:psd"))
    }

    @Test
    fun findsAllFiveCaptureGroups() {
        loadExample()
        val rows = presentTags().filter { it.startsWith("data:table:row") }
        assertTrue("expected five capture-group rows, got $rows",
                   rows.size == 5)
    }

    @Test
    fun runsTheCaptureGroupTools() {
        loadExample()
        compose.onNodeWithTag("consumeExtras").performScrollTo()
            .performClick()
        // Four consumers: tau identification, a state-spline refit, an
        // RX de-embedding calibration and a cross-condition scheduler.
        // 0.8 s on the desktop over this container's 4,352 samples, so
        // the timeout below is slack for an emulator, not an estimate.
        //
        // Waiting on the busy marker rather than on a note: a note is
        // already on screen from the load, so awaiting one would pass
        // the instant it was clicked and measure nothing.
        awaitIdle(CONSUME_TIMEOUT_MS)
        assertFalse("the capture-group tools failed", exists("data:error"))
        assertTrue("no verdict after consuming",
                   presentTags().any { it == "data:note" })
    }

    @Test
    fun removesTheSourceAgain() {
        loadExample()
        compose.onNodeWithTag("removeSource").performScrollTo().performClick()
        awaitIdle(LOAD_TIMEOUT_MS)
        // With nothing registered the preview has nothing to draw, and
        // the checklist rows go with it.
        assertTrue("rows survived the removal; present: ${presentTags()}",
                   presentTags().none { it.startsWith("data:table:row") })
    }

    @Test
    fun readsTheBundledTwoToneTable() {
        openData()
        compose.onNodeWithTag("twoToneExample").performScrollTo()
            .performClick()
        awaitAny(LOAD_TIMEOUT_MS, "chart:two_tone", "twoTone:error")
        assertFalse("the two-tone example failed", exists("twoTone:error"))
        // Memory strength, recommended depth, cross terms, coefficient
        // estimate, thermal verdict.
        assertTrue("expected five two-tone readings; ${presentTags()}",
                   presentTags().count { it.startsWith("metric:") } >= 5)
    }

    @Test
    fun saysWhyOpenDpdDirectoriesAreNotOffered() {
        openData()
        assertTrue("no explanation for the missing directory scan",
                   exists("opendpdUnavailable"))
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

    /**
     * Wait for the screen's own work to finish.
     *
     * Two phases, because the assertions that follow a tap need to
     * separate "not started yet" from "finished". The busy marker is
     * given a short window to appear and then the full window to go
     * away; a job that finished inside the first window leaves nothing
     * to wait for, which is a pass rather than a failure.
     */
    private fun awaitIdle(timeoutMs: Long) {
        val started = System.currentTimeMillis() + BUSY_APPEARS_MS
        while (System.currentTimeMillis() < started && !exists("data:busy")) {
            compose.waitForIdle()
            Thread.sleep(POLL_MS)
        }
        val deadline = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < deadline) {
            compose.waitForIdle()
            if (!exists("data:busy")) return
            Thread.sleep(POLL_MS)
        }
        fail("still busy after ${timeoutMs}ms. Tags: ${presentTags()}")
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
        // Both are milliseconds on the desktop; the slack is for a
        // cold interpreter on an emulated CPU, and a timeout that is hit
        // is a failure whose cost is the wait.
        const val LOAD_TIMEOUT_MS = 60_000L
        const val CONSUME_TIMEOUT_MS = 120_000L
        const val BUSY_APPEARS_MS = 5_000L
        const val POLL_MS = 250L
    }
}
