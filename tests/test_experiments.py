"""The experiment layer: schema, verdicts, provenance, persistence.

gui_core.experiments is what the desktop renders; these tests pin the
contract it promises independently of any widget:

- every string a front end will show has an English translation, since
  the schema's labels are plain strings rather than ``tr()`` calls the
  AST guard in test_mobile_pages.py can see;
- an input that does not apply is hidden and does not leak into a run;
- verdicts are judged against the spec, so a FAIL is a FAIL whatever
  colour a front end would have picked;
- a stored outcome re-presents in another language without recomputing;
- the workspace survives a restart with its lineage.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from gui_core import chart_spec, experiments, i18n  # noqa: E402
from gui_core.runstore import RunStore  # noqa: E402
from gui_core.workspace import Workspace  # noqa: E402

CJK = __import__("re").compile(r"[一-鿿]")


@pytest.fixture()
def ws(tmp_path):
    return Workspace(tmp_path / "ws")


@pytest.fixture()
def store(tmp_path):
    return RunStore(tmp_path / "runs")


def _strings():
    for e in experiments.EXPERIMENTS.values():
        yield e.title
        yield e.summary
        yield from e.chart_titles.values()
        yield from (label for _, label in e.actions)
        for p in e.params:
            yield p.label
            yield p.group
            yield p.help
    for p in experiments.SYNTHETIC_SOURCE:
        yield p.label
        yield p.group
        yield p.help
    yield from experiments.CHOICE_LABELS.values()
    yield from experiments.KIND_LABELS.values()


def test_every_schema_string_has_an_english_translation():
    missing = sorted({s for s in _strings()
                      if s and CJK.search(s) and s not in i18n._EN})
    assert not missing, f"add to gui_core/i18n.py: {missing}"


def test_hidden_inputs_do_not_reach_a_run(ws):
    """Neural settings are irrelevant to an LS fit; they must not end up
    in its record, where they would read as if they had been used."""
    ctx = experiments.Context(ws)
    exp = experiments.PA_MODEL
    v = experiments.effective_values(exp, {"family": "classical",
                                           "hidden": 99}, ctx)
    assert "hidden" not in v and "backbone" not in v
    assert v["type"] == "GMP"
    v = experiments.effective_values(exp, {"family": "neural"}, ctx)
    assert "type" not in v and v["hidden"] == 8


def test_the_surrogate_input_appears_only_where_it_is_needed(ws):
    ctx = experiments.Context(ws)
    def keys(vals):
        return {p.key for p in experiments.DPD.visible(vals, ctx)}
    assert "surrogate" not in keys({"algo": "ILA"})   # synthetic source
    assert "surrogate" in keys({"algo": "DLA"})


def test_dpd_verdicts_judge_against_the_spec(ws, store):
    """The default synthetic source at drive 0.14: DPD passes all three
    checks, and the same run without DPD fails all three. Measured on
    2026-10-28: EVM -19.0 -> -59.8 dB, ACLR -31.1 -> -59.5 dBc, mask
    margin -7.2 -> +18.7 dB."""
    ctx = experiments.Context(ws)
    out = experiments.execute(experiments.DPD, {}, ctx, runstore=store)
    shown = experiments.present(out, ctx, "zh")
    v = {d["label"][:4]: d for d in shown["verdicts"]}
    assert set(v) == {"EVM", "ACLR", "发射 M"}
    for d in shown["verdicts"]:
        assert d["ok"] is True and d["was_ok"] is False, d
    assert v["EVM"]["value"] < -55                     # measured -59.8
    assert v["发射 M"]["value"] > 10                    # measured +18.7
    # a tighter spec turns the same stored result into a FAIL, unrun
    ws.set_spec(evm_db=-65.0)
    tight = experiments.present(out, ctx, "zh")["verdicts"][0]
    assert tight["ok"] is False and tight["margin"] < 0
    # and the run is on record with where it came from
    run = store.get(out.run_id)
    assert run.config["source"] == ws.active_source
    assert run.metrics["mask_margin_db"] == pytest.approx(
        v["发射 M"]["value"])


def test_mask_margin_ignores_the_channel_itself():
    """check_mask reports 0.0 for every capture, because the PSD is
    normalised to its own in-band peak and the mask is 0 dB there."""
    fs = 640e6
    rng = np.random.default_rng(0)
    x = rng.standard_normal(65536) + 1j * rng.standard_normal(65536)
    # band-limit to +-80 MHz, the shape of a clean 160 MHz channel
    X = np.fft.fft(x)
    f = np.fft.fftfreq(len(x), 1 / fs)
    X[np.abs(f) > 78e6] *= 1e-4
    y = np.fft.ifft(X)
    mask = np.array([[0, 0], [79.04e6, 0], [80.96e6, -20], [120e6, -28],
                     [160e6, -40], [800e6, -40]])
    m = experiments.mask_margin_db(y, fs, mask)
    assert m > 15, m
    assert experiments.mask_margin_db(y, fs, None) is None


def test_an_outcome_re_presents_in_another_language_without_rerunning(
        ws, store):
    ctx = experiments.Context(ws)
    out = experiments.execute(experiments.THREE_LOOP, {"blocks": 4}, ctx,
                              runstore=store)
    zh = experiments.present(out, ctx, "zh")
    en = experiments.present(out, ctx, "en")
    assert [d["value"] for d in zh["verdicts"]] == \
        [d["value"] for d in en["verdicts"]]
    assert zh["verdicts"][0]["label"] != en["verdicts"][0]["label"]
    assert CJK.search(zh["callout"]) and not CJK.search(en["callout"])


def test_three_loop_chart_leaves_out_the_failed_raw_loop(ws, store):
    ctx = experiments.Context(ws)
    out = experiments.execute(experiments.THREE_LOOP, {"blocks": 4}, ctx,
                              runstore=store)
    name, args, kwargs = experiments.present(out, ctx, "en")["charts"][
        "three_loop"]
    spec, _ = chart_spec.build(name, *args, lang="en", **kwargs)
    labels = [s["label"] for s in spec["panels"][0]["series"]]
    assert not any("raw" in s.lower() for s in labels), labels
    # Android's default still draws it
    spec, _ = chart_spec.build(name, *args, lang="en")
    assert len(spec["panels"][0]["series"]) == len(labels) + 1


@pytest.mark.parametrize("exp_id", ["waveform", "pa_model", "dpd",
                                    "gain_modulation", "adaptive",
                                    "three_loop", "two_tone"])
def test_every_chart_an_experiment_names_builds(exp_id, ws, store):
    ctx = experiments.Context(ws)
    exp = experiments.EXPERIMENTS[exp_id]
    small = {"waveform": {"symbols": 2}, "adaptive": {"blocks": 4},
             "three_loop": {"blocks": 4}}.get(exp_id, {})
    out = experiments.execute(exp, small, ctx, runstore=store)
    for lang in ("zh", "en"):
        shown = experiments.present(out, ctx, lang)
        assert shown["charts"], exp_id
        for slot, (name, args, kwargs) in shown["charts"].items():
            spec, blobs = chart_spec.build(name, *args, lang=lang, **kwargs)
            assert spec["panels"], (exp_id, slot)
            assert slot in exp.chart_titles, (exp_id, slot)


def test_a_fitted_model_lands_in_the_workspace_and_survives_restart(
        ws, store, tmp_path):
    ctx = experiments.Context(ws)
    out = experiments.execute(experiments.PA_MODEL,
                              {"type": "MP", "order": 5, "memory": 3},
                              ctx, runstore=store)
    name = f"MP @ {ws.active_source}"
    assert name in ws.models and ws.models[name].persisted
    assert ws.models[name].run_id == out.run_id
    again = Workspace(tmp_path / "ws")
    assert name in again.models
    model = again.model(name)
    x = again.source()["x_val"][:1000]
    np.testing.assert_allclose(model(x), ws.model(name)(x))
    # and the deployment sweep can use it straight away
    dep = experiments.execute(experiments.DEPLOY,
                              {"models": [name], "bits": (16, 8)},
                              experiments.Context(again), runstore=store)
    shown = experiments.present(dep, experiments.Context(again), "en")
    assert shown["rows"][0]["W16"] and shown["verdicts"]


def test_workspace_keeps_sources_and_spec(tmp_path):
    ws = Workspace(tmp_path / "w")
    first = ws.active_source
    second = ws.add_synthetic({"bandwidth_hz": 80e6, "drive": 0.12})
    ws.set_spec(evm_db=-38, aclr_dbc=-42)
    again = Workspace(tmp_path / "w")
    assert set(again.sources) == {first, second}
    assert again.active_source == second
    assert again.spec == {"evm_db": -38.0, "aclr_dbc": -42.0}
    again.remove_source(second)
    assert Workspace(tmp_path / "w").active_source == first
