"""LUT extraction (spline -> interpolation tables) and LUTDPD runtime."""

import json

import numpy as np
import pytest

from padpd.deploy import (
    LUTDPD,
    export_lut,
    lut_from_model,
    quantize_lut,
    spline_mac_cost,
)
from padpd.pa import ReferencePA, SplineGMP, SplineMemoryPolynomial, nmse_db
from padpd.waveform import OFDMConfig, generate_ofdm


@pytest.fixture(scope="module")
def fitted_smp():
    x = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=256,
                                 n_symbols=8, seed=11)).x
    y = ReferencePA()(x)
    smp = SplineMemoryPolynomial.from_signal(x, n_knots=8,
                                             memory_depth=4).fit(x, y)
    return x, y, smp


def test_lut_high_depth_matches_model(fitted_smp):
    x, _, smp = fitted_smp
    lut = LUTDPD.from_table(lut_from_model(smp, n_entries=1024))
    assert nmse_db(smp(x), lut(x)) < -60


def test_lut_depth_degrades_monotonically(fitted_smp):
    x, _, smp = fitted_smp
    ref = smp(x)
    errs = [nmse_db(ref, LUTDPD.from_table(
        lut_from_model(smp, n_entries=n))(x)) for n in (512, 64, 16)]
    assert errs[0] < errs[1] < errs[2]


def test_lut_clamps_beyond_r_max(fitted_smp):
    """Constant-envelope drives beyond r_max all see the endpoint gain."""
    _, _, smp = fitted_smp
    lut = LUTDPD.from_table(lut_from_model(smp, n_entries=256))
    r_max = lut.r_grid[-1]
    gains = []
    for scale in (1.0, 2.0, 5.0):
        probe = np.full(64, scale * r_max, dtype=complex)
        out = lut(probe)
        assert np.all(np.isfinite(out))
        gains.append(out[-1] / probe[-1])   # steady state: all taps clamped
    np.testing.assert_allclose(gains, gains[0], rtol=1e-9)


def test_lut_from_sgmp_carries_cross_delays(fitted_smp):
    x, y, _ = fitted_smp
    sgmp = SplineGMP.from_signal(x, n_knots=6, memory_depth=3).fit(x, y)
    lut = lut_from_model(sgmp, n_entries=512)
    assert lut["delays"] == sgmp.branch_delays()
    evaluator = LUTDPD.from_table(lut)
    assert evaluator.n_branches == sgmp.n_branches
    assert nmse_db(sgmp(x), evaluator(x)) < -55


def test_quantize_lut_and_export_roundtrip(fitted_smp, tmp_path):
    _, _, smp = fitted_smp
    lut = lut_from_model(smp, n_entries=128)
    q = quantize_lut(lut, entry_bits=12)
    assert q["entry_bits"] == 12
    p = tmp_path / "lut.json"
    payload = export_lut(lut, w_bits=12, path=str(p))
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert loaded == json.loads(json.dumps(payload))
    assert loaded["n_entries"] == 128 and loaded["n_branches"] == 4
    # dequantized entries match the float table within 1 LSB
    for b, g in zip(loaded["branches"], lut["gains"], strict=True):
        step = 2.0 ** b["scale_exp"]
        got = (np.array(b["gains_real"]) + 1j * np.array(b["gains_imag"])
               ) * step
        assert np.abs(got - g).max() <= step * np.sqrt(2) / 2 + 1e-15


def test_lut_requires_gain_curve():
    from padpd.pa import SalehPA
    with pytest.raises(TypeError):
        lut_from_model(SalehPA())
    with pytest.raises(ValueError):
        lut_from_model(SplineMemoryPolynomial(n_knots=4, r_max=1.0),
                       n_entries=1)


def test_spline_mac_cost_structure():
    c = spline_mac_cost(4, 320e6, degree=3)
    assert c["active_bases"] == 4
    assert c["real_macs_per_sample_lut"] == 4 * 6
    assert c["real_macs_per_sample_spline"] == 4 * 12
    assert c["real_gmac_per_s_lut"] == pytest.approx(4 * 6 * 0.32)
    # LUT runtime beats the polynomial-MAC cost for a like-for-like model
    from padpd.deploy import mac_cost
    assert (c["real_macs_per_sample_lut"]
            < mac_cost(28, 320e6)["real_macs_per_sample"])


def test_lut_conjugate_branches_roundtrip(fitted_smp, tmp_path):
    """A widely-linear SMP extracts to a LUT whose evaluator applies
    conj() on image branches and matches the model."""
    x, y, _ = fitted_smp
    wl = SplineMemoryPolynomial.from_signal(
        x, n_knots=8, memory_depth=3, conjugate=True).fit(x, y)
    lut = lut_from_model(wl, n_entries=1024)
    assert lut["conjugate"] == [False] * 3 + [True] * 3
    ev = LUTDPD.from_table(lut)
    assert ev.conjugate == lut["conjugate"]
    assert nmse_db(wl(x), ev(x)) < -60
    payload = export_lut(lut, w_bits=12, path=str(tmp_path / "wl.json"))
    assert [b["conjugate"] for b in payload["branches"]] == lut["conjugate"]


def test_lut_cim3_and_dc_roundtrip(fitted_smp, tmp_path):
    """conj^3 branches and the DC term survive LUT extraction, the
    evaluator applies them, and the JSON export carries the metadata."""
    x, y, _ = fitted_smp
    m = SplineMemoryPolynomial.from_signal(
        x, n_knots=6, memory_depth=2, conjugate=True, cim3=True,
        dc_term=True).fit(x, y)
    lut = lut_from_model(m, n_entries=1024)
    assert lut["phase_orders"] == [1, 1, -1, -1, -3, -3]
    assert lut["dc"] == m.dc_coefficient()
    ev = LUTDPD.from_table(lut)
    assert nmse_db(m(x), ev(x)) < -60
    payload = export_lut(lut, w_bits=12, path=str(tmp_path / "c3.json"))
    assert [b["phase_order"] for b in payload["branches"]] \
        == lut["phase_orders"]
    assert payload["dc_real"] == m.dc_coefficient().real
