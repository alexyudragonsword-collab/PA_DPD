"""Streamlit AppTest smoke + e2e for the web workbench."""

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = ["home", "waveform", "data", "pa_modeling", "dpd_lab", "compare",
         "deploy", "codesign"]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page):
    at = AppTest.from_file(f"gui/pages/{page}.py", default_timeout=120)
    at.run()
    assert not at.exception, at.exception


def test_pa_modeling_classical_fit_e2e():
    at = AppTest.from_file("gui/pages/pa_modeling.py", default_timeout=300)
    at.run()
    # defaults: synthetic source, classical GMP; click the fit button
    at.sidebar.button[0].click().run()
    assert not at.exception
    # a metric card with NMSE appears and a run is registered
    assert any("NMSE" in str(m.label) for m in at.metric)
    from gui_core import RunStore
    runs = RunStore("gui_runs").list(kind="pa_model")
    assert runs, "fit should register a pa_model run"


def test_waveform_cfr_toggle():
    at = AppTest.from_file("gui/pages/waveform.py", default_timeout=120)
    at.run()
    at.sidebar.toggle[0].set_value(True).run()
    assert not at.exception
    labels = [str(m.label) for m in at.metric]
    assert any("CFR" in label for label in labels)


def test_compare_lists_runs():
    at = AppTest.from_file("gui/pages/compare.py", default_timeout=120)
    at.run()
    assert not at.exception


def test_home_renders_in_english_light(monkeypatch):
    from gui import ui
    monkeypatch.setattr(ui, "load_prefs",
                        lambda *a: {"lang": "en", "theme": "light"})
    at = AppTest.from_file("gui/pages/home.py", default_timeout=120)
    at.run()
    assert not at.exception
    assert any("Workbench" in str(t.value) for t in at.title)
