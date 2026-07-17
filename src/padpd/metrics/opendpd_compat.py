"""Metrics replicating OpenDPD's conventions (utils/metrics.py there).

Use these ONLY for apples-to-apples comparison with numbers published by
OpenDPD (https://github.com/lab-emi/OpenDPD). They differ from padpd's
native metrics:

- ``nmse_segmented``: NMSE is computed per nperseg-segment in dB, then
  averaged over segments (padpd's ``nmse_db`` is one global ratio).
- ``aclr_opendpd``: the reference power is the STRONGEST in-band
  sub-channel (not total in-band power); each adjacent channel is one
  sub-channel wide, immediately next to the main band edge.
- ``evm_spectral``: a spectral-domain EVM (normalized FFT-difference
  magnitude), NOT a demodulated constellation EVM. OpenDPD's README
  acknowledges this is an approximation; padpd's ``evm``/``evm_of_signal``
  remain the engineering-grade metric.
- ``target_gain_opendpd``: peak-amplitude ratio max|y|/max|x| (padpd's
  ILA uses a least-squares scalar by default).

All functions take 1-D complex baseband arrays; they are internally
reshaped to (n_segments, nperseg), truncating any remainder samples.
OpenDPD's dataset splits are exact multiples of nperseg, so truncation
never triggers on their data.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import welch


def _segments(x: np.ndarray, nperseg: int) -> np.ndarray:
    x = np.asarray(x)
    n_seg = len(x) // nperseg
    if n_seg == 0:
        raise ValueError(f"signal shorter than one segment ({nperseg})")
    return x[: n_seg * nperseg].reshape(n_seg, nperseg)


def nmse_segmented(y_pred: np.ndarray, y_true: np.ndarray,
                   nperseg: int) -> float:
    """Per-segment NMSE in dB, averaged over segments (OpenDPD NMSE)."""
    p = _segments(y_pred, nperseg)
    t = _segments(y_true, nperseg)
    mse = np.mean(np.abs(t - p) ** 2, axis=-1)
    energy = np.mean(np.abs(t) ** 2, axis=-1)
    return float(np.mean(10 * np.log10(mse / energy)))


def _main_channel_indices(fs: float, nperseg: int, bw_main_ch: float):
    freq = np.fft.fftshift(np.fft.fftfreq(nperseg, d=1 / fs))
    index_left = int(np.min(np.where(freq >= -bw_main_ch / 2)))
    index_right = int(np.max(np.where(freq <= bw_main_ch / 2)))
    return index_left, index_right


def evm_spectral(y_pred: np.ndarray, y_true: np.ndarray, fs: float,
                 bw_main_ch: float, n_sub_ch: int, nperseg: int) -> float:
    """Spectral-domain EVM in dB (OpenDPD EVM convention)."""
    sp = np.fft.fftshift(np.fft.fft(_segments(y_pred, nperseg), axis=-1),
                         axes=-1)
    st = np.fft.fftshift(np.fft.fft(_segments(y_true, nperseg), axis=-1),
                         axes=-1)
    index_left, index_right = _main_channel_indices(fs, nperseg, bw_main_ch)
    ch_len = int((index_right - index_left) / n_sub_ch)
    error = np.zeros((sp.shape[0], n_sub_ch))
    for c in range(n_sub_ch):
        sl = slice(index_left + c * ch_len, index_left + (c + 1) * ch_len)
        error[:, c] = (np.mean(np.abs(sp[:, sl] - st[:, sl]), axis=-1)
                       / np.mean(np.abs(st[:, sl]), axis=-1))
    return float(20 * np.log10(np.mean(error.mean(axis=-1))))


def aclr_opendpd(y: np.ndarray, fs: float, bw_main_ch: float,
                 n_sub_ch: int, nperseg: int) -> dict:
    """ACLR in dBc per OpenDPD convention.

    Welch PSD (scaling='spectrum', two-sided) averaged over segments;
    reference = max in-band sub-channel power; adjacent channels are one
    sub-channel wide on each side of the main band.
    """
    seg = _segments(y, nperseg)
    freq, psd = welch(seg, fs=fs, nperseg=nperseg, return_onesided=False,
                      scaling="spectrum", axis=-1)
    half = nperseg // 2
    freq = np.concatenate((freq[half:], freq[:half]))
    psd = np.concatenate((psd[..., half:], psd[..., :half]), axis=-1)
    psd = psd.mean(axis=0)

    index_left = int(np.min(np.where(freq >= -bw_main_ch / 2)))
    index_right = int(np.max(np.where(freq <= bw_main_ch / 2)))
    ch_len = int((index_right - index_left) / n_sub_ch)

    sub_power = np.array([
        psd[index_left + c * ch_len: index_left + (c + 1) * ch_len].sum()
        for c in range(n_sub_ch)])
    ref = sub_power.max()
    left = psd[index_left - ch_len: index_left].sum()
    right = psd[index_right: index_right + ch_len].sum()
    aclr_l = float(10 * np.log10(left / ref))
    aclr_r = float(10 * np.log10(right / ref))
    return {"left_dbc": aclr_l, "right_dbc": aclr_r,
            "avg_dbc": (aclr_l + aclr_r) / 2}


def target_gain_opendpd(x: np.ndarray, y: np.ndarray) -> float:
    """OpenDPD target linear gain: peak-amplitude ratio max|y| / max|x|."""
    return float(np.max(np.abs(y)) / np.max(np.abs(x)))
