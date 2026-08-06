"""Phase 3: fixed-point deployment of behavioral models / predistorters.

Linear-in-parameters models (MP, GMP, DDR-Volterra) map to hardware as a
bank of fixed basis functions followed by a coefficient dot product —
i.e. multiply-accumulate over LS-fitted taps. Deploying them needs no
retraining (unlike neural models, which need QAT): the float coefficients
are simply quantized (post-training quantization), and the whole datapath
is evaluated bit-true. This module provides that quantization and a
hardware-cost estimate.
"""

from .fixed_point import (quantize_symmetric, FixedPointPolyModel,
                          mac_cost, spline_mac_cost)
from .export import (export_linear_coeffs, export_lut,
                     export_reference_vectors, export_onnx)
from .lut import LUTDPD, lut_from_model, quantize_lut

__all__ = ["quantize_symmetric", "FixedPointPolyModel", "mac_cost",
           "spline_mac_cost", "export_linear_coeffs", "export_lut",
           "export_reference_vectors", "export_onnx", "LUTDPD",
           "lut_from_model", "quantize_lut"]
