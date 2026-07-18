"""Neural PA behavioral modeling and DPD (PyTorch, optional dependency).

Install with ``pip install -e .[nn]`` (or ``pip install torch``). The rest
of padpd stays numpy-only and works without torch.
"""

try:
    import torch  # noqa: F401
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "padpd.nn requires PyTorch. Install it with: pip install -e .[nn] "
        "(CPU-only: pip install torch --index-url "
        "https://download.pytorch.org/whl/cpu)") from e

from .features import iq_features, complex_to_iq, iq_to_complex
from .backbones import (GRUBackbone, DGRUBackbone, TCNBackbone,
                        count_params)
from .frame_data import FrameDataset
from .torch_model import NeuralPAModel
from .dla import DLAPredistorter
from ..deploy.neural_ptq import quantize_neural_ptq

__all__ = [
    "quantize_neural_ptq",
    "iq_features",
    "complex_to_iq",
    "iq_to_complex",
    "GRUBackbone",
    "DGRUBackbone",
    "TCNBackbone",
    "count_params",
    "FrameDataset",
    "NeuralPAModel",
    "DLAPredistorter",
]
