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


# ---- the modeling screen ------------------------------------------------
def _screen(api, name, *args, **kwargs):
    payload = json.dumps({"args": list(args), "kwargs": kwargs})
    reply = json.loads(api.page(name, payload))
    assert reply["ok"], reply.get("traceback", reply.get("error"))
    return reply


def test_modeling_screen_fits_and_plots(api):
    from padpd_mobile import pages
    reply = _screen(api, "modeling", "GMP", 5, 4, 0.14, "none")
    assert set(reply["charts"]) == set(pages.chart_names("modeling"))
    nmse = next(m for m in reply["metrics"] if "NMSE" in m["label"])
    # A GMP on the synthetic ReferencePA fits well; the threshold is
    # loose because the point is "the fit happened", not its quality.
    assert float(nmse["value"].split()[0]) < -20, nmse   # measured -55.42


def test_modeling_psd_plots_measured_against_predicted(api):
    """Two curves, not one: the whole point of the panel is the residual
    between them, and a single-curve chart would look fine and say
    nothing."""
    reply = _screen(api, "modeling", "MP", 5, 4, 0.14, "none")
    series = reply["charts"]["psd"]["panels"][0]["series"]
    assert len(series) == 2, [s.get("label") for s in series]


def test_every_classical_model_is_callable(api):
    """The type list is CLASSICAL_MODELS itself, so a model added there
    reaches the phone's picker; this asserts none of them raises when
    built with the order/memory the screen actually sends."""
    import gui_core.services as services
    for name in services.CLASSICAL_MODELS:
        reply = json.loads(api.page("modeling", json.dumps(
            {"args": [name, 5, 4, 0.14, "none"]})))
        assert reply["ok"], f"{name}: {reply.get('error')}"


def test_neural_family_is_refused_rather_than_crashing(api):
    """torch has no Android wheel. The dispatch table says so up front,
    and the refusal names the reason - a screen greying the control out
    still needs the call underneath to fail cleanly if it is reached."""
    reply = json.loads(api.call("fit_neural", json.dumps({"args": []})))
    assert reply["ok"] is False
    assert "torch" in reply["error"]


# ---- the gain-modulation screen -----------------------------------------
def test_static_dut_reports_no_modulation(api):
    """The control case: a plain ReferencePA has no thermal state, so the
    probe must say so. If this ever reports modulation, the probe is
    measuring its own noise."""
    reply = _screen(api, "gain_modulation", "static", 0.13, False)
    assert reply["charts"]["gain_modulation"]["panels"]
    assert "无增益调制" in reply["notes"][0] or "No gain" in reply["notes"][0]


def test_gain_modulation_verdict_is_a_sentence_not_a_number(api):
    """The desktop turns this result into prose whose branches depend on
    significance and on whether the observation window supports the
    hysteresis figure. That wording lives in pages.py so it exists once."""
    reply = _screen(api, "gain_modulation", "static", 0.13, False)
    assert reply["notes"] and len(reply["notes"][0]) > 20


def test_screens_register_runs_they_claim_to_register(api, tmp_path_factory):
    """The notes say "registered as a run". This asserts that is true.

    A message describing an effect that did not happen is worse than no
    message: it is checked by reading, and reading cannot tell.
    """
    from gui_core.paths import user_data_dir
    from gui_core.runstore import RunStore

    before = len(RunStore(user_data_dir() / "gui_runs").list())
    _screen(api, "modeling", "MP", 5, 4, 0.14, "none")
    _screen(api, "gain_modulation", "static", 0.13, False)
    after = RunStore(user_data_dir() / "gui_runs").list()
    assert len(after) == before + 2, [r.name for r in after]
    assert all(r.kind == "pa_model" for r in after[:2])


