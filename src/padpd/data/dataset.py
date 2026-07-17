"""IQ input/output dataset container.

The canonical in-memory format for PA modeling and DPD training: a pair of
aligned complex baseband sequences (PA input ``x``, PA output ``y``) plus
the sample rate and free-form metadata. Every external source (synthetic,
Cadence envelope export, MATLAB capture, OpenDPD dataset) is converted to
this container so downstream code has a single interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class IQDataset:
    x: np.ndarray  # PA input, complex baseband
    y: np.ndarray  # PA output, complex baseband, sample-aligned with x
    sample_rate_hz: float
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        self.x = np.asarray(self.x, dtype=complex)
        self.y = np.asarray(self.y, dtype=complex)
        if self.x.shape != self.y.shape or self.x.ndim != 1:
            raise ValueError("x and y must be 1-D arrays of equal length")

    def __len__(self) -> int:
        return len(self.x)

    def split(self, train_fraction: float = 0.8) -> tuple["IQDataset", "IQDataset"]:
        """Contiguous train/test split (preserves memory-effect continuity)."""
        n = int(len(self) * train_fraction)
        train = IQDataset(self.x[:n], self.y[:n], self.sample_rate_hz,
                          {**self.meta, "split": "train"})
        test = IQDataset(self.x[n:], self.y[n:], self.sample_rate_hz,
                         {**self.meta, "split": "test"})
        return train, test

    def normalized(self) -> "IQDataset":
        """Return a copy with x scaled to unit average power.

        y is scaled by the same factor so the PA gain is preserved.
        The scale factor is recorded in meta["norm_scale"].
        """
        s = float(np.sqrt(np.mean(np.abs(self.x) ** 2)))
        return IQDataset(self.x / s, self.y / s, self.sample_rate_hz,
                         {**self.meta, "norm_scale": s})

    def save(self, path: str) -> None:
        np.savez_compressed(path, x=self.x, y=self.y,
                            sample_rate_hz=self.sample_rate_hz,
                            meta=np.array(repr(self.meta)))

    @classmethod
    def load(cls, path: str) -> "IQDataset":
        import ast
        d = np.load(path, allow_pickle=False)
        meta = ast.literal_eval(str(d["meta"])) if "meta" in d else {}
        return cls(d["x"], d["y"], float(d["sample_rate_hz"]), meta)
