"""Two PAs in cascade, as one PA.

The IF-extension topology drives a second PA (60 GHz) with the output of
a first one (the WiFi 7 driver), each with its own AM/AM, AM/PM and
memory. A DPD sees only the cascade, so the cascade has to be one
``PAModel``: ``__call__`` maps x to y like any single PA, and a DPD
trained against it needs no change (issue #4).

Levels. Each stage takes a unit-power input as its nominal operating
point - that is what ``ReferencePA.drive`` is defined against.
``interstage_backoff_db`` scales the signal between the stages only: the
second stage sees the first stage's output ``interstage_backoff_db`` dB
lower, and the cascade divides the same factor back out at its output,
so the backoff adds no gain of its own. The first stage's normalization
is never touched; its operating point is set by its own ``drive``.

The cascade's small-signal gain is therefore the product of the two
stages' small-signal gains. "About 1" for a single ReferencePA is
really 1.2: the Saleh stage is normalized, but the matching-network
FIRs keep their gain (|sum(fir_in) * sum(fir_out)| = 1.230 at DC).
Measured as the least-squares gain on a small 80 MHz OFDM signal: one
ReferencePA 1.195, two in cascade 1.416, the same with any interstage
backoff. A caller that needs an absolute gain wraps the cascade in its
own scaling; normalizing here would mean probing stateful stages.

After every call ``stage_input_rms`` and ``stage_backoff_db`` hold, per
stage, the rms of the signal that stage actually received and how far
that sits below its nominal unit-power level - the per-stage numbers an
output-backoff table reports.
"""

from __future__ import annotations

import numpy as np

from .base import PAModel


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.abs(x) ** 2))) if len(x) else 0.0


class CascadePA(PAModel):
    def __init__(self, first, second, interstage_backoff_db: float = 0.0):
        if not (callable(first) and callable(second)):
            raise TypeError("both stages must map x -> y (be callable)")
        self.first = first
        self.second = second
        self.interstage_backoff_db = float(interstage_backoff_db)
        self._g = 10 ** (-self.interstage_backoff_db / 20)
        self.stage_input_rms: tuple[float, float] | None = None

    @property
    def stage_backoff_db(self) -> tuple[float, float] | None:
        """Per stage, dB below its nominal unit-power input, from the
        last call (positive = backed off)."""
        if self.stage_input_rms is None:
            return None
        return tuple(float(-20 * np.log10(max(r, 1e-300))) + 0.0
                     for r in self.stage_input_rms)

    def __call__(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x)
        u = self._g * self.first(x)
        self.stage_input_rms = (_rms(x), _rms(u))
        return self.second(u) / self._g

    def get_config(self) -> dict:
        """Both stages' configs. Raises when a stage has none: a virtual
        DUT such as ReferencePA is deliberately not persistable, and a
        cascade containing one is not either."""
        return {"first": {"class_name": type(self.first).__name__,
                          "config": self.first.get_config()},
                "second": {"class_name": type(self.second).__name__,
                           "config": self.second.get_config()},
                "interstage_backoff_db": self.interstage_backoff_db}

    def save(self, path: str) -> None:
        # PAModel.save stores one coefficient array; a cascade of two
        # fitted models has two, and saving only the config would
        # silently drop both
        raise NotImplementedError(
            "CascadePA cannot be saved: the .npz format holds one "
            "coefficient array. Save each stage on its own.")
