#!/usr/bin/env python3
"""Generate a synthetic PA input/output dataset.

OFDM waveform -> ReferencePA -> IQDataset (.npz). The output file stands
in for a Cadence envelope simulation until real EDA data is available.

Example:
    python scripts/generate_dataset.py --bandwidth 160e6 --qam 1024 \\
        --symbols 40 --seed 0 --output data/pa_160mhz_1024qam.npz
"""

import argparse
import os

from padpd.data import IQDataset
from padpd.pa import ReferencePA
from padpd.waveform import OFDMConfig, generate_ofdm, papr_db


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bandwidth", type=float, default=160e6,
                    help="channel bandwidth in Hz (20e6..320e6)")
    ap.add_argument("--qam", type=int, default=1024,
                    help="QAM order (16..4096)")
    ap.add_argument("--symbols", type=int, default=40,
                    help="number of OFDM symbols")
    ap.add_argument("--oversampling", type=int, default=4)
    ap.add_argument("--drive", type=float, default=0.14,
                    help="ReferencePA operating point")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output", default="data/pa_dataset.npz")
    args = ap.parse_args()

    cfg = OFDMConfig(bandwidth_hz=args.bandwidth, qam_order=args.qam,
                     n_symbols=args.symbols, oversampling=args.oversampling,
                     seed=args.seed)
    wf = generate_ofdm(cfg)
    pa = ReferencePA(drive=args.drive)
    y = pa(wf.x)

    ds = IQDataset(wf.x, y, cfg.sample_rate_hz, meta={
        "source": "synthetic-reference-pa",
        "bandwidth_hz": args.bandwidth,
        "qam_order": args.qam,
        "n_symbols": args.symbols,
        "oversampling": args.oversampling,
        "drive": args.drive,
        "seed": args.seed,
    })
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    ds.save(args.output)
    print(f"saved {len(ds)} samples to {args.output}")
    print(f"  sample rate : {cfg.sample_rate_hz / 1e6:.1f} MSPS")
    print(f"  waveform PAPR: {papr_db(wf.x):.2f} dB")


if __name__ == "__main__":
    main()
