package com.padpd.spike

import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * Runs the feasibility probe headlessly so CI can execute it without a
 * human tapping the button.
 *
 * Caveat that matters when reading the numbers this produces: GitHub's
 * runners only offer x86_64 emulators. That is enough to answer "do the
 * scipy submodules load", "does the service layer import torch-free" and
 * "does Python start at all" - but emulated x86_64 timings say nothing
 * useful about an arm64 phone. Acceptance criterion 3 (the benchmark
 * budget) still has to be checked on real hardware.
 */
@RunWith(AndroidJUnit4::class)
class ProbeTest {

    @Test
    fun probeCompletesWithoutFailures() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(ctx))
        }
        val report = Python.getInstance()
            .getModule("padpd_spike.probe")
            .callAttr("boot", ctx.filesDir.absolutePath)
            .toString()

        // One log call per line: logcat truncates long messages, and a
        // truncated report is worse than no report when the point of the
        // run is to read the numbers.
        report.lineSequence().forEach { Log.i(TAG, it) }

        // Also drop it on disk so the workflow can pull the whole thing
        // as an artifact rather than scraping a ring buffer.
        ctx.getExternalFilesDir(null)?.let { dir ->
            runCatching { File(dir, "probe-report.txt").writeText(report) }
                .onFailure { Log.w(TAG, "could not write report file: $it") }
        }

        assertTrue("probe produced no verdict:\n$report",
                   report.contains("VERDICT:"))
        assertFalse("probe reported failures:\n$report",
                    report.contains("FAILURE(S)"))
    }

    private companion object {
        const val TAG = "padpd-probe"
    }
}
