import json
import os

import numpy as np
import pytest

from padpd.data import IQDataset, align_delay, load_opendpd_dataset

OPENDPD_ROOT = os.environ.get("OPENDPD_ROOT", "/home/user/OpenDPD")


def _write_iq_csv(path, z):
    with open(path, "w") as f:
        f.write("I,Q\n")
        for v in z:
            f.write(f"{v.real},{v.imag}\n")


def test_load_split_csv_format(tmp_path):
    rng = np.random.default_rng(0)
    spec = {"dataset_format": "split_csv", "input_signal_fs": 800e6,
            "bw_main_ch": 200e6, "n_sub_ch": 10, "nperseg": 2560}
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    data = {}
    for split, n in (("train", 60), ("val", 20), ("test", 20)):
        x = rng.standard_normal(n) + 1j * rng.standard_normal(n)
        y = 0.9 * x
        _write_iq_csv(tmp_path / f"{split}_input.csv", x)
        _write_iq_csv(tmp_path / f"{split}_output.csv", y)
        data[split] = (x, y)
    ds = load_opendpd_dataset(str(tmp_path))
    for split in ("train", "val", "test"):
        np.testing.assert_allclose(ds[split].x, data[split][0], rtol=1e-6)
        np.testing.assert_allclose(ds[split].y, data[split][1], rtol=1e-6)
        assert ds[split].sample_rate_hz == 800e6
        assert ds[split].meta["spec"]["n_sub_ch"] == 10


def test_load_single_csv_format(tmp_path):
    rng = np.random.default_rng(1)
    n = 100
    x = rng.standard_normal(n) + 1j * rng.standard_normal(n)
    y = 0.8 * x
    spec = {"dataset_format": "single_csv", "csv_filename": "data.csv",
            "split_ratios": {"train": 0.6, "val": 0.2, "test": 0.2},
            "input_signal_fs": 640e6}
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    # UTF-8 BOM like OpenDPD's example file
    with open(tmp_path / "data.csv", "w", encoding="utf-8-sig") as f:
        f.write("I_in,Q_in,I_out,Q_out\n")
        for k in range(n):
            f.write(f"{x[k].real},{x[k].imag},{y[k].real},{y[k].imag}\n")
    ds = load_opendpd_dataset(str(tmp_path))
    assert len(ds["train"]) == 60
    assert len(ds["val"]) == 20
    assert len(ds["test"]) == 20
    np.testing.assert_allclose(ds["train"].x, x[:60], rtol=1e-6)
    np.testing.assert_allclose(ds["test"].y, y[80:], rtol=1e-6)


def test_missing_fs_raises(tmp_path):
    with pytest.raises(ValueError):
        load_opendpd_dataset(str(tmp_path))


@pytest.mark.skipif(not os.path.isdir(os.path.join(OPENDPD_ROOT, "datasets",
                                                   "DPA_200MHz")),
                    reason="OpenDPD repo not available")
def test_load_real_dpa200():
    ds = load_opendpd_dataset(
        os.path.join(OPENDPD_ROOT, "datasets", "DPA_200MHz"))
    assert len(ds["train"]) == 23040
    assert len(ds["val"]) == 7680
    assert len(ds["test"]) == 7680
    assert ds["train"].sample_rate_hz == 800e6
    assert ds["spec"]["nperseg"] == 2560
    assert ds["spec"]["n_sub_ch"] == 10


def test_three_way_split():
    rng = np.random.default_rng(2)
    z = rng.standard_normal(100) + 1j * rng.standard_normal(100)
    ds = IQDataset(z, 2 * z, 1e6)
    train, val, test = ds.split((0.6, 0.2, 0.2))
    assert len(train) == 60 and len(val) == 20 and len(test) == 20
    assert val.meta["split"] == "val"
    np.testing.assert_array_equal(np.concatenate([train.x, val.x, test.x]),
                                  ds.x)
    # backward-compatible two-way form
    a, b = ds.split(0.8)
    assert len(a) == 80 and len(b) == 20


def test_align_delay_recovers_lag_and_gain():
    rng = np.random.default_rng(3)
    x = rng.standard_normal(5000) + 1j * rng.standard_normal(5000)
    g = 1.7 * np.exp(1j * 0.6)
    lag = 7
    y = np.concatenate([np.zeros(lag, complex), g * x])[: len(x)]
    x_a, y_a, info = align_delay(x, y, max_lag=100)
    assert info["lag"] == lag
    assert info["gain"] == pytest.approx(g, rel=1e-6)
    np.testing.assert_allclose(y_a, info["gain"] * x_a, rtol=1e-9)


def test_align_delay_negative_lag():
    rng = np.random.default_rng(4)
    x = rng.standard_normal(3000) + 1j * rng.standard_normal(3000)
    y = x[5:]  # y leads: x delayed relative to y
    x_a, y_a, info = align_delay(x, y, max_lag=50)
    assert info["lag"] == -5
    np.testing.assert_allclose(y_a, x_a, rtol=1e-9)


def test_align_delay_fractional():
    rng = np.random.default_rng(5)
    # band-limited signal so a fractional shift is well defined
    n = 8192
    spec = np.zeros(n, complex)
    spec[:n // 8] = rng.standard_normal(n // 8) + 1j * rng.standard_normal(n // 8)
    spec[-n // 8:] = rng.standard_normal(n // 8) + 1j * rng.standard_normal(n // 8)
    x = np.fft.ifft(spec)
    delay = 3.4
    freq = np.fft.fftfreq(n)
    y = np.fft.ifft(np.fft.fft(x) * np.exp(-2j * np.pi * freq * delay))
    x_a, y_a, info = align_delay(x, y, max_lag=100)
    assert info["lag"] == 3
    assert info["lag_total"] == pytest.approx(delay, abs=0.05)
    # residual after fractional correction is small
    resid = np.mean(np.abs(y_a - info["gain"] * x_a) ** 2)
    assert 10 * np.log10(resid / np.mean(np.abs(x_a) ** 2)) < -30
