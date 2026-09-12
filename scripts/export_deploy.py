#!/usr/bin/env python3
"""Phase 3: generate deployment hand-off artifacts for a dataset.

For the given OpenDPD dataset, fits the classical DPD bases and exports:
- quantized integer coefficients (JSON) for GMP and DDR predistorters,
- bit-true reference input/output vectors (CSV) for RTL verification,
- (if a neural checkpoint is given) an ONNX model + reference vectors.

Everything lands under <out>/<dataset>/ so a hardware team can implement
and check the datapath sample-for-sample against these files.

Example:
    python scripts/export_deploy.py \\
        --dataset-dir ../OpenDPD/datasets/DPA_160MHz \\
        --pa-model models/DPA_200MHz_tcn_h16_f200.pt --w-bits 16
"""

import argparse
import os

from padpd.data import load_opendpd_dataset
from padpd.deploy import (
    FixedPointPolyModel,
    export_linear_coeffs,
    export_reference_vectors,
)
from padpd.dpd import ILAPredistorter
from padpd.metrics import target_gain_opendpd
from padpd.pa import ddr_volterra_default, gmp_opendpd_510


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--pa-model", default=None,
                    help="optional neural checkpoint to export to ONNX")
    ap.add_argument("--w-bits", type=int, default=16)
    ap.add_argument("--n-vectors", type=int, default=4096)
    ap.add_argument("--out", default="deploy_export")
    args = ap.parse_args()

    ds = load_opendpd_dataset(args.dataset_dir)
    tr, te = ds["train"], ds["test"]
    name = os.path.basename(os.path.normpath(args.dataset_dir))
    out = os.path.join(args.out, name)
    os.makedirs(out, exist_ok=True)
    g = target_gain_opendpd(tr.x, tr.y)

    # classical DPD bases -> integer coeffs + bit-true reference vectors
    for label, factory in [("gmp510", gmp_opendpd_510),
                           ("ddr_r1", ddr_volterra_default)]:
        ila = ILAPredistorter(model_factory=factory, target_gain=g,
                              fit_kwargs={"regularization": 1e-9})
        ila.fit_measured(tr.x, tr.y)
        model = ila.dpd_model
        cpath = os.path.join(out, f"{label}_w{args.w_bits}_coeffs.json")
        p = export_linear_coeffs(model, args.w_bits, cpath)
        fp = FixedPointPolyModel(model, args.w_bits, args.w_bits)
        vpath = os.path.join(out, f"{label}_w{args.w_bits}_refvec.csv")
        export_reference_vectors(fp, te.x, vpath, n=args.n_vectors)
        print(f"{label}: {p['n_coeffs']} coeffs "
              f"(scale 2^{p['coeff_scale_exp']})"
              f" -> {os.path.basename(cpath)}, {os.path.basename(vpath)}")

    # optional neural ONNX export
    if args.pa_model:
        from padpd.deploy import export_onnx
        from padpd.nn import NeuralPAModel
        nm = NeuralPAModel.load(args.pa_model)
        opath = os.path.join(out, "neural_pa.onnx")
        res = export_onnx(nm, opath, frame_length=nm.config["frame_length"])
        status = (f"verified (max err {res.get('max_abs_err', 0):.1e})"
                  if res.get("verified") else res.get("note", "exported"))
        vpath = os.path.join(out, "neural_pa_refvec.csv")
        export_reference_vectors(nm, te.x, vpath, n=args.n_vectors)
        print(f"neural: {os.path.basename(opath)} [{status}], "
              f"{os.path.basename(vpath)}")

    print(f"\nartifacts in {out}/")


if __name__ == "__main__":
    main()
