#!/usr/bin/env python3
"""Re-evaluate the Phase 1.5 classical DPD through a NEURAL PA surrogate.

Phase 1.5 finding: on APA_200MHz the ILA-GMP-510 DPD showed ACLR ~-26 dBc
when evaluated through a GMP surrogate (NMSE -35.5 dB), while OpenDPD's
published number (-38.8 dBc) was measured through a GRU surrogate
(NMSE -43.5 dB) — the reading was limited by surrogate fidelity, not by
the DPD. This script repeats the exact same DPD evaluation with a trained
neural surrogate to close that gap.

Example:
    python scripts/rerun_apa_surrogate.py \\
        --dataset-dir ../OpenDPD/datasets/APA_200MHz \\
        --pa-model models/APA_200MHz_dgru_h23.pt
"""

import argparse
import os

import numpy as np

from padpd.data import load_opendpd_dataset
from padpd.dpd import ILAPredistorter
from padpd.metrics import (aclr_opendpd, evm_spectral, nmse_segmented,
                           target_gain_opendpd)
from padpd.nn import NeuralPAModel
from padpd.pa import gmp_opendpd_510, nmse_db


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--pa-model", required=True,
                    help="trained NeuralPAModel checkpoint for this dataset")
    args = ap.parse_args()

    ds = load_opendpd_dataset(args.dataset_dir)
    train, val, test, spec = ds["train"], ds["val"], ds["test"], ds["spec"]
    name = os.path.basename(os.path.normpath(args.dataset_dir))
    fs = train.sample_rate_hz
    aclr_args = (fs, spec["bw_main_ch"], spec["n_sub_ch"], spec["nperseg"])
    g = target_gain_opendpd(train.x, train.y)

    # surrogates: classical GMP (Phase 1.5) vs neural
    gmp_sur = gmp_opendpd_510().fit(train.x, train.y, regularization=1e-9)
    nn_sur = NeuralPAModel.load(args.pa_model)
    print(f"{name}: surrogate fidelity (test NMSE)")
    for label, sur in (("GMP-510", gmp_sur), ("neural", nn_sur)):
        pred = sur(np.concatenate([val.x[-200:], test.x]))[200:]
        print(f"  {label:<8}: {nmse_db(test.y, pred):7.2f} dB (global) | "
              f"{nmse_segmented(pred, test.y, spec['nperseg']):7.2f} dB "
              f"(segmented)")

    # the SAME classical DPD as Phase 1.5 (data-driven ILA-GMP-510)
    dpd = ILAPredistorter(model_factory=gmp_opendpd_510, target_gain=g,
                          fit_kwargs={"regularization": 1e-9})
    dpd.fit_measured(train.x, train.y)
    u = dpd(np.concatenate([val.x[-200:], test.x]))

    print(f"\n-- same ILA-GMP-510 DPD, different evaluation surrogates --")
    print(f"{'surrogate':<12}{'ACLR_L':>9}{'ACLR_R':>9}{'ACLR_AVG':>10}"
          f"{'EVM(spec)':>11}")
    for label, sur in (("GMP-510", gmp_sur), ("neural", nn_sur)):
        y = sur(u)[200:]
        a = aclr_opendpd(y, *aclr_args)
        e = evm_spectral(y, g * test.x, *aclr_args)
        print(f"{label:<12}{a['left_dbc']:>9.2f}{a['right_dbc']:>9.2f}"
              f"{a['avg_dbc']:>10.2f}{e:>11.2f}")
    print("\npublished (OpenDPD, GRU surrogate): GMP-QR ACLR -38.80, "
          "EVM -38.53")


if __name__ == "__main__":
    main()
