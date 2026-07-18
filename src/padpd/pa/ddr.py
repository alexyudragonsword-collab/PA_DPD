"""Dynamic Deviation Reduction (DDR) Volterra model.

Zhu, Pedro & Brazil, "Dynamic Deviation Reduction-Based Volterra
Behavioral Modeling of RF Power Amplifiers," IEEE TMTT 2006.

The full Volterra series is intractable (coefficient count grows as
(M+1)^P). DDR reorganizes the kernels by *dynamic order* r = the number
of factors evaluated at a nonzero lag, then truncates at a low r. The
physical justification: PA memory is a weak dynamic effect, so terms with
many simultaneously-deviating delays contribute negligibly.

This sits between GMP and full Volterra: more systematic cross-term
coverage than GMP's hand-picked lag/lead set, yet parameter count grows
polynomially (not exponentially) with memory, and the model stays linear
in its coefficients -> least-squares closed form (reuses ``lstsq_fit``).

Basis (signal factor x(.), envelope factors |x(.)| = a(.); K = order,
M = memory_depth):

  r=0 (static):    x(n) a(n)^k                              k=0..K-1
  r=1 signal:      x(n-m) a(n)^k                            m=1..M, k=0..K-1
  r=1 envelope:    x(n) a(n-m) a(n)^k                       m=1..M, k=0..K-2
  r=2 signal:      x(n-m1) a(n-m2) a(n)^k                   m1,m2=1..M, k=0..K-2
  r=2 envelope:    x(n) a(n-m1) a(n-m2) a(n)^k              1<=m1<=m2<=M, k=0..K-3

``dynamic_order`` selects the highest r kept (1 or 2). r=0 is always
included; r=1 is the workhorse (captures the dominant memory effect).
"""

from __future__ import annotations

from itertools import combinations_with_replacement

import numpy as np

from .base import PAModel, lstsq_fit
from .memory_polynomial import delayed


class DDRVolterraModel(PAModel):
    def __init__(self, order: int = 5, memory_depth: int = 4,
                 dynamic_order: int = 1):
        if dynamic_order not in (1, 2):
            raise ValueError("dynamic_order must be 1 or 2")
        self.order = order
        self.memory_depth = memory_depth
        self.dynamic_order = dynamic_order
        self.coeffs: np.ndarray | None = None

    def get_config(self) -> dict:
        return {"order": self.order, "memory_depth": self.memory_depth,
                "dynamic_order": self.dynamic_order}

    def basis_matrix(self, x: np.ndarray) -> np.ndarray:
        K, M = self.order, self.memory_depth
        a = np.abs(x)
        xd = [delayed(x, m) for m in range(M + 1)]   # signal at lag 0..M
        ad = [delayed(a, m) for m in range(M + 1)]   # envelope at lag 0..M
        a0 = ad[0]
        cols = []

        # r = 0 : static nonlinearity
        for k in range(K):
            cols.append(xd[0] * a0**k)

        # r = 1 : one factor at nonzero lag
        for m in range(1, M + 1):
            for k in range(K):                       # delayed signal
                cols.append(xd[m] * a0**k)
            for k in range(K - 1):                   # one delayed envelope
                cols.append(xd[0] * ad[m] * a0**k)

        # r = 2 : two factors at nonzero lag
        if self.dynamic_order >= 2:
            for m1 in range(1, M + 1):               # delayed signal + env
                for m2 in range(1, M + 1):
                    for k in range(K - 1):
                        cols.append(xd[m1] * ad[m2] * a0**k)
            for m1, m2 in combinations_with_replacement(  # two delayed env
                    range(1, M + 1), 2):
                for k in range(K - 2):
                    cols.append(xd[0] * ad[m1] * ad[m2] * a0**k)

        return np.stack(cols, axis=1)

    @property
    def n_coeffs(self) -> int:
        return self.basis_matrix(np.ones(self.memory_depth + 2,
                                          dtype=complex)).shape[1]

    def fit(self, x: np.ndarray, y: np.ndarray,
            regularization: float = 0.0) -> "DDRVolterraModel":
        self.coeffs = lstsq_fit(self.basis_matrix(x), y, regularization)
        return self

    def __call__(self, x: np.ndarray) -> np.ndarray:
        if self.coeffs is None:
            raise RuntimeError("model is not fitted; call fit(x, y) first")
        return self.basis_matrix(x) @ self.coeffs
