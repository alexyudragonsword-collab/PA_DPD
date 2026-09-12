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


def drain_efficiency(pa, x: np.ndarray, pa_class: str = "B",
                     eta_peak: float | None = None) -> float:
    """Average drain efficiency of an ideal reduced-conduction-angle PA.

    Physically grounded (not a bare proxy) and computable from any
    :class:`~padpd.pa.base.PAModel` — the synthetic ReferencePA or a
    Wiener-Hammerstein PA imported from harmonic-balance simulation — via
    its AM-AM saturation. Instantaneous efficiency scales with output
    voltage relative to the saturation amplitude ``Vmax``; averaging uses
    the power (PAE) convention ``eta = <P_out> / <P_dc>``:

    - **Class A**  : DC current constant, ``eta = eta_peak * <|y|^2>/Vmax^2``
    - **Class B/AB**: DC current tracks output amplitude,
      ``eta = eta_peak * <|y|^2> / (Vmax * <|y|>)``

    At CW saturation both give ``eta_peak`` (pi/4 for Class B, 1/2 for
    Class A by default). Back-off (high PAPR) drops the average, and
    driving the PA harder raises it — the efficiency/linearity tension
    the co-design balances. Pass ``eta_peak`` to model higher-efficiency
    architectures (e.g. Doherty/Class-F peak ~0.9).
    """
    peaks = {"A": 0.5, "B": np.pi / 4, "AB": 0.6}
    if eta_peak is None:
        eta_peak = peaks.get(pa_class.upper(), np.pi / 4)
    y = pa(x)
    a = np.abs(y)
    vmax = saturation_amplitude(pa)
    if pa_class.upper() == "A":
        return float(eta_peak * np.mean(a ** 2) / vmax ** 2)
    return float(eta_peak * np.mean(a ** 2) / (vmax * np.mean(a) + 1e-30))


def pae_proxy(pa: ReferencePA, x: np.ndarray, eta_max: float = 0.70) -> float:
    """Deprecated alias; see :func:`drain_efficiency`."""
    return drain_efficiency(pa, x, pa_class="B", eta_peak=eta_max)


def _dpd_cost_options():
    """DPD complexity ladder (DDR memory depth -> coefficient count)."""
    return [2, 4, 8, 12, 16]


def codesign_point(drive: float, x_train: np.ndarray, x_val, val_wf,
                   evm_spec_db: float, fs: float, bw: float,
                   cfr_papr_db: float | None = None,
                   pa_class: str = "B") -> dict:
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

    pae = drain_efficiency(pa, xv, pa_class=pa_class)
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
                   cfr_papr_db=None, pa_class="B"):
    """Run :func:`codesign_point` over a list of PA operating points."""
    return [codesign_point(d, x_train, x_val, val_wf, evm_spec_db, fs, bw,
                           cfr_papr_db, pa_class) for d in drives]
