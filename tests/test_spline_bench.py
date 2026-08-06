"""Tiny-config smoke of the spline-vs-GMP benchmark script."""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src"), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from run_spline_vs_gmp import main, report  # noqa: E402


def test_benchmark_small_config_runs():
    res = main(bw_hz=20e6, qam=256, n_symbols=3, thermal_symbols=6)
    assert set(res["rows"]) == {"MP o7 m4", "GMP (default)",
                                "Spline-MP K8 m4", "Spline-GMP K8"}
    for r in res["rows"].values():
        assert np.isfinite(r["pa_nmse_db"]) and np.isfinite(r["dpd_evm_db"])
        assert r["dpd_evm_db"] < res["evm_no_dpd_db"] - 5
    # runtime claim: spline LUT datapath beats polynomial coeff MACs
    assert (res["rows"]["Spline-MP K8 m4"]["macs_per_sample"]
            < res["rows"]["MP o7 m4"]["macs_per_sample"])
    # conditioning claim
    assert (res["rows"]["Spline-MP K8 m4"]["cond"]
            < res["rows"]["MP o7 m4"]["cond"] / 10)
    # thermal claim
    t = res["thermal"]
    assert t["state_nmse_db"] < t["smp_nmse_db"] - 4
    assert "thermal" in report(res)