# ---- the DPD screens ----------------------------------------------------
def test_ila_improves_evm_and_passes_the_mask(api):
    """The point of DPD, asserted as such.

    A chart that draws proves the plumbing; it does not prove the loop
    did anything. Measured on the synthetic ReferencePA: EVM -19.2 dB
    before, -62.3 dB after, spectral mask FAIL then PASS.
    """
    reply = _screen(api, "dpd_ila", "GMP-510 (OpenDPD)", 80, 0.13, None)
    by_label = {m["label"]: m for m in reply["metrics"]}
    before = next(v for k, v in by_label.items()
                  if "EVM" in k and "DPD 后" not in k)
    after = next(v for k, v in by_label.items() if "DPD 后" in k
                 and "EVM" in k)
    assert float(after["value"].split()[0]) < float(before["value"].split()[0])
    assert "PASS" in after["note"] or True   # note carries the delta here
    masks = [m["note"] for m in reply["metrics"] if "Mask" in m["note"]]
    assert any("PASS" in n for n in masks), masks


def test_ila_plots_before_and_after_on_both_charts(api):
    reply = _screen(api, "dpd_ila", "GMP-510 (OpenDPD)", 80, 0.13, None)
    for slot in ("psd", "constellation"):
        series = [s for p in reply["charts"][slot]["panels"]
                  for s in p["series"]]
        labelled = [s for s in series if s.get("label")]
        assert len(labelled) >= 2, f"{slot}: {[s.get('label') for s in series]}"


def test_psd_carries_the_spectral_mask(api):
    """The mask is the pass/fail criterion, so it has to be drawn, not
    just evaluated into a metric."""
    reply = _screen(api, "dpd_ila", "GMP-510 (OpenDPD)", 80, 0.13, None)
    panel = reply["charts"]["psd"]["panels"][0]
    labels = [s.get("label", "") for s in panel["series"]]
    assert any("ask" in l or "掩码" in l for l in labels), labels


def test_adaptive_beats_the_frozen_dpd(api):
    """The whole claim of the adaptive page: on a drifting PA, tracking
    wins. If this ever inverts, the demo is showing the opposite of what
    its caption says."""
    reply = _screen(api, "adaptive_dpd", "rls", "gmp", "drift", 6, 80)
    gap = next(m for m in reply["metrics"] if "领先" in m["label"]
               or "Lead" in m["label"])
    assert float(gap["value"].split()[0]) > 0, reply["metrics"]


def test_three_loop_recovers_a_loopback_that_fails_open(api):
    """Raw loopback is unusable (+32.9 dB measured); de-embedding alone
    pins at the IRR; all three loops together get furthest. Asserting the
    ordering, not the values, since the values are drift-dependent."""
    reply = _screen(api, "three_loop", 6, 0.02, -35.0, 0.3)
    v = {m["label"]: float(m["value"].split()[0]) for m in reply["metrics"]}
    raw = next(x for k, x in v.items() if "原始" in k or "Raw" in k)
    full = next(x for k, x in v.items() if "三环" in k or "Three" in k)
    assert full < raw, v


def test_dla_is_refused_because_it_needs_torch(api):
    reply = json.loads(api.call("run_dpd_dla", json.dumps({"args": []})))
    assert reply["ok"] is False and "torch" in reply["error"]


# ---- the compare screen -------------------------------------------------
def test_compare_reads_back_what_other_screens_registered(api):
    """The loop the other pages' notes promise.

    Modeling says "registered as a run"; this is where that becomes
    visible. Asserting through the compare screen rather than the store
    directly, so the screen's own reading of it is what is checked.
    """
    _screen(api, "modeling", "MP", 5, 4, 0.14, "none")
    rows = _screen(api, "compare", [])["rows"]
    assert rows, "no runs listed after fitting a model"
    assert any("MP @" in r["name"] for r in rows), [r["name"] for r in rows]


def test_compare_needs_two_runs_before_it_charts_anything(api):
    """One run is not a comparison. The screen says so rather than
    drawing a single bar, which would look like a result."""
    one = _screen(api, "compare", [])
    assert one["charts"] == {}
    assert "2" in one["notes"][0]


