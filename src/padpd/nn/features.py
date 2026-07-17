"""Feature construction and complex <-> I/Q tensor conversion.

The 6-channel feature vector follows OpenDPD's DGRU convention exactly:
[I, Q, |x|, |x|^3, sin(phi), cos(phi)] (note |x|^3, not |x|^2, and the
sin/cos order as in their implementation).
"""

from __future__ import annotations

import numpy as np
import torch


def complex_to_iq(x: np.ndarray) -> torch.Tensor:
    """1-D complex numpy array -> float32 tensor of shape (N, 2)."""
    x = np.asarray(x)
    return torch.from_numpy(
        np.stack([x.real, x.imag], axis=-1).astype(np.float32))


def iq_to_complex(t: torch.Tensor) -> np.ndarray:
    """(..., 2) tensor -> complex numpy array of shape (...)."""
    a = t.detach().cpu().numpy()
    return a[..., 0] + 1j * a[..., 1]


def iq_features(x: torch.Tensor) -> torch.Tensor:
    """(..., 2) I/Q tensor -> (..., 6) feature tensor (OpenDPD DGRU)."""
    i_x = x[..., 0:1]
    q_x = x[..., 1:2]
    amp2 = i_x.pow(2) + q_x.pow(2)
    amp = torch.sqrt(amp2)
    amp3 = amp.pow(3)
    cos = i_x / amp
    sin = q_x / amp
    return torch.cat((i_x, q_x, amp, amp3, sin, cos), dim=-1)
