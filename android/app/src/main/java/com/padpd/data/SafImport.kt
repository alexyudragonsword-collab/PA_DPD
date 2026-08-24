package com.padpd.data

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import java.io.File

/**
 * Turning a picked document into something Python can open.
 *
 * `gui_core.services.load_source` takes a filesystem path, because on
 * the desktop that is what a file is. Android's Storage Access Framework
 * hands out a `content://` URI instead, which is a revocable permission
 * grant addressed to a provider - not a location, and not something the
 * interpreter can pass to `open()`. There is no path to recover from it:
 * the document may live in another app's private storage, on a network
 * provider, or inside a zip.
 *
 * So the bytes are copied out while the grant is live. That is the
 * intended shape of SAF, not a workaround for it - the grant a picker
 * returns is scoped to this task and can be revoked the moment the user
 * leaves the app, so anything that needs the content later must have
 * taken a copy.
 *
 * Copies land in `cacheDir`, which the system may reclaim under storage
 * pressure. That is the correct place regardless: the imported source is
 * already held in memory as numpy arrays once Python has read it, and
 * keeping a second permanent copy of a 40 MB capture would grow the
 * app's footprint with every import.
 */
object SafImport {

    /** Sub-directory of cacheDir the copies go to, so they can be cleared. */
    private const val DIR = "imports"

    /**
     * Copy [uri] into the cache and return its absolute path.
     *
     * The document's display name is preserved because the extension is
     * load-bearing: pages.py picks the loader (`npz`, `cadence`, `mat`)
     * from the suffix, so a copy named after the URI's opaque last path
     * segment would arrive as an unsupported type.
     */
    fun copyToCache(context: Context, uri: Uri): String {
        val dir = File(context.cacheDir, DIR).apply { mkdirs() }
        val dest = File(dir, displayName(context, uri))
        context.contentResolver.openInputStream(uri).use { input ->
            requireNotNull(input) { "cannot open $uri" }
            dest.outputStream().use { input.copyTo(it) }
        }
        return dest.absolutePath
    }

    /**
     * The document's file name, sanitised.
     *
     * A provider is free to return anything as the display name, path
     * separators included, and this name is joined onto a directory. A
     * name of "../../databases/x" would write outside the cache; taking
     * only the last segment makes that impossible rather than unlikely.
     */
    fun displayName(context: Context, uri: Uri): String {
        val raw = context.contentResolver.query(
            uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null,
        )?.use { c ->
            if (c.moveToFirst() && !c.isNull(0)) c.getString(0) else null
        } ?: uri.lastPathSegment ?: "imported"
        val name = raw.substringAfterLast('/').substringAfterLast('\\')
        return if (name.isBlank() || name == "." || name == "..") "imported"
               else name
    }

    /** MIME types the pickers offer. */
    val SOURCE_TYPES = arrayOf("*/*")
}
