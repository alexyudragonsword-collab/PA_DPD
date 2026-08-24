package com.padpd

import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.ComposeTestRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo

/**
 * Go to a destination, whichever shell this build wears.
 *
 * The app has two navigation shells chosen at build time (see
 * com.padpd.shell.AppShell). Every test here was written against the
 * classic one, tapping `nav:<id>` in a row that is always on screen. The
 * drawer shell puts the same ten entries behind a hamburger - and tags
 * them with the same `nav:<id>`, precisely so this is the only place
 * that has to know the difference.
 *
 * Detecting the shell from the tree rather than reading BuildConfig: the
 * test APK and the app APK are built together, so either would work, but
 * asking what is on screen keeps this honest if a third shell ever
 * arrives that also has a hamburger.
 *
 * The drawer is left open only as long as it takes: tapping an entry
 * closes it, and a test that ran with it open would be measuring a
 * screen behind a scrim.
 */
fun ComposeTestRule.goTo(id: String, timeoutMs: Long = 20_000) {
    if (hasTag("drawerToggle")) {
        onNodeWithTag("drawerToggle").performClick()
        awaitTag("drawer", timeoutMs)
        // Two separate things are needed here, and the first run only
        // needed one of them badly enough to fail.
        //
        // useUnmergedTree because NavigationDrawerItem is clickable, and
        // a clickable merges its descendants - the same trap that hid
        // the gallery's chart tags.
        //
        // performScrollTo because the drawer's own list of ten entries
        // scrolls, and the tenth sits below the fold on a 320x640
        // screen. It is composed, so the tag resolves and performClick
        // reports success while injecting a touch nobody receives - the
        // gallery, last in the list, was the one test that noticed.
        // Opening the drawer is not the same as reaching into it.
        onNodeWithTag("nav:$id", useUnmergedTree = true)
            .performScrollTo().performClick()
    } else {
        onNodeWithTag("nav:$id").performScrollTo().performClick()
    }
}

/** Whether any node currently carries [tag]. */
fun ComposeTestRule.hasTag(tag: String): Boolean =
    onAllNodes(hasTestTag(tag), useUnmergedTree = true)
        .fetchSemanticsNodes().isNotEmpty()

/** Wait for [tag] to appear, or fail with what was on screen instead. */
fun ComposeTestRule.awaitTag(tag: String, timeoutMs: Long = 20_000) {
    val deadline = System.currentTimeMillis() + timeoutMs
    while (System.currentTimeMillis() < deadline) {
        waitForIdle()
        if (hasTag(tag)) return
        Thread.sleep(250)
    }
    throw AssertionError("$tag did not appear within ${timeoutMs}ms")
}
