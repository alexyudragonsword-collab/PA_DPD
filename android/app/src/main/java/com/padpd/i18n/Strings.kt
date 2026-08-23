package com.padpd.i18n

/**
 * Translation by lookup, with the Chinese string as the key.
 *
 * This mirrors `gui_core/i18n.py` exactly: Kotlin sources carry the
 * Chinese sentence verbatim, the same way `gui_qt/pages/*.py` carry it,
 * and translation is a dictionary hit that falls back to the key. One
 * table, in Python, for all three front ends.
 *
 * Not res/values/strings.xml, which is the obvious Android answer.
 * Resource names cannot be Chinese, so generating that file would give
 * every string a synthetic identifier and Kotlin would read
 * `stringResource(R.string.s_9f2a41)` where the desktop reads the
 * sentence - unreviewable, and the mapping back to i18n.py would live
 * only in a generator. Resource files buy following the system locale,
 * and this app does not: language is a control in the UI, as on desktop.
 *
 * tests/test_mobile_pages.py scans these sources for Chinese literals
 * and fails if one has no entry in i18n.py, which is the Kotlin half of
 * the rule AGENTS.md states and test_gui_i18n.py enforces for Qt.
 */
object Strings {

    @Volatile
    private var table: Map<String, String> = emptyMap()

    /** Install the table for a language. Empty means "show the keys". */
    fun install(map: Map<String, String>) {
        table = map
    }

    /** Translate, falling back to the Chinese so nothing ever blanks. */
    fun tr(zh: String): String = table[zh] ?: zh

    /**
     * Translate and substitute, for the parameterised entries.
     *
     * i18n.py writes placeholders as `{name}` because Python formats with
     * str.format; both the key and its translation carry them, so the
     * substitution has to happen after the lookup, on whichever string
     * came back.
     */
    fun tr(zh: String, vararg subs: Pair<String, Any>): String {
        var out = tr(zh)
        for ((k, v) in subs) out = out.replace("{$k}", v.toString())
        return out
    }
}

/** Shorthand, so call sites read like the Qt sources do. */
fun tr(zh: String): String = Strings.tr(zh)

fun tr(zh: String, vararg subs: Pair<String, Any>): String =
    Strings.tr(zh, *subs)
