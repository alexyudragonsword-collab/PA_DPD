"""Time alignment of PA input/output captures.

Measured or EDA-exported data often has an unknown bulk delay (and complex
gain) between the stimulus and the capture. Behavioral-model fitting
assumes sample-aligned x/y, so run :func:`align_delay` first. (OpenDPD
datasets ship pre-aligned; Cadence envelope exports and lab captures
usually do not.)
"""

from __future__ import annotations

import numpy as np
from scipy import signal as sig


def align_delay(x: np.ndarray, y: np.ndarray, max_lag: int = 4096):
    """Estimate and remove the integer bulk delay of ``y`` relative to ``x``.

    The delay is the argmax of the complex cross-correlation within
    ``+/- max_lag`` samples (positive = y lags x). Returns
    ``(x_aligned, y_aligned, info)`` where the aligned arrays are the
    overlapping region and ``info`` holds ``{"lag", "gain"}`` with the
    least-squares complex gain y ≈ gain * x after alignment.
    """
    x = np.asarray(x)
    y = np.asarray(y)
    corr = sig.correlate(y, x, mode="full", method="fft")
    lags = sig.correlation_lags(len(y), len(x), mode="full")
    window = np.abs(lags) <= max_lag
    lag = int(lags[window][np.argmax(np.abs(corr[window]))])

    if lag >= 0:
        y_a = y[lag:]
        x_a = x[: len(y_a)]
    else:
        x_a = x[-lag:]
        y_a = y[: len(x_a)]
    n = min(len(x_a), len(y_a))
    x_a, y_a = x_a[:n], y_a[:n]

    gain = complex(np.vdot(x_a, y_a) / np.vdot(x_a, x_a))
    return x_a, y_a, {"lag": lag, "gain": gain}
