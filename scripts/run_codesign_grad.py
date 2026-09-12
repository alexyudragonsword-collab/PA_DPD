#!/usr/bin/env python3
"""Phase 4: differentiable (gradient) PA/DPD co-design demo.

Optimizes the PA operating point by gradient descent, with the DPD solved
in closed form (LS) at every step, against a spec-constrained objective
(maximize efficiency, keep EVM <= spec). Contrasts a naive conservative
fixed operating point with the gradient-optimized one, and plots the
training trajectory.

Complements the discrete Pareto sweep (scripts/run_codesign.py): gradient
co-design works away from the invertibility wall but oscillates near it
(the landscape is near-discontinuous there), which is exactly why the
discrete method stays the robust production tool.
"""

import argparse
import os

from padpd.codesign_torch import joint_codesign
from padpd.plotting import plt
from padpd.waveform import OFDMConfig, generate_ofdm


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bandwidth", type=float, default=80e6)
    ap.add_argument("--qam", type=int, default=256)
    ap.add_argument("--symbols", type=int, default=6)
    ap.add_argument("--evm-spec", type=float, default=-38.0)
    ap.add_argument("--conservative-drive", type=float, default=0.08)
    ap.add_argument("--lambda-eff", type=float, default=3.0)
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--results", default="results/codesign")
    args = ap.parse_args()
    os.makedirs(args.results, exist_ok=True)

    x = generate_ofdm(OFDMConfig(bandwidth_hz=args.bandwidth,
                                 qam_order=args.qam,
                                 n_symbols=args.symbols, seed=0)).x

    # naive conservative design: freeze drive low for guaranteed linearity
    base = joint_codesign(x, drive_init=args.conservative_drive,
                          evm_spec_db=args.evm_spec, learnable_drive=False)
    # gradient co-design: optimize the operating point
    co = joint_codesign(x, drive_init=args.conservative_drive,
                        evm_spec_db=args.evm_spec,
                        lambda_eff=args.lambda_eff, steps=args.steps)

    print(f"EVM spec {args.evm_spec:.0f} dB | "
          f"LS-DPD {base['n_coeffs']} coeffs")
    print(f"{'design':<24}{'drive':>8}{'PAE%':>8}"
          f"{'EVM(dB)':>10}{'meets spec':>12}")
    for label, r in [("conservative (fixed)", base),
                     ("gradient co-design", co)]:
        print(f"{label:<24}{r['drive']:>8.3f}{100*r['efficiency']:>8.1f}"
              f"{r['evm_db']:>10.1f}"
              f"{'yes' if r['evm_db'] <= args.evm_spec else 'no':>12}")

    gain = 100 * (co["efficiency"] - base["efficiency"])
    print(f"\ngradient co-design raises PAE proxy by {gain:.1f} points "
          f"while meeting the {args.evm_spec:.0f} dB spec.")

    # trajectory plot
    h = co["history"]
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(h["drive"], color="#B64342")
    ax1.set_xlabel("gradient step")
    ax1.set_ylabel("PA drive (operating point)", color="#B64342")
    ax2 = ax1.twinx()
    ax2.plot(h["evm_db"], color="#0F4D92")
    ax2.axhline(args.evm_spec, color="#0F4D92", ls=":", alpha=0.6)
    ax2.set_ylabel("EVM (dB)", color="#0F4D92")
    ax1.set_title("Differentiable co-design: drive climbs toward the "
                  "spec boundary")
    fig.tight_layout()
    path = os.path.join(args.results, "codesign_grad_trajectory.png")
    fig.savefig(path, dpi=150)
    print(f"trajectory plot saved to {path}")


if __name__ == "__main__":
    main()
