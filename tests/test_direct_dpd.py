"""Direct-learning spline DPD (gradient through a spline surrogate)."""

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from padpd.dpd import (  # noqa: E402
    ILAPredistorter,
    direct_learn_spline_dpd,
    torch_spline_basis,
)
from padpd.pa import (  # noqa: E402
    ReferencePA,
    SplineMemoryPolynomial,
    TxFrontEndPA,
    nmse_db,
)
from padpd.waveform import OFDMConfig, generate_ofdm  # noqa: E402


@pytest.fixture(scope="module")
def chain():
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                  n_symbols=6, seed=0))
    wf2 = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                   n_symbols=6, seed=1))
    x, xv = wf.x, wf2.x
    pa = TxFrontEndPA(ReferencePA(drive=0.14), cim3_dbc=-32.0)
    y = pa(x)
    g = complex(np.vdot(x, y) / np.vdot(x, x))
    sur = SplineMemoryPolynomial.from_signal(
        x, n_knots=8, memory_depth=4, conjugate=True, cim3=True,
        dc_term=True, headroom=1.6).fit(x, y, regularization=1e-9)
    return x, xv, pa, g, sur


def test_torch_basis_matches_numpy(chain):
    x, _, _, _, sur = chain
    xt = torch.tensor(x[:6000])
    tw = (torch_spline_basis(sur)(xt)
          @ torch.tensor(sur.coeffs)).detach().numpy()
    assert nmse_db(sur(x[:6000]), tw) < -250      # machine precision


def test_torch_basis_is_differentiable(chain):
    x, _, _, _, sur = chain
    z = torch.tensor(x[:512], requires_grad=True)
    out = torch_spline_basis(sur)(z) @ torch.tensor(sur.coeffs)
    torch.abs(out).sum().backward()
    assert z.grad is not None and torch.all(torch.isfinite(z.grad.real))


@pytest.mark.slow
def test_direct_learning_beats_ila_on_cim3_chain(chain):
    """The headline: exact gradients through the chain buy what ILA's
    copy assumption cannot, on held-out data."""
    x, xv, pa, g, sur = chain
    ila = ILAPredistorter(lambda: SplineMemoryPolynomial.from_signal(
        x, n_knots=8, memory_depth=4, conjugate=True, cim3=True,
        dc_term=True, headroom=1.3), n_iterations=2,
        fit_kwargs={"regularization": 1e-9})
    ila.fit(pa, x)
    refined, hist = direct_learn_spline_dpd(ila.dpd_model, sur, x, g,
                                            epochs=200, lr=1e-3)
    assert hist[-1] < hist[0] - 2                 # optimizer made progress
    assert refined.get_config() == ila.dpd_model.get_config()

    def lin(model, sig):
        y = pa(model(sig))
        gg = np.vdot(sig, y) / np.vdot(sig, sig)
        return nmse_db(gg * sig, y)

    assert lin(refined, xv) < lin(ila.dpd_model, xv) - 0.5


def test_direct_learning_smoke_and_validation(chain):
    x, _, _, g, sur = chain
    pre = SplineMemoryPolynomial.from_signal(x, n_knots=6, memory_depth=2)
    with pytest.raises(ValueError):
        direct_learn_spline_dpd(pre, sur, x, g)   # unfitted predistorter
    pre.coeffs = pre.passthrough_coeffs()
    seen = []
    refined, hist = direct_learn_spline_dpd(
        pre, sur, x[:8000], g, epochs=3,
        on_epoch=lambda h: seen.append(h["epoch"]))
    assert len(hist) == 3 and seen == [0, 1, 2]
    assert np.all(np.isfinite(refined.coeffs))
