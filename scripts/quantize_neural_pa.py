#!/usr/bin/env python3
"""Phase 3: fixed-point comparison of neural (PTQ) vs linear PA models.

Loads a trained neural PA checkpoint and fits the linear-params baselines,
then evaluates every model bit-true across bit widths (neural via
post-training quantization of weights+activations; linear via
FixedPointPolyModel). Reports test NMSE and per-sample MAC cost, so the
accuracy / robustness / hardware tradeoff is visible in one table.

Example:
    python scripts/quantize_neural_pa.py \\
        --dataset-dir ../OpenDPD/datasets/DPA_200MHz \\
        --pa-model models/DPA_200MHz_tcn_h16_f200.pt
"""

import argparse
import os

import numpy as np

from padpd.data import load_opendpd_dataset
from padpd.deploy import FixedPointPolyModel, mac_cost
from padpd.nn import NeuralPAModel, quantize_neural_ptq
from padpd.pa import ddr_volterra_default, gmp_opendpd_510, nmse_db

WARMUP = 200


def tcn_mac_per_sample(hidden: int) -> int:
    """Real MAC/sample for the OpenDPD TCN (pointwise + 4 depthwise k5 +
    pointwise)."""
    return 6 * hidden + 4 * (hidden * 5) + hidden * 2


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--pa-model", required=True,
                    help="trained neural PA checkpoint (.pt)")
    ap.add_argument("--bits", type=int, nargs="+", default=[16, 12, 10, 8])
    args = ap.parse_args()

    ds = load_opendpd_dataset(args.dataset_dir)
    tr, va, te = ds["train"], ds["val"], ds["test"]
    name = os.path.basename(os.path.normpath(args.dataset_dir))
    ctx = va.x[-WARMUP:]

    def full(sig_fn):
        return sig_fn(np.concatenate([ctx, te.x]))[WARMUP:]

    hdr = (f"{'model':<16}{'MAC/smp':>8}{'float':>8}"
           + "".join(f"{'W'+str(b):>8}" for b in args.bits))
    print(f"=== {name}: PA modeling, fixed-point NMSE (dB) ===")
    print(hdr)

    # neural (PTQ)
    neural = NeuralPAModel.load(args.pa_model)
    cfg = neural.config
    n_mac = (tcn_mac_per_sample(cfg["hidden_size"])
             if cfg["backbone"] == "tcn" else "-")
    row = f"{cfg['backbone']+'-H'+str(cfg['hidden_size'])+'(nn)':<16}" \
          f"{str(n_mac):>8}{nmse_db(te.y, full(neural)):>8.2f}"
    for b in args.bits:
        q = quantize_neural_ptq(neural, w_bits=b, a_bits=b)
        row += f"{nmse_db(te.y, full(q)):>8.2f}"
    print(row)

    # linear-params baselines
    for label, factory in [("DDR r=1", ddr_volterra_default),
                           ("GMP-510", gmp_opendpd_510)]:
        m = factory().fit(tr.x, tr.y, regularization=1e-9)
        nc = m.basis_matrix(np.ones(20, dtype=complex)).shape[1]
        row = f"{label:<16}{mac_cost(nc, 1)['real_macs_per_sample']:>8}" \
              f"{nmse_db(te.y, full(m)):>8.2f}"
        for b in args.bits:
            fp = FixedPointPolyModel(m, b, b)
            row += f"{nmse_db(te.y, full(fp)):>8.2f}"
        print(row)

    print("\nNeural PTQ = weight+activation post-training quantization "
          "(TCN fully bit-true; RNN activations approximate).")


if __name__ == "__main__":
    main()
