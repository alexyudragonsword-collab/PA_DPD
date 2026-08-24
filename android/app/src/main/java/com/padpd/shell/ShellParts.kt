package com.padpd.shell

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.padpd.chart.PyBridge
import com.padpd.i18n.tr

/**
 * The chrome both navigation shells share.
 *
 * Kept in one place rather than copied into each shell: the language
 * switch and the capability line are the same controls whichever way the
 * app navigates, and two copies of a control is how the two shells would
 * start behaving differently without anyone deciding they should.
 */

/**
 * Title, an optional leading slot, and the language switch.
 *
 * [leading] is where the drawer shell puts its hamburger. The classic
 * shell passes nothing and the row lays out exactly as it did before.
 */
@Composable
fun TopBar(
    lang: String,
    onLang: (String) -> Unit,
    leading: @Composable (() -> Unit)? = null,
) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (leading != null) {
            leading()
        }
        Text(
            tr("WiFi 7 PA + DPD 工作台"),
            fontSize = 15.sp, fontWeight = FontWeight.SemiBold,
            modifier = Modifier.testTag("appTitle"),
        )
        Row(Modifier.fillMaxWidth().padding(start = 12.dp)) {
            for (code in listOf("zh", "en")) {
                Text(
                    code.uppercase(),
                    fontSize = 12.sp,
                    fontWeight = if (code == lang) FontWeight.Bold
                                 else FontWeight.Normal,
                    color = if (code == lang) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(end = 8.dp)
                        .testTag("lang:$code")
                        .clickable { onLang(code) },
                )
            }
        }
    }
}

/**
 * What this build can and cannot do, stated up front.
 *
 * torch has no Android wheel, so five entry points cannot run at all.
 * Saying so here - rather than only greying controls where they appear -
 * means the limitation is visible before someone plans work around it.
 */
@Composable
fun CapabilityLine(caps: PyBridge.Capabilities, modifier: Modifier = Modifier) {
    Text(
        "padpd ${caps.version} · " +
            tr("{n} 种图表", "n" to caps.charts.size) + " · " +
            tr("torch 不可用({n} 个入口)", "n" to caps.unavailable.size),
        fontSize = 11.sp,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = modifier.padding(horizontal = 12.dp).testTag("caps"),
    )
}
