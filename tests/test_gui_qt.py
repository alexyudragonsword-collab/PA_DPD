"""Offscreen tests for the PySide6 desktop workbench.

What is pinned here is behaviour the old window got wrong: every page
fits a 1280 px screen in both languages, a result stays on screen across
a language or theme switch, a result whose inputs were edited is marked
stale, a spec change re-judges a stored result without re-running it,
and the comparison only lines up runs of one kind.
"""

import os
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

QtWidgets = pytest.importorskip(
    "PySide6.QtWidgets", reason="PySide6 (or its EGL runtime) not available")
pytest.importorskip("pyqtgraph", reason="pyqtgraph not installed")


@pytest.fixture(scope="module")
def app():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app
    # Destroy all Qt garbage NOW, on this thread, while the QApplication
    # is still alive. If a QWidget destructor instead runs later inside a
    # GC pass on a non-Qt thread (observed: streamlit's ScriptRunner
    # thread during the web tests), it blocks forever in
    # QWindow::close -> flushWindowSystemEvents and freezes the whole
    # pytest process while holding the GIL.
    import gc
    gc.collect()
    app.processEvents()
    gc.collect()


@pytest.fixture(scope="module")
def window(app, tmp_path_factory):
    from gui_qt import common
    common.reset_state(tmp_path_factory.mktemp("padpd_data"))
    saved = dict(common.PREFS)
    common.PREFS.update({"lang": "zh", "theme": "light"})
    from gui_qt.main import MainWindow
    win = MainWindow()
    win.resize(1280, 860)
    win.show()
    yield win
    common.PREFS.update(saved)
    # Tear the C++ side down deterministically (deleteLater skips
    # closeEvent's confirm dialog); the surviving Python wrapper is then
    # harmless to collect from any thread.
    win.deleteLater()
    app.processEvents()


@pytest.fixture()
def no_prefs_io(monkeypatch):
    from gui_qt import common
    monkeypatch.setattr(common, "save_prefs", lambda *a, **k: None)


def _settle(app, page=None, timeout_s=300):
    """Wait for a page's run, then pump queued signals until no worker
    is alive (the finished signal arrives through the event loop)."""
    from gui_qt import common
    if page is not None and hasattr(page, "wait"):
        assert page.wait(timeout_s * 1000)
    deadline = time.time() + 15
    while time.time() < deadline:
        app.processEvents()
        if common.live_worker_count() == 0:
            break
        time.sleep(0.02)
    app.processEvents()


def _run(app, window, pid, **values):
    window.navigate(pid)
    page = window.pages[pid]
    if values:
        page.form.set_values(values)
    page.run()
    _settle(app, page)
    assert not page.error, page.error
    return page


def _tiles(page):
    from gui_qt.experiment_page import VerdictTile
    return page.findChildren(VerdictTile)


def _dpd(app, window):
    page = window.page("dpd")
    if page.outcome is None:
        _run(app, window, "dpd")
    window.navigate("dpd")
    app.processEvents()
    return page


def test_rail_lists_every_page_and_each_one_opens(app, window):
    from gui_qt.main import PAGES
    assert [p for p, *_ in PAGES][:6] == [
        "overview", "waveform", "sources", "pa_model", "dpd", "deploy"]
    for pid, *_ in PAGES:
        window.navigate(pid)
        app.processEvents()
        assert window.stack.currentWidget() is window.pages[pid]
        assert window.rail_btns[pid].isChecked()


def test_dpd_run_judges_against_the_spec_and_records_where_it_came_from(
        app, window):
    from gui_qt import common
    page = _dpd(app, window)
    tiles = _tiles(page)
    assert len(tiles) == 3                     # EVM, ACLR, mask margin
    assert all(t.d["ok"] is True for t in tiles)
    assert all(t.d["was_ok"] is False for t in tiles)
    run = common.state().runstore.get(page.outcome.run_id)
    assert run.kind == "dpd"
    assert run.config["source"] == common.state().workspace.active_source
    assert page.prov.isVisible() and page.outcome.run_id in \
        page.prov_id.text()


def test_a_spec_change_rejudges_the_shown_result_without_rerunning(
        app, window):
    from gui_qt import common
    page = _dpd(app, window)
    outcome = page.outcome
    ws = common.state().workspace
    try:
        ws.set_spec(evm_db=-65.0)
        window.workspace_changed()
        app.processEvents()
        evm = _tiles(page)[0]
        assert evm.d["ok"] is False             # -59.8 dB vs a -65 limit
        assert page.outcome is outcome
        assert "-65" in window.chip_spec.text()
    finally:
        ws.set_spec(evm_db=-40.0)
        window.workspace_changed()


def test_editing_an_input_marks_the_result_stale_until_reproduced(
        app, window):
    page = _dpd(app, window)
    assert page.stale.isHidden()
    page.form.fields["basis"].set_value("MP")
    page.form.changed.emit()
    assert not page.stale.isHidden()
    page.reproduce()
    assert page.stale.isHidden()


