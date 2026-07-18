import json

import numpy as np
import pytest

from padpd.deploy import (FixedPointPolyModel, export_linear_coeffs,
                          export_reference_vectors)
from padpd.deploy.export import _int_codes
from padpd.pa import ddr_volterra_default, ReferencePA, nmse_db
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
    d = json.load(open(p))
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
    assert rows.shape == (500, 4)
    # the dumped output equals the fixed-point model's output
    y_ref = fp(np.asarray(x[:500], dtype=complex))
    np.testing.assert_allclose(rows[:, 2], y_ref.real, rtol=0, atol=1e-9)
    np.testing.assert_allclose(rows[:, 3], y_ref.imag, rtol=0, atol=1e-9)


def test_export_unfitted_raises(tmp_path):
    from padpd.pa import DDRVolterraModel
    with pytest.raises(ValueError):
        export_linear_coeffs(DDRVolterraModel(), 16, str(tmp_path / "x.json"))
