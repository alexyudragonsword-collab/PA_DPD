package com.padpd.shell

import androidx.compose.runtime.Composable
import com.padpd.BuildConfig
import com.padpd.Destination
import com.padpd.chart.PyBridge

/**
 * Which navigation shell this build wears.
 *
 * Chosen at build time from the padpdNav Gradle property, the same way
 * this module already chooses its ABIs and its buildPython. The default
 * is the classic shell, so a build with no extra arguments behaves
 * exactly as it did before the drawer existed.
 *
 * Both shells are compiled in and only one is reached, which costs a few
 * tens of kilobytes in the APK. The alternative - product flavours -
 * would rename every Gradle task the CI workflow and its scripts name
 * literally (assembleRelease, connectedDebugAndroidTest,
 * updateDebugScreenshotTest, and an APK path glob), and two separate
 * APKs are not yet worth that. If this app ever ships both, flavours are
 * the right answer then.
 *
 * The two shells share a signature so the caller cannot tell them apart,
 * and share [TopBar] and [CapabilityLine] so their common controls
 * cannot drift.
 *
 * @param caps null until Python has booted; the shells show what they
 *   can without it.
 * @param navigable false while booting or after a boot failure - the
 *   destinations exist but going to them would show nothing.
 */
@Composable
fun AppShell(
    current: Destination,
    onPick: (Destination) -> Unit,
    lang: String,
    onLang: (String) -> Unit,
    caps: PyBridge.Capabilities?,
    navigable: Boolean,
    content: @Composable () -> Unit,
) {
    if (BuildConfig.NAV_SHELL == "drawer") {
        DrawerShell(current, onPick, lang, onLang, caps, navigable, content)
    } else {
        ClassicShell(current, onPick, lang, onLang, caps, navigable, content)
    }
}
