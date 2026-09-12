#!/usr/bin/env python3
"""End-to-end baseline demo: OFDM -> PA -> GMP model -> ILA DPD -> metrics.

Steps
-----
1. Generate a WiFi 7-style OFDM burst (default 160 MHz, 1024-QAM).
2. Pass it through the virtual ReferencePA (stand-in for Spectre envelope
   simulation) and measure the distortion.
3. Fit MP and GMP behavioral models, report NMSE on a held-out signal.
4. Train an ILA-GMP predistorter and compare no-DPD vs DPD:
   EVM, ACLR, spectral mask margin, plus PSD / constellation / AM-AM plots.

Outputs are printed to the console and saved under results/.
"""

import argparse
import os


from padpd.cfr import cfr_clip_filter
from padpd.dpd import ILAPredistorter
from padpd.metrics import (aclr, check_mask, default_wifi_mask, evm_of_signal,
                           psd)
from padpd.pa import GMPModel, MemoryPolynomialModel, ReferencePA, nmse_db
from padpd.plotting import (plot_am_curves, plot_constellation,
                            plot_psd_comparison)
from padpd.waveform import (OFDMConfig, demodulate_ofdm, generate_ofdm,
                            papr_db)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bandwidth", type=float, default=160e6)
    ap.add_argument("--qam", type=int, default=1024)
    ap.add_argument("--symbols", type=int, default=20)
    ap.add_argument("--drive", type=float, default=0.14)
    ap.add_argument("--cfr-papr", type=float, default=None,
                    help="enable CFR (iterative clipping and filtering) to "
                         "this target PAPR in dB before the PA; lets DPD "
                         "work at aggressive operating points (drive>=0.22)")
    ap.add_argument("--results", default="results")
    args = ap.parse_args()
    os.makedirs(args.results, exist_ok=True)

    # --- 1. waveform ------------------------------------------------------
    cfg = OFDMConfig(bandwidth_hz=args.bandwidth, qam_order=args.qam,
                     n_symbols=args.symbols, seed=0)
    train = generate_ofdm(cfg)
    val_cfg = OFDMConfig(bandwidth_hz=args.bandwidth, qam_order=args.qam,
                         n_symbols=args.symbols, seed=1)
    val = generate_ofdm(val_cfg)
    fs, bw = cfg.sample_rate_hz, cfg.bandwidth_hz
    print("=" * 64)
    print("WiFi 7 PA + DPD baseline demo")
    print("=" * 64)
    print(f"bandwidth      : {bw / 1e6:.0f} MHz  ({cfg.fft_size}-FFT, "
          f"{cfg.n_active} active tones)")
    print(f"modulation     : {args.qam}-QAM, {args.symbols} OFDM symbols")
    print(f"sample rate    : {fs / 1e6:.0f} MSPS (x{cfg.oversampling} "
          f"oversampling)")
    print(f"waveform PAPR  : {papr_db(train.x):.2f} dB")

    # --- 2. optional CFR ----------------------------------------------------
    x_train, x_val = train.x, val.x
    if args.cfr_papr is not None:
        x_train = cfr_clip_filter(x_train, args.cfr_papr, fs, bw)
        x_val = cfr_clip_filter(x_val, args.cfr_papr, fs, bw)
        print(f"CFR            : target {args.cfr_papr:.1f} dB -> "
              f"PAPR {papr_db(x_val):.2f} dB, "
              f"EVM cost {evm_of_signal(x_val, val).db:.1f} dB")

    # --- 3. PA (virtual DUT) ----------------------------------------------
    pa = ReferencePA(drive=args.drive)
    y_train = pa(x_train)
    y_val = pa(x_val)

    # --- 4. behavioral models ---------------------------------------------
    mp = MemoryPolynomialModel(order=7, memory_depth=4).fit(x_train, y_train)
    gmp = GMPModel().fit(x_train, y_train)
    print("\n-- PA behavioral modeling (validation NMSE, unseen signal) --")
    print(f"Memory Polynomial (order 7, mem 4)  : "
          f"{nmse_db(y_val, mp(x_val)):7.2f} dB")
    print(f"GMP ({gmp.n_coeffs} coeffs)                    : "
          f"{nmse_db(y_val, gmp(x_val)):7.2f} dB")

    # --- 5. DPD -------------------------------------------------------------
    dpd = ILAPredistorter(n_iterations=2).fit(pa, x_train)
    y_dpd_val = pa(dpd(x_val))

    mask = default_wifi_mask(bw)
    rows = []
    for label, sig in (("no DPD", y_val), ("ILA-GMP DPD", y_dpd_val)):
        e = evm_of_signal(sig, val)
        a = aclr(sig, fs, bw)
        f, p = psd(sig, fs)
        ok, margin, _ = check_mask(f, p, mask)
        rows.append((label, e.db, a["lower_dbc"], a["upper_dbc"],
                     margin, "PASS" if ok else "FAIL"))

    print("\n-- linearization results (validation signal) --")
    header = (f"{'case':<14}{'EVM (dB)':>10}{'ACLR- (dBc)':>13}"
              f"{'ACLR+ (dBc)':>13}{'mask margin':>13}{'mask':>7}")
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r[0]:<14}{r[1]:>10.2f}{r[2]:>13.2f}{r[3]:>13.2f}"
              f"{r[4]:>12.2f} {r[5]:>6}")

    # --- 6. plots -----------------------------------------------------------
    plot_psd_comparison(
        {"input (ideal)": val.x, "PA, no DPD": y_val,
         "PA + ILA-GMP DPD": y_dpd_val},
        fs, mask=mask, path=os.path.join(args.results, "psd_comparison.png"))
    g = dpd.target_gain
    plot_constellation(
        {"no DPD": demodulate_ofdm(y_val / g, val),
         "ILA-GMP DPD": demodulate_ofdm(y_dpd_val / g, val)},
        path=os.path.join(args.results, "constellation.png"))
    plot_am_curves(
        {"no DPD": (x_val, y_val), "DPD": (x_val, y_dpd_val)},
        path=os.path.join(args.results, "am_am_am_pm.png"))
    print(f"\nplots saved to {args.results}/ (psd_comparison.png, "
          f"constellation.png, am_am_am_pm.png)")


if __name__ == "__main__":
    main()
