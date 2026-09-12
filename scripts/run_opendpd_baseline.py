#!/usr/bin/env python3
"""Classical MP/GMP baselines on real measured OpenDPD PA datasets.

For each dataset:
1. Fit MP-500 and GMP-510 (OpenDPD benchmark parameter budgets) as PA
   behavioral models on the train split; report test NMSE in both padpd
   (global) and OpenDPD (segmented) conventions.
2. Identify an ILA-GMP predistorter directly from the measured train data
   (single-shot data-driven ILA — the same protocol as OpenDPD's
   classical benchmark), then evaluate it through the fitted GMP PA model
   as a surrogate for the real PA (OpenDPD evaluates through a trained
   GRU surrogate); report ACLR and spectral EVM in OpenDPD conventions.
3. Print published OpenDPD benchmark numbers next to ours for context.

Requires a clone of https://github.com/lab-emi/OpenDPD (55 MB datasets):
    git clone --depth 1 https://github.com/lab-emi/OpenDPD.git

NOTE: "after DPD" numbers are surrogate-based (DPD applied to the fitted
GMP PA model, not the physical PA). They are comparable to OpenDPD's
benchmark protocol but not to on-device measurements, and they are only
trustworthy down to roughly the surrogate's own NMSE floor — on strongly
nonlinear PAs (APA_200MHz) the GMP surrogate under-reports ACLR
improvement; a neural surrogate (Phase 2) is needed there.

Evaluation uses memory warmup: the tail of the val split is prepended as
context before the test split and the corresponding outputs discarded, so
zero-padded memory taps never contaminate the metrics (high-order
polynomial models otherwise produce large boundary transients).
"""

import argparse
import os

import numpy as np

WARMUP = 200  # samples of context, > any model's memory span (incl. DPD+PA)

from padpd.data import load_opendpd_dataset  # noqa: E402
from padpd.dpd import ILAPredistorter  # noqa: E402
from padpd.metrics import (  # noqa: E402
    aclr_opendpd,
    evm_spectral,
    nmse_segmented,
    target_gain_opendpd,
)
from padpd.pa import gmp_opendpd_510, mp_opendpd_500, nmse_db  # noqa: E402
from padpd.plotting import plot_am_curves, plot_psd_comparison  # noqa: E402

# Published numbers from OpenDPD benchmark/benchmark_report.md
# (~500-param fair comparison): (ACLR_AVG dB, EVM dB)
PUBLISHED = {
    "APA_200MHz": {"MP (500, QR)": (-41.01, -32.68),
                   "GMP (510, QR)": (-38.80, -38.53),
                   "TRes-DeltaGRU (524)": (-53.35, -49.08)},
    "DPA_160MHz": {"MP (500, QR)": (-51.29, -50.26),
                   "GMP (510, QR)": (-54.02, -51.08),
                   "TRes-DeltaGRU (524)": (-56.81, -54.00)},
}


def run_dataset(root: str, name: str, results_dir: str):
    path = os.path.join(root, "datasets", name)
    ds = load_opendpd_dataset(path)
    train, val, test, spec = ds["train"], ds["val"], ds["test"], ds["spec"]
    ctx = val.x[-WARMUP:]  # warmup context preceding the test split
    fs = train.sample_rate_hz
    bw = spec["bw_main_ch"]
    n_sub = spec["n_sub_ch"]
    nperseg = spec["nperseg"]

    print("\n" + "=" * 70)
    print(f"{name}: fs={fs / 1e6:.2f} MSPS, bw={bw / 1e6:.0f} MHz, "
          f"{n_sub} sub-ch, nperseg={nperseg}, "
          f"train/test={len(train)}/{len(test)}")
    print("=" * 70)

    g = target_gain_opendpd(train.x, train.y)

    # -- PA behavioral modeling --------------------------------------------
    print("\n-- PA behavioral modeling (test split) --")
    models = {"MP-500": mp_opendpd_500(), "GMP-510": gmp_opendpd_510()}
    for label, model in models.items():
        model.fit(train.x, train.y, regularization=1e-9)
        pred = model(np.concatenate([ctx, test.x]))[WARMUP:]
        print(f"{label:<8} NMSE: global {nmse_db(test.y, pred):7.2f} dB | "
              f"OpenDPD segmented "
              f"{nmse_segmented(pred, test.y, nperseg):7.2f} dB")

    # -- data-driven ILA DPD, evaluated through the GMP surrogate PA -------
    surrogate = models["GMP-510"]
    dpd = ILAPredistorter(model_factory=gmp_opendpd_510, target_gain=g,
                          fit_kwargs={"regularization": 1e-9})
    dpd.fit_measured(train.x, train.y)
    y_dpd = surrogate(dpd(np.concatenate([ctx, test.x])))[WARMUP:]

    print("\n-- linearization, OpenDPD metric conventions (test split) --")
    print("(surrogate-based evaluation; results are only meaningful down "
          "to the surrogate's NMSE floor above)")
    print(f"{'case':<28}{'ACLR_L':>9}{'ACLR_R':>9}{'ACLR_AVG':>10}"
          f"{'EVM(spec)':>11}")
    rows = [("no DPD (measured PA out)", test.y),
            ("ILA-GMP-510 (surrogate)", y_dpd)]
    for label, sig in rows:
        a = aclr_opendpd(sig, fs, bw, n_sub, nperseg)
        e = evm_spectral(sig, g * test.x, fs, bw, n_sub, nperseg)
        print(f"{label:<28}{a['left_dbc']:>9.2f}{a['right_dbc']:>9.2f}"
              f"{a['avg_dbc']:>10.2f}{e:>11.2f}")

    if name in PUBLISHED:
        print("\n-- published OpenDPD benchmark (~500 params, "
              "GRU-surrogate protocol) --")
        for label, (a, e) in PUBLISHED[name].items():
            print(f"{label:<28}{'':>9}{'':>9}{a:>10.2f}{e:>11.2f}")
    else:
        print("\n(no published ~500-param benchmark for this dataset)")

    out_dir = os.path.join(results_dir, name)
    os.makedirs(out_dir, exist_ok=True)
    plot_psd_comparison(
        {"input (scaled)": g * test.x, "PA, no DPD": test.y,
         "PA + ILA-GMP DPD (surrogate)": y_dpd},
        fs, path=os.path.join(out_dir, "psd_comparison.png"))
    plot_am_curves(
        {"measured PA": (test.x, test.y),
         "DPD (surrogate)": (test.x, y_dpd)},
        path=os.path.join(out_dir, "am_am_am_pm.png"))
    print(f"plots saved to {out_dir}/ (psd_comparison.png, am_am_am_pm.png)")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--opendpd-root", default="/home/user/OpenDPD",
                    help="path to a clone of lab-emi/OpenDPD")
    ap.add_argument("--datasets", nargs="+",
                    default=["DPA_200MHz", "DPA_160MHz", "APA_200MHz"])
    ap.add_argument("--results", default="results/opendpd")
    args = ap.parse_args()

    if not os.path.isdir(os.path.join(args.opendpd_root, "datasets")):
        raise SystemExit(
            f"OpenDPD not found at {args.opendpd_root}. Clone it first:\n"
            "  git clone --depth 1 https://github.com/lab-emi/OpenDPD.git")

    for name in args.datasets:
        run_dataset(args.opendpd_root, name, args.results)


if __name__ == "__main__":
    main()
