import numpy as np
import pytest

from padpd.dpd import ILAPredistorter
from padpd.pa import (GMPModel, MemoryPolynomialModel, ReferencePA, SalehPA,
                      SplineGMP, SplineMemoryPolynomial, load_model)


@pytest.fixture(scope="module")
def signal():
    rng = np.random.default_rng(0)
    x = (rng.standard_normal(20_000) + 1j * rng.standard_normal(20_000))
    return x / np.sqrt(2)


@pytest.mark.parametrize("factory", [
    lambda: MemoryPolynomialModel(order=5, memory_depth=3),
    lambda: GMPModel(order=5, memory_depth=4, lag_order=2, lag_memory=2,
                     lag_span=1, lead_order=2, lead_memory=2, lead_span=1),
    lambda: SplineMemoryPolynomial(knots=[0.0, 0.2, 0.45, 0.7, 1.1],
                                   degree=3, memory_depth=3),
    lambda: SplineMemoryPolynomial(knots=[0.0, 0.3, 0.7, 1.1], degree=2,
                                   memory_depth=2, conjugate=True),
    lambda: SplineGMP(knots=[0.0, 0.25, 0.55, 1.1], degree=2,
                      memory_depth=3, lag_memory=2, lag_span=1,
                      lead_memory=1, lead_span=1),
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


def test_ila_load_restores_factory_and_iterations(tmp_path):
    """A loaded predistorter refit must keep the saved structure, not
    silently fall back to the default GMP factory / 2 iterations."""
    from padpd.dpd import ILAPredistorter
    from padpd.pa import DDRVolterraModel, ReferencePA
    from padpd.waveform import OFDMConfig, generate_ofdm
    x = generate_ofdm(OFDMConfig(bandwidth_hz=20e6, qam_order=256,
                                 n_symbols=4, seed=0)).x
    pa = ReferencePA(drive=0.12)
    dpd = ILAPredistorter(
        model_factory=lambda: DDRVolterraModel(order=5, memory_depth=3,
                                               dynamic_order=1),
        n_iterations=3)
    dpd.fit(pa, x)
    p = tmp_path / "dpd.npz"
    dpd.save(str(p))
    loaded = ILAPredistorter.load(str(p))
    assert loaded.n_iterations == 3
    assert type(loaded.model_factory()).__name__ == "DDRVolterraModel"
    import numpy as np
    assert np.allclose(loaded(x[:2048]), dpd(x[:2048]))


def test_adaptive_dpd_save_load_roundtrip(tmp_path):
    from padpd.dpd import AdaptiveDPD
    from padpd.pa import GMPModel, ReferencePA
    from padpd.waveform import OFDMConfig, generate_ofdm
    import numpy as np
    x = generate_ofdm(OFDMConfig(bandwidth_hz=20e6, qam_order=256,
                                 n_symbols=4, seed=0)).x
    pa = ReferencePA(drive=0.14)
    dpd = AdaptiveDPD(lambda: GMPModel(order=5, memory_depth=3),
                      method="apa", forget=0.9)
    dpd.warm_start(pa, x, blocks=3)
    p = tmp_path / "adpd.npz"
    dpd.save(str(p))
    loaded = AdaptiveDPD.load(str(p))
    assert loaded.method == "apa"
    assert np.allclose(loaded(x[:2048]), dpd(x[:2048]))
    loaded.update(pa, x)                     # adaptation still works
    assert np.all(np.isfinite(loaded.w))
