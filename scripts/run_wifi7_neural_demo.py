#!/usr/bin/env python3
"""WiFi 7 synthetic chain with a NEURAL PA model and DLA neural DPD.

Chain: 802.11be-style OFDM (default 320 MHz / 4096-QAM) -> optional CFR
-> ReferencePA (virtual DUT). A NeuralPAModel is fitted as the
differentiable surrogate, a DLA neural DPD is trained through it, and
the result is compared against the classical ILA-GMP DPD on constellation
EVM / ACLR / spectral mask (padpd native metrics).

Example:
    python scripts/run_wifi7_neural_demo.py --bandwidth 320e6 --qam 4096
"""

import argparse
import os

from padpd.cfr import cfr_clip_filter
from padpd.dpd import ILAPredistorter
from padpd.metrics import aclr, check_mask, default_wifi_mask, evm_of_signal
from padpd.nn import DLAPredistorter, NeuralPAModel
from padpd.pa import ReferencePA, nmse_db
from padpd.plotting import plot_psd_comparison
from padpd.waveform import OFDMConfig, generate_ofdm, papr_db


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bandwidth", type=float, default=320e6)
    ap.add_argument("--qam", type=int, default=4096)
    ap.add_argument("--symbols", type=int, default=10)
    ap.add_argument("--drive", type=float, default=0.14)
    ap.add_argument("--cfr-papr", type=float, default=None)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--hidden", type=int, default=8)
    ap.add_argument("--frame-stride", type=int, default=4)
    ap.add_argument("--results", default="results/neural")
    args = ap.parse_args()
    os.makedirs(args.results, exist_ok=True)

    cfg = OFDMConfig(bandwidth_hz=args.bandwidth, qam_order=args.qam,
                     n_symbols=args.symbols, seed=0)
    train = generate_ofdm(cfg)
    val = generate_ofdm(OFDMConfig(bandwidth_hz=args.bandwidth,
                                   qam_order=args.qam,
                                   n_symbols=args.symbols, seed=1))
    fs, bw = cfg.sample_rate_hz, cfg.bandwidth_hz
    x_train, x_val = train.x, val.x
    if args.cfr_papr is not None:
        x_train = cfr_clip_filter(x_train, args.cfr_papr, fs, bw)
        x_val = cfr_clip_filter(x_val, args.cfr_papr, fs, bw)

    pa = ReferencePA(drive=args.drive)
    print(f"WiFi 7 neural demo: {bw / 1e6:.0f} MHz / {args.qam}-QAM, "
          f"PAPR {papr_db(x_val):.2f} dB, drive {args.drive}")

    # 1. neural PA surrogate
    surrogate = NeuralPAModel(backbone="dgru", hidden_size=args.hidden,
                              n_epochs=args.epochs,
                              stride=args.frame_stride, seed=0)
    print(f"\nfitting neural PA surrogate ({surrogate.n_params} params)...")
    surrogate.fit(x_train, pa(x_train))
    print(f"surrogate NMSE on val: "
          f"{nmse_db(pa(x_val), surrogate(x_val)):.2f} dB")

    # 2. DLA neural DPD through the surrogate
    dpd = DLAPredistorter(backbone="dgru", hidden_size=args.hidden,
                          n_epochs=args.epochs, stride=args.frame_stride,
                          seed=0)
    print("\ntraining DLA neural DPD...")
    dpd.fit(surrogate, x_train)

    # 3. classical baseline on the same setup
    ila = ILAPredistorter(n_iterations=2).fit(pa, x_train)

    # 4. evaluate everything on the REAL (reference) PA
    mask = default_wifi_mask(bw)
    print(f"\n-- validation signal, real ReferencePA in the loop --")
    print(f"{'case':<22}{'EVM (dB)':>10}{'ACLR+ (dBc)':>13}{'mask':>7}")
    cases = {
        "no DPD": pa(x_val),
        "ILA-GMP DPD": pa(ila(x_val)),
        "DLA neural DPD": pa(dpd(x_val)),
    }
    from padpd.metrics import psd
    for label, y in cases.items():
        e = evm_of_signal(y, val).db
        a = aclr(y, fs, bw)["upper_dbc"]
        f, p = psd(y, fs)
        ok, _, _ = check_mask(f, p, mask)
        print(f"{label:<22}{e:>10.2f}{a:>13.2f}"
              f"{'PASS' if ok else 'FAIL':>7}")

    plot_psd_comparison(
        {"input (ideal)": x_val, **cases}, fs, mask=mask,
        path=os.path.join(args.results, "wifi7_psd_neural_vs_ila.png"))
    print(f"\nPSD plot saved to {args.results}/wifi7_psd_neural_vs_ila.png")


if __name__ == "__main__":
    main()
