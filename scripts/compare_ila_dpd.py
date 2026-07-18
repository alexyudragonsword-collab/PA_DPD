#!/usr/bin/env python3
"""Compare classical ILA DPD basis families (GMP vs DDR-Volterra).

Runs the identical ILA protocol (data-driven post-inverse fit) with
different basis families and evaluates every predistorter through the
SAME trained neural PA surrogate, so the only variable is the DPD basis.
Metrics are OpenDPD-convention ACLR / spectral EVM on the test split.

Requires trained neural surrogates (scripts/train_neural_pa.py); pass one
per dataset. Absolute numbers are only trustworthy down to the surrogate's
NMSE floor, but the relative comparison across bases is fair.

Example:
    python scripts/compare_ila_dpd.py \\
        --dataset-dir ../OpenDPD/datasets/DPA_160MHz \\
        --pa-model models/DPA_160MHz_dgru_h8_f200.pt
"""

import argparse
import os

import numpy as np

from padpd.data import load_opendpd_dataset
from padpd.dpd import ILAPredistorter
from padpd.metrics import aclr_opendpd, evm_spectral, target_gain_opendpd
from padpd.nn import NeuralPAModel
from padpd.pa import DDRVolterraModel, ddr_volterra_default, gmp_opendpd_510

WARMUP = 200


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--pa-model", required=True,
                    help="trained NeuralPAModel checkpoint (evaluation "
                         "surrogate)")
    args = ap.parse_args()

    ds = load_opendpd_dataset(args.dataset_dir)
    tr, va, te, spec = ds["train"], ds["val"], ds["test"], ds["spec"]
    name = os.path.basename(os.path.normpath(args.dataset_dir))
    A = (tr.sample_rate_hz, spec["bw_main_ch"], spec["n_sub_ch"],
         spec["nperseg"])
    g = target_gain_opendpd(tr.x, tr.y)
    pa = NeuralPAModel.load(args.pa_model)
    ctx = va.x[-WARMUP:]

    def evaluate(sig):
        return (aclr_opendpd(sig, *A)["avg_dbc"],
                evm_spectral(sig, g * te.x, *A))

    print(f"=== {name}: ILA DPD basis comparison "
          f"(neural-surrogate eval, OpenDPD conventions) ===")
    print(f"{'DPD basis':<16}{'cplx':>6}{'ACLR_AVG':>10}{'EVM(spec)':>11}")
    a0, e0 = evaluate(pa(np.concatenate([ctx, te.x]))[WARMUP:])
    print(f"{'(no DPD)':<16}{'-':>6}{a0:>10.2f}{e0:>11.2f}")

    bases = [
        ("ILA-GMP-510", gmp_opendpd_510, 255),
        ("ILA-DDR r=1", ddr_volterra_default, 140),
        ("ILA-DDR r=2",
         lambda: DDRVolterraModel(order=5, memory_depth=8, dynamic_order=2),
         441),
    ]
    for label, factory, nc in bases:
        dpd = ILAPredistorter(model_factory=factory, target_gain=g,
                              fit_kwargs={"regularization": 1e-9})
        dpd.fit_measured(tr.x, tr.y)
        a, e = evaluate(pa(dpd(np.concatenate([ctx, te.x])))[WARMUP:])
        print(f"{label:<16}{nc:>6}{a:>10.2f}{e:>11.2f}")


if __name__ == "__main__":
    main()
