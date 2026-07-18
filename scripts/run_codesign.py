#!/usr/bin/env python3
"""Phase 4: PA / DPD co-design trade study (AI-Native flow demo).

Sweeps the PA operating point; at each point reports the efficiency proxy,
the EVM without DPD, and the cheapest DDR DPD that meets the EVM spec (or
marks the point uninvertible). Then contrasts two design philosophies:

  * Sequential : pick the PA drive for maximum efficiency, then add DPD.
  * Co-design  : pick the drive that maximizes efficiency subject to the
                 EVM spec being reachable within a DPD cost budget.

Shows that co-design reaches the linearity target at higher efficiency /
lower DPD cost than the sequential flow, which tends to pick an operating
point that is expensive or impossible to linearize.
"""

import argparse
import os

import numpy as np

from padpd.codesign import codesign_sweep
from padpd.plotting import plt  # matplotlib Agg-configured
from padpd.waveform import OFDMConfig, generate_ofdm


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bandwidth", type=float, default=160e6)
    ap.add_argument("--qam", type=int, default=1024)
    ap.add_argument("--symbols", type=int, default=8)
    ap.add_argument("--evm-spec", type=float, default=-40.0,
                    help="EVM specification in dB")
    ap.add_argument("--cfr-papr", type=float, default=None)
    ap.add_argument("--dpd-budget", type=int, default=90,
                    help="max DPD coefficient count allowed (co-design)")
    ap.add_argument("--results", default="results/codesign")
    args = ap.parse_args()
    os.makedirs(args.results, exist_ok=True)

    cfg = OFDMConfig(bandwidth_hz=args.bandwidth, qam_order=args.qam,
                     n_symbols=args.symbols, seed=0)
    train = generate_ofdm(cfg)
    val = generate_ofdm(OFDMConfig(bandwidth_hz=args.bandwidth,
                                   qam_order=args.qam,
                                   n_symbols=args.symbols, seed=1))
    fs, bw = cfg.sample_rate_hz, cfg.bandwidth_hz

    drives = [0.08, 0.10, 0.12, 0.14, 0.17, 0.20, 0.24]
    rows = codesign_sweep(drives, train.x, val.x, val, args.evm_spec, fs, bw,
                          cfr_papr_db=args.cfr_papr)

    print(f"EVM spec {args.evm_spec:.0f} dB | DPD budget {args.dpd_budget} "
          f"coeffs | CFR {args.cfr_papr}")
    print(f"{'drive':>6}{'PAE%':>7}{'EVM noDPD':>11}{'DPD cost':>10}"
          f"{'EVM DPD':>9}{'feasible':>10}")
    for r in rows:
        print(f"{r['drive']:>6.2f}{100*r['pae']:>7.1f}{r['evm_nodpd']:>11.1f}"
              f"{r['dpd_cost']:>10}{r['evm_dpd']:>9.1f}"
              f"{'yes' if r['feasible'] else 'NO':>10}")

    # sequential: max efficiency ignoring DPD -> the highest drive
    seq = max(rows, key=lambda r: r["pae"])
    # co-design: max efficiency among points feasible within DPD budget
    feasible = [r for r in rows
                if r["feasible"] and r["dpd_cost"] <= args.dpd_budget]
    co = max(feasible, key=lambda r: r["pae"]) if feasible else None

    print("\n-- design decision --")
    print(f"Sequential (max PAE, DPD after): drive {seq['drive']:.2f}, "
          f"PAE {100*seq['pae']:.1f}%, "
          f"{'FEASIBLE' if seq['feasible'] and seq['dpd_cost']<=args.dpd_budget else 'over budget / uninvertible'} "
          f"(needs {seq['dpd_cost']} coeffs, EVM {seq['evm_dpd']:.1f})")
    if co:
        print(f"Co-design  (max PAE within budget): drive {co['drive']:.2f}, "
              f"PAE {100*co['pae']:.1f}%, DPD {co['dpd_cost']} coeffs, "
              f"EVM {co['evm_dpd']:.1f} dB")

    # plot: efficiency vs drive, feasibility, DPD cost
    fig, ax1 = plt.subplots(figsize=(8, 5))
    d = [r["drive"] for r in rows]
    ax1.plot(d, [100 * r["pae"] for r in rows], "o-", color="#B64342",
             label="PAE proxy (%)")
    ax1.set_xlabel("PA drive (operating point)")
    ax1.set_ylabel("PAE proxy (%)", color="#B64342")
    ax2 = ax1.twinx()
    ax2.plot(d, [r["dpd_cost"] for r in rows], "s--", color="#0F4D92",
             label="DPD cost (coeffs)")
    ax2.axhline(args.dpd_budget, color="#0F4D92", ls=":", alpha=0.5)
    ax2.set_ylabel("DPD cost to meet spec (coeffs)", color="#0F4D92")
    for r in rows:
        if not r["feasible"]:
            ax1.axvspan(r["drive"] - 0.005, r["drive"] + 0.005,
                        color="gray", alpha=0.15)
    if co:
        ax1.axvline(co["drive"], color="green", lw=2, alpha=0.6,
                    label="co-design point")
    ax1.legend(loc="upper left")
    fig.tight_layout()
    path = os.path.join(args.results, "codesign_tradeoff.png")
    fig.savefig(path, dpi=150)
    print(f"\nplot saved to {path}")


if __name__ == "__main__":
    main()
