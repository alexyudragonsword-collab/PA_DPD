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


@pytest.fixture(scope="module")
def window(app, tmp_path_factory):
    from gui_qt import common
    common._STATE = type("S", (), {})()
    from gui_core import RunStore
    common._STATE.runstore = RunStore(tmp_path_factory.mktemp("runs"))
    common._STATE.sources = {}
    common._STATE.models = {}
    from gui_qt.main import MainWindow
    win = MainWindow()
    win.show()
    yield win


def test_all_pages_instantiate_and_switch(app, window):
    from gui_qt.main import PAGES
    assert window.stack.count() == len(PAGES) == 8
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


def test_modeling_classical_fit_registers_model_and_run(app, window):
    page = window._pages["modeling"]
    page.family.setCurrentText("经典 (LS)")
    page.mtype.setCurrentText("GMP")
    page.fit()
    app.processEvents()
    from gui_qt.common import get_state
    state = get_state()
    assert len(state.models) == 1
    assert "dB" in page.c_nmse.val.text()
    runs = state.runstore.list()
    assert any(r.kind == "pa_model" for r in runs)


def test_compare_lists_runs(app, window):
    page = window._pages["compare"]
    page.refresh()
    assert page.table.rowCount() >= 1


def test_deploy_refresh_sees_model(app, window):
    page = window._pages["deploy"]
    page.refresh()
    assert page.model_list.count() >= 1


def test_grab_screenshots(app, window, tmp_path):
    window.resize(1280, 860)
    window.nav.setCurrentRow(0)
    app.processEvents()
    pix = window.grab()
    out = tmp_path / "home.png"
    assert pix.save(str(out))
    assert out.stat().st_size > 10_000
