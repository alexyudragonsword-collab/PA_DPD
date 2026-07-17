"""Common interface for PA behavioral models.

Every model maps a complex baseband input sequence to a complex output
sequence via ``__call__``. Trainable models additionally implement
``fit(x, y)``. Neural models added in later phases should follow the same
interface so they can be swapped against the GMP baseline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class PAModel(ABC):
    @abstractmethod
    def __call__(self, x: np.ndarray) -> np.ndarray:
        """Apply the model to a complex baseband sequence."""

    def fit(self, x: np.ndarray, y: np.ndarray) -> "PAModel":
        raise NotImplementedError(f"{type(self).__name__} is not trainable")


def nmse_db(y_ref: np.ndarray, y_est: np.ndarray) -> float:
    """Normalized mean squared error in dB between two complex sequences."""
    err = np.abs(y_ref - y_est) ** 2
    return float(10 * np.log10(err.sum() / (np.abs(y_ref) ** 2).sum()))
