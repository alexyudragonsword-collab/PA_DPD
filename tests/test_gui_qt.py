"""Offscreen smoke tests for the PySide6 desktop GUI."""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

QtWidgets = pytest.importorskip(
    "PySide6.QtWidgets", reason="PySide6 (or its EGL runtime) not available")


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
    common._STATE = type("S", (), {})()
    from gui_core import RunStore
    common._STATE.runstore = RunStore(tmp_path_factory.mktemp("runs"))
    common._STATE.sources = {}
    common._STATE.models = {}
    common.PREFS.update({"lang": "zh", "theme": "dark"})
    from gui_qt.main import MainWindow
    win = MainWindow()
    win.show()
    yield win
    # Tear the C++ side down deterministically (deleteLater skips
    # closeEvent's confirm dialog); the surviving Python wrapper is then
    # harmless to collect from any thread.
    win.deleteLater()
    app.processEvents()


@pytest.fixture()
def no_prefs_io(monkeypatch):
    from gui_qt import common
    monkeypatch.setattr(common, "save_prefs", lambda *a, **k: None)


def test_all_pages_instantiate_and_switch(app, window):
    from gui_qt.main import PAGES
    assert window.stack.count() == len(PAGES) == 9
    for i in range(len(PAGES)):
        window.nav.setCurrentRow(i)
        app.processEvents()
        assert window.stack.currentIndex() == i


def test_waveform_generate(app, window):
    page = window._pages["waveform"]
    page.bw.setCurrentText("20")
    page.sym.setValue(2)
    page.cfr_on.setChecked(True)
    page.generate()
    app.processEvents()
    assert "dB" in page.c_papr.val.text()
    assert "dB" in page.c_cfr.val.text()
    assert page.export.isEnabled()


def _wait_worker(app, page, timeout_ms=120000):
    """Classical fits now run through FnWorker; pump events until done."""
    import time
    w = getattr(page, "_worker", None)
    if w is not None:
        assert w.wait(timeout_ms)
    deadline = time.time() + 10
    while time.time() < deadline:
        app.processEvents()
        from gui_qt import common as C
        if C.live_worker_count() == 0:
            break
        time.sleep(0.02)
    app.processEvents()


def _seed_model_and_run(window):
    """Give the shared state one model + one run without depending on a
    sibling test having run first (node-level selection must work)."""
    from gui_core import Run, services
    from gui_qt.common import get_state
    state = get_state()
    if not state.models:
        src = services.make_synthetic_source(bandwidth_hz=20e6, qam=256,
                                             symbols=4, drive=0.14)
        res = services.fit_classical(src, "GMP",
                                     {"order": 5, "memory": 3})
        state.models["GMP @ seed"] = {
            "model": res["model"],
            "meta": {"config": {"family": "classical"},
                     "source": src["name"], "metrics": res["metrics"]}}
        state.runstore.add(Run(name="GMP @ seed", kind="pa_model",
                               config={"family": "classical"},
                               metrics=res["metrics"]))
    return state


def test_modeling_classical_fit_registers_model_and_run(app, window):
    page = window._pages["modeling"]
    page.family.setCurrentText("经典 (LS)")
    page.mtype.setCurrentText("GMP")
    n_before = len(get_state_models(window))
    page.fit()
    _wait_worker(app, page)
    from gui_qt.common import get_state
    state = get_state()
    assert len(state.models) == n_before + 1
    assert "dB" in page.c_nmse.val.text()
    runs = state.runstore.list()
    assert any(r.kind == "pa_model" for r in runs)


def get_state_models(window):
    from gui_qt.common import get_state
    return get_state().models


def test_compare_lists_runs(app, window):
    _seed_model_and_run(window)
    page = window._pages["compare"]
    page.refresh()
    assert page.table.rowCount() >= 1


def test_deploy_refresh_sees_model(app, window):
    _seed_model_and_run(window)
    page = window._pages["deploy"]
    page.refresh()
    assert page.model_list.count() >= 1
    assert page.lut_model.count() >= 1


def test_deploy_lut_sweep_needs_gain_curve(app, window):
    """A model without gain_curve (plain GMP) shows the info text and
    starts no worker."""
    _seed_model_and_run(window)
    page = window._pages["deploy"]
    page.refresh()
    page.lut_model.setCurrentText("GMP @ seed")
    page.lut_sweep()
    assert "LUT" in page.msg.text()
    assert page.lut_table.isHidden()


def test_deploy_lut_sweep_spline(app, window):
    from gui_core import services
    from gui_qt.common import get_state
    state = get_state()
    if "Spline-MP @ seed" not in state.models:
        src = services.make_synthetic_source(bandwidth_hz=20e6, qam=256,
                                             symbols=4, drive=0.14)
        res = services.fit_classical(src, "Spline-MP",
                                     {"order": 6, "memory": 2})
        state.models["Spline-MP @ seed"] = {
            "model": res["model"],
            "meta": {"config": {"family": "classical"},
                     "source": src["name"], "metrics": res["metrics"]}}
    page = window._pages["deploy"]
    page.refresh()
    page.lut_model.setCurrentText("Spline-MP @ seed")
    page.lut_sweep()
    _wait_worker(app, page)
    assert page.lut_table.rowCount() >= 2      # float + LUT depths
    assert "LUT MAC" in page.msg.text()


def test_dpd_adaptive_basis_dut_combos(app, window):
    from gui_core import services
    page = window._pages["dpd"]
    assert [page.ad_basis.itemText(i) for i in range(page.ad_basis.count())] \
        == list(services.ADAPTIVE_BASES)
    assert [page.ad_dut.itemText(i) for i in range(page.ad_dut.count())] \
        == list(services.ADAPTIVE_DUTS)
    assert page.basis.findText("Spline-MP") >= 0
    assert page.basis.findText("Spline-GMP (K8)") >= 0


def test_language_switch_rebuilds_in_english(app, window, no_prefs_io):
    window._on_lang(1)  # -> en
    app.processEvents()
    assert "Overview" in window.nav.item(0).text()
    assert window.windowTitle() == "padpd — WiFi 7 PA + DPD Workbench"
    window._on_lang(0)  # back to zh
    app.processEvents()
    assert "总览" in window.nav.item(0).text()


def test_theme_switch_updates_mpl_and_qss(app, window, no_prefs_io):
    import matplotlib
    window._on_theme(1)  # -> light
    assert matplotlib.rcParams["figure.facecolor"] == "#ffffff"
    assert "#f4f6fb" in app.styleSheet()
    window._on_theme(0)  # back to dark
    assert matplotlib.rcParams["figure.facecolor"] == "#121828"


def test_manual_page_renders_chapters(app, window):
    page = window._pages["manual"]
    assert page.toc.count() == 8
    html = page.view.toHtml()
    assert "padpd" in html
    page.toc.setCurrentRow(5)  # benchmarks chapter
    app.processEvents()
    assert "TCN" in page.view.toPlainText()


def test_grab_screenshots(app, window, tmp_path):
    window.resize(1280, 860)
    window.nav.setCurrentRow(0)
    app.processEvents()
    pix = window.grab()
    out = tmp_path / "home.png"
    assert pix.save(str(out))
    assert out.stat().st_size > 10_000


def test_fnworker_live_registry(window):
    """Language/theme switches consult this registry to avoid destroying
    pages that own running QThreads."""
    import time
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