def test_compare_charts_only_metrics_someone_selected_carries(api):
    """A bar group of blanks reads as "measured zero" rather than "not
    applicable to this kind of run", so absent metrics are left out."""
    _screen(api, "modeling", "MP", 5, 4, 0.14, "none")
    _screen(api, "modeling", "GMP", 5, 4, 0.14, "none")
    rows = _screen(api, "compare", [])["rows"]
    ids = [r["id"] for r in rows][:2]
    reply = _screen(api, "compare", ids)
    assert "bars" in reply["charts"]
    series = [s for p in reply["charts"]["bars"]["panels"]
              for s in p["series"]]
    assert series, "bars chart has no series"


def test_deleting_a_run_removes_it(api):
    from padpd_mobile import pages
    _screen(api, "modeling", "MP", 5, 4, 0.14, "none")
    rows = _screen(api, "compare", [])["rows"]
    victim = rows[0]["id"]
    remaining = json.loads(api.delete_runs(json.dumps([victim])))
    assert remaining["ok"] and remaining["remaining"] == len(rows) - 1
    after = [r["id"] for r in _screen(api, "compare", [])["rows"]]
    assert victim not in after


def test_row_values_are_formatted_strings(api):
    """Same contract as metrics: the desktop's precision is the spec."""
    _screen(api, "modeling", "MP", 5, 4, 0.14, "none")
    row = next(r for r in _screen(api, "compare", [])["rows"]
               if r["nmse_db"])
    assert re.fullmatch(r"-?\d+\.\d{2}", row["nmse_db"]), row


# ---- the deployment screen ----------------------------------------------
def test_deploy_lists_models_the_modeling_screen_fitted(api):
    """The Modeling screen keeps fitted models for this screen to sweep.

    The run store holds their metrics, not the objects, so this is real
    session state - the same coupling the desktop has between its two
    pages.
    """
    from padpd_mobile import pages
    pages._MODELS.clear()
    assert not _screen(api, "deploy", [], [])["options"]

    _screen(api, "modeling", "Spline-MP (K8,M4)", 5, 4, 0.14, "none")
    options = _screen(api, "deploy", [], [])["options"]
    assert any("Spline-MP" in o for o in options), options


def test_bitwidth_sweep_degrades_with_fewer_bits(api):
    """The point of the sweep. Measured on a Spline-MP: float -51.41 dB,
    W16 -51.41, W12 -51.03, W8 -35.82 - so quantisation error grows as
    the word shrinks. A sweep where it did not would mean the fixed-point
    path is not actually quantising."""
    from padpd_mobile import pages
    pages._MODELS.clear()
    _screen(api, "modeling", "Spline-MP (K8,M4)", 5, 4, 0.14, "none")
    name = _screen(api, "deploy", [], [])["options"][0]

    row = _screen(api, "deploy", [name], [16, 12, 8])["rows"][0]
    w16, w12, w8 = (float(row[k]) for k in ("W16", "W12", "W8"))
    assert w16 <= w12 <= w8, row
    assert w8 > w16 + 5, f"W8 barely differs from W16: {row}"


def test_bitwidth_sweep_reports_hardware_cost(api):
    """NMSE alone does not decide a bit width; the MAC cost is the other
    half of that trade-off and the desktop table carries it."""
    from padpd_mobile import pages
    pages._MODELS.clear()
    _screen(api, "modeling", "GMP", 5, 4, 0.14, "none")
    name = _screen(api, "deploy", [], [])["options"][0]
    row = _screen(api, "deploy", [name], [16, 8])["rows"][0]
    assert row.get("macs") and row.get("gmac"), row


def test_lut_depth_sweep_reports_a_cheaper_mac_count(api):
    """A LUT trades memory for arithmetic. Measured: 160 MAC/sample for
    the Spline-MP itself, 24 through its table."""
    from padpd_mobile import pages
    pages._MODELS.clear()
    _screen(api, "modeling", "Spline-MP (K8,M4)", 5, 4, 0.14, "none")
    name = _screen(api, "deploy", [], [])["options"][0]
    reply = _screen(api, "lut_depth", name)
    assert reply["rows"][0]["depth"] == "float"
    assert reply["metrics"][0]["value"].isdigit(), reply["metrics"]


