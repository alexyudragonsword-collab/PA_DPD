"""Tests for the HB / S-parameter import path (WienerHammersteinPA)."""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from padpd.pa import (  # noqa: E402
    ReferencePA,
    SalehPA,
    WienerHammersteinPA,
    load_amam_table,
    load_model,
    s21_to_fir,
)

FS = 320e6


def _saleh_tables(n=200, r_max=1.4):
    saleh = SalehPA()
    r = np.linspace(1e-3, r_max, n)
    y = saleh(r.astype(complex))
    return r, np.abs(y), np.rad2deg(np.angle(y)), saleh


def test_lut_matches_source_curve_and_saturates():
    r, r_out, ph, saleh = _saleh_tables()
    pa = WienerHammersteinPA(r, r_out, ph)
    x = np.linspace(0.05, 1.2, 500).astype(complex)
    y = pa(x)
    ref = saleh(x) / saleh.small_signal_gain * (r_out[0] / r[0]) / \
        (r_out[0] / r[0])
    ref = saleh(x) / (r_out[0] / r[0])
    assert np.max(np.abs(y - ref)) < 2e-2
    # beyond-table inputs saturate instead of extrapolating
    y_big = pa(np.array([5.0 + 0j]))
    assert abs(y_big[0]) <= r_out[-1] / (r_out[0] / r[0]) * 1.01


def test_amam_csv_both_conventions(tmp_path):
    r, r_out, ph, _ = _saleh_tables(50)
    p1 = tmp_path / "amam_lin.csv"
    lines = ["r_in,r_out,phase_deg"] + [
        f"{a},{b},{c}" for a, b, c in zip(r, r_out, ph, strict=True)]
    p1.write_text("\n".join(lines), encoding="utf-8")
    r1, o1, p1_ = load_amam_table(str(p1))
    assert np.allclose(r1, r) and np.allclose(o1, r_out)

    # dBm convention round-trips through the 50-ohm conversion
    pin = 10 * np.log10(r ** 2 / (2 * 50) / 1e-3)
    pout = 10 * np.log10(r_out ** 2 / (2 * 50) / 1e-3)
    p2 = tmp_path / "amam_dbm.csv"
    lines = ["pin_dbm,pout_dbm,phase_deg"] + [
        f"{a},{b},{c}" for a, b, c in zip(pin, pout, ph, strict=True)]
    p2.write_text("\n".join(lines), encoding="utf-8")
    r2, o2, _ = load_amam_table(str(p2))
    assert np.allclose(r2, r, rtol=1e-6)
    assert np.allclose(o2, r_out, rtol=1e-6)


def test_s21_fir_reproduces_table(tmp_path):
    f_tab = np.linspace(-120e6, 120e6, 25)
    mag_db = 1.0 * np.cos(2 * np.pi * f_tab / 200e6)
    ph_deg = 8.0 * np.sin(2 * np.pi * f_tab / 200e6)
    p = tmp_path / "s21.csv"
    lines = ["freq_hz,mag_db,phase_deg"] + [
        f"{a},{b},{c}"
        for a, b, c in zip(f_tab, mag_db, ph_deg, strict=True)]
    p.write_text("\n".join(lines), encoding="utf-8")
    taps = s21_to_fir(str(p), FS, n_taps=31)
    # check realized response at in-band table points
    n = 4096
    h = np.fft.fft(taps, n)
    f = np.fft.fftfreq(n, d=1 / FS)
    for ft, md in zip(f_tab[5:-5], mag_db[5:-5], strict=True):
        k = np.argmin(np.abs(f - ft))
        realized_db = 20 * np.log10(np.abs(h[k]))
        assert abs(realized_db - md) < 0.35


def test_wh_model_reproduces_reference_pa(tmp_path):
    """Full WH import path recovers a known WH-structured PA."""
    ref = ReferencePA(drive=0.14)
    r, r_out, ph, saleh = _saleh_tables(300, r_max=2.0)
    pa = WienerHammersteinPA(r, r_out, ph, fir_in=ref.fir_in,
                             fir_out=ref.fir_out, drive=0.14)
    rng = np.random.default_rng(0)
    x = (rng.standard_normal(8192) + 1j * rng.standard_normal(8192)) * 0.3
    y_ref, y_wh = ref(x), pa(x)
    nmse = 10 * np.log10(np.mean(np.abs(y_ref - y_wh) ** 2)
                         / np.mean(np.abs(y_ref) ** 2))
    assert nmse < -40


def test_save_load_roundtrip(tmp_path):
    r, r_out, ph, _ = _saleh_tables(60)
    pa = WienerHammersteinPA(r, r_out, ph,
                             fir_in=np.array([1.0, 0.1 - 0.04j]),
                             drive=0.5)
    path = str(tmp_path / "wh.npz")
    pa.save(path)
    pa2 = load_model(path)
    x = (np.linspace(0.1, 1.0, 100) * np.exp(0.3j)).astype(complex)
    assert np.allclose(pa(x), pa2(x))


def test_rejects_unsorted_table():
    with pytest.raises(ValueError):
        WienerHammersteinPA(np.array([0.2, 0.1]), np.array([1, 2]),
                            np.array([0, 0]))
