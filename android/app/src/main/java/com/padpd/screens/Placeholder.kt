package com.padpd.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.padpd.i18n.tr

/**
 * A screen that exists in the navigation but has no implementation yet.
 *
 * Deliberately present rather than omitted. The nine screens are ported
 * one at a time, and a navigation bar that grows an entry per port hides
 * how much is left; one that is complete from the start shows it. The
 * label says "not implemented yet" rather than something reassuring, so
 * a screenshot of this build cannot be mistaken for a finished app.
 */
@Composable
fun Placeholder(title: String, modifier: Modifier = Modifier) {
    Column(
        modifier.fillMaxSize().padding(24.dp).testTag("placeholder"),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(title, fontSize = 18.sp, textAlign = TextAlign.Center)
        Text(
            tr("尚未实现"),
            fontSize = 13.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