def test_hidden_inputs_follow_the_algorithm(app, window):
    page = window.page("dpd")
    f = page.form.fields
    page.form.set_values({"algo": "DLA"})
    assert not f["hidden"].row.isHidden()
    assert not f["surrogate"].row.isHidden()
    assert f["basis"].row.isHidden()
    page.form.set_values({"algo": "ILA"})
    assert f["hidden"].row.isHidden()
    assert f["surrogate"].row.isHidden()      # synthetic source


def test_language_switch_keeps_results_and_translates_in_place(
        app, window, no_prefs_io):
    page = _dpd(app, window)
    outcome = page.outcome
    window.set_lang("en")
    app.processEvents()
    try:
        assert page.outcome is outcome
        assert window.windowTitle() == "padpd — WiFi 7 PA + DPD Workbench"
        assert window.rail_btns["overview"].text() == "Overview"
        assert page.run_btn.text() == "Run"
        assert any("worse side" in t.d["label"] for t in _tiles(page))
    finally:
        window.set_lang("zh")
        app.processEvents()
    assert window.rail_btns["overview"].text() == "总览"
    assert any("较差一侧" in t.d["label"] for t in _tiles(page))


def test_theme_switch_restyles_without_losing_results(
        app, window, no_prefs_io):
    from gui_qt.theme import TOKENS
    page = _dpd(app, window)
    outcome = page.outcome
    window.set_theme("dark")
    try:
        assert TOKENS["dark"]["bg"] in app.styleSheet()
        assert page.outcome is outcome and _tiles(page)
    finally:
        window.set_theme("light")
    assert TOKENS["light"]["bg"] in app.styleSheet()


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_every_page_fits_a_1280_px_window(app, window, no_prefs_io, lang):
    """The old modeling page needed 1730 px in Chinese and 1930 px in
    English, so on a laptop the window could not be made to fit. A page
    that needs more than the window gives it either grows the window or
    overflows a scroll area horizontally; both fail here. In English,
    no Chinese may be left on screen either."""
    from gui_qt.main import PAGES
    _dpd(app, window)                          # a page with results on it
    if window.page("pa_model").outcome is None:
        _run(app, window, "pa_model", type="MP", order=5, memory=3)
    window.set_lang(lang)
    try:
        window.resize(1280, 860)
        for pid, *_ in PAGES:
            window.navigate(pid)
            app.processEvents()
            assert window.width() == 1280, (lang, pid, window.width())
            for sa in window.findChildren(QtWidgets.QScrollArea):
                if not sa.isVisible() or sa.widget() is None:
                    continue
                need = sa.widget().minimumSizeHint().width()
                have = sa.viewport().width()
                assert need <= have + 1, (lang, pid,
                                          type(sa.widget()).__name__,
                                          need, have)
            if lang == "en":
                assert not _visible_chinese(window), (pid,
                                                      _visible_chinese(window))
    finally:
        window.set_lang("zh")


def _visible_chinese(window) -> list:
    """Chinese text on screen in the English UI: a string that reached a
    widget without going through tr(), or a key with no translation."""
    import re
    cjk = re.compile(r"[一-鿿]")
    W = QtWidgets
    out = []
    for cls in (W.QLabel, W.QAbstractButton):
        for w in window.findChildren(cls):
            # the language switch names Chinese in Chinese, on purpose
            if w.isVisible() and cjk.search(w.text()) and w.text() != "中文":
                out.append(w.text())
    for tb in window.findChildren(W.QTabBar):
        if tb.isVisible():
            out += [tb.tabText(i) for i in range(tb.count())
                    if cjk.search(tb.tabText(i))]
    for t in window.findChildren(W.QTableWidget):
        if t.isVisible():
            for c in range(t.columnCount()):
                h = t.horizontalHeaderItem(c)
                if h and cjk.search(h.text()):
                    out.append(h.text())
            for r in range(t.rowCount()):
                for c in range(t.columnCount()):
                    it = t.item(r, c)
                    if it and cjk.search(it.text()):
                        out.append(it.text())
    for cb in window.findChildren(W.QComboBox):
        if cb.isVisible():
            out += [cb.itemText(i) for i in range(cb.count())
                    if cjk.search(cb.itemText(i))]
    return out


def test_a_fitted_model_lands_in_the_workspace_and_the_pickers(app, window):
    from gui_qt import common
    page = _run(app, window, "pa_model", family="classical", type="GMP",
                order=5, memory=3)
    ws = common.state().workspace
    name = f"GMP @ {ws.active_source}"
    assert name in ws.models and ws.models[name].persisted
    assert ws.models[name].run_id == page.outcome.run_id
    assert window.chip_models.text().endswith(str(len(ws.models)))
    panel = page.footer_widgets[0]
    texts = [panel.list.item(i).text() for i in range(panel.list.count())]
    assert any(page.outcome.run_id in t for t in texts)
    deploy = window.page("deploy")
    assert name in deploy.form.fields["models"].value() or \
        deploy.form.fields["models"].widget.count() >= 1