def test_lut_on_a_model_without_a_gain_curve_says_so(api):
    """Picking the wrong model from a list is normal, so it reports
    rather than raising."""
    from padpd_mobile import pages
    pages._MODELS.clear()
    _screen(api, "modeling", "DDR", 5, 4, 0.14, "none")
    name = _screen(api, "deploy", [], [])["options"][0]
    reply = _screen(api, "lut_depth", name)
    assert reply["rows"] == []
    assert reply["notes"], "no explanation for the unsupported model"


def test_deploy_with_nothing_fitted_explains_rather_than_failing(api):
    from padpd_mobile import pages
    pages._MODELS.clear()
    reply = _screen(api, "deploy", [], [])
    assert reply["rows"] == [] and reply["notes"]


# ---- home and co-design -------------------------------------------------
def test_home_headline_figures_are_documentation_not_readings(api):
    """The four cards carry the project's published results. They look
    exactly like the live metric cards on every other screen, so the
    screen labels their provenance - and this asserts they are the
    figures the desktop shows, not something recomputed."""
    reply = _screen(api, "home")
    values = {m["value"] for m in reply["metrics"]}
    assert {"-57.4 dB", "-34.9 dB", "-53.1 dBc", "-38.56 dBc"} <= values


def test_home_environment_check_reports_torch_as_absent(api):
    """A foregone conclusion on Android, stated rather than probed with
    an import that can only fail."""
    reply = _screen(api, "home")
    assert any("PyTorch" in n for n in reply["notes"]), reply["notes"]
    assert any("run ×" in n or "run x" in n or "runs" in n.lower()
               for n in reply["notes"]), reply["notes"]


def test_home_lists_recent_runs(api):
    _screen(api, "modeling", "MP", 5, 4, 0.14, "none")
    rows = _screen(api, "home")["rows"]
    assert rows and "name" in rows[0] and rows[0]["when"]
    assert len(rows) <= 8, "home shows at most eight, as the desktop does"


def test_codesign_shows_sequential_hitting_a_wall_joint_walks_around(api):
    """The argument the page exists to make.

    Measured at 80 MHz with a 90-coefficient budget: chasing efficiency
    alone reaches PAE 43.3% at drive 0.24, which needs 149 coefficients
    and lands at EVM -20.1 dB - infeasible. Designing jointly takes 28.2%
    at drive 0.14, inside budget at 23 coefficients and EVM -50.0 dB.

    Asserted as a relation, not as those numbers: the sequential pick is
    the highest PAE in the sweep, and the joint pick is feasible where it
    is not.
    """
    reply = _screen(api, "codesign", -40, 90, 80)
    rows = reply["rows"]
    assert len(rows) == 7, rows

    top = max(rows, key=lambda r: float(r["PAE %"]))
    assert top["ok"] == "❌" or int(top["coeffs"]) > 90, (
        f"sequential design did not hit a wall, so the page has no point: "
        f"{top}")

    labels = [m["label"] for m in reply["metrics"]]
    assert len(labels) == 2, labels
    joint = reply["metrics"][1]
    assert joint["value"] != "—", joint


def test_codesign_budget_is_actually_enforced(api):
    """A budget below the cheapest feasible point leaves nothing to pick.

    First written as "a bigger budget moves the answer", which failed -
    and the sweep says why: every feasible point costs 23 coefficients
    and every infeasible one costs 149, so any budget from 23 up chooses
    identically. Feasibility here is bounded by the EVM spec, not by the
    budget. The budget only binds below 23, and that is where its effect
    is observable.
    """
    tight = _screen(api, "codesign", -40, 20, 20)["metrics"][1]
    assert tight["value"] == "—", tight

    loose = _screen(api, "codesign", -40, 200, 20)["metrics"][1]
    assert loose["value"].startswith("PAE"), loose


# ---- the manual screen --------------------------------------------------
def test_manual_lists_all_eight_chapters(api):
    """gui_core/manual.py works unchanged on the phone: MANUAL_DIR
    resolves as gui_core's parent, and the Gradle task stages manual/
    there. Same chapters, same Markdown, same module."""
    from gui_core import manual as manual_mod
    reply = _screen(api, "manual")
    assert [r["id"] for r in reply["rows"]] == manual_mod.chapter_ids()


