package com.padpd

import android.net.Uri
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.padpd.data.SafImport
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * The import half of the Data screen, without the picker.
 *
 * The system picker cannot be driven from an instrumented test, but it
 * is not the part worth testing: it returns a URI and nothing else. What
 * this project wrote is the copy that follows - reading the bytes out
 * through a ContentResolver, keeping the extension that decides which
 * loader runs, and refusing a name that would escape the cache
 * directory. A `file://` URI exercises all three through the same
 * ContentResolver path a `content://` one takes.
 */
@RunWith(AndroidJUnit4::class)
class SafImportTest {

    private val context =
        InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun copiesTheBytesAndKeepsTheExtension() {
        val source = File(context.cacheDir, "two_tone_probe.csv")
        source.writeText("spacing_hz,im3_lower_dbc\n1e6,-40.0\n")

        val copied = SafImport.copyToCache(context, Uri.fromFile(source))

        assertTrue("copy is not under cacheDir: $copied",
                   copied.startsWith(context.cacheDir.absolutePath))
        assertEquals("the suffix decides the loader, so it must survive",
                     "csv", File(copied).extension)
        assertEquals(source.readText(), File(copied).readText())
    }

    @Test
    fun refusesANameThatWouldEscapeTheCacheDirectory() {
        // A provider chooses its own display name, so a name carrying
        // path separators is input this code receives, not input it
        // constructs. "../../databases/x" joined onto the cache dir
        // would write into the app's databases.
        val name = SafImport.displayName(
            context, Uri.parse("file:///tmp/../../databases/x"))

        assertTrue("kept a path separator: $name", '/' !in name)
        assertTrue("kept a path separator: $name", '\\' !in name)
    }

    @Test
    fun fallsBackWhenTheNameIsOnlyADotSegment() {
        val name = SafImport.displayName(context, Uri.parse("file:///a/b/.."))
        assertEquals("imported", name)
    }
}
