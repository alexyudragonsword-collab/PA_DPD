package com.padpd

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertFalse
import org.junit.Test
import org.junit.Rule
import org.junit.runner.RunWith

/**
 * The screen itself: does the app start, does Python come up, does
 * tapping an entry draw something.
 *
 * Only the first entry is exercised. The gallery is a LazyColumn, so
 * entries below the fold are not composed until scrolled to, and driving
 * all fourteen through the list would be testing scrolling rather than
 * charts - which is what PyBridgeTest and ChartRenderTest already cover
 * without it.
 */
@RunWith(AndroidJUnit4::class)
class GalleryScreenTest {

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    @Test
    fun startsAndDrawsTheFirstChart() {
        compose.waitUntil(BOOT_TIMEOUT_MS) { exists("caps") || exists("bootError") }
        assertFalse("Python failed to start on device", exists("bootError"))
        compose.onNodeWithTag("caps").assertIsDisplayed()

        compose.onNodeWithTag("entry:psd").performClick()
        compose.waitUntil(CHART_TIMEOUT_MS) { exists("chart:psd") || exists("error:psd") }
        assertFalse("psd failed to build on device", exists("error:psd"))
        compose.onNodeWithTag("chart:psd").assertIsDisplayed()
    }

    private fun exists(tag: String): Boolean =
        compose.onAllNodes(hasTestTag(tag)).fetchSemanticsNodes().isNotEmpty()

    private companion object {
        // First launch unpacks numpy and scipy.
        const val BOOT_TIMEOUT_MS = 120_000L
        const val CHART_TIMEOUT_MS = 60_000L
    }
}
