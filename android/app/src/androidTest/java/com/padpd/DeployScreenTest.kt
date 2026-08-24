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
 * Deployment on a device.
 *
 * Fits a model first, because this screen sweeps over what the Modeling
 * screen registered in the session and instrumented tests share an app
 * installation but not an order. A deployment test that passed only
 * because an earlier test left a model behind would be testing the test
 * order.
 */
@RunWith(AndroidJUnit4::class)
class DeployScreenTest {

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    @Test
    fun sweepsAModelFittedInTheSameSession() {
        awaitAny(BOOT_TIMEOUT_MS, "caps", "bootError")
        assertFalse("Python failed to start on device", exists("bootError"))

        compose.onNodeWithTag("nav:modeling").performScrollTo().performClick()
        awaitAny(NAV_TIMEOUT_MS, "fit")
        compose.onNodeWithTag("fit", useUnmergedTree = true).performClick()
        val fitted = awaitAny(FIT_TIMEOUT_MS, "chart:psd", "fit:error")
        assertFalse("fit failed, so there is nothing to sweep",
                    fitted == "fit:error")

        compose.onNodeWithTag("nav:deploy").performScrollTo().performClick()
        awaitAny(NAV_TIMEOUT_MS, "sweep", "noModels")
        assertFalse("deployment screen saw no fitted model",
                    exists("noModels"))

        // Pick the model, then sweep. The default bit widths are already
        // selected, matching the desktop.
        //
        // "multi:model:" rather than the first tag starting "multi:":
        // that picked the bit-width row instead, because the tags were
        // built from translated labels and 位 sorts before 模. Control
        // tags are ASCII and explicit now, so this names what it means.
        val model = presentTags().first { it.startsWith("multi:model:") }
        compose.onNodeWithTag(model, useUnmergedTree = true)
            .performScrollTo().performClick()
        compose.onNodeWithTag("sweep", useUnmergedTree = true)
            .performScrollTo().performClick()

        val seen = awaitAny(SWEEP_TIMEOUT_MS, "chart:bitwidth", "sweep:error")
        assertFalse("bit-width sweep failed on device", seen == "sweep:error")
        assertTrue("no result table", exists("sweep:table"))
    }

    @Test
    fun statesWhyExportIsUnavailable() {
        awaitAny(BOOT_TIMEOUT_MS, "caps", "bootError")
        compose.onNodeWithTag("nav:deploy").performScrollTo().performClick()
        awaitAny(NAV_TIMEOUT_MS, "exportUnavailable", "noModels",
                 "sweep")
        // Three blockers - SAF, torch, iverilog - so the screen explains
        // rather than drawing a button that cannot work.
        assertTrue("no explanation for the missing export",
                   exists("exportUnavailable"))
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
        // A three-width sweep measures 0.6 s on a workstation.
        const val SWEEP_TIMEOUT_MS = 90_000L
        const val POLL_MS = 250L
    }
}
