"""Phase 4: differentiable PA/DPD co-design by gradient descent.

The grid sweep in ``codesign.py`` searches PA operating points discretely.
Here the PA operating point is a *learnable* parameter and the DPD is a
differentiable module, so a single gradient descent jointly adapts both
against one objective: minimize linearity error while rewarding
efficiency. This is the "AI-native" step - the design parameter is
optimized by autograd, not enumerated.

Requires torch. The PA is a differentiable Saleh model whose ``drive``
(operating point) carries gradients; efficiency is a Class-B-like proxy
that rises with drive, so the optimizer trades linearity against
efficiency and settles at a balanced co-design point.
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn


def _delay(x: torch.Tensor, m: int) -> torch.Tensor:
    if m == 0:
        return x
    return torch.cat([x.new_zeros(m), x[:-m]])


class DiffSalehPA(nn.Module):
    """Differentiable Saleh PA with a learnable operating point (drive)."""

    def __init__(self, drive_init: float = 0.14, eta_max: float = 0.70,
                 alpha_a: float = 2.1587, beta_a: float = 1.1517,
                 alpha_p: float = 4.0033, beta_p: float = 9.1040,
                 learnable: bool = True):
        super().__init__()
        v = torch.log(torch.tensor(float(drive_init)))
        self.log_drive = nn.Parameter(v) if learnable else \
            self.register_buffer("_ld", v) or v
        self.eta_max = eta_max
        for k, val in dict(alpha_a=alpha_a, beta_a=beta_a,
                           alpha_p=alpha_p, beta_p=beta_p).items():
            self.register_buffer(k, torch.tensor(float(val)))

    @property
    def drive(self) -> torch.Tensor:
        return torch.exp(self.log_drive if isinstance(self.log_drive,
                                                      nn.Parameter)
                         else self._ld)

    def _raw(self, x: torch.Tensor, drive: torch.Tensor) -> torch.Tensor:
        u = drive * x
        r = u.abs()
        amp = self.alpha_a * r / (1 + self.beta_a * r ** 2)
        phase = self.alpha_p * r ** 2 / (1 + self.beta_p * r ** 2)
        unit = torch.where(r > 0, u / torch.clamp(r, min=1e-12),
                           torch.zeros_like(u))
        return amp * unit * torch.exp(1j * phase)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        drive = self.drive
        v = self._raw(x, drive)
        return v / (drive * self.alpha_a)  # normalize small-signal gain -> ~x

    def efficiency(self, x: torch.Tensor) -> torch.Tensor:
        """Class-B-like average efficiency proxy in [0, eta_max]; rises
        with drive as the raw output approaches saturation."""
        v = self._raw(x, self.drive)
        p_avg = (v.abs() ** 2).mean()
        a_max = self.alpha_a / (2 * torch.sqrt(self.beta_a))  # Saleh peak
        return self.eta_max * torch.sqrt(p_avg) / a_max


class DiffMPDPD(nn.Module):
    """Differentiable memory-polynomial predistorter (complex coeffs)."""

    def __init__(self, order: int = 5, memory: int = 4):
        super().__init__()
        self.order = order
        self.memory = memory
        n = order * memory
        wr = torch.zeros(n)
        wr[0] = 1.0  # identity init: output ~= input
        self.wr = nn.Parameter(wr)
        self.wi = nn.Parameter(torch.zeros(n))

    def _basis(self, x: torch.Tensor) -> torch.Tensor:
        a = x.abs()
        cols = []
        for m in range(self.memory):
            xm, am = _delay(x, m), _delay(a, m)
            for k in range(self.order):
                cols.append(xm * am ** k)
        return torch.stack(cols, dim=-1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        w = torch.complex(self.wr, self.wi)
        return self._basis(x) @ w

    @property
    def n_coeffs(self) -> int:
        return self.order * self.memory


def _mp_basis_torch(x: torch.Tensor, order: int, memory: int) -> torch.Tensor:
    a = x.abs()
    cols = []
    for m in range(memory):
        xm, am = _delay(x, m), _delay(a, m)
        for k in range(order):
            cols.append(xm * am ** k)
    return torch.stack(cols, dim=-1)


def _ls_predistort(pa: DiffSalehPA, x: torch.Tensor, order: int,
                   memory: int, reg: float) -> torch.Tensor:
    """Least-squares ILA predistortion, differentiable w.r.t. the PA drive.

    Fits the post-inverse w = argmin ||Phi(y) w - x||^2 via the (complex)
    normal equations solved with torch.linalg.solve (autograd-friendly),
    then predistorts x. The DPD is always LS-optimal for the current
    drive, so the outer gradient sees a clean efficiency-vs-linearity
    landscape without SGD noise on the DPD.
    """
    y = pa(x)
    phi_y = _mp_basis_torch(y, order, memory)
    a = phi_y.conj().transpose(-2, -1) @ phi_y
    a = a + reg * torch.eye(a.shape[0], dtype=a.dtype)
    b = phi_y.conj().transpose(-2, -1) @ x
    w = torch.linalg.solve(a, b)
    return _mp_basis_torch(x, order, memory) @ w


def joint_codesign(x: np.ndarray, drive_init: float = 0.10,
                   evm_spec_db: float = -40.0, lambda_eff: float = 1.0,
                   penalty: float = 50.0, order: int = 5, memory: int = 4,
                   steps: int = 200, lr: float = 3e-2, reg: float = 1e-6,
                   learnable_drive: bool = True, seed: int = 0):
    """Differentiable joint optimization of the PA operating point.

    Inner loop: the DPD is solved in closed form (LS) at the current drive
    - always optimal, differentiable. Outer loop: gradient descent on the
    PA drive against a spec-constrained objective

        penalty * relu(lin / lin_spec - 1)  -  lambda_eff * efficiency

    so the drive climbs for efficiency until EVM meets the spec boundary.
    ``lambda_eff`` sweeps the efficiency-linearity trade-off (a larger
    value accepts a higher-drive, higher-efficiency operating point).
    With ``learnable_drive=False`` the drive is frozen (baseline).
    """
    torch.manual_seed(seed)
    xt = torch.as_tensor(np.asarray(x, dtype=np.complex64))
    energy = (xt.abs() ** 2).mean()
    lin_spec = energy * (10.0 ** (evm_spec_db / 10.0))

    pa = DiffSalehPA(drive_init=drive_init, learnable=learnable_drive)
    hist = {"evm_db": [], "eff": [], "drive": []}

    if learnable_drive:
        opt = torch.optim.Adam([pa.log_drive], lr=lr)
        for _ in range(steps):
            opt.zero_grad()
            u = _ls_predistort(pa, xt, order, memory, reg)
            lin = ((pa(u) - xt).abs() ** 2).mean()
            eff = pa.efficiency(xt)
            (penalty * torch.relu(lin / lin_spec - 1.0)
             - lambda_eff * eff).backward()
            opt.step()
            with torch.no_grad():
                hist["evm_db"].append(float(10 * torch.log10(lin / energy)))
                hist["eff"].append(float(eff))
                hist["drive"].append(float(pa.drive))

    with torch.no_grad():
        u = _ls_predistort(pa, xt, order, memory, reg)
        lin = ((pa(u) - xt).abs() ** 2).mean()
        return {"drive": float(pa.drive),
                "efficiency": float(pa.efficiency(xt)),
                "evm_db": float(10 * torch.log10(lin / energy)),
                "n_coeffs": order * memory, "history": hist}
