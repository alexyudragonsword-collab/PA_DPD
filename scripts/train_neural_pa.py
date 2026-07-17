#!/usr/bin/env python3
"""Train a neural PA behavioral model on an OpenDPD dataset.

Follows OpenDPD's recipe (sliding frames, AdamW/MSE, plateau schedule,
best checkpoint by validation NMSE) and reports test NMSE in both padpd
(global) and OpenDPD (segmented) conventions.

Example:
    python scripts/train_neural_pa.py \\
        --dataset-dir ../OpenDPD/datasets/DPA_200MHz \\
        --backbone dgru --hidden 8 --output models/dpa200_dgru_h8.pt
"""

import argparse
import os

from padpd.data import load_opendpd_dataset
from padpd.metrics import nmse_segmented
from padpd.nn import NeuralPAModel
from padpd.pa import gmp_opendpd_510, nmse_db


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--backbone", default="dgru",
                    choices=["gru", "dgru", "tcn"])
    ap.add_argument("--hidden", type=int, default=8)
    ap.add_argument("--layers", type=int, default=1)
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--frame-length", type=int, default=50)
    ap.add_argument("--frame-stride", type=int, default=1)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--compare-gmp", action="store_true",
                    help="also fit GMP-510 and print its test NMSE")
    ap.add_argument("--output", default=None,
                    help="checkpoint path (.pt); default models/<auto>.pt")
    args = ap.parse_args()

    ds = load_opendpd_dataset(args.dataset_dir)
    train, val, test, spec = ds["train"], ds["val"], ds["test"], ds["spec"]
    name = os.path.basename(os.path.normpath(args.dataset_dir))
    nperseg = spec["nperseg"]

    model = NeuralPAModel(backbone=args.backbone, hidden_size=args.hidden,
                          num_layers=args.layers, n_epochs=args.epochs,
                          frame_length=args.frame_length,
                          stride=args.frame_stride, lr=args.lr,
                          batch_size=args.batch_size, seed=args.seed)
    print(f"training {args.backbone}-H{args.hidden} "
          f"({model.n_params} params) on {name} "
          f"({len(train)} train samples, {args.epochs} epochs)")
    model.fit(train.x, train.y, val.x, val.y)

    pred = model(test.x)
    print(f"\n{args.backbone}-H{args.hidden} test NMSE: "
          f"global {nmse_db(test.y, pred):7.2f} dB | OpenDPD segmented "
          f"{nmse_segmented(pred, test.y, nperseg):7.2f} dB")

    if args.compare_gmp:
        gmp = gmp_opendpd_510().fit(train.x, train.y, regularization=1e-9)
        gpred = gmp(test.x)
        print(f"GMP-510 (510 real params) test NMSE: "
              f"global {nmse_db(test.y, gpred):7.2f} dB | segmented "
              f"{nmse_segmented(gpred, test.y, nperseg):7.2f} dB")

    out = args.output or os.path.join(
        "models", f"{name}_{args.backbone}_h{args.hidden}.pt")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    model.save(out)
    print(f"saved checkpoint to {out}")


if __name__ == "__main__":
    main()
