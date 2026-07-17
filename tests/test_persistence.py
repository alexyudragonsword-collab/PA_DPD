import numpy as np
import pytest

from padpd.dpd import ILAPredistorter
from padpd.pa import (GMPModel, MemoryPolynomialModel, ReferencePA, SalehPA,
                      load_model)


@pytest.fixture(scope="module")
def signal():
    rng = np.random.default_rng(0)
    x = (rng.standard_normal(20_000) + 1j * rng.standard_normal(20_000))
    return x / np.sqrt(2)


@pytest.mark.parametrize("factory", [
    lambda: MemoryPolynomialModel(order=5, memory_depth=3),
    lambda: GMPModel(order=5, memory_depth=4, lag_order=2, lag_memory=2,
                     lag_span=1, lead_order=2, lead_memory=2, lead_span=1),
])
def test_fitted_model_roundtrip(factory, signal, tmp_path):
    x = signal
    y = ReferencePA()(x)
    model = factory().fit(x, y)
    p = str(tmp_path / "model.npz")
    model.save(p)
    loaded = load_model(p)
    assert type(loaded) is type(model)
    assert loaded.get_config() == model.get_config()
    np.testing.assert_array_equal(loaded(x), model(x))


def test_saleh_roundtrip(signal, tmp_path):
    model = SalehPA(alpha_a=2.0, beta_a=1.1, alpha_p=3.0, beta_p=9.0)
    p = str(tmp_path / "saleh.npz")
    model.save(p)
    loaded = load_model(p)
    np.testing.assert_array_equal(loaded(signal), model(signal))


def test_ila_roundtrip(signal, tmp_path):
    pa = ReferencePA()
    dpd = ILAPredistorter(n_iterations=2).fit(pa, signal)
    p = str(tmp_path / "dpd.npz")
    dpd.save(p)
    loaded = ILAPredistorter.load(p)
    assert loaded.target_gain == dpd.target_gain
    np.testing.assert_array_equal(loaded(signal), dpd(signal))


def test_unfitted_ila_save_raises(tmp_path):
    with pytest.raises(RuntimeError):
        ILAPredistorter().save(str(tmp_path / "x.npz"))
