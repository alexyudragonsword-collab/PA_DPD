"""Adaptive / online DPD over a linear-in-parameters basis.

Batch ILA (:class:`~padpd.dpd.ila.ILAPredistorter`) identifies the
predistorter once. A shipped product instead adapts continuously from a
TX->coupler->RX loopback so the DPD tracks PA drift (temperature,
supply, aging). Because GMP/DDR/MP are linear in their coefficients, the
indirect-learning update reduces to a recursive linear estimator on the
post-inverse regressors:

    drive PA with u = DPD(x);  observe y;  target G in y ~= G*x
    post-inverse regressors  Phi = basis(y / G),   target = u
    reduce  || u - Phi @ w ||  and apply  DPD(x) = basis(x) @ w

The update is exponentially-weighted recursive least squares in block
covariance form: ``R = ff*R + Phi^H Phi`` and ``p = ff*p + Phi^H u``,
solved as ``w = (R + ridge*I)^{-1} p`` each block. The forgetting factor
``ff`` sets the tracking memory (smaller = faster tracking, noisier).

Only RLS is offered: plain LMS/NLMS diverges on this basis. The |x|^k
polynomial columns give the regressor covariance a condition number on
the order of 1e10, so gradient-descent steps (even whitened by the
warm-up covariance) are unstable — the same reason batch fitting uses
closed-form least squares rather than SGD. RLS tracks because it
implicitly inverts that covariance every block.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from ..pa.base import PAModel
from ..pa.gmp import GMPModel


class AdaptiveDPD:
    def __init__(self, model_factory: Callable[[], PAModel] | None = None,
                 target_gain: complex | None = None,
                 forget: float = 0.995, ridge: float = 1e-6,
                 method: str = "rls"):
        if method != "rls":
            raise ValueError(
                "only 'rls' is supported; LMS/NLMS diverge on the "
                "ill-conditioned polynomial DPD basis (see module docstring)")
        self.template = (model_factory or GMPModel)()
        if not hasattr(self.template, "basis_matrix"):
            raise TypeError("adaptive DPD needs a linear-in-params model "
                            "with basis_matrix() (GMP/DDR/MP)")
        self.method = method
        self.target_gain = target_gain
        self.forget = float(forget)
        self.ridge = float(ridge)
        self.w: np.ndarray | None = None
        self._R: np.ndarray | None = None   # RLS covariance
        self._p: np.ndarray | None = None   # RLS cross term

    @property
    def n_coeffs(self) -> int:
        return self.template.n_coeffs

    def _phi(self, x: np.ndarray) -> np.ndarray:
        return self.template.basis_matrix(x)

    def _init(self, n: int) -> None:
        if self.w is None:
            self.w = np.zeros(n, dtype=complex)
            self.w[0] = 1.0                      # start from pass-through
            self._R = np.zeros((n, n), dtype=complex)
            self._p = np.zeros(n, dtype=complex)

    def predistort(self, x: np.ndarray) -> np.ndarray:
        if self.w is None:
            return np.asarray(x, dtype=complex)
        return self._phi(x) @ self.w

    __call__ = predistort

    def update(self, pa: Callable[[np.ndarray], np.ndarray],
               x: np.ndarray) -> dict:
        """Run one adaptation block against ``pa``; returns block metrics.

        ``pa`` may change between calls (a drifting PA) — that is the
        point. Returns ``{"resid_db", "gain_db", "coeff_norm"}`` where
        ``resid_db`` is the post-inverse fit residual (a proxy for how
        well the DPD currently matches the PA).
        """
        u = self.predistort(x)
        y = pa(u)
        if self.target_gain is None:
            self.target_gain = complex(np.vdot(x, y) / np.vdot(x, x))
        phi = self._phi(y / self.target_gain)
        self._init(phi.shape[1])

        self._R = self.forget * self._R + phi.conj().T @ phi
        self._p = self.forget * self._p + phi.conj().T @ u
        n = self._R.shape[0]
        lam = self.ridge * np.trace(self._R).real / max(n, 1)
        self.w = np.linalg.solve(self._R + lam * np.eye(n), self._p)

        resid = u - phi @ self.w
        return {
            "resid_db": 10 * np.log10(
                float(np.mean(np.abs(resid) ** 2)
                      / (np.mean(np.abs(u) ** 2) + 1e-30)) + 1e-30),
            "gain_db": 20 * np.log10(abs(self.target_gain) + 1e-30),
            "coeff_norm": float(np.linalg.norm(self.w)),
        }

    def warm_start(self, pa: Callable[[np.ndarray], np.ndarray],
                   x: np.ndarray, blocks: int = 3) -> dict:
        """Converge from pass-through with a few blocks on a static PA."""
        info = {}
        for _ in range(blocks):
            info = self.update(pa, x)
        return info

    def as_model(self) -> PAModel:
        """Freeze the current coefficients into a plain PAModel."""
        m = type(self.template)(**self.template.get_config())
        m.coeffs = None if self.w is None else self.w.copy()
        return m

    def save(self, path: str) -> None:
        if self.w is None:
            raise RuntimeError("nothing to save; run update() first")
        np.savez(path, class_name=type(self.template).__name__,
                 config=repr(self.template.get_config()), coeffs=self.w,
                 target_gain=np.complex128(self.target_gain),
                 method=self.method)