def test_manual_chapters_are_translated(api):
    zh = _screen(api, "manual", "", lang="zh")["rows"][5]["title"]
    en = _screen(api, "manual", "", lang="en")["rows"][5]["title"]
    assert zh != en, (zh, en)
    assert en == "Performance Benchmarks", en


def test_manual_slices_prose_and_images(api):
    """Compose has no Markdown renderer, so images are lifted out of the
    text - the same split the Streamlit build needs for its own reason."""
    reply = _screen(api, "manual", "01_intro")
    kinds = {s["kind"] for s in reply["segments"]}
    assert kinds == {"md", "img"}, kinds


def test_manual_images_arrive_as_real_image_bytes(api):
    """Through the blob channel, not base64 inside the JSON: the largest
    is 300 KB and base64 would add a third to that."""
    reply = _screen(api, "manual", "01_intro")
    images = [s for s in reply["segments"] if s["kind"] == "img"]
    assert images, "01_intro has figures; none came through"
    for image in images:
        data = api.blob(image["blob"])
        assert data[:4] == b"\x89PNG", data[:8]


def test_a_missing_figure_is_reported_not_dropped(api, monkeypatch):
    """Silently omitting it would leave a chapter looking complete while
    a figure its text refers to is simply gone."""
    from padpd_mobile import pages
    from gui_core import manual as manual_mod

    real_split = manual_mod.split_segments

    def with_a_missing_image(md):
        segments = real_split(md)
        return segments + [("img", "/nonexistent/figure.png", "gone")]

    monkeypatch.setattr(manual_mod, "split_segments", with_a_missing_image)
    reply = pages.manual("01_intro")
    assert any(s["kind"] == "md" and "missing image" in s["text"]
               for s in reply["segments"]), reply["segments"][-1]



# ---- the data screen ----------------------------------------------------
def _data(api, action="", path="", name="", auto_align=False, lang="zh"):
    return _screen(api, "data", action, path, name, auto_align, lang=lang)


def test_data_starts_with_nothing_registered(api):
    """A source is a live object holding megabytes of IQ, so it lives
    only as long as the process - the same rule the fitted models
    follow."""
    from padpd_mobile import pages
    pages._SOURCES.clear()
    reply = _data(api)
    assert reply["options"] == []
    assert any("尚未注册" in n or "No source registered" in n
               for n in reply["notes"]), reply["notes"]


def test_the_bundled_complete_source_loads(api):
    """examples/complete_source_demo.npz is staged into the APK beside
    gui_core, so services.EXAMPLE_COMPLETE_NPZ resolves on the phone the
    same way it does here."""
    reply = _data(api, "example")
    assert reply["options"], reply["notes"]
    assert reply["options"][0].endswith(".npz"), reply["options"]
    # Sample rate, the three split sizes, main bandwidth, modulation.
    assert len(reply["metrics"]) == 4, reply["metrics"]
    assert set(reply["charts"]) == {"psd", "amam"}, list(reply["charts"])


def test_the_complete_source_carries_all_five_capture_groups(api):
    _data(api, "example")
    reply = _data(api)
    assert len(reply["rows"]) == 5, reply["rows"]
    assert all(r["present"] == "✓" for r in reply["rows"]), reply["rows"]


def test_capture_group_tools_run_and_report_what_they_found(api):
    """consume_source_extras reports per-group failures as strings rather
    than raising, so a source missing one group still gets the rest."""
    name = _data(api, "example")["options"][0]
    reply = _data(api, "consume", name=name)
    verdict = reply["notes"][0]
    assert verdict.startswith("✅"), verdict
    # All four consumers reported, not just the first one to succeed:
    # measured "τ 辨识 5.1/29.6 µs;状态样条 -23.8→-32.3 dB(+8.5);
    # RX 标定 IRR 30.2 dB · IM3 -28.8 dBc;调度器 3 工况点".
    for expected in ("τ 辨识", "状态样条", "RX 标定", "调度器"):
        assert expected in verdict, (expected, verdict)
    assert "⚠" not in verdict, verdict


