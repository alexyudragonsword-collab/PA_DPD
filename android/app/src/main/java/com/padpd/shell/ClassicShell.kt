package com.padpd.shell

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.padpd.Destination
import com.padpd.chart.PyBridge
import com.padpd.i18n.tr

/**
 * The original shell: everything on screen at once.
 *
 * Ten destinations in a horizontally scrolling row under the title. It
 * costs a permanent strip of vertical space and hides destinations off
 * the right edge, which is what the drawer shell exists to try
 * differently - but it is also the shape every device test was written
 * against, so it stays, unchanged, as the default.
 */
@Composable
fun ClassicShell(
    current: Destination,
    onPick: (Destination) -> Unit,
    lang: String,
    onLang: (String) -> Unit,
    caps: PyBridge.Capabilities?,
    navigable: Boolean,
    content: @Composable () -> Unit,
) {
    Column(Modifier.fillMaxSize()) {
        TopBar(lang, onLang)
        if (navigable && caps != null) {
            CapabilityLine(caps)
            NavBar(current, onPick)
        }
        content()
    }
}

@Composable
private fun NavBar(current: Destination, onPick: (Destination) -> Unit) {
    Row(
        Modifier.fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 4.dp)
            .horizontalScroll(rememberScrollState())
            .testTag("nav"),
    ) {
        for (d in Destination.entries) {
            val here = d == current
            Text(
                tr(d.zh),
                fontSize = 13.sp,
                fontWeight = if (here) FontWeight.Bold else FontWeight.Normal,
                color = if (here) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(end = 14.dp)
                    .testTag("nav:${d.id}")
                    .clickable { onPick(d) },
            )
        }
    }
}
