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
 * The manual on a device.
 *
 * This is the only screen whose content is files rather than
 * computation, so what it really proves is that the Gradle staging task
 * put manual/ where gui_core/manual.py looks for it - inside the APK,
 * with its 2.9 MB of Markdown and PNGs.
 */
@RunWith(AndroidJUnit4::class)
class ManualScreenTest {

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    private fun openManual() {
        awaitAny(BOOT_TIMEOUT_MS, "caps", "bootError")
        assertFalse("Python failed to start on device", exists("bootError"))
        compose.goTo("manual")
        awaitAny(NAV_TIMEOUT_MS, "toc", "manual:error")
        assertFalse("manual failed to load", exists("manual:error"))
    }

    @Test
    fun showsTheChapterListAndTheFirstChapter() {
        openManual()
        val chapters = presentTags().filter { it.startsWith("chapter:") }
        assertTrue("expected eight chapters, got $chapters",
                   chapters.size == 8)
        assertTrue("no chapter body", exists("chapterBody"))
    }

    @Test
    fun rendersTheFiguresBundledWithTheChapter() {
        openManual()
        // 01_intro carries three PNGs, the largest 300 KB. Their arriving
        // as decodable images is what proves the assets shipped: the text
        // would render the same whether or not they did.
        awaitAny(IMAGE_TIMEOUT_MS, "img:1", "img:2", "img:3", "imgError:1")
        assertTrue("a figure failed to decode; present: ${presentTags()}",
                   presentTags().none { it.startsWith("imgError:") })
        assertTrue("no figure rendered",
                   presentTags().any { it.startsWith("img:") })
    }

    @Test
    fun switchesChapters() {
        openManual()
        compose.onNodeWithTag("chapter:06_benchmarks", useUnmergedTree = true)
            .performScrollTo().performClick()
        awaitAny(NAV_TIMEOUT_MS, "chapterBody")
        assertTrue("chapter body empty after switching",
                   presentTags().any { it.startsWith("seg:") })
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
        const val NAV_TIMEOUT_MS = 30_000L
        // Three PNGs to read across the bridge and decode.
        const val IMAGE_TIMEOUT_MS = 60_000L
        const val POLL_MS = 250L
    }
}