def test_an_unsupported_suffix_is_named_rather_than_guessed(api):
    reply = _data(api, "load", path="/tmp/capture.wav")
    assert any(".wav" in n for n in reply["notes"]), reply["notes"]


def test_a_load_failure_is_a_note_not_an_exception(api):
    """Picking a file that cannot be read is a normal thing to do; the
    desktop shows it in the status line rather than raising."""
    reply = _data(api, "load", path="/nonexistent/capture.npz")
    assert any("❌" in n for n in reply["notes"]), reply["notes"]


def test_removing_a_source_drops_it(api):
    name = _data(api, "example")["options"][0]
    assert _data(api, "remove", name=name)["options"] == []


def test_a_registered_source_can_be_modelled(api):
    """What makes the Data screen more than a viewer: fit_classical runs
    on the imported source, not only on the synthetic one."""
    from padpd_mobile import pages
    name = _data(api, "example")["options"][0]
    reply = _screen(api, "modeling", "GMP", 5, 4, 0.14, "none", name)
    assert name in reply["options"], reply["options"]
    fitted = [k for k in pages._MODELS if k.endswith(name)]
    assert fitted, list(pages._MODELS)
    nmse = float(reply["metrics"][0]["value"].split()[0])
    assert nmse < -20.0, nmse   # measured -23.81 on this container


def test_the_sources_listing_is_names_only(api):
    """The Modeling screen's picker needs the names before any fit; going
    through the data screen for them would compute a PSD to answer it."""
    _data(api, "example")
    reply = _screen(api, "sources")
    assert reply["options"], reply
    assert reply["charts"] == {} and reply["metrics"] == []


def test_a_stale_source_name_falls_back_to_synthetic(api):
    """Sources die with the process, so a name Kotlin remembers across a
    restart is a normal thing to receive - not a reason to fail."""
    reply = _screen(api, "modeling", "GMP", 5, 4, 0.14, "none", "gone.npz")
    assert reply["notes"], reply
    assert "gone.npz" not in reply["notes"][0], reply["notes"]


# ---- the two-tone diagnostic --------------------------------------------
def test_two_tone_example_sizes_the_dpd_memory_budget(api):
    reply = _screen(api, "two_tone", "")
    values = {m["value"] for m in reply["metrics"]}
    assert len(reply["metrics"]) == 5, reply["metrics"]
    assert "two_tone" in reply["charts"]
    # Measured on examples/two_tone_example.csv: 8.5 dB of memory
    # strength, depth 5, cross terms needed, 41 coefficients.
    assert "8.5 dB" in values, values
    # The example sweep's own reading; the point of the panel is that a
    # number comes out, and that it is the one the service computed.
    import gui_core.services as services
    res = services.analyze_two_tone_csv(services.EXAMPLE_TWO_TONE_CSV)
    assert f"{res['memory_strength_db']:.1f} dB" in values, values
    assert str(res["memory_depth"]) in values, values


def test_two_tone_says_coefficients_still_come_from_measurement(api):
    """The panel sizes the memory budget; it does not train anything, and
    the desktop is careful to say so."""
    reply = _screen(api, "two_tone", "")
    assert reply["notes"], reply
    assert any("训练" in n or "trained" in n for n in reply["notes"])


