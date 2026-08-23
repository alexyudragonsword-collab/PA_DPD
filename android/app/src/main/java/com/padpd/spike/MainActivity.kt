package com.padpd.spike

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.TypedValue
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.util.concurrent.Executors

/**
 * Phase 0 feasibility spike: one button, one text view, no business UI.
 *
 * The UI is built in code rather than XML because the whole activity is
 * throwaway - it exists to get numbers off a real device, and a layout
 * file would be one more thing to keep in sync for no benefit.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var output: TextView
    private lateinit var runButton: Button

    // Python calls block for seconds and share a single interpreter, so
    // they get one dedicated background thread and never the UI thread.
    // This is the same rule the desktop Qt GUI follows with FnWorker.
    private val worker = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        output = TextView(this).apply {
            typeface = Typeface.MONOSPACE
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 11f)
            setTextIsSelectable(true)
            text = getString(R.string.idle)
            setPadding(24, 24, 24, 24)
        }

        runButton = Button(this).apply {
            text = getString(R.string.run_probe)
            setOnClickListener { runProbe() }
        }

        val copyButton = Button(this).apply {
            text = "Copy result"
            setOnClickListener {
                val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                cm.setPrimaryClip(ClipData.newPlainText("padpd probe", output.text))
                Toast.makeText(this@MainActivity, "Copied", Toast.LENGTH_SHORT).show()
            }
        }

        val buttons = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            addView(runButton)
            addView(copyButton)
        }

        val scroll = ScrollView(this).apply {
            addView(output)
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f)
        }

        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.BLACK)
            addView(buttons)
            addView(scroll)
        })
    }

    private fun runProbe() {
        runButton.isEnabled = false
        output.text = getString(R.string.running)
        val startedAt = System.nanoTime()

        worker.execute {
            val report = try {
                // Starting the interpreter is itself part of what we are
                // measuring: unpacking numpy/scipy on first launch is the
                // slowest thing this app does.
                if (!Python.isStarted()) {
                    Python.start(AndroidPlatform(this))
                }
                val bootMs = (System.nanoTime() - startedAt) / 1_000_000

                // filesDir is the app's private, writable, backed-up-free
                // directory. gui_core/paths.py already honours
                // PADPD_DATA_DIR, so no padpd code needs changing - the
                // probe sets the variable from inside Python because Java
                // cannot portably mutate the process environment.
                val probe = Python.getInstance().getModule("padpd_spike.probe")
                val body = probe.callAttr("boot", filesDir.absolutePath).toString()

                "python start + import: ${bootMs} ms\n\n$body"
            } catch (t: Throwable) {
                "PROBE CRASHED\n\n${t.stackTraceToString()}"
            }

            main.post {
                output.text = report
                runButton.isEnabled = true
            }
        }
    }

    override fun onDestroy() {
        worker.shutdown()
        super.onDestroy()
    }
}
