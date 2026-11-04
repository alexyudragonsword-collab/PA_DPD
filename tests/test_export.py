import json
from pathlib import Path

import numpy as np
import pytest

from padpd.deploy import (
    FixedPointPolyModel,
    export_linear_coeffs,
    export_reference_vectors,
)
from padpd.deploy.export import _int_codes
from padpd.pa import ReferencePA, ddr_volterra_default
from padpd.waveform import OFDMConfig, generate_ofdm


@pytest.fixture(scope="module")
def fitted():
    cfg = OFDMConfig(bandwidth_hz=80e6, qam_order=256, n_symbols=8, seed=11)
    x = generate_ofdm(cfg).x
    y = ReferencePA()(x)
    return x, y, ddr_volterra_default().fit(x, y, regularization=1e-9)


def test_int_codes_reconstruct():
    rng = np.random.default_rng(0)
    w = rng.standard_normal(50) + 1j * rng.standard_normal(50)
    cr, ci, e = _int_codes(w, 16)
    qmax = 2 ** 15 - 1
    assert cr.max() <= qmax and cr.min() >= -qmax - 1
    # codes * 2**e reconstructs the W16 quantized value
    from padpd.deploy import quantize_symmetric
    recon = (cr + 1j * ci) * (2.0 ** e)
    np.testing.assert_allclose(recon, quantize_symmetric(w, 16), rtol=0,
                               atol=1e-12)


def test_export_linear_coeffs(fitted, tmp_path):
    _, _, ddr = fitted
    p = str(tmp_path / "coeffs.json")
    payload = export_linear_coeffs(ddr, w_bits=16, path=p)
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    # what the call returns and what it wrote are the same payload
    assert payload == d
    assert d["model_class"] == "DDRVolterraModel"
    assert d["n_coeffs"] == len(ddr.coeffs)
    assert len(d["coeffs_real"]) == len(ddr.coeffs)
    assert d["w_bits"] == 16
    # reconstruct coefficients from integer codes + exponent
    recon = (np.array(d["coeffs_real"]) + 1j * np.array(d["coeffs_imag"])) \
        * (2.0 ** d["coeff_scale_exp"])
    from padpd.deploy import quantize_symmetric
    np.testing.assert_allclose(recon, quantize_symmetric(ddr.coeffs, 16),
                               atol=1e-12)


def test_export_reference_vectors_matches_fixedpoint(fitted, tmp_path):
    x, _, ddr = fitted
    fp = FixedPointPolyModel(ddr, w_bits=16, sig_bits=16)
    p = str(tmp_path / "vectors.csv")
    export_reference_vectors(fp, x, p, n=500)
    rows = np.loadtxt(p, delimiter=",", skiprows=1)
    # 4 float columns + the 2 integer input-code columns of a fixed-point model
    assert rows.shape == (500, 6)
    # the dumped output equals the fixed-point model's output
    y_ref = fp(np.asarray(x[:500], dtype=complex))
    np.testing.assert_allclose(rows[:, 2], y_ref.real, rtol=0, atol=1e-9)
    np.testing.assert_allclose(rows[:, 3], y_ref.imag, rtol=0, atol=1e-9)


def test_export_unfitted_raises(tmp_path):
    from padpd.pa import DDRVolterraModel
    with pytest.raises(ValueError):
        export_linear_coeffs(DDRVolterraModel(), 16, str(tmp_path / "x.json"))


def test_refvec_input_codes_are_the_quantized_input(fitted, tmp_path):
    """The appended code columns times 2**in_scale_exp are exactly the input
    FixedPointPolyModel quantized to, on the same block (PA_DPD#2)."""
    from padpd.deploy import quantize_symmetric
    x, _, ddr = fitted
    fp = FixedPointPolyModel(ddr, w_bits=16, sig_bits=16)
    p = tmp_path / "vectors.csv"
    export_reference_vectors(fp, x, str(p), n=500)
    assert p.read_text(encoding="utf-8").splitlines()[0] == \
        "i_in,q_in,i_out,q_out,i_in_code,q_in_code"
    rows = np.loadtxt(p, delimiter=",", skiprows=1)
    e_in = fp.scale_exponents(x[:500])["in_scale_exp"]
    codes = rows[:, 4] + 1j * rows[:, 5]
    assert np.all(codes.real == np.round(codes.real))
    np.testing.assert_array_equal(
        codes * 2.0 ** e_in,
        quantize_symmetric(np.asarray(x[:500], dtype=complex), 16))


def test_reference_vectors_of_other_models_keep_four_columns(fitted, tmp_path):
    """Neural / float models have no input codes: the layout is unchanged."""
    x, _, ddr = fitted
    p = tmp_path / "float.csv"
    export_reference_vectors(ddr, x, str(p), n=100)
    header = p.read_text(encoding="utf-8").splitlines()[0]
    assert header == "i_in,q_in,i_out,q_out"
    assert np.loadtxt(p, delimiter=",", skiprows=1).shape == (100, 4)


def test_scale_exponents_are_what_call_uses(fitted):
    """Every basis column FixedPointPolyModel quantizes is an exact integer
    multiple of 2**col_scale_exp[c] within the signed sig_bits range, and the
    exponent is the smallest that holds the column's peak (_pow2_step)."""
    from padpd.deploy import quantize_symmetric
    x, _, ddr = fitted
    fp = FixedPointPolyModel(ddr, w_bits=16, sig_bits=16)
    xb = np.asarray(x[:800], dtype=complex)
    m = fp.scale_exponents(xb)
    assert m["sig_bits"] == 16 and m["n_samples"] == 800
    phi = ddr.basis_matrix(quantize_symmetric(xb, 16))
    assert len(m["col_scale_exp"]) == phi.shape[1] == len(ddr.coeffs)
    qmax = 2 ** 15 - 1
    for c, e in enumerate(m["col_scale_exp"]):
        q = quantize_symmetric(phi[:, c], 16) / 2.0 ** e
        assert np.all(q.real == np.round(q.real)), c
        assert np.all(q.imag == np.round(q.imag)), c
        peak = max(np.abs(phi[:, c].real).max(), np.abs(phi[:, c].imag).max())
        assert peak <= qmax * 2.0 ** e and (peak > qmax * 2.0 ** (e - 1)
                                            or peak == 0), c
    _, _, e_w = _int_codes(ddr.coeffs, 16)
    assert m["acc_lsb_exp"] == e_w + min(m["col_scale_exp"])


def test_export_linear_coeffs_carries_fixed_point_meta(fitted, tmp_path):
    x, _, ddr = fitted
    fp = FixedPointPolyModel(ddr, w_bits=16, sig_bits=16)
    meta = fp.scale_exponents(x[:500])
    p = tmp_path / "coeffs.json"
    payload = export_linear_coeffs(ddr, 16, str(p), fixed_point_meta=meta)
    d = json.loads(p.read_text(encoding="utf-8"))
    assert payload == d
    assert d["fixed_point"]["in_scale_exp"] == meta["in_scale_exp"]
    assert d["fixed_point"]["col_scale_exp"] == meta["col_scale_exp"]
    assert "not quantized" in d["fixed_point"]["note"]
    # without meta the payload is exactly the old one (no new keys)
    d0 = export_linear_coeffs(ddr, 16, str(tmp_path / "c0.json"))
    assert "fixed_point" not in d0
