import numpy as np
import pytest

from padpd.pa import (DDRVolterraModel, ddr_volterra_default, load_model,
                      nmse_db)
from padpd.pa import MemoryPolynomialModel
from padpd.waveform import OFDMConfig, generate_ofdm
from padpd.pa import ReferencePA


@pytest.fixture(scope="module")
def pa_data():
    cfg = OFDMConfig(bandwidth_hz=80e6, qam_order=256, n_symbols=8, seed=11)
    x = generate_ofdm(cfg).x
    return x, ReferencePA()(x)


def test_config_and_coeff_count():
    m1 = DDRVolterraModel(order=5, memory_depth=4, dynamic_order=1)
    m2 = DDRVolterraModel(order=5, memory_depth=4, dynamic_order=2)
    # r=2 strictly adds basis columns over r=1
    assert m2.n_coeffs > m1.n_coeffs
    # coeff count matches the actual basis matrix width
    x = np.ones(20, dtype=complex)
    assert m1.basis_matrix(x).shape[1] == m1.n_coeffs
    assert m1.get_config()["dynamic_order"] == 1


def test_invalid_dynamic_order():
    with pytest.raises(ValueError):
        DDRVolterraModel(dynamic_order=3)


def test_fits_reference_pa(pa_data):
    x, y = pa_data
    ddr = ddr_volterra_default().fit(x, y)
    assert nmse_db(y, ddr(x)) < -35


def test_ddr_beats_plain_mp(pa_data):
    x, y = pa_data
    mp = MemoryPolynomialModel(order=5, memory_depth=15).fit(x, y)
    ddr = DDRVolterraModel(order=5, memory_depth=15,
                           dynamic_order=1).fit(x, y)
    # cross terms should help vs the diagonal-only MP at similar memory
    assert nmse_db(y, ddr(x)) <= nmse_db(y, mp(x))


def test_dynamic_order2_not_worse(pa_data):
    x, y = pa_data
    e1 = nmse_db(y, DDRVolterraModel(order=5, memory_depth=6,
                                     dynamic_order=1).fit(x, y)(x))
    e2 = nmse_db(y, DDRVolterraModel(order=5, memory_depth=6,
                                     dynamic_order=2).fit(x, y)(x))
    assert e2 <= e1 + 0.5  # richer basis does not hurt the fit


def test_generalizes(pa_data):
    x_train, y_train = pa_data
    cfg = OFDMConfig(bandwidth_hz=80e6, qam_order=256, n_symbols=8, seed=99)
    x_val = generate_ofdm(cfg).x
    y_val = ReferencePA()(x_val)
    ddr = ddr_volterra_default().fit(x_train, y_train)
    assert nmse_db(y_val, ddr(x_val)) < -35


def test_save_load_roundtrip(pa_data, tmp_path):
    x, y = pa_data
    ddr = DDRVolterraModel(order=5, memory_depth=4,
                           dynamic_order=2).fit(x, y)
    p = str(tmp_path / "ddr.npz")
    ddr.save(p)
    loaded = load_model(p)
    assert type(loaded) is DDRVolterraModel
    assert loaded.get_config() == ddr.get_config()
    np.testing.assert_array_equal(loaded(x), ddr(x))


def test_unfitted_raises():
    with pytest.raises(RuntimeError):
        DDRVolterraModel()(np.zeros(10, dtype=complex))
