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
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Walk every screen in both languages and photograph it.
 *
 * The tour captures each screen's resting state - no sweeps, no fits -
 * because what it is looking for is layout, and layout is settled before
 * any result arrives. The English half is the half that earns its keep:
 * the whole i18n table swaps at once and English runs about three times
 * the character count of the Chinese it replaces, so this is where a
 * metric card outgrows its slot or a table column stops lining up. Tests
 * that assert on nodes cannot see any of that - the node is present and
 * its text is correct while the card is four lines tall.
 *
 * Screens that compute are photographed with results by the tests that
 * already drive them; duplicating a one-minute co-design sweep here to
 * get one more picture would not be worth the minute.
 *
 * See [Screenshots] for why none of this compares against a golden.
 */
@RunWith(AndroidJUnit4::class)
class ScreenshotTour {

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    @Test
    fun photographEveryScreenInBothLanguages() {
        awaitAny(BOOT_TIMEOUT_MS, "caps", "bootError")
        assertFalse("Python failed to start on device", exists("bootError"))

        tour("zh")
        compose.onNodeWithTag("lang:en", useUnmergedTree = true)
            .performClick()
        // Switching language reboots Python and reinstalls the string
        // table, so the capability line goes away and comes back.
        awaitAny(BOOT_TIMEOUT_MS, "caps", "bootError")
        assertFalse("Python failed to restart in English",
                    exists("bootError"))
        tour("en")

        // The capture path is allowed to fail silently inside
        // Screenshots.capture so that it can never redden a behavioural
        // test. This is the one place it is checked, so a broken path is
        // still noticed - here, where nothing else is being measured.
        assertTrue("no screenshots were written at all",
                   Screenshots.written > 0)
    }

    private fun tour(lang: String) {
        for ((destination, landmarks) in DESTINATIONS) {
            compose.onNodeWithTag("nav:$destination").performScrollTo()
                .performClick()
            // Best effort: a screen that has not settled is still worth
            // a picture, and this must not fail.
            settle(landmarks)
            Screenshots.capture(compose, "$lang-$destination")
        }
    }

    /**
     * Wait briefly for a screen's landmark, then give up quietly.
     *
     * Prefixes rather than exact tags, because several landmarks are
     * built at runtime - an option row tags itself `opt:<name>:<value>`,
     * so pinning the exact tag would also pin which option happens to be
     * selected by default, and a screen would stop being photographed
     * the day someone changed that default.
     */
    private fun settle(landmarks: List<String>) {
        val deadline = System.currentTimeMillis() + SETTLE_MS
        while (System.currentTimeMillis() < deadline) {
            compose.waitForIdle()
            val present = presentTags()
            if (landmarks.any { p -> present.any { it.startsWith(p) } }) return
            Thread.sleep(POLL_MS)
        }
    }

    private fun presentTags(): List<String> =
        compose.onAllNodes(SemanticsMatcher("has a test tag") { node ->
            node.config.getOrNull(SemanticsProperties.TestTag) != null
        }, useUnmergedTree = true).fetchSemanticsNodes()
            .mapNotNull { it.config.getOrNull(SemanticsProperties.TestTag) }

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

    private companion object {
        // Destination id, and a tag that says the screen has arrived.
        // The compute screens have no result at rest, so their landmark
        // is whichever control starts the work.
        val DESTINATIONS = listOf(
            "home" to listOf("env"),
            "waveform" to listOf("generate"),
            "modeling" to listOf("opt:modelType:"),
            "dpd" to listOf("opt:ilaBasis:"),
            "data" to listOf("loadExample"),
            // Deployment shows the sweep controls or an explanation of
            // why there is nothing to sweep, depending on whether a
            // model was fitted earlier in the run. Both are the screen.
            "deploy" to listOf("sweep", "noModels"),
            "compare" to listOf("refreshRuns"),
            "codesign" to listOf("runSweep"),
            "manual" to listOf("chapterBody"),
            "gallery" to listOf("entry:"),
        )
        const val BOOT_TIMEOUT_MS = 120_000L
        const val SETTLE_MS = 15_000L
        const val POLL_MS = 250L
    }
}
