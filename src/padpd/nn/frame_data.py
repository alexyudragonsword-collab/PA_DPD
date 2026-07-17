"""Frame datasets for BPTT training (OpenDPD convention).

Training uses overlapping sliding frames of ``frame_length`` with
``stride``; each frame is trained independently with a zero initial
hidden state.
"""

from __future__ import annotations

import numpy as np
import torch
from torch.utils.data import Dataset

from .features import complex_to_iq


class FrameDataset(Dataset):
    def __init__(self, x: np.ndarray, y: np.ndarray,
                 frame_length: int = 50, stride: int = 1):
        if len(x) != len(y):
            raise ValueError("x and y must have equal length")
        if len(x) < frame_length:
            raise ValueError("signal shorter than one frame")
        self.x = complex_to_iq(x)
        self.y = complex_to_iq(y)
        self.frame_length = frame_length
        self.stride = stride
        self.n_frames = (len(x) - frame_length) // stride + 1

    def __len__(self) -> int:
        return self.n_frames

    def __getitem__(self, idx: int):
        start = idx * self.stride
        sl = slice(start, start + self.frame_length)
        return self.x[sl], self.y[sl]
