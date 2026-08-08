"""Direct-learning trainer for spline predistorters (torch).

ILA copies a post-inverse and assumes the copy composes; that assumption
measurably fails for post-PA additive impairments (counter-IM3), where
the injected correction rides the raw PA's *local* complex gain. Direct
learning sidesteps the copy entirely: fit a differentiable surrogate of
the whole TX chain (a widely-nonlinear spline model handles image / LO
leakage / C-IM3 at -46 dB class fidelity), then gradient-optimize the
predistorter coefficients through it,

    min_w  || surrogate( basis_pre(x) @ w ) - g*x ||^2 ,

exactly the DLA recipe (padpd.nn.DLAPredistorter) but with spline
models on both sides — linear-in-parameter structures, so the trained
result deploys through the existing LUT/RTL chain unchanged.

The torch B-spline twin here reproduces the numpy basis to machine
precision and is differentiable w.r.t. its *input* signal (knots and
surrogate coefficients stay frozen), which is all the chain rule needs.

Honest finding, measured on the C-IM3 TxFrontEndPA chain: the optimizer
converges cleanly, yet even *inside* the surrogate the cascade floors
near -35 dB — with exact gradients the bottleneck is the predistorter
STRUCTURE, not the algorithm: cancelling a conj(x)^3 spur through a
cubic PA spawns ever-higher phase harmonics that a basis truncated at
order 3 cannot chase. Direct learning still beats ILA (+1 dB over
ILA-M2, +3.6 dB over the conj-only DPD on held-out data), and the
structural ceiling it exposes is the actionable conclusion: past it,
fix the mixer (hardware harmonic reject) rather than the DSP.
"""

from __future__ import annotations

import numpy as np


def torch_spline_basis(model):
    """Differentiable torch twin of ``model.basis_matrix`` (spline family).

    ``model`` is a SplineMemoryPolynomial (any conjugate/cim3/dc_term
    combination). Returns ``basis(z: complex tensor) -> (N, n_coeffs)``
    complex tensor, matching the numpy basis to machine precision and
    differentiable w.r.t. ``z``.
    """
    import torch

    b = np.asarray(model.knots, dtype=float)
    deg = model.degree
    t = np.concatenate([np.full(deg, b[0]), b, np.full(deg, b[-1])])
    n_k = len(t)

    def bspline(r):
        r = torch.clamp(r, float(b[0]), float(b[-1]))
        cols = [((r >= t[i]) & (r < t[i + 1])).double()
                if t[i] < t[i + 1] else torch.zeros_like(r)
                for i in range(n_k - 1)]
        basis = torch.stack(cols, dim=1)
        last = n_k - deg - 2
        basis[:, last] = basis[:, last] + (r == float(b[-1])).double()
        for p in range(1, deg + 1):
            nxt = []
            for i in range(n_k - 1 - p):
                d1 = t[i + p] - t[i]
                d2 = t[i + p + 1] - t[i + 1]
                c = torch.zeros_like(r)
                if d1 > 0:
                    c = (r - float(t[i])) / d1 * basis[:, i]
                if d2 > 0:
                    c = c + (float(t[i + p + 1]) - r) / d2 * basis[:, i + 1]
                nxt.append(c)
            basis = torch.stack(nxt, dim=1)
        return basis

    def basis(z):
        blocks = []
        for order in model.branch_phase_orders()[::model.memory_depth]:
            for m in range(model.memory_depth):
                zm = z if m == 0 else torch.cat(
                    [torch.zeros(m, dtype=z.dtype), z[:-m]])
                cols = bspline(torch.abs(zm)).to(torch.complex128)
                if order == 1:
                    car = zm
                elif order == -1:
                    car = torch.conj(zm)
                else:
                    car = torch.conj(zm) ** 3
                blocks.append(car[:, None] * cols)
        if model.dc_term:
            blocks.append(torch.ones(len(z), 1, dtype=torch.complex128))
        return torch.cat(blocks, dim=1)

    return basis


def direct_learn_spline_dpd(predistorter, surrogate, x: np.ndarray,
                            target_gain: complex, epochs: int = 250,
                            lr: float = 1e-3, on_epoch=None):
    """Gradient-refine a spline predistorter through a spline surrogate.

    ``predistorter`` is a fitted SplineMemoryPolynomial (its coefficients
    are the starting point — warm-start from an ILA solution) and
    ``surrogate`` a fitted spline forward model of the full TX chain
    (fit it with conjugate/cim3/dc_term as the chain requires).
    Returns ``(model, history)``: a NEW predistorter of identical config
    with the direct-learned coefficients, and the per-epoch surrogate
    cascade NMSE (dB). Requires torch.
    """
    import torch

    if getattr(predistorter, "coeffs", None) is None \
            or getattr(surrogate, "coeffs", None) is None:
        raise ValueError("predistorter and surrogate must be fitted")
    xt = torch.tensor(np.asarray(x, dtype=complex))
    pre_cols = torch_spline_basis(predistorter)(xt)   # input fixed -> once
    sur_basis = torch_spline_basis(surrogate)
    w_sur = torch.tensor(surrogate.coeffs)
    w0 = torch.tensor(predistorter.coeffs)
    wr = torch.nn.Parameter(w0.real.clone())
    wi = torch.nn.Parameter(w0.imag.clone())
    opt = torch.optim.Adam([wr, wi], lr=lr)
    target = torch.tensor(complex(target_gain)) * xt
    tpow = float(np.mean(np.abs(complex(target_gain) * x) ** 2))

    history = []
    for ep in range(epochs):
        opt.zero_grad()
        z = pre_cols @ torch.complex(wr, wi)
        yhat = sur_basis(z) @ w_sur
        loss = torch.mean(torch.abs(yhat - target) ** 2) / tpow
        loss.backward()
        opt.step()
        nmse = float(10 * np.log10(max(loss.item(), 1e-30)))
        history.append(nmse)
        if on_epoch is not None:
            on_epoch({"epoch": ep, "cascade_nmse_db": nmse})

    out = type(predistorter)(**predistorter.get_config())
    out.coeffs = torch.complex(wr, wi).detach().numpy()
    return out, history
