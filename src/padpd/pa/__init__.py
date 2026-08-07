import ast

import numpy as np

from .base import PAModel, basis_cond, nmse_db
from .saleh import SalehPA
from .memory_polynomial import MemoryPolynomialModel
from .gmp import GMPModel
from .ddr import DDRVolterraModel
from .reference_pa import ReferencePA
from .drift import DriftingReferencePA
from .hb_import import (WienerHammersteinPA, load_amam_table, load_hb_pa,
                        s21_to_fir)
from .spline import (SplineGMP, SplineMemoryPolynomial,
                     bspline_design_matrix, place_knots)
from .spline_state import CoefficientScheduler, StateConditionedSpline
from .thermal import ThermalReferencePA, burst_stimulus
from .iq import IQImbalancePA, TxFrontEndPA, iq_imbalance_coeffs
from .presets import mp_opendpd_500, gmp_opendpd_510, ddr_volterra_default

_MODEL_CLASSES = {cls.__name__: cls
                  for cls in (SalehPA, MemoryPolynomialModel, GMPModel,
                              DDRVolterraModel, WienerHammersteinPA,
                              SplineMemoryPolynomial, SplineGMP,
                              StateConditionedSpline)}


def load_model(path: str) -> PAModel:
    """Load a model saved with :meth:`PAModel.save`."""
    d = np.load(path, allow_pickle=False)
    class_name = str(d["class_name"])
    if class_name not in _MODEL_CLASSES:
        raise ValueError(f"unknown model class in {path}: {class_name}")
    model = _MODEL_CLASSES[class_name](**ast.literal_eval(str(d["config"])))
    if "coeffs" in d:
        model.coeffs = d["coeffs"]
    return model


__all__ = [
    "mp_opendpd_500",
    "gmp_opendpd_510",
    "ddr_volterra_default",
    "PAModel",
    "load_model",
    "nmse_db",
    "basis_cond",
    "SalehPA",
    "MemoryPolynomialModel",
    "GMPModel",
    "DDRVolterraModel",
    "ReferencePA",
    "DriftingReferencePA",
    "WienerHammersteinPA",
    "SplineMemoryPolynomial",
    "SplineGMP",
    "StateConditionedSpline",
    "CoefficientScheduler",
    "ThermalReferencePA",
    "burst_stimulus",
    "IQImbalancePA",
    "TxFrontEndPA",
    "iq_imbalance_coeffs",
    "bspline_design_matrix",
    "place_knots",
    "load_amam_table",
    "load_hb_pa",
    "s21_to_fir",
]
