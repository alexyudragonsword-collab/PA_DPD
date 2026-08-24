package com.padpd

import android.util.Log
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.test.junit4.ComposeTestRule
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.captureToImage
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File

/**
 * Screenshots as evidence, not as assertions.
 *
 * Nothing here compares against a golden image, and that is the point.
 * These run on an emulator whose binary version comes from the GitHub
 * runner image, which GitHub upgrades on its own schedule; font
 * rasterisation and anti-aliasing move with it, so a pixel comparison
 * taken here would go red for reasons that have nothing to do with the
 * commit under test. Golden comparison belongs on the JVM, where
 * layoutlib is a pinned artifact.
 *
 * What these are for is the question node assertions structurally cannot
 * answer: does it *look* right. A test can confirm a metric card exists
 * and carries the right text while the card is four lines tall and
 * shoving its neighbours off screen. So every CI run leaves a set of
 * PNGs in the artifact, and looking at the app becomes opening a zip
 * rather than building and installing an APK.
 *
 * They are deliberately unable to fail the build. Evidence that gates
 * CI is an assertion, and an assertion this flaky would be turned off
 * within a month.
 */
object Screenshots {

    /**
     * Where the PNGs go.
     *
     * AGP passes `additionalTestOutputDir` to the runner and pulls that
     * directory off the device after the run, which is the supported way
     * to get files out - `adb pull` of an app's external files directory
     * needs root on API 30+. When the argument is absent (an older AGP,
     * or a plain `am instrument`) this falls back to the app's own
     * external files directory, and the emulator script pulls it as a
     * second chance.
     */
    private val dir: File by lazy {
        val args = InstrumentationRegistry.getArguments()
        val fromAgp = args.getString("additionalTestOutputDir")
        val base = if (fromAgp != null) File(fromAgp) else File(
            InstrumentationRegistry.getInstrumentation().targetContext
                .getExternalFilesDir(null),
            "screenshots",
        )
        base.apply { mkdirs() }
    }

    private const val TAG = "padpd"

    /** How many PNGs this run has written, for the smoke test below. */
    var written: Int = 0
        private set

    /**
     * Capture the whole screen under [name].
     *
     * Swallows its own failures: a screenshot that cannot be taken must
     * not turn a passing behavioural test red. The count above is what
     * a dedicated test checks, so a silently broken capture path is
     * still noticed - just not by breaking someone else's test.
     */
    fun capture(compose: ComposeTestRule, name: String) {
        runCatching {
            compose.waitForIdle()
            val bitmap = compose.onRoot().captureToImage().asAndroidBitmap()
            File(dir, "$name.png").outputStream().use { out ->
                bitmap.compress(
                    android.graphics.Bitmap.CompressFormat.PNG, 100, out)
            }
            written++
            // Log, not println: an instrumented test's stdout does not
            // reliably reach the log the CI script greps, and this line
            // is how a run with zero collected screenshots says whether
            // the write failed or only the pull did.
            Log.i(TAG, "padpd-screenshot: ${File(dir, "$name.png")}")
        }.onFailure {
            Log.w(TAG, "padpd-screenshot: FAILED $name", it)
        }
    }
}