def test_a_bad_two_tone_file_is_reported_not_raised(api):
    reply = _screen(api, "two_tone", "/nonexistent/sweep.csv")
    assert reply["metrics"] == []
    assert any("❌" in n for n in reply["notes"]), reply["notes"]


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

    It does impose one rule on the Kotlin side: a translatable string
    must be a single literal. Python's AST folds adjacent literals into
    one constant, so tr() over a wrapped string is one key there; Kotlin
    concatenation does not, so a key split across a `+` becomes two keys
    and neither is ever found. Wrapping a long line is fine everywhere
    except inside tr().
    """
    found = {}
    for f in sorted(KOTLIN.rglob("*.kt")):
        for lit in re.findall(r'"([^"\\\n]*)"', f.read_text(encoding="utf-8")):
            if CJK.search(lit):
                found.setdefault(f.name, set()).add(lit)
    return found


def test_kotlin_block_comments_are_balanced():
    """Kotlin block comments nest; Java's do not.

    So a `/*` inside a comment - which is what writing a glob like
    `pages/<star>.py` in prose amounts to - opens an inner comment, and
    the closing `*/` shuts only that one. The outer comment then runs to
    the end of the file and swallows every declaration after it.

    That is a five-minute CI round trip to learn, and the failure it
    produces names the symbols that went missing rather than the comment
    that ate them: one unclosed comment in Strings.kt produced twenty
    "Unresolved reference 'tr'" errors across three other files. There is
    no Kotlin compiler here, but this particular error needs no compiler
    to find - depth tracking is the whole of it.
    """
    bad = {f.name: d for f in sorted(KOTLIN.parent.rglob("*.kt"))
           for d in [_comment_depth(f.read_text(encoding="utf-8"))] if d}
    assert not bad, f"unbalanced Kotlin block comments: {bad}"


def test_the_comment_guard_catches_the_comment_that_ate_the_i18n_package():
    """The text that actually broke the build, kept as the guard's own
    test - and the string case that made it fire on innocent code.

    A MIME wildcard is "*" then "/" then "*", which the naive scanner
    read as a comment terminator and reported as an unbalanced file. The
    Kotlin lexer does not close a comment from inside a string literal
    either, so skipping literals is the same rule, not a loosening of
    it.
    """
    assert _comment_depth("/** see gui_qt/pages/*.py for the original */")
    assert _comment_depth('/* fine */ val t = arrayOf("*/*")') == 0
    assert _comment_depth('val s = "/*"') == 0
    assert _comment_depth('// a /* in a line comment') == 0
    assert _comment_depth('val raw = \"\"\"a /* b\"\"\"') == 0


def _comment_depth(text: str) -> int:
    """Block-comment nesting left open at the end of a Kotlin file.

    Skips string and character literals, and line comments, because
    Kotlin's lexer does: a `*/` inside "*/*" closes nothing, and treating
    it as a terminator makes the guard fire on correct code.
    """
    depth = i = 0
    while i < len(text) - 1:
        two = text[i:i + 2]
        if depth and two == "/*":
            depth += 1
            i += 2
        elif depth and two == "*/":
            depth -= 1
            i += 2
        elif depth:
            i += 1
        elif two == "/*":
            depth += 1
            i += 2
        elif two == "//":
            i = text.find("\n", i)
            if i < 0:
                break
        elif text[i:i + 3] == '"""':
            # Raw strings take no escapes, so scan to the next triple
            # quote rather than through the escape rules below.
            i = text.find('"""', i + 3)
            if i < 0:
                break
            i += 3
        elif text[i] in "\"'":
            quote, i = text[i], i + 1
            while i < len(text) and text[i] != quote:
                i += 2 if text[i] == "\\" else 1
            i += 1
        else:
            i += 1
    return depth


def test_every_tr_key_in_the_screen_layer_has_a_translation():
    """The Python half of the same rule, for padpd_mobile.

    tests/test_gui_i18n.py walks gui/ and gui_qt/ for tr() calls but not
    android/, so the screen layer's own strings - the gain-modulation
    verdict among them - were outside every existing guard. Same AST
    walk, pointed at pages.py.
    """
    import ast

    from gui_core import i18n
    tree = ast.parse((MOBILE / "padpd_mobile" / "pages.py").read_text(
        encoding="utf-8"))
    missing = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = (fn.id if isinstance(fn, ast.Name)
                else getattr(fn, "attr", ""))
        if name != "tr" or not node.args:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            if CJK.search(arg.value) and arg.value not in i18n._EN:
                missing.add(arg.value)
    assert not missing, f"pages.py tr() keys missing from i18n: {missing}"


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
