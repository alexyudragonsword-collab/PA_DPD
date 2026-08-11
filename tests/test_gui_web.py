"""Streamlit AppTest smoke + e2e for the web workbench."""

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def page_path(name: str) -> str:
    """Absolute path to a view.

    AppTest.from_file resolves a relative path against the file that
    CALLS it (i.e. tests/), not the working directory — a bare
    "gui/views/x.py" silently became "tests/gui/views/x.py".
    """
    return str(ROOT / "gui" / "views" / f"{name}.py")


@pytest.fixture(autouse=True)
def _isolated_registry(tmp_path, monkeypatch):
    """Redirect the app's run registry/prefs to a temp dir so tests never
    write into (or depend on) the real repo gui_runs/."""
    monkeypatch.setenv("PADPD_DATA_DIR", str(tmp_path))
    yield tmp_path

PAGES = ["home", "waveform", "data", "pa_modeling", "dpd_lab", "compare",
         "deploy", "codesign", "manual"]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page):
    at = AppTest.from_file(page_path(page), default_timeout=120)
    at.run()
    assert not at.exception, at.exception


def test_pa_modeling_classical_fit_e2e(_isolated_registry):
    at = AppTest.from_file(page_path("pa_modeling"), default_timeout=300)
    at.run()
    # defaults: synthetic source, classical GMP; click the fit button
    at.sidebar.button[0].click().run()
    assert not at.exception
    # a metric card with NMSE appears and a run is registered
    assert any("NMSE" in str(m.label) for m in at.metric)
    from gui_core import RunStore
    runs = RunStore(_isolated_registry / "gui_runs").list(kind="pa_model")
    assert runs, "fit should register a pa_model run"


def test_waveform_cfr_toggle():
    at = AppTest.from_file(page_path("waveform"), default_timeout=120)
    at.run()
    at.sidebar.toggle[0].set_value(True).run()
    assert not at.exception
    labels = [str(m.label) for m in at.metric]
    assert any("CFR" in label for label in labels)


def test_compare_lists_runs():
    at = AppTest.from_file(page_path("compare"), default_timeout=120)
    at.run()
    assert not at.exception


def test_home_renders_in_english_light(monkeypatch):
    from gui import ui
    monkeypatch.setattr(ui, "load_prefs",
                        lambda *a: {"lang": "en", "theme": "light"})
    at = AppTest.from_file(page_path("home"), default_timeout=120)
    at.run()
    assert not at.exception
    assert any("Workbench" in str(t.value) for t in at.title)
