import numpy as np
import pytest

from padpd.deploy import FixedPointPolyModel, mac_cost, quantize_symmetric
from padpd.pa import (DDRVolterraModel, ReferencePA, ddr_volterra_default,
                      gmp_opendpd_510, nmse_db)
from padpd.waveform import OFDMConfig, generate_ofdm


@pytest.fixture(scope="module")
def pa_data():
    cfg = OFDMConfig(bandwidth_hz=80e6, qam_order=256, n_symbols=8, seed=11)
    x = generate_ofdm(cfg).x
    return x, ReferencePA()(x)


def test_quantize_range_and_step():
    rng = np.random.default_rng(0)
    x = rng.standard_normal(1000)
    xq = quantize_symmetric(x, 8)
    # only 2^8 distinct levels, all within the original peak (+1 step)
    assert len(np.unique(xq)) <= 256
    assert np.abs(xq).max() <= np.abs(x).max() * 1.01
    # step is a power of two
    steps = np.diff(np.unique(xq))
    step = steps[steps > 0].min()
    assert np.log2(step) == pytest.approx(round(np.log2(step)), abs=1e-9)


def test_quantize_more_bits_less_error():
    rng = np.random.default_rng(1)
    x = rng.standard_normal(5000) + 1j * rng.standard_normal(5000)
    errs = [nmse_db(x, quantize_symmetric(x, b)) for b in (6, 10, 16)]
    assert errs[0] > errs[1] > errs[2]
    # each extra bit ~ -6 dB; 16-bit is very clean
    assert errs[2] < -80


def test_fixedpoint_requires_fitted_model():
    with pytest.raises(ValueError):
        FixedPointPolyModel(DDRVolterraModel())


def test_fixedpoint_w16_close_to_float(pa_data):
    x, y = pa_data
    ddr = ddr_volterra_default().fit(x, y, regularization=1e-9)
    fp16 = FixedPointPolyModel(ddr, w_bits=16, sig_bits=16)
    # bit-true W16A16 barely degrades vs float model
    assert nmse_db(ddr(x), fp16(x)) < -55


def test_fixedpoint_degrades_gracefully(pa_data):
    x, y = pa_data
    ddr = ddr_volterra_default().fit(x, y, regularization=1e-9)
    nmse = {b: nmse_db(y, FixedPointPolyModel(ddr, b, b)(x))
            for b in (16, 12, 8)}
    # W16 is essentially lossless; degrades monotonically with fewer bits
    assert nmse[16] < -50
    assert nmse[16] < nmse[12] < nmse[8]
    # W12 still gives a useful DPD-grade model (industry uses W16)
    assert nmse[12] < -30


def test_ddr_quantizes_comparably_to_gmp(pa_data):
    x, y = pa_data
    ddr = ddr_volterra_default().fit(x, y, regularization=1e-9)
    gmp = gmp_opendpd_510().fit(x, y, regularization=1e-9)
    ddr12 = nmse_db(ddr(x), FixedPointPolyModel(ddr, 12, 12)(x))
    gmp12 = nmse_db(gmp(x), FixedPointPolyModel(gmp, 12, 12)(x))
    # both linear-params models quantize to a similar SQNR floor
    assert abs(ddr12 - gmp12) < 15


def test_mac_cost():
    c = mac_cost(140, 800e6)
    assert c["complex_macs_per_sample"] == 140
    assert c["real_macs_per_sample"] == 560
    assert c["real_gmac_per_s"] == pytest.approx(560 * 800e6 / 1e9)
