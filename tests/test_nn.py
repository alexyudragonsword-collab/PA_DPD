import numpy as np
import pytest

torch = pytest.importorskip("torch")

pytestmark = pytest.mark.slow  # minutes-long trainings; full CI lane only

from padpd.nn import (  # noqa: E402
    DGRUBackbone,
    DLAPredistorter,
    FrameDataset,
    GRUBackbone,
    NeuralPAModel,
    TCNBackbone,
    complex_to_iq,
    count_params,
    iq_features,
    iq_to_complex,
)
from padpd.pa import MemoryPolynomialModel, ReferencePA, nmse_db  # noqa: E402
from padpd.waveform import OFDMConfig, generate_ofdm  # noqa: E402


@pytest.fixture(scope="module")
def pa_data():
    cfg = OFDMConfig(bandwidth_hz=20e6, qam_order=256, n_symbols=6, seed=42)
    x = generate_ofdm(cfg).x
    return x, ReferencePA()(x)


def test_iq_conversion_roundtrip():
    rng = np.random.default_rng(0)
    x = rng.standard_normal(100) + 1j * rng.standard_normal(100)
    np.testing.assert_allclose(iq_to_complex(complex_to_iq(x)), x,
                               rtol=1e-6)


def test_iq_features_values():
    x = torch.tensor([[3.0, 4.0]])
    f = iq_features(x).numpy()[0]
    # [I, Q, |x|, |x|^3, sin, cos]
    np.testing.assert_allclose(f, [3, 4, 5, 125, 0.8, 0.6], rtol=1e-6)


def test_frame_dataset_shapes():
    rng = np.random.default_rng(1)
    x = rng.standard_normal(1000) + 1j * rng.standard_normal(1000)
    ds = FrameDataset(x, 2 * x, frame_length=50, stride=10)
    assert len(ds) == (1000 - 50) // 10 + 1
    fx, fy = ds[3]
    assert fx.shape == (50, 2) and fy.shape == (50, 2)
    np.testing.assert_allclose(fy.numpy(), 2 * fx.numpy(), rtol=1e-6)


def test_backbone_shapes_and_params():
    x = torch.randn(4, 32, 2)
    for net in (GRUBackbone(hidden_size=11), DGRUBackbone(hidden_size=8),
                TCNBackbone(hidden_size=16)):
        out = net(x)
        assert out.shape == (4, 32, 2)
        assert count_params(net) > 0
    # OpenDPD reference: dgru H8 ~= 500 params
    assert 400 < count_params(DGRUBackbone(hidden_size=8)) < 600


def test_tcn_learns_nonlinearity(pa_data):
    x, y = pa_data
    model = NeuralPAModel(backbone="tcn", hidden_size=16, n_epochs=30,
                          verbose=False, seed=0)
    model.fit(x, y)
    assert nmse_db(y, model(x)) < -25


@pytest.fixture(scope="module")
def trained_pa(pa_data):
    x, y = pa_data
    model = NeuralPAModel(backbone="dgru", hidden_size=8, n_epochs=60,
                          verbose=False, seed=0)
    return model.fit(x, y)


def test_neural_pa_learns(pa_data, trained_pa):
    x, y = pa_data
    nmse = nmse_db(y, trained_pa(x))
    assert nmse < -28  # learns the nonlinearity well
    # better than a linear (memoryless, order-1) fit
    linear = MemoryPolynomialModel(order=1, memory_depth=1).fit(x, y)
    assert nmse < nmse_db(y, linear(x)) - 5


def test_neural_pa_save_load(trained_pa, pa_data, tmp_path):
    x, _ = pa_data
    p = str(tmp_path / "pa.pt")
    trained_pa.save(p)
    loaded = NeuralPAModel.load(p)
    np.testing.assert_allclose(loaded(x), trained_pa(x), rtol=1e-5)


def test_dla_dpd_improves_linearity(pa_data, trained_pa, tmp_path):
    x, y = pa_data
    dpd = DLAPredistorter(backbone="dgru", hidden_size=8, n_epochs=60,
                          verbose=False, seed=0)
    dpd.fit(trained_pa, x)
    g = dpd.target_gain
    e_raw = nmse_db(g * x, trained_pa(x))
    e_dpd = nmse_db(g * x, trained_pa(dpd(x)))
    assert e_dpd < e_raw - 5  # cascade is linearized vs no DPD

    p = str(tmp_path / "dpd.pt")
    dpd.save(p)
    loaded = DLAPredistorter.load(p)
    np.testing.assert_allclose(loaded(x), dpd(x), rtol=1e-5)
    assert loaded.target_gain == pytest.approx(g)


def test_neural_pa_works_with_classical_ila(pa_data, trained_pa):
    """NeuralPAModel is a drop-in pa callable for the classical ILA."""
    from padpd.dpd import ILAPredistorter
    x, _ = pa_data
    ila = ILAPredistorter(n_iterations=1).fit(trained_pa, x)
    g = ila.target_gain
    e_raw = nmse_db(g * x, trained_pa(x))
    e_dpd = nmse_db(g * x, ila.linearize(trained_pa, x))
    assert e_dpd < e_raw


def test_iq_features_zero_sample_produces_no_nan():
    from padpd.nn.features import iq_features
    x = torch.tensor([[0.0, 0.0], [0.3, -0.4]])
    f = iq_features(x)
    assert torch.isfinite(f).all()
    # sin/cos of the zero sample are 0, not NaN
    assert f[0, 4] == 0.0 and f[0, 5] == 0.0
    # nonzero sample unchanged: cos = i/|x| = 0.6, sin = q/|x| = -0.8
    assert torch.allclose(f[1, 5], torch.tensor(0.6), atol=1e-6)
    assert torch.allclose(f[1, 4], torch.tensor(-0.8), atol=1e-6)
