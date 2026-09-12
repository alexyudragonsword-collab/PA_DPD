import numpy as np
import pytest

torch = pytest.importorskip("torch")

pytestmark = pytest.mark.slow  # minutes-long trainings; full CI lane only

from padpd.nn import NeuralPAModel, quantize_neural_ptq  # noqa: E402
from padpd.pa import ReferencePA, nmse_db  # noqa: E402
from padpd.waveform import OFDMConfig, generate_ofdm  # noqa: E402


@pytest.fixture(scope="module")
def trained():
    cfg = OFDMConfig(bandwidth_hz=20e6, qam_order=256, n_symbols=6, seed=42)
    x = generate_ofdm(cfg).x
    y = ReferencePA()(x)
    model = NeuralPAModel(backbone="tcn", hidden_size=16, n_epochs=30,
                          verbose=False, seed=0).fit(x, y)
    return x, y, model


def test_weight_ptq_w16_near_float(trained):
    x, y, model = trained
    q = quantize_neural_ptq(model, w_bits=16)
    # W16 weight PTQ barely changes the output
    assert nmse_db(model(x), q(x)) < -45


def test_ptq_degrades_with_fewer_bits(trained):
    x, y, model = trained
    err = {b: nmse_db(model(x), quantize_neural_ptq(model, w_bits=b)(x))
           for b in (16, 10, 6)}
    assert err[16] < err[10] < err[6]


def test_tcn_activation_ptq_runs(trained):
    x, y, model = trained
    q = quantize_neural_ptq(model, w_bits=12, a_bits=12)
    out = q(x)
    assert out.shape == x.shape
    # still a usable model at W12A12 (TCN is fully bit-true here)
    assert nmse_db(y, out) < nmse_db(y, x)  # better than identity


def test_ptq_does_not_mutate_original(trained):
    x, y, model = trained
    before = model(x).copy()
    quantize_neural_ptq(model, w_bits=8, a_bits=8)(x)
    np.testing.assert_array_equal(model(x), before)
