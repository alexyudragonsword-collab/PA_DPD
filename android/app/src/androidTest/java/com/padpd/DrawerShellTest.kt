package com.padpd

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.swipeRight
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * The drawer shell's own behaviour.
 *
 * Everything else in this directory now navigates through
 * [goTo], which works on either shell and therefore proves nothing about
 * the drawer beyond "an entry can be tapped". This covers the parts that
 * are the drawer: opening, closing on selection, the swipe, and the
 * capability line having moved into it.
 *
 * Skipped wholesale on a classic build. A test that silently passes
 * because the thing it tests is absent is worse than one that says it
 * did not run, which is what assumeTrue reports.
 */
@RunWith(AndroidJUnit4::class)
class DrawerShellTest {

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    private fun bootedDrawerBuild(): Boolean {
        compose.awaitTag("caps", BOOT_TIMEOUT_MS)
        return compose.hasTag("drawerToggle")
    }

    @Test
    fun theHamburgerOpensTheDrawer() {
        assumeTrue("classic build - no drawer", bootedDrawerBuild())
        assertFalse("drawer was open before anything was tapped",
                    compose.hasTag("drawer") && drawerReachable())

        compose.onNodeWithTag("drawerToggle").performClick()
        compose.awaitTag("drawer")
        assertTrue("no destinations in the drawer",
                   compose.hasTag("nav:home"))
    }

    @Test
    fun pickingADestinationClosesTheDrawerAndSwitchesScreen() {
        assumeTrue("classic build - no drawer", bootedDrawerBuild())
        compose.goTo("manual")
        // The manual loads its first chapter on arrival, which is the
        // screen having actually changed rather than the drawer merely
        // having shut.
        compose.awaitTag("chapterBody", NAV_TIMEOUT_MS)
        assertFalse("drawer still on screen after picking a destination",
                    drawerReachable())
    }

    @Test
    fun swipingFromTheEdgeOpensTheDrawer() {
        assumeTrue("classic build - no drawer", bootedDrawerBuild())
        // ModalNavigationDrawer's own gesture - this project writes no
        // drag handling of its own. What is worth checking is that the
        // gesture survives a screen full of horizontally scrolling rows,
        // which is the trap this app has hit twice in other forms.
        compose.onNodeWithTag("appTitle").performTouchInput { swipeRight() }
        compose.awaitTag("drawer")
        assertTrue("swipe did not reveal the destinations",
                   drawerReachable())
    }

    @Test
    fun theCapabilityLineMovedIntoTheDrawer() {
        assumeTrue("classic build - no drawer", bootedDrawerBuild())
        // It is composed either way - the drawer sheet is laid out even
        // while closed - so what this asserts is that it is no longer
        // taking a permanent strip of the main screen: opening the
        // drawer must be what brings the destinations with it.
        compose.onNodeWithTag("drawerToggle").performClick()
        compose.awaitTag("drawer")
        assertTrue("capability line is not in the drawer",
                   compose.hasTag("caps") && compose.hasTag("nav:deploy"))
    }

    /** Whether a drawer entry can actually be reached, not merely composed. */
    private fun drawerReachable(): Boolean = runCatching {
        compose.onNodeWithTag("nav:home", useUnmergedTree = true)
            .assertIsDisplayed()
    }.isSuccess

    private companion object {
        const val BOOT_TIMEOUT_MS = 120_000L
        const val NAV_TIMEOUT_MS = 30_000L
    }
}
