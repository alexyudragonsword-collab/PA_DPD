"""The mobile screen layer, and the guards that keep it honest.

``padpd_mobile/pages.py`` is the Android counterpart of
``gui_qt/pages/``: it assembles a screen's metrics and chart specs so the
bridge is crossed once per view. These tests run on the desktop - no
emulator - because everything they check is Python.

The i18n guard is the important one. AGENTS.md requires every new Chinese
UI string to have an English translation, and ``tests/test_gui_i18n.py``
enforces that for the Qt sources by walking their AST for ``tr()`` calls.
Kotlin sources carry Chinese strings the same way, so they need the same
guard or the rule silently stops applying to a third of the UI.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MOBILE = ROOT / "android" / "app" / "src" / "main" / "python"
KOTLIN = ROOT / "android" / "app" / "src" / "main" / "java" / "com" / "padpd"

if str(MOBILE) not in sys.path:
    sys.path.insert(0, str(MOBILE))

CJK = re.compile(r"[一-鿿]")


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    from padpd_mobile import api as _api
    _api.boot(str(tmp_path_factory.mktemp("padpd-data")))
    yield _api
    _api.reset()


# ---- the waveform screen ------------------------------------------------
def _waveform(api, **kw):
    args = {"args": [80, 1024, 4, 0], "kwargs": kw}
    reply = json.loads(api.page("waveform", json.dumps(args)))
    assert reply["ok"], reply.get("traceback", reply.get("error"))
    return reply


def test_waveform_screen_returns_every_chart_slot(api):
    from padpd_mobile import pages
    reply = _waveform(api)
    assert set(reply["charts"]) == set(pages.chart_names("waveform"))


def test_waveform_charts_carry_drawable_series(api):
    """A spec with no series draws an empty box and looks like a styling
    problem rather than a broken screen, so require real series here."""
    reply = _waveform(api)
    for slot, spec in reply["charts"].items():
        series = [s for p in spec["panels"] for s in p["series"]]
        assert series, f"{slot} has no series"
        for s in series:
            assert api.blob(s["x"]), f"{slot}/{s.get('label')} has an empty x"


def test_waveform_metrics_are_formatted_not_raw(api):
    """Values cross as strings deliberately: the desktop's precision is
    the specification, and a float would let Kotlin invent its own."""
    reply = _waveform(api)
    labels = [m["label"] for m in reply["metrics"]]
    assert "PAPR" in labels
    for m in reply["metrics"]:
        assert isinstance(m["value"], str) and m["value"]
    papr = next(m for m in reply["metrics"] if m["label"] == "PAPR")
    assert re.fullmatch(r"\d+\.\d{2} dB", papr["value"]), papr


def test_cfr_metric_is_a_dash_when_clipping_is_off(api):
    """Desktop shows the card with an em dash rather than removing it, so
    the screen does not reflow when the checkbox moves."""
    off = _waveform(api)
    cfr = [m for m in off["metrics"] if "CFR" in m["label"]][0]
    assert cfr["value"] == "—"

    on = _waveform(api, cfr_papr_db=8.0)
    cfr_on = [m for m in on["metrics"] if "CFR" in m["label"]][0]
    assert "dB /" in cfr_on["value"], cfr_on


def test_cfr_adds_a_second_curve(api):
    """The CFR comparison is the point of the option: with it on, every
    line chart should plot the original against the clipped waveform."""
    off_series = _waveform(api)["charts"]["psd"]["panels"][0]["series"]
    on_series = _waveform(api, cfr_papr_db=8.0)["charts"]["psd"]["panels"][0][
        "series"]
    assert len(on_series) == len(off_series) + 1


def test_screen_handle_can_be_passed_back(api):
    """The handle exists so the next action - exporting the waveform -
    does not have to rebuild it."""
    reply = _waveform(api)
    assert reply["handle"] in api._SESSION


def test_unknown_screen_is_an_error_not_a_crash(api):
    reply = json.loads(api.page("no-such-screen"))
    assert reply["ok"] is False and "no-such-screen" in reply["error"]


def test_bad_parameters_return_the_traceback(api):
    """Chaquopy turns a Python exception into a Java one that says almost
    nothing; errors come back as data so the screen can show the cause."""
    bad = json.dumps({"args": [80, 1024, 4, 0], "kwargs": {"nope": 1}})
    reply = json.loads(api.page("waveform", bad))
    assert reply["ok"] is False
    assert "traceback" in reply


# ---- i18n ---------------------------------------------------------------
def test_i18n_map_translates_and_is_empty_for_chinese(api):
    from gui_core import i18n
    en = json.loads(api.i18n_map("en"))
    assert en["波形工作台"] == i18n.tr("波形工作台", "en")
    assert len(en) == len(i18n._EN)
    assert json.loads(api.i18n_map("zh")) == {}


def _kotlin_literals() -> dict:
    """Chinese string literals in the Kotlin sources, by file.

    A regex rather than a parser because there is no Kotlin AST here.
    That is sound for this purpose: it over-collects if anything (a
    Chinese comment would be caught), and over-collecting only ever asks
    for a translation that already exists.
    """
    found = {}
    for f in sorted(KOTLIN.rglob("*.kt")):
        for lit in re.findall(r'"([^"\\\n]*)"', f.read_text(encoding="utf-8")):
            if CJK.search(lit):
                found.setdefault(f.name, set()).add(lit)
    return found


def test_every_chinese_string_in_kotlin_has_a_translation():
    """The Kotlin half of AGENTS.md's i18n rule.

    Kotlin looks each string up in the map i18n_map() sends, so a string
    that is not a key there stays Chinese in English mode - a silent
    half-translated screen, not an error.
    """
    from gui_core import i18n
    missing = {lit for lits in _kotlin_literals().values() for lit in lits
               if lit not in i18n._EN}
    assert not missing, (
        f"{len(missing)} Chinese strings in Kotlin have no i18n.py entry: "
        f"{sorted(missing)[:8]}")
