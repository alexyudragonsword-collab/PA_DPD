#!/usr/bin/env python3
"""Phase 3: fixed-point deployment analysis of classical DPD models.

For a real OpenDPD dataset, fits DDR-Volterra and GMP predistorters
(data-driven ILA), evaluates each at several coefficient/signal bit
widths (bit-true), and reports the DPD ACLR through a trained neural
surrogate plus the hardware MAC cost. Shows the accuracy-vs-bitwidth
tradeoff and DDR's parameter-efficiency advantage in fixed point.

Example:
    python scripts/quantize_dpd.py \\
        --dataset-dir ../OpenDPD/datasets/DPA_160MHz \\
        --pa-model models/DPA_160MHz_dgru_h8_f200.pt
"""

import argparse
import os

import numpy as np

from padpd.data import load_opendpd_dataset
from padpd.deploy import FixedPointPolyModel, mac_cost
from padpd.dpd import ILAPredistorter
from padpd.metrics import aclr_opendpd, target_gain_opendpd
from padpd.nn import NeuralPAModel
from padpd.pa import ddr_volterra_default, gmp_opendpd_510

WARMUP = 200


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--pa-model", required=True)
    ap.add_argument("--bits", type=int, nargs="+", default=[16, 12, 10, 8])
    args = ap.parse_args()

    ds = load_opendpd_dataset(args.dataset_dir)
    tr, va, te, spec = ds["train"], ds["val"], ds["test"], ds["spec"]
    name = os.path.basename(os.path.normpath(args.dataset_dir))
    fs = tr.sample_rate_hz
    A = (fs, spec["bw_main_ch"], spec["n_sub_ch"], spec["nperseg"])
    g = target_gain_opendpd(tr.x, tr.y)
    pa = NeuralPAModel.load(args.pa_model)
    ctx = va.x[-WARMUP:]

    def dpd_aclr(predist):
        y = pa(predist(np.concatenate([ctx, te.x])))[WARMUP:]
        return aclr_opendpd(y, *A)["avg_dbc"]

    print(f"=== {name}: fixed-point DPD (ACLR_AVG dBc, neural surrogate) ===")
    bases = [("DDR r=1", ddr_volterra_default),
             ("GMP-510", gmp_opendpd_510)]
    header = f"{'DPD basis':<10}{'cplx':>6}{'float':>9}" + \
             "".join(f"{'W'+str(b):>9}" for b in args.bits)
    print(header)
    for label, factory in bases:
        ila = ILAPredistorter(model_factory=factory, target_gain=g,
                              fit_kwargs={"regularization": 1e-9})
        ila.fit_measured(tr.x, tr.y)
        model = ila.dpd_model
        nc = model.basis_matrix(np.ones(20, dtype=complex)).shape[1]
        row = f"{label:<10}{nc:>6}{dpd_aclr(ila):>9.2f}"
        for b in args.bits:
            fp = FixedPointPolyModel(model, w_bits=b, sig_bits=b)
            row += f"{dpd_aclr(lambda x, m=fp: m(x)):>9.2f}"
        print(row)
        c = mac_cost(nc, fs)
        print(f"           HW cost: {c['real_macs_per_sample']} real MAC/sample"
              f"  ->  {c['real_gmac_per_s']:.1f} GMAC/s @ {fs/1e6:.0f} MSPS")


if __name__ == "__main__":
    main()
