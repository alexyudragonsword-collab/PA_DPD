"""Desktop tests for the Android adapter layer.

The adapter is pure Python, so all of it is testable here - no emulator,
no SDK. That matters because the failure this suite mainly exists to
prevent is silent contract drift: ``padpd_mobile/api.py`` dispatches by
name into ``gui_core/services.py``, and a rename on the services side
would otherwise surface as a runtime error inside a phone, weeks later,
pointing nowhere near the commit that caused it.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "android" / "app" / "src" / "main" / "python"))

from padpd_mobile import api, chart_spec  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_registry():
    api.reset()
    yield
    api.reset()


def _call(fn, *args, **kwargs):
    out = json.loads(api.call(fn, json.dumps({"args": list(args),
                                              "kwargs": kwargs})))
    assert out["ok"], out.get("error")
    return out


def _gallery_entries():
    from padpd_mobile import gallery
    return gallery.ENTRIES


def _gallery_listing():
    from padpd_mobile import gallery
    return gallery.listing()


def _floats(key):
    raw = api.blob(key)
    return np.array(struct.unpack(f"<{len(raw) // 4}f", raw))


# ---------------------------------------------------------------- contract

def test_every_dispatch_name_exists_in_services():
    """The guard this file exists for."""
    import gui_core.services as services
    missing = [n for n in api.DISPATCH if not hasattr(services, n)]
    assert not missing, f"dispatch table names not in services.py: {missing}"


def test_torch_only_names_exist_but_are_not_dispatchable():
    import gui_core.services as services
    for name in api.TORCH_ONLY:
        assert hasattr(services, name), f"{name} vanished from services.py"
        assert name not in api.DISPATCH


def test_unknown_function_is_refused_as_data_not_an_exception():
    out = json.loads(api.call("os.system"))
    assert out["ok"] is False
    assert "not callable" in out["error"]


def test_torch_entry_point_refused_with_a_reason():
    out = json.loads(api.call("fit_neural"))
    assert out["ok"] is False
    assert "torch" in out["error"]


def test_service_exception_comes_back_as_data():
    # Nonsense argument: the point is that the app gets a message rather
    # than an exception crossing into Java.
    out = json.loads(api.call("load_source", json.dumps(
        {"args": ["npz", "/definitely/not/here.npz"]})))
    assert out["ok"] is False
    assert "traceback" in out


# ---------------------------------------------------------------- boot

def test_boot_reports_capabilities(tmp_path):
    caps = json.loads(api.boot(str(tmp_path)))
    assert caps["torch"] is False
    assert caps["onnx"] is False
    assert caps["rtl_cosim"] is False
    assert "fit_neural" in caps["unavailable"]
    assert set(caps["charts"]) == set(chart_spec.BUILDERS)


def test_boot_points_the_run_registry_at_the_given_dir(tmp_path):
    api.boot(str(tmp_path))
    import os
    assert os.environ["PADPD_DATA_DIR"] == str(tmp_path)
    # paths.py honours the override with no change of its own - the
    # property the Android port leans on.
    from gui_core.paths import user_data_dir
    assert str(user_data_dir()) == str(tmp_path)


# ---------------------------------------------------------------- transport

def test_blob_round_trips_as_float32():
    src = _call("cached_synthetic_source")
    preview = _call("source_preview", src["handle"])["result"]
    freq = _floats(preview["freq"]["__blob__"])
    assert freq.size == preview["freq"]["n"] == 4096
    assert np.all(np.diff(freq) > 0)          # monotonic frequency axis


def test_blob_values_match_the_service_output():
    src = _call("cached_synthetic_source")
    got = _floats(_call("source_preview", src["handle"])
                  ["result"]["psd_in"]["__blob__"])

    import gui_core.services as services
    want = services.source_preview(
        services.cached_synthetic_source())["psd_in"]

    # float32 storage is the only loss; anything larger means the wrong
    # array was transported.
    assert np.allclose(got, want, rtol=1e-6, atol=1e-4)


def test_unknown_blob_key_is_empty_not_an_error():
    assert api.blob("nope") == b""


def test_complex_arrays_split_into_two_blobs():
    wf = _call("make_waveform", 80e6, 1024, 4, 0, 0.0)["result"]
    x = wf["x"]
    assert x["__complex__"] is True
    re, im = _floats(x["re"]), _floats(x["im"])
    assert re.size == im.size == x["n"]
    assert np.any(im != 0)                     # genuinely complex


# ---------------------------------------------------------------- handles

def test_live_objects_stay_python_side():
    res = _call("cached_synthetic_source")
    # The PA is a live object: encoded as a handle, never as data.
    assert res["result"]["pa"]["__handle__"].startswith("h")
    assert "ReferencePA" in res["result"]["pa"]["type"]


def test_handle_can_be_passed_straight_back():
    src = _call("cached_synthetic_source")
    fit = _call("fit_classical", src["handle"], "GMP")
    assert "nmse_db" in json.dumps(fit["result"])


def test_nested_encoded_handle_is_dereferenced():
    src = _call("cached_synthetic_source")
    # Pass the encoded {"__handle__": ...} form rather than the bare id.
    out = json.loads(api.call("source_preview", json.dumps(
        {"args": [{"__handle__": src["handle"]}]})))
    assert out["ok"], out.get("error")


def test_release_frees_handles_and_blobs():
    src = _call("cached_synthetic_source")
    before = json.loads(api.stats())
    assert before["handles"] > 0
    api.release(src["handle"])
    assert json.loads(api.stats())["handles"] == before["handles"] - 1
    api.reset()
    after = json.loads(api.stats())
    assert after == {"handles": 0, "blobs": 0, "blob_bytes": 0}


# ---------------------------------------------------------------- charts

def test_every_figs_builder_has_a_spec_builder():
    """chart_spec must not quietly fall behind figs.py.

    Read figs.py with ast rather than importing it: importing pulls in
    matplotlib and PySide6 (via gui_qt.common), neither of which the CI
    fast lane installs, and this guard is worth more running everywhere
    than it costs to parse one file.
    """
    import ast
    tree = ast.parse((ROOT / "gui_qt" / "figs.py")
                     .read_text(encoding="utf-8"))
    fig_names = {n.name[:-4] for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef)
                 and n.name.endswith("_fig") and not n.name.startswith("_")}
    spec_names = set(chart_spec.BUILDERS)
    assert fig_names == spec_names, (
        f"only in figs.py: {sorted(fig_names - spec_names)}; "
        f"only in chart_spec: {sorted(spec_names - fig_names)}")


def test_psd_spec_carries_the_same_curve_as_figs():
    from padpd.metrics import psd
    rng = np.random.default_rng(0)
    y = rng.normal(size=4096) + 1j * rng.normal(size=4096)
    spec, blobs = chart_spec.build("psd", {"y": y}, 100e6)

    panel = spec["panels"][0]
    assert panel["kind"] == "line"
    assert panel["ylim"] == [-90, 5]           # same as figs.py
    f_want, p_want = psd(y, 100e6)
    s = panel["series"][0]
    assert np.allclose(blobs[s["x"]], f_want / 1e6, rtol=1e-5)
    assert np.allclose(blobs[s["y"]], p_want, rtol=1e-4, atol=1e-3)


def test_psd_mask_is_mirrored_about_dc():
    mask = np.array([[10e6, -20.0], [20e6, -40.0]])
    spec, blobs = chart_spec.build("psd", {"y": np.ones(256)}, 100e6,
                                   mask=mask)
    m = spec["panels"][0]["series"][-1]
    assert m["style"] == "dashed"
    x = blobs[m["x"]]
    assert np.allclose(x, [-20, -10, 10, 20])


def test_scatter_specs_decimate():
    n = 200_000
    pts = np.arange(n) + 1j * np.arange(n)
    spec, blobs = chart_spec.build("constellation", {"rx": pts})
    s = spec["panels"][0]["series"][0]
    assert blobs[s["x"]].size <= chart_spec.MAX_SCATTER_POINTS
    assert spec["panels"][0]["aspect_equal"] is True


def test_amam_panels_share_one_decimation():
    rng = np.random.default_rng(1)
    x = rng.normal(size=50_000) + 1j * rng.normal(size=50_000)
    spec, blobs = chart_spec.build("amam", x, 1.9 * x)
    p1, p2 = spec["panels"]
    # Same x key in both panels: the two curves are parallel samples, and
    # decimating them apart would pair the wrong points.
    assert p1["series"][0]["x"] == p2["series"][0]["x"]
    assert blobs[p1["series"][0]["y"]].size == blobs[p1["series"][0]["x"]].size


def test_twin_axis_series_are_marked():
    res = {"blocks": [0, 1, 2], "evm_raw": [-30, -31, -32],
           "evm_deembed": [-35, -35, -36], "evm_full": [-40, -41, -41],
           "image_dbc": [-55, -58, -60]}
    spec, _ = chart_spec.build("three_loop", res)
    axes = [s["axis"] for s in spec["panels"][0]["series"]]
    assert axes == ["left", "left", "left", "right"]
    assert spec["panels"][0]["y2label"]


def test_bars_spec_uses_nan_for_missing_metrics():
    spec, blobs = chart_spec.build("bars", ["run A", "run B"],
                                   {"ACLR": [-45.0, None]})
    y = blobs[spec["panels"][0]["series"][0]["y"]]
    assert np.isnan(y[1])                      # a gap, not a 0 dB reading


def test_bars_spec_truncates_long_names():
    long = "x" * 40
    spec, _ = chart_spec.build("bars", [long], {"m": [1.0]})
    label = spec["panels"][0]["x_ticks"][0]["label"]
    assert label.endswith("…") and len(label) == 24


def test_chart_language_switches_labels():
    zh, _ = chart_spec.build("psd", {"y": np.ones(256)}, 100e6, lang="zh")
    en, _ = chart_spec.build("psd", {"y": np.ones(256)}, 100e6, lang="en")
    assert zh["panels"][0]["xlabel"] != en["panels"][0]["xlabel"]
    assert "MHz" in en["panels"][0]["xlabel"]


def test_unknown_chart_names_the_known_ones():
    with pytest.raises(KeyError, match="psd"):
        chart_spec.build("no_such_chart")


def test_chart_api_namespaces_blob_keys():
    """Two charts alive at once must not collide in the blob store."""
    a = json.loads(api.chart("psd", json.dumps(
        {"args": [{"y": [1.0] * 256}, 100e6]})))
    b = json.loads(api.chart("psd", json.dumps(
        {"args": [{"y": [2.0] * 256}, 100e6]})))
    assert a["ok"] and b["ok"], (a.get("error"), b.get("error"))
    ka = a["spec"]["panels"][0]["series"][0]["x"]
    kb = b["spec"]["panels"][0]["series"][0]["x"]
    assert ka != kb
    assert api.blob(ka) and api.blob(kb)


def test_chart_api_reports_errors_as_data():
    out = json.loads(api.chart("psd", json.dumps({"args": []})))
    assert out["ok"] is False
    assert "traceback" in out


# ---------------------------------------------------------------- gallery

def test_gallery_covers_every_chart_type():
    """The gallery is how each spec shape gets drawn at least once."""
    from padpd_mobile import gallery
    ids = {e["id"] for e in gallery.listing()}
    assert ids == set(chart_spec.BUILDERS)


def test_gallery_labels_provenance_honestly():
    """Half these entries carry fixtures because their real producers are
    minutes of compute or need torch. The UI shows which, so a plausible
    chart is not mistaken for a working pipeline."""
    from padpd_mobile import gallery
    provenance = {e["id"]: e["provenance"] for e in gallery.listing()}
    assert set(provenance.values()) <= {"computed", "sampled"}
    # These four cannot be computed on a phone at all: codesign_sweep is
    # minutes, train history and gradient co-design need torch, and the
    # two-tone analysis needs an instrument CSV that is not on the device.
    for fixture in ("codesign", "grad", "train", "two_tone"):
        assert provenance[fixture] == "sampled"


@pytest.mark.parametrize("entry_id", [e[0] for e in _gallery_entries()])
def test_every_gallery_entry_builds(entry_id):
    out = json.loads(api.gallery_chart(entry_id))
    assert out["ok"], out.get("error", "") + out.get("traceback", "")
    spec = out["spec"]
    assert spec["panels"]
    for panel in spec["panels"]:
        assert panel["series"], f"{entry_id}: panel with no series"
        for s in panel["series"]:
            # Every referenced blob must resolve, or the phone draws a
            # chart with an invisible curve and no error.
            assert api.blob(s["x"]), f"{entry_id}: empty x blob"
            assert api.blob(s["y"]), f"{entry_id}: empty y blob"


def test_committed_spec_fixture_matches_what_python_emits():
    """The Kotlin side parses `gallery_specs.json` as its contract test.

    If the Python schema gains or loses a panel key, that fixture goes
    stale and the Kotlin test keeps passing against yesterday's shape.
    Compare keys - not values, which carry floats and would be brittle.
    """
    fixture_path = (ROOT / "android" / "app" / "src" / "test" / "resources"
                    / "gallery_specs.json")
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert set(fixture) == {e["id"] for e in _gallery_listing()}

    for entry_id, want in fixture.items():
        got = json.loads(api.gallery_chart(entry_id))["spec"]
        assert len(got["panels"]) == len(want["panels"]), entry_id
        for gp, wp in zip(got["panels"], want["panels"], strict=True):
            assert set(gp) == set(wp), (
                f"{entry_id}: panel keys drifted from the committed "
                f"fixture; regenerate it (see android/README.md). "
                f"added={set(gp) - set(wp)} removed={set(wp) - set(gp)}")
            for gs, ws in zip(gp["series"], wp["series"], strict=True):
                assert set(gs) == set(ws), f"{entry_id}: series keys drifted"
