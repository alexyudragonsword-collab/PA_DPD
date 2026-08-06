import numpy as np
import pytest

from gui_core import Run, RunStore, services


@pytest.fixture(scope="module")
def synth():
    return services.make_synthetic_source(bandwidth_hz=20e6, qam=256,
                                          symbols=4, drive=0.14)


def test_runstore_roundtrip(tmp_path):
    store = RunStore(tmp_path / "runs")
    r = store.add(Run(name="gmp test", kind="pa_model",
                      config={"model": "GMP"}, metrics={"nmse_db": -33.7}))
    listed = store.list()
    assert len(listed) == 1 and listed[0].name == "gmp test"
    assert store.get(r.run_id).metrics["nmse_db"] == -33.7
    assert store.list(kind="dpd") == []
    assert store.delete(r.run_id)
    assert store.list() == []


def test_runstore_rejects_bad_id(tmp_path):
    store = RunStore(tmp_path)
    with pytest.raises(ValueError):
        store.get("../evil")


def test_make_waveform_with_cfr():
    w = services.make_waveform(20e6, 256, 4, seed=0, cfr_papr_db=8.0)
    assert w["papr_db"] > w["papr_cfr_db"]
    assert w["cfr_evm_db"] < -25


def test_synthetic_source_and_classical_fit(synth):
    assert len(synth["x_train"]) == len(synth["y_train"])
    res = services.fit_classical(synth, "GMP", {"order": 5, "memory": 3})
    assert res["metrics"]["nmse_db"] < -30
    # aligned 5*3 + lag 3*2*2 + lead 3*2*2 (GMP defaults)
    assert res["metrics"]["n_coeffs"] == 39


def test_ila_dpd_synthetic(synth):
    res = services.run_dpd_ila(synth, basis="DDR-140 (preset)")
    m = res["metrics"]
    assert m["DPD"]["evm_db"] < m["no DPD"]["evm_db"] - 10
    assert res["convention"] == "constellation"


def test_source_preview(synth):
    p = services.source_preview(synth)
    assert len(p["freq"]) == len(p["psd_in"])
    assert p["n_train"] > 0


def test_bitwidth_sweep_classical(synth):
    res = services.fit_classical(synth, "DDR", {"order": 5, "memory": 4})
    sweep = services.bitwidth_sweep(res["model"], synth, bits=(16, 8))
    assert sweep["bits"][16] < sweep["bits"][8]
    assert sweep["macs"]["real_macs_per_sample"] > 0


def test_export_artifacts_classical(synth, tmp_path):
    res = services.fit_classical(synth, "GMP", {"order": 5, "memory": 3})
    paths = services.export_artifacts(res["model"], synth,
                                     str(tmp_path / "exp"))
    import os
    assert os.path.exists(paths["coeffs"])
    assert os.path.exists(paths["vectors"])


def test_default_opendpd_dir_is_platform_appropriate(monkeypatch):
    from pathlib import Path
    # with a bogus env override and no real dirs, falls back to a
    # home-relative path valid on the current OS (never a hardcoded
    # foreign path)
    monkeypatch.setenv("OPENDPD_DIR", str(Path("nope_xyz_123")))
    monkeypatch.chdir(Path.home())
    d = services.default_opendpd_dir()
    assert d
    assert "OpenDPD" in d and "datasets" in d


def test_default_opendpd_dir_honours_env(tmp_path, monkeypatch):
    (tmp_path / "spec_dir").mkdir()
    monkeypatch.setenv("OPENDPD_DIR", str(tmp_path))
    assert services.default_opendpd_dir() == str(tmp_path)


def test_analyze_two_tone_csv_example():
    res = services.analyze_two_tone_csv(services.EXAMPLE_TWO_TONE_CSV)
    assert res["memory_strength_db"] > 4.0
    assert res["memory_depth"] >= 4 and res["use_cross_terms"]
    assert len(res["spacings_hz"]) == len(res["im3_lower_dbc"])


@pytest.mark.parametrize("method", ["rls", "whitened", "apa"])
def test_run_adaptive_dpd_tracks_drift(method):
    res = services.run_adaptive_dpd(method=method, n_blocks=8, warm_blocks=5)
    assert res["method"] == method
    assert len(res["evm_adaptive"]) == 8 == len(res["evm_frozen"])
    assert np.all(np.isfinite(res["evm_adaptive"]))   # did not diverge
    # adaptation beats the frozen baseline at full drift
    assert res["final_adaptive"] < res["final_frozen"] - 1.0
    assert res["gap_db"] > 1.0


def test_run_adaptive_dpd_rejects_bad_method():
    with pytest.raises(ValueError):
        services.run_adaptive_dpd(method="nlms")


def test_adaptive_run_record_shape():
    res = services.run_adaptive_dpd(method="apa", n_blocks=6, warm_blocks=4,
                                    apa_k=3)
    name, cfg, metrics = services.adaptive_run_record(res)
    assert "APA(K3)" in name                      # K encoded for apa
    assert cfg["algo"] == "adaptive" and cfg["apa_k"] == 3
    # metrics slot alongside batch DPD (evm_db plotted the same way)
    assert metrics["evm_db"] == res["final_adaptive"]
    assert metrics["evm_before_db"] == res["final_frozen"]
    assert "gap_db" in metrics

    r = services.adaptive_run_record(
        services.run_adaptive_dpd(method="rls", n_blocks=6, warm_blocks=4))
    assert r[0] == "Adapt-RLS @ drift"            # no K suffix for non-apa


def test_run_adaptive_dpd_honours_bandwidth():
    res = services.run_adaptive_dpd(method="rls", n_blocks=5, warm_blocks=4,
                                    bw=40e6)
    assert res["bw"] == 40e6
    assert res["gap_db"] > 1.0                    # still tracks drift
    _, cfg, _ = services.adaptive_run_record(res)
    assert cfg["bw_mhz"] == 40.0


def test_eval_source_for_rebuilds_exact_synthetic_source():
    # a model fitted on 160 MHz / 4096-QAM / CFR must NOT be evaluated on
    # the default 80 MHz / 1024-QAM waveform
    src = services.make_synthetic_source(bandwidth_hz=40e6, qam=256,
                                         symbols=4, drive=0.15,
                                         cfr_papr_db=8.0)
    rebuilt = services.eval_source_for({"source": src["name"]}, {})
    assert rebuilt["bw"] == 40e6
    assert rebuilt["cfr_papr"] == 8.0
    assert rebuilt["drive"] == 0.15
    assert rebuilt["name"].endswith("CFR8.0")
