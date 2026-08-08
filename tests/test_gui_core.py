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


def test_fit_classical_spline_entries(synth):
    res = services.fit_classical(synth, "Spline-MP (K8,M4)")
    assert res["metrics"]["nmse_db"] < -30
    assert res["metrics"]["n_coeffs"] == 4 * (8 - 1 + 3)
    res_p = services.fit_classical(synth, "Spline-MP",
                                   {"order": 6, "memory": 2})
    assert res_p["metrics"]["n_coeffs"] == 2 * (6 - 1 + 3)


def test_ila_dpd_spline_basis(synth):
    res = services.run_dpd_ila(synth, basis="Spline-GMP (K8)")
    m = res["metrics"]
    assert m["DPD"]["evm_db"] < m["no DPD"]["evm_db"] - 10


def test_lut_sweep_service(synth):
    res = services.fit_classical(synth, "Spline-MP (K8,M4)")
    sweep = services.lut_sweep(res["model"], synth, entries=(256, 16))
    assert sweep["entries"][256] <= sweep["entries"][16]
    assert np.isfinite(sweep["float"])
    assert sweep["macs"]["real_macs_per_sample_lut"] == 4 * 6


def test_run_adaptive_dpd_spline_thermal_smoke():
    res = services.run_adaptive_dpd(basis="spline", dut="thermal",
                                    n_blocks=2, n_symbols=2,
                                    warm_blocks=1, bw=20e6)
    assert res["basis"] == "spline" and res["dut"] == "thermal"
    assert np.all(np.isfinite(res["evm_adaptive"]))
    assert 0.0 < res["states"][-1] <= 1.0
    name, config, _ = services.adaptive_run_record(res)
    assert "Spl" in name and "thermal" in name
    assert config["basis"] == "spline"


def test_run_adaptive_dpd_rejects_bad_basis_and_dut():
    with pytest.raises(ValueError):
        services.run_adaptive_dpd(basis="volterra", n_blocks=2)
    with pytest.raises(ValueError):
        services.run_adaptive_dpd(dut="oven", n_blocks=2)


def test_two_tone_csv_includes_spline_recipe():
    out = services.analyze_two_tone_csv(services.EXAMPLE_TWO_TONE_CSV)
    assert out["spline_config"]["memory_depth"] == out["memory_depth"]
    assert out["spline_runtime_macs"] >= 4 * out["memory_depth"]


def test_frontend_source_and_wl_model():
    """A front-end-impaired synthetic DUT needs the widely-linear model
    entries; the plain phase-equivariant spline pins near the IRR."""
    src = services.make_synthetic_source(bandwidth_hz=20e6, qam=256,
                                         symbols=4, drive=0.14,
                                         frontend="iq+lo")
    assert "FE(iq+lo)" in src["name"] and src["frontend"] == "iq+lo"
    plain = services.fit_classical(src, "Spline-MP (K8,M4)")
    wl = services.fit_classical(src, "Spline-MP-WL (conj+dc)")
    assert wl["metrics"]["nmse_db"] < plain["metrics"]["nmse_db"] - 5.0


def test_frontend_rejects_unknown():
    with pytest.raises(ValueError):
        services.make_synthetic_source(bandwidth_hz=20e6, qam=256,
                                       symbols=2, frontend="magic")


def test_eval_source_for_rebuilds_frontend_source():
    meta = {"source": "ReferencePA d=0.14 20MHz/256QAM FE(iq+lo)"}
    src = services.eval_source_for(meta, {})
    assert src["frontend"] == "iq+lo"
    assert src["bw"] == 20e6


def test_run_three_loop_demo_service():
    res = services.run_three_loop_demo(n_blocks=4, n_symbols=2)
    assert res["final_raw"] > -10.0                 # broken without loops
    assert res["final_full"] < res["final_deembed"] - 2.0
    name, config, metrics = services.three_loop_run_record(res)
    assert "3Loop" in name
    assert config["algo"] == "three_loop"
    assert metrics["evm_db"] == res["final_full"]
    assert np.isfinite(metrics["image_dbc"])


def test_run_gain_modulation_thermal_closes_the_loop():
    """Identification recovers the thermal DUT's taus (truth 5/30 us)
    and the identified alphas buy a real state-spline gain."""
    res = services.run_gain_modulation(dut="thermal")
    assert res["significant"]
    assert len(res["taus_heat_us"]) == 2
    assert abs(res["taus_heat_us"][0] - 5.0) < 1.5
    assert abs(res["taus_heat_us"][1] - 30.0) < 6.0
    assert 0.5 < res["hysteresis_ratio"] < 2.0     # linear thermal RC
    assert res["state_gain_db"] > 6.0              # measured +10.5
    name, config, metrics = services.gain_mod_run_record(res)
    assert config["algo"] == "gain_modulation"
    assert metrics["tau1_us"] == res["taus_heat_us"][0]
    assert metrics["state_gain_db"] == res["state_gain_db"]


def test_run_gain_modulation_static_control():
    """The probe must not hallucinate modulation on a static PA."""
    res = services.run_gain_modulation(dut="static")
    assert not res["significant"]
    assert abs(res["droop_db"]) < 0.05
    assert res["state_gain_db"] is None
    with pytest.raises(ValueError):
        services.run_gain_modulation(dut="oven")
