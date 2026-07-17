import numpy as np
import pytest

from padpd.data import (IQDataset, load_cadence_csv, load_matlab_mat,
                        load_opendpd_csv)


@pytest.fixture
def dataset():
    rng = np.random.default_rng(0)
    x = rng.standard_normal(1000) + 1j * rng.standard_normal(1000)
    y = 0.9 * x + 0.05 * x * np.abs(x) ** 2
    return IQDataset(x, y, sample_rate_hz=640e6, meta={"note": "test"})


def test_save_load_roundtrip(dataset, tmp_path):
    p = str(tmp_path / "ds.npz")
    dataset.save(p)
    loaded = IQDataset.load(p)
    np.testing.assert_allclose(loaded.x, dataset.x)
    np.testing.assert_allclose(loaded.y, dataset.y)
    assert loaded.sample_rate_hz == dataset.sample_rate_hz
    assert loaded.meta["note"] == "test"


def test_split_and_normalize(dataset):
    train, test = dataset.split(0.8)
    assert len(train) == 800 and len(test) == 200
    norm = dataset.normalized()
    assert np.mean(np.abs(norm.x) ** 2) == pytest.approx(1.0)
    # gain preserved
    g_orig = np.abs(dataset.y).mean() / np.abs(dataset.x).mean()
    g_norm = np.abs(norm.y).mean() / np.abs(norm.x).mean()
    assert g_norm == pytest.approx(g_orig)


def test_load_cadence_csv(tmp_path):
    fs = 320e6
    n = 100
    t = np.arange(n) / fs
    rng = np.random.default_rng(1)
    x = rng.standard_normal(n) + 1j * rng.standard_normal(n)
    y = 0.8 * x
    p = tmp_path / "env.csv"
    with open(p, "w") as f:
        f.write("time,i_in,q_in,i_out,q_out\n")
        for k in range(n):
            f.write(f"{t[k]:.12e},{x[k].real},{x[k].imag},"
                    f"{y[k].real},{y[k].imag}\n")
    ds = load_cadence_csv(str(p))
    assert ds.sample_rate_hz == pytest.approx(fs, rel=1e-6)
    np.testing.assert_allclose(ds.x, x)
    np.testing.assert_allclose(ds.y, y)


def test_load_matlab_mat(tmp_path):
    from scipy.io import savemat
    rng = np.random.default_rng(2)
    x = rng.standard_normal(50) + 1j * rng.standard_normal(50)
    y = 1.1 * x
    p = str(tmp_path / "cap.mat")
    savemat(p, {"x": x, "y": y, "fs": 640e6})
    ds = load_matlab_mat(p)
    assert ds.sample_rate_hz == 640e6
    np.testing.assert_allclose(ds.x, x)


def test_load_opendpd_csv(tmp_path):
    rng = np.random.default_rng(3)
    x = rng.standard_normal(60) + 1j * rng.standard_normal(60)
    y = 0.7 * x
    pin, pout = tmp_path / "in.csv", tmp_path / "out.csv"
    for p, z in ((pin, x), (pout, y)):
        with open(p, "w") as f:
            f.write("I,Q\n")
            for v in z:
                f.write(f"{v.real},{v.imag}\n")
    ds = load_opendpd_csv(str(pin), str(pout), sample_rate_hz=800e6)
    np.testing.assert_allclose(ds.x, x)
    np.testing.assert_allclose(ds.y, y)
    assert ds.sample_rate_hz == 800e6
