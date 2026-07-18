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
