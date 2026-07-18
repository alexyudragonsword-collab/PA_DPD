"""Phase 4: PA / DPD co-design.

The traditional flow designs the PA first (for peak efficiency), then bolts
on DPD to rescue linearity. Co-design instead treats the PA operating point
and the DPD complexity as one joint optimization: driving the PA harder
raises efficiency but worsens nonlinearity, which then demands a bigger (more
expensive) DPD — and past a point becomes uninvertible no matter the DPD.
The sweet spot balances efficiency against DPD cost under a linearity spec.

This module runs that trade study on the synthetic ReferencePA, where the
"real" PA is fully known so DPD is evaluated directly (no surrogate). The
efficiency figure is a physically-motivated proxy (Class-B-like: average
output amplitude relative to saturation), not a calibrated PAE.
"""

from __future__ import annotations

import numpy as np

from .cfr import cfr_clip_filter
from .dpd import ILAPredistorter
from .metrics import evm_of_signal
from .pa import DDRVolterraModel, ReferencePA


def saturation_amplitude(pa: ReferencePA) -> float:
    """Peak achievable output amplitude of the PA (AM-AM saturation)."""
    r = np.linspace(0.0, 30.0, 2000).astype(complex)
    return float(np.abs(pa(r)).max())


def pae_proxy(pa: ReferencePA, x: np.ndarray, eta_max: float = 0.70) -> float:
    """Efficiency proxy in [0, eta_max]: Class-B-like average output
    amplitude relative to saturation. Increases as the PA is driven
    harder (higher operating point), capturing the efficiency-linearity
    tension."""
    y = pa(x)
    return float(eta_max * np.mean(np.abs(y)) / saturation_amplitude(pa))


def _dpd_cost_options():
    """DPD complexity ladder (DDR memory depth -> coefficient count)."""
    return [2, 4, 8, 12, 16]


def codesign_point(drive: float, x_train: np.ndarray, x_val, val_wf,
                   evm_spec_db: float, fs: float, bw: float,
                   cfr_papr_db: float | None = None) -> dict:
    """Evaluate one PA operating point: efficiency, and the cheapest DDR
    DPD (if any) that meets the EVM spec.

    Returns dict with drive, pae, evm_nodpd, and the min DPD cost
    (coeff count) + achieved EVM, or feasible=False if no DPD on the
    ladder meets the spec (uninvertible operating point).
    """
    pa = ReferencePA(drive=drive)
    xt, xv = x_train, x_val
    if cfr_papr_db is not None:
        xt = cfr_clip_filter(xt, cfr_papr_db, fs, bw)
        xv = cfr_clip_filter(xv, cfr_papr_db, fs, bw)

    pae = pae_proxy(pa, xv)
    evm_nodpd = evm_of_signal(pa(xv), val_wf).db

    best = None
    for mem in _dpd_cost_options():
        dpd = ILAPredistorter(
            model_factory=lambda m=mem: DDRVolterraModel(
                order=5, memory_depth=m, dynamic_order=1),
            n_iterations=2, fit_kwargs={"regularization": 1e-9})
        dpd.fit(pa, xt)
        evm_dpd = evm_of_signal(pa(dpd(xv)), val_wf).db
        n_coeffs = dpd.dpd_model.basis_matrix(
            np.ones(mem + 2, dtype=complex)).shape[1]
        if evm_dpd <= evm_spec_db:
            best = {"dpd_cost": n_coeffs, "dpd_memory": mem,
                    "evm_dpd": evm_dpd}
            break
        best = {"dpd_cost": n_coeffs, "dpd_memory": mem,
                "evm_dpd": evm_dpd}  # keep last (deepest) attempt

    feasible = best is not None and best["evm_dpd"] <= evm_spec_db
    return {"drive": drive, "pae": pae, "evm_nodpd": evm_nodpd,
            "feasible": feasible, **best}


def codesign_sweep(drives, x_train, x_val, val_wf, evm_spec_db, fs, bw,
                   cfr_papr_db=None):
    """Run :func:`codesign_point` over a list of PA operating points."""
    return [codesign_point(d, x_train, x_val, val_wf, evm_spec_db, fs, bw,
                           cfr_papr_db) for d in drives]
