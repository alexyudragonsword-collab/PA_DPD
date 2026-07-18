"""Pre-tapeout PA+DPD prediction from circuit-simulation exports.

Builds a Wiener-Hammerstein PA from a harmonic-balance AM-AM/AM-PM
sweep plus input/output matching S21 tables, then runs the padpd
prediction chain on it: GMP behavioral fit -> ILA DPD -> EVM / ACLR /
mask verdict. This is the "will this PA pass spec with DPD, and at what
back-off" answer before silicon exists.

Usage:
    python scripts/import_hb_pa.py --amam hb.csv \
        [--s21-in in.csv] [--s21-out out.csv] [--drive 0.9] [--bw 80e6]
    python scripts/import_hb_pa.py --demo     # generate example CSVs
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from padpd.dpd import ILAPredistorter
from padpd.metrics import (aclr, check_mask, default_wifi_mask,
                           evm, psd)
from padpd.pa import GMPModel, SalehPA, load_hb_pa, nmse_db
from padpd.waveform import OFDMConfig, demodulate_ofdm, generate_ofdm


def write_demo_csvs(out_dir: Path) -> dict:
    """Emit example exports in exactly the documented CSV formats."""
    out_dir.mkdir(parents=True, exist_ok=True)
    saleh = SalehPA()
    r = np.linspace(1e-3, 2.0, 240)
    y = saleh(r.astype(complex))
    amam = out_dir / "hb_amam.csv"
    amam.write_text("\n".join(
        ["r_in,r_out,phase_deg"] +
        [f"{a:.6f},{abs(b):.6f},{np.rad2deg(np.angle(b)):.4f}"
         for a, b in zip(r, y)]))

    f = np.linspace(-160e6, 160e6, 33)
    s21_in = out_dir / "s21_in.csv"
    s21_in.write_text("\n".join(
        ["freq_hz,mag_db,phase_deg"] +
        [f"{fi:.0f},{0.6 * np.cos(2 * np.pi * fi / 260e6):.4f},"
         f"{10 * np.sin(2 * np.pi * fi / 260e6):.4f}" for fi in f]))
    s21_out = out_dir / "s21_out.csv"
    s21_out.write_text("\n".join(
        ["freq_hz,mag_db,phase_deg"] +
        [f"{fi:.0f},{0.3 * np.cos(2 * np.pi * fi / 400e6):.4f},"
         f"{5 * np.sin(2 * np.pi * fi / 400e6):.4f}" for fi in f]))
    return {"amam": str(amam), "s21_in": str(s21_in),
            "s21_out": str(s21_out)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--amam")
    ap.add_argument("--s21-in", dest="s21_in")
    ap.add_argument("--s21-out", dest="s21_out")
    ap.add_argument("--drive", type=float, default=0.14,
                    help="operating point applied inside the WH model")
    ap.add_argument("--bw", type=float, default=80e6)
    ap.add_argument("--demo", action="store_true",
                    help="generate example CSVs and run on them")
    args = ap.parse_args()

    if args.demo or not args.amam:
        paths = write_demo_csvs(Path("deploy_export/hb_example"))
        print("demo CSVs:", ", ".join(paths.values()))
        args.amam, args.s21_in, args.s21_out = (
            paths["amam"], paths["s21_in"], paths["s21_out"])

    cfg = OFDMConfig(bandwidth_hz=args.bw, qam_order=1024, n_symbols=6,
                     seed=0)
    fs = cfg.sample_rate_hz
    pa = load_hb_pa(args.amam, args.s21_in, args.s21_out, fs=fs,
                    drive=args.drive)
    print(f"imported WH PA: LUT {len(pa.r_in)} pts, "
          f"fir_in {len(pa.fir_in)} taps, fir_out {len(pa.fir_out)} taps, "
          f"drive {args.drive}")

    wf_tr = generate_ofdm(cfg)
    wf_val = generate_ofdm(replace(cfg, seed=1))

    # behavioral fit sanity: how well does GMP capture the imported PA
    gmp = GMPModel(order=7, memory_depth=4)
    gmp.fit(wf_tr.x, pa(wf_tr.x))
    print(f"GMP fit of imported PA: val NMSE "
          f"{nmse_db(pa(wf_val.x), gmp(wf_val.x)):.1f} dB")

    # DPD prediction
    dpd = ILAPredistorter(
        model_factory=lambda: GMPModel(order=7, memory_depth=4))
    dpd.fit(pa, wf_tr.x)

    for label, y in (("no DPD", pa(wf_val.x)),
                     ("ILA-GMP DPD", pa(dpd(wf_val.x)))):
        g = np.vdot(wf_val.x, y) / np.vdot(wf_val.x, wf_val.x)
        e = evm(demodulate_ofdm(y / g, wf_val), wf_val.tx_symbols).db
        a = aclr(y, fs, args.bw)
        fr, p_db = psd(y, fs)
        ok, _, _ = check_mask(fr, p_db, default_wifi_mask(args.bw))
        print(f"{label:<14} EVM {e:6.1f} dB   ACLR "
              f"{a['upper_dbc']:6.1f} dBc   mask "
              f"{'PASS' if ok else 'FAIL'}")

    print("\npre-tapeout verdict: sweep --drive (and CFR) to find the "
          "deepest operating point that still passes; see also the "
          "Co-Design page/scripts for the efficiency trade-off.")


if __name__ == "__main__":
    main()
