#!/usr/bin/env python3
"""Train a DLA neural DPD against a trained neural PA surrogate.

OpenDPD protocol: freeze the neural PA model, train a neural DPD through
it toward the linear target G*x (G = peak-amplitude-ratio gain from the
measured data), select the best checkpoint by validation ACLR_AVG.
Reports ACLR / spectral EVM (OpenDPD conventions) on the test split.

Example:
    python scripts/train_neural_dpd.py \\
        --dataset-dir ../OpenDPD/datasets/DPA_200MHz \\
        --pa-model models/DPA_200MHz_dgru_h8.pt \\
        --output models/DPA_200MHz_dpd_dgru_h8.pt
"""

import argparse
import os

from padpd.data import load_opendpd_dataset
from padpd.metrics import aclr_opendpd, evm_spectral, target_gain_opendpd
from padpd.nn import DLAPredistorter, NeuralPAModel
from padpd.plotting import plot_psd_comparison


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--pa-model", required=True,
                    help="NeuralPAModel checkpoint (.pt)")
    ap.add_argument("--backbone", default="dgru", choices=["gru", "dgru"])
    ap.add_argument("--hidden", type=int, default=8)
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--frame-length", type=int, default=50)
    ap.add_argument("--frame-stride", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output", default=None)
    ap.add_argument("--results", default="results/neural")
    args = ap.parse_args()

    ds = load_opendpd_dataset(args.dataset_dir)
    train, val, test, spec = ds["train"], ds["val"], ds["test"], ds["spec"]
    name = os.path.basename(os.path.normpath(args.dataset_dir))
    fs = train.sample_rate_hz
    bw, n_sub, nperseg = spec["bw_main_ch"], spec["n_sub_ch"], spec["nperseg"]
    aclr_args = (fs, bw, n_sub, nperseg)

    pa = NeuralPAModel.load(args.pa_model)
    g = target_gain_opendpd(train.x, train.y)

    dpd = DLAPredistorter(
        backbone=args.backbone, hidden_size=args.hidden,
        n_epochs=args.epochs, frame_length=args.frame_length,
        stride=args.frame_stride, seed=args.seed, target_gain=g,
        aclr_spec={"fs": fs, "bw_main_ch": bw, "n_sub_ch": n_sub,
                   "nperseg": nperseg})
    print(f"training DLA DPD {args.backbone}-H{args.hidden} "
          f"({dpd.n_params} params) on {name}, target gain {g:.3f}")
    dpd.fit(pa, train.x, val.x)

    y_dpd = pa(dpd(test.x))
    print(f"\n-- {name} test split, OpenDPD conventions "
          f"(neural-surrogate evaluation) --")
    print(f"{'case':<26}{'ACLR_L':>9}{'ACLR_R':>9}{'ACLR_AVG':>10}"
          f"{'EVM(spec)':>11}")
    for label, sig in (("no DPD (measured)", test.y),
                       (f"DLA {args.backbone}-H{args.hidden}", y_dpd)):
        a = aclr_opendpd(sig, *aclr_args)
        e = evm_spectral(sig, g * test.x, *aclr_args)
        print(f"{label:<26}{a['left_dbc']:>9.2f}{a['right_dbc']:>9.2f}"
              f"{a['avg_dbc']:>10.2f}{e:>11.2f}")

    out = args.output or os.path.join(
        "models", f"{name}_dpd_{args.backbone}_h{args.hidden}.pt")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    dpd.save(out)
    os.makedirs(os.path.join(args.results, name), exist_ok=True)
    plot_psd_comparison(
        {"input (scaled)": g * test.x, "PA, no DPD": test.y,
         "PA + DLA neural DPD": y_dpd}, fs,
        path=os.path.join(args.results, name, "psd_neural_dpd.png"))
    print(f"saved {out} and PSD plot")


if __name__ == "__main__":
    main()
