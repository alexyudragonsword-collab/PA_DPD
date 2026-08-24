package com.padpd.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import android.graphics.BitmapFactory
import com.padpd.chart.PyBridge
import com.padpd.i18n.tr
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonPrimitive

/**
 * The built-in manual, the mobile port of gui_qt/pages/manual.py.
 *
 * Compose has no Markdown renderer, so the Python side slices each
 * chapter into prose and image segments - the same split_segments() the
 * Streamlit build uses for its own reason - and this walks the pieces.
 *
 * The prose is shown as-is rather than rendered. Pulling in a Markdown
 * library to style headings and lists would be the obvious next step;
 * showing the source is honest in the meantime and the text is readable,
 * where a half-implemented renderer that silently drops tables would not
 * be.
 */
@Composable
fun ManualScreen(lang: String, modifier: Modifier = Modifier) {
    var chapter by remember { mutableStateOf("") }
    var run by remember { mutableStateOf<ScreenRun>(ScreenRun.Idle) }
    var images by remember { mutableStateOf<Map<String, ImageBytes>>(emptyMap()) }

    LaunchedEffect(chapter, lang) {
        run = ScreenRun.Busy
        val loaded = loadScreen("manual", lang, JsonPrimitive(chapter))
        // Fetch the chapter's images off the UI thread, before anything
        // is drawn: decoding a 300 KB PNG during layout would drop
        // frames on the scroll that reveals it.
        if (loaded is ScreenRun.Ready) {
            images = withContext(Dispatchers.Default) {
                loaded.screen.segments
                    .filter { it.kind == "img" && it.blob.isNotEmpty() }
                    .associate { it.blob to ImageBytes(PyBridge.blob(it.blob)) }
            }
        }
        run = loaded
    }

    Column(modifier.fillMaxSize().padding(12.dp)) {
        Text(tr("用户手册"), fontSize = 18.sp,
             fontWeight = FontWeight.SemiBold)

        when (val state = run) {
            is ScreenRun.Idle, is ScreenRun.Busy -> Text(
                tr("计算中…"), fontSize = 12.sp,
                modifier = Modifier.testTag("manual:busy"),
            )
            is ScreenRun.Failed -> Text(
                state.message, fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.testTag("manual:error"),
            )
            is ScreenRun.Ready -> {
                val current = state.screen.options.firstOrNull().orEmpty()
                Row(Modifier.fillMaxWidth().padding(vertical = 6.dp)
                    .horizontalScroll(rememberScrollState())
                    .testTag("toc")) {
                    for (row in state.screen.rows) {
                        val id = row["id"].orEmpty()
                        val here = id == current
                        Text(
                            row["title"].orEmpty(),
                            fontSize = 12.sp,
                            fontWeight = if (here) FontWeight.Bold
                                         else FontWeight.Normal,
                            color = if (here)
                                MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(end = 12.dp)
                                .testTag("chapter:$id")
                                .clickable { chapter = id },
                        )
                    }
                }

                Column(Modifier.fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .testTag("chapterBody")) {
                    for ((i, seg) in state.screen.segments.withIndex()) {
                        when (seg.kind) {
                            "img" -> images[seg.blob]?.let { bytes ->
                                ManualImage(bytes, seg.caption, i)
                            }
                            else -> Text(
                                seg.text, fontSize = 12.sp,
                                modifier = Modifier.padding(vertical = 6.dp)
                                    .testTag("seg:$i"),
                            )
                        }
                    }
                }
            }
        }
    }
}

/** Decoded lazily and once, since a chapter can carry three 300 KB PNGs. */
private class ImageBytes(val raw: ByteArray) {
    val bitmap by lazy {
        runCatching {
            BitmapFactory.decodeByteArray(raw, 0, raw.size)
        }.getOrNull()
    }
}

@Composable
private fun ManualImage(bytes: ImageBytes, caption: String, index: Int) {
    val bitmap = bytes.bitmap
    if (bitmap == null) {
        // Say so rather than leaving a gap: a chapter whose figure is
        // missing should not look complete.
        Text(tr("[图片解码失败]"), fontSize = 11.sp,
             color = MaterialTheme.colorScheme.error,
             modifier = Modifier.testTag("imgError:$index"))
        return
    }
    Column(Modifier.padding(vertical = 8.dp)) {
        Image(
            bitmap.asImageBitmap(),
            contentDescription = caption,
            contentScale = ContentScale.FillWidth,
            modifier = Modifier.fillMaxWidth()
                .clip(RoundedCornerShape(6.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant)
                .testTag("img:$index"),
        )
        if (caption.isNotEmpty()) {
            Text(caption, fontSize = 10.sp,
                 color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