def test_deploy_sweeps_a_workspace_model(app, window):
    from gui_qt import common
    ws = common.state().workspace
    if not ws.models:
        _run(app, window, "pa_model", type="MP", order=5, memory=3)
    window.workspace_changed()
    page = window.page("deploy")
    page.form.set_values({"models": tuple(ws.models)[-1:], "bits": (16, 8)})
    page = _run(app, window, "deploy")
    assert page.outcome.raw["bits"] == [16, 8]
    assert _tiles(page)[0].d["unit"] == "bit"


def test_compare_lines_up_runs_of_one_kind_and_shows_what_differs(
        app, window):
    _run(app, window, "pa_model", family="classical", type="MP", order=5,
         memory=2)
    _run(app, window, "pa_model", family="classical", type="MP", order=5,
         memory=4)
    window.pages["pa_model"].open_compare.emit("pa_model")
    app.processEvents()
    page = window.pages["compare"]
    assert window.stack.currentWidget() is page
    assert page.kind() == "pa_model"
    assert len(page.picked()) == 2
    assert {r.kind for r in page.picked()} == {"pa_model"}
    diff_keys = {row[next(iter(row))] for row in page.last["diff"]}
    assert "memory" in diff_keys
    assert "bars" in page.last["charts"]


def test_sources_page_adds_a_synthetic_source_and_makes_it_active(
        app, window):
    from gui_qt import common
    ws = common.state().workspace
    before = ws.active_source
    window.navigate("sources")
    page = window.pages["sources"]
    page.synth.set_values({"bw": 20, "symbols": 4, "drive": 0.12})
    page.add_synthetic()
    _settle(app, page)
    try:
        assert ws.active_source != before
        assert "20MHz" in ws.active_source
        assert ws.active_source in window.chip_source.toolTip()
        # a result computed on the old source is now flagged stale
        dpd = window.pages.get("dpd")
        if dpd is not None and dpd.outcome is not None:
            assert not dpd.stale.isHidden()
    finally:
        ws.set_active(before)
        window.workspace_changed()


def test_sources_page_loads_the_complete_source_example(app, window):
    from gui_core import services
    from gui_qt import common
    ws = common.state().workspace
    before = ws.active_source
    page = window.page("sources")
    window.navigate("sources")
    page.add_example()
    _settle(app, page)
    try:
        assert Path(services.EXAMPLE_COMPLETE_NPZ).name in ws.active_source
        assert not page.btn_consume.isHidden()
    finally:
        ws.set_active(before)
        window.workspace_changed()


def test_gain_modulation_study_runs(app, window):
    page = _run(app, window, "gain_modulation", dut="static")
    assert _tiles(page)
    assert page.results.tabs is not None


def test_two_tone_runs_on_the_bundled_example(app, window):
    page = _run(app, window, "two_tone")
    assert _tiles(page)[0].d["unit"] == "dB"


def test_manual_page_renders_chapters(app, window):
    window.navigate("manual")
    page = window.pages["manual"]
    assert page.toc.count() == 8
    assert "padpd" in page.view.toHtml()
    page.toc.setCurrentRow(5)  # benchmarks chapter
    app.processEvents()
    assert "TCN" in page.view.toPlainText()


def test_grab_screenshot(app, window, tmp_path):
    window.resize(1280, 860)
    window.navigate("overview")
    app.processEvents()
    pix = window.grab()
    out = tmp_path / "overview.png"
    assert pix.save(str(out))
    assert out.stat().st_size > 10_000


def test_signal_emit_does_not_leak_true():
    """PySide6 6.12.0 drops a reference to True on every Signal.emit().

    From Python 3.12 True is immortal and nothing happens; on 3.11 - the
    CI and Windows build interpreter - True's refcount of about two
    thousand reaches zero and the process aborts with "bool_dealloc".
    Every repaint of a pyqtgraph view emits one signal, so that is a few
    minutes of moving the mouse over a chart. Measured on 2026-10-28:
    -1.0 per emit on 6.12.0, 0.0 on 6.11.3. pyproject keeps Python 3.11
    below 6.12; this fails if that pin is lost.
    """
    from PySide6.QtCore import QObject, Signal

    class Probe(QObject):
        fired = Signal()

    probe = Probe()
    before = sys.getrefcount(True)
    for _ in range(200):
        probe.fired.emit()
    lost = before - sys.getrefcount(True)
    if sys.version_info < (3, 12):
        assert lost < 50, f"True lost {lost} refs in 200 emits"


def test_fnworker_live_registry(window):
    """closeEvent consults this registry before letting the window go
    while a QThread is still running."""
    from gui_qt import common as C
    assert C.live_worker_count() == 0
    w = C.FnWorker(lambda on_progress=None: time.sleep(0.3) or 42)
    w.start()
    assert C.live_worker_count() == 1
    assert w.wait(5000)
    for _ in range(50):                      # finished signal is queued
        QtWidgets.QApplication.processEvents()
        if C.live_worker_count() == 0:
            break
        time.sleep(0.02)
    assert C.live_worker_count() == 0
