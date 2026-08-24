package com.padpd.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.padpd.i18n.tr

/**
 * Overview, the mobile port of gui_qt/pages/home.py.
 *
 * The four headline figures are the project's measured results carried
 * over verbatim - documentation rather than anything this screen
 * computes. They are labelled as such below the row, because a metric
 * card is exactly the shape a live reading takes on every other screen
 * here and there would otherwise be nothing to tell them apart.
 */
@Composable
fun HomeScreen(lang: String, modifier: Modifier = Modifier) {
    var run by remember { mutableStateOf<ScreenRun>(ScreenRun.Idle) }

    LaunchedEffect(lang) {
        run = ScreenRun.Busy
        run = loadScreen("home", lang)
    }

    Column(modifier.fillMaxSize().padding(12.dp)
        .verticalScroll(rememberScrollState())) {
        Text(tr("padpd 工作台总览"), fontSize = 18.sp,
             fontWeight = FontWeight.SemiBold)

        when (val state = run) {
            is ScreenRun.Idle, is ScreenRun.Busy -> Text(
                tr("计算中…"), fontSize = 12.sp,
                modifier = Modifier.testTag("home:busy"),
            )
            is ScreenRun.Failed -> Text(
                state.message, fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.testTag("home:error"),
            )
            is ScreenRun.Ready -> {
                Text(tr("代表性成果(实测)"), fontSize = 13.sp,
                     fontWeight = FontWeight.Medium,
                     modifier = Modifier.padding(top = 8.dp))
                MetricRow(state.screen.metrics)
                Text(
                    tr("以上为项目已发布的实测结果,不是本机运行所得。"),
                    fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.testTag("headlineProvenance"),
                )

                Text(tr("环境自检"), fontSize = 13.sp,
                     fontWeight = FontWeight.Medium,
                     modifier = Modifier.padding(top = 16.dp))
                for (line in state.screen.notes) {
                    Text(line, fontSize = 11.sp,
                         modifier = Modifier.testTag("env"))
                }

                Text(tr("最近实验"), fontSize = 13.sp,
                     fontWeight = FontWeight.Medium,
                     modifier = Modifier.padding(top = 16.dp))
                if (state.screen.rows.isEmpty()) {
                    Text(tr("还没有 run。先在建模或 DPD 页跑一次。"),
                         fontSize = 12.sp,
                         modifier = Modifier.testTag("noRecentRuns"))
                } else {
                    RowTable(state.screen.rows, "recent")
                }
            }
        }
    }
}
