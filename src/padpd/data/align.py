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


def _fractional_advance(y: np.ndarray, frac: float) -> np.ndarray:
    """Advance y by a fractional number of samples via an FFT phase ramp.

    Circular by construction; only the few edge samples are affected for
    |frac| < 1.
    """
    freq = np.fft.fftfreq(len(y))
    return np.fft.ifft(np.fft.fft(y) * np.exp(2j * np.pi * freq * frac))


def align_delay(x: np.ndarray, y: np.ndarray, max_lag: int = 4096):
    """Estimate and remove the bulk delay of ``y`` relative to ``x``.

    The integer delay is the argmax of the complex cross-correlation
    within ``+/- max_lag`` samples (positive = y lags x). A residual
    fractional delay is then estimated by parabolic interpolation of the
    correlation peak and, if larger than 0.02 samples, removed with an
    FFT phase ramp.

    Returns ``(x_aligned, y_aligned, info)`` where the aligned arrays are
    the overlapping region and ``info`` holds ``{"lag"``: integer part,
    ``"lag_total"``: float total delay, ``"gain"``: least-squares complex
    gain with y ≈ gain * x after alignment``}``.
    """
    x = np.asarray(x)
    y = np.asarray(y)
    corr = sig.correlate(y, x, mode="full", method="fft")
    lags = sig.correlation_lags(len(y), len(x), mode="full")
    window = np.where(np.abs(lags) <= max_lag)[0]
    peak = window[np.argmax(np.abs(corr[window]))]
    lag = int(lags[peak])

    # Parabolic interpolation of |corr| around the peak -> fractional lag.
    frac = 0.0
    if 0 < peak < len(corr) - 1:
        c_m, c_0, c_p = np.abs(corr[peak - 1: peak + 2])
        denom = c_m - 2 * c_0 + c_p
        if denom != 0:
            frac = float(np.clip(0.5 * (c_m - c_p) / denom, -0.5, 0.5))

    if lag >= 0:
        y_a = y[lag:]
        x_a = x[: len(y_a)]
    else:
        x_a = x[-lag:]
        y_a = y[: len(x_a)]
    n = min(len(x_a), len(y_a))
    x_a, y_a = x_a[:n], y_a[:n]

    if abs(frac) > 0.02:
        y_a = _fractional_advance(y_a, frac)

    gain = complex(np.vdot(x_a, y_a) / np.vdot(x_a, x_a))
    return x_a, y_a, {"lag": lag, "lag_total": lag + frac, "gain": gain}
