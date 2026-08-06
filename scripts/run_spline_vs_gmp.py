"""Benchmark: spline (SMP/SplineGMP/LUT) vs polynomial (MP/GMP) DPD.

Verifies the two headline claims of the spline family on the
ReferencePA virtual DUT:

1. accuracy parity — spline bases reach GMP-class PA-modeling NMSE and
   ILA-DPD EVM/ACLR at comparable coefficient counts;
2. runtime advantage — the deployed datapath (LUT + interpolation)
   costs ~6 real MACs per branch per sample regardless of knot count,
   versus 4 real MACs *per coefficient* for polynomial MAC engines;
   plus the conditioning gap that makes the spline LS fit robust.

Also runs the thermal scenario: plain SMP vs StateConditionedSpline on
the self-heating ThermalReferencePA.

Run from the repo root:  python scripts/run_spline_vs_gmp.py
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from padpd.deploy import (LUTDPD, lut_from_model, mac_cost,  # noqa: E402
                          spline_mac_cost)
from padpd.dpd import ILAPredistorter  # noqa: E402
from padpd.metrics import aclr, evm_of_signal  # noqa: E402
from padpd.pa import (GMPModel, MemoryPolynomialModel,  # noqa: E402
                      ReferencePA, SplineGMP, SplineMemoryPolynomial,
                      StateConditionedSpline, ThermalReferencePA,
                      basis_cond, burst_stimulus, nmse_db)
from padpd.waveform import OFDMConfig, generate_ofdm  # noqa: E402


def _models(x):
    return {
        "MP o7 m4": MemoryPolynomialModel(order=7, memory_depth=4),
        "GMP (default)": GMPModel(),
        "Spline-MP K8 m4": SplineMemoryPolynomial.from_signal(
            x, n_knots=8, memory_depth=4),
        "Spline-GMP K8": SplineGMP.from_signal(x, n_knots=8),
    }


def _runtime_macs(name, model):
    # splines deploy as LUT+interp datapaths; polynomials as coeff MACs
    if hasattr(model, "knots"):
        c = spline_mac_cost(len(model.branch_delays()), 1.0,
                            degree=model.degree)
        return c["real_macs_per_sample_lut"]
    return mac_cost(model.n_coeffs, 1.0)["real_macs_per_sample"]


def main(bw_hz: float = 160e6, qam: int = 1024, n_symbols: int = 8,
         drive: float = 0.14, thermal_symbols: int = 12) -> dict:
    wf_tr = generate_ofdm(OFDMConfig(bandwidth_hz=bw_hz, qam_order=qam,
                                     n_symbols=n_symbols, seed=0))
    wf_va = generate_ofdm(OFDMConfig(bandwidth_hz=bw_hz, qam_order=qam,
                                     n_symbols=n_symbols, seed=1))
    fs = wf_tr.sample_rate_hz
    pa = ReferencePA(drive=drive)
    y_tr, y_va = pa(wf_tr.x), pa(wf_va.x)

    rows = {}
    for name, model in _models(wf_tr.x).items():
        model.fit(wf_tr.x, y_tr, regularization=1e-9)
        row = {"n_coeffs": model.n_coeffs,
               "macs_per_sample": _runtime_macs(name, model),
               "cond": basis_cond(model, wf_tr.x),
               "pa_nmse_db": nmse_db(y_va, model(wf_va.x))}

        dpd = ILAPredistorter(
            model_factory=lambda m=model: type(m)(**m.get_config()),
            n_iterations=2, fit_kwargs={"regularization": 1e-9})
        dpd.fit(pa, wf_tr.x)
        y_lin = pa(dpd(wf_va.x))
        a = aclr(y_lin, fs, bw_hz)
        row["dpd_evm_db"] = evm_of_signal(y_lin, wf_va).db
        row["dpd_aclr_dbc"] = max(a["lower_dbc"], a["upper_dbc"])

        if hasattr(dpd.dpd_model, "knots"):         # deployed LUT form
            lut = LUTDPD.from_table(lut_from_model(dpd.dpd_model,
                                                   n_entries=256))
            y_lut = pa(lut(wf_va.x))
            row["dpd_evm_lut256_db"] = evm_of_signal(y_lut, wf_va).db
        rows[name] = row

    e0 = evm_of_signal(pa(wf_va.x), wf_va).db

    # ---- thermal scenario ------------------------------------------
    wf_t = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=qam,
                                    n_symbols=thermal_symbols, seed=2))
    xb = burst_stimulus(wf_t.x, n_bursts=6, low_scale=0.3)
    tpa = ThermalReferencePA(fs=wf_t.sample_rate_hz)
    yb = tpa(xb)
    alphas = tuple(float(np.exp(-1.0 / (t * wf_t.sample_rate_hz)))
                   for t in tpa.taus_s)
    smp_t = SplineMemoryPolynomial.from_signal(
        xb, n_knots=8, memory_depth=4).fit(xb, yb, regularization=1e-9)
    scs_t = StateConditionedSpline.from_signal(
        xb, n_knots=8, memory_depth=4, state_alphas=alphas
    ).fit(xb, yb, regularization=1e-9)
    thermal = {"smp_nmse_db": nmse_db(yb, smp_t(xb)),
               "state_nmse_db": nmse_db(yb, scs_t(xb)),
               "final_state": tpa.state}

    return {"bw_hz": bw_hz, "evm_no_dpd_db": e0, "rows": rows,
            "thermal": thermal}


def report(res: dict) -> str:
    lines = [f"# Spline vs GMP @ {res['bw_hz']/1e6:.0f} MHz "
             f"(no-DPD EVM {res['evm_no_dpd_db']:.1f} dB)", ""]
    hdr = (f"{'model':16s} {'coeffs':>6s} {'MACs/spl':>8s} {'cond':>9s} "
           f"{'PA NMSE':>8s} {'DPD EVM':>8s} {'ACLR':>7s} {'LUT256':>7s}")
    lines += [hdr, "-" * len(hdr)]
    for name, r in res["rows"].items():
        lut = (f"{r['dpd_evm_lut256_db']:7.1f}"
               if "dpd_evm_lut256_db" in r else "      -")
        lines.append(
            f"{name:16s} {r['n_coeffs']:6d} {r['macs_per_sample']:8.0f} "
            f"{r['cond']:9.1e} {r['pa_nmse_db']:8.1f} "
            f"{r['dpd_evm_db']:8.1f} {r['dpd_aclr_dbc']:7.1f} {lut}")
    t = res["thermal"]
    lines += ["", f"thermal DUT (final state {t['final_state']:.2f}): "
              f"SMP {t['smp_nmse_db']:.1f} dB -> state-conditioned "
              f"{t['state_nmse_db']:.1f} dB "
              f"({t['smp_nmse_db'] - t['state_nmse_db']:.1f} dB better)"]
    return "\n".join(lines)


if __name__ == "__main__":
    print(report(main()))
