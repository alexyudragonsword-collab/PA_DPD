package com.padpd.shell

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.Text
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.padpd.Destination
import com.padpd.chart.PyBridge
import com.padpd.i18n.tr
import kotlinx.coroutines.launch

/**
 * The drawer shell: destinations live behind a hamburger and a swipe.
 *
 * This is the shape the desktop already has - gui_qt/main.py puts the
 * same ten entries in a permanent left list - so the phone is not being
 * given a novel idea here, it is being brought back in line. What a
 * phone cannot afford is the *permanent* list, hence a drawer.
 *
 * Swiping is [ModalNavigationDrawer]'s own gesture; there is no custom
 * drag handling. It is disabled until the app can navigate, so a swipe
 * during boot cannot open a drawer whose entries do nothing yet.
 *
 * **The gesture shares the screen with a lot of horizontal scrolling.**
 * Nine of the ten screens put option rows, metric cards or tables inside
 * Modifier.horizontalScroll. Compose negotiates this through nested
 * scroll - a row already at its start cannot consume a rightward drag,
 * so the drawer takes it - which is standard Android behaviour and the
 * intended outcome. It is also the third variant of a trap this project
 * has hit twice before (see android/README.md), so it is verified on a
 * device rather than reasoned about.
 */
@Composable
fun DrawerShell(
    current: Destination,
    onPick: (Destination) -> Unit,
    lang: String,
    onLang: (String) -> Unit,
    caps: PyBridge.Capabilities?,
    navigable: Boolean,
    content: @Composable () -> Unit,
) {
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()

    ModalNavigationDrawer(
        drawerContent = {
            ModalDrawerSheet(Modifier.testTag("drawer")) {
                Text(
                    tr("功能"),
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Medium,
                    modifier = Modifier.padding(start = 28.dp, top = 16.dp,
                                                bottom = 8.dp),
                )
                // Ten entries do not fit every phone in portrait, and a
                // destination that cannot be reached is worse here than
                // on the classic shell - there is no second way in.
                Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
                    for (d in Destination.entries) {
                        NavigationDrawerItem(
                            label = { Text("${d.emoji}  ${tr(d.zh)}") },
                            selected = d == current,
                            onClick = {
                                onPick(d)
                                scope.launch { drawerState.close() }
                            },
                            modifier = Modifier
                                .padding(horizontal = 12.dp, vertical = 2.dp)
                                .testTag("nav:${d.id}"),
                        )
                    }
                }
                // Low-frequency and explanatory, so it sits at the foot
                // of the drawer rather than taking a permanent strip of
                // the screen the way it does on the classic shell.
                if (caps != null) {
                    CapabilityLine(caps, Modifier.padding(vertical = 12.dp))
                }
            }
        },
        drawerState = drawerState,
        gesturesEnabled = navigable,
    ) {
        Column(Modifier.fillMaxSize()) {
            TopBar(
                lang, onLang,
                leading = {
                    Text(
                        "☰",
                        fontSize = 18.sp,
                        modifier = Modifier.padding(end = 12.dp)
                            .testTag("drawerToggle")
                            .clickable(enabled = navigable) {
                                scope.launch { drawerState.open() }
                            },
                    )
                },
            )
            content()
        }
    }
}
