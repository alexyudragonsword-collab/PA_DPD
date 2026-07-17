"""Indirect Learning Architecture (ILA) digital predistortion.

Classic industrial flow:

    1. Drive the PA with u(n) (initially u = x).
    2. Fit a post-inverse model:  y(n)/G  ->  u(n)   (G = target linear gain)
    3. Copy the post-inverse in front of the PA as the predistorter and
       iterate with u = DPD(x).

The predistorter can be any trainable :class:`~padpd.pa.PAModel`
(GMP by default). The ``pa`` argument is a black box callable — the
ReferencePA today, a Cadence/measurement replay tomorrow.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from ..pa.base import PAModel
from ..pa.gmp import GMPModel


class ILAPredistorter:
    def __init__(self, model_factory: Callable[[], PAModel] | None = None,
                 n_iterations: int = 2):
        self.model_factory = model_factory or GMPModel
        self.n_iterations = n_iterations
        self.dpd_model: PAModel | None = None
        self.target_gain: complex | None = None

    def fit(self, pa: Callable[[np.ndarray], np.ndarray],
            x: np.ndarray) -> "ILAPredistorter":
        """Learn the predistorter against a black-box PA on signal ``x``."""
        u = x
        for it in range(self.n_iterations):
            y = pa(u)
            if it == 0:
                # Target linear gain: least-squares scalar of the first pass.
                self.target_gain = complex(np.vdot(x, y) / np.vdot(x, x))
            model = self.model_factory()
            model.fit(y / self.target_gain, u)
            self.dpd_model = model
            u = model(x)
        return self

    def __call__(self, x: np.ndarray) -> np.ndarray:
        """Predistort a signal."""
        if self.dpd_model is None:
            raise RuntimeError("predistorter is not fitted; call fit() first")
        return self.dpd_model(x)

    def linearize(self, pa: Callable[[np.ndarray], np.ndarray],
                  x: np.ndarray) -> np.ndarray:
        """Convenience: PA output with DPD applied, i.e. pa(dpd(x))."""
        return pa(self(x))
