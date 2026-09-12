"""Three-loop joint demo: QMC + observation de-embedding + adaptive DPD.

The system experiment behind manual section 5.9: a drifting PA behind a
TX front end (I/Q image + LO leakage), observed through a corrupted
loopback (delay, CFO, phase noise, RX I/Q, in-band ripple, noise).
Three configurations run over the same drift trajectory:

- raw:      adaptive DPD fed the raw loopback capture (broken);
- deembed:  DPD fed the de-embedded capture, no QMC (tracks drift,
            EVM pinned at the TX image-rejection ratio);
- full:     de-embed + QMC slow loop + adaptive DPD (pinned floor
            broken, tracks drift).

Prints the per-block table and saves the figure used by the manual.

Usage:  python scripts/run_three_loop_demo.py [--fast] [--out PNG]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from padpd.three_loop import run_three_loop

OUT_DEFAULT = str(Path(__file__).resolve().parent.parent
                  / "manual" / "assets" / "three_loop_demo.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--out", default=OUT_DEFAULT)
    args = ap.parse_args()

    res = run_three_loop(
        n_blocks=6 if args.fast else 12,
        n_symbols=4 if args.fast else 6,
        on_block=lambda d: print(
            f"block {d['block']:2d}  state {d['state']:.2f}  "
            f"raw {d['evm_raw']:6.1f}  deembed {d['evm_deembed']:6.1f}  "
            f"full {d['evm_full']:6.1f}  image {d['image_dbc']:6.1f} dBc",
            flush=True))

    print(f"\nfinal on-air EVM (hot): raw {res['final_raw']:.1f} dB, "
          f"de-embed only {res['final_deembed']:.1f} dB, "
          f"three loops {res['final_full']:.1f} dB")
    print(f"QMC: image {res['final_image_dbc']:.1f} dBc, "
          f"IRR estimate {res['qmc_irr_db']:.1f} dB")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9.2, 6.4), dpi=100, sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1.0]})
    fig.patch.set_facecolor("white")
    b = res["blocks"]
    ax1.plot(b, res["evm_raw"], "o-", color="#c0392b",
             label="raw loopback (no loops)")
    ax1.plot(b, res["evm_deembed"], "s-", color="#e67e22",
             label="de-embed only (no QMC)")
    ax1.plot(b, res["evm_full"], "d-", color="#2471a3",
             label="three loops (de-embed + QMC + DPD)")
    ax1.axhline(-30.1, color="#e67e22", ls=":", lw=1,
                label="TX IRR pin (~-30 dB)")
    ax1.set_ylabel("on-air EVM (dB)")
    ax1.set_title("QMC + observation de-embedding + adaptive DPD "
                  "on a drifting PA (cold → hot)")
    ax1.grid(alpha=0.3)
    ax1.legend(loc="center right", fontsize=9)

    ax2.plot(b, res["image_dbc"], "d-", color="#2471a3",
             label="TX image residual (QMC loop)")
    ax2.plot(b, res["dc_dbc"], "v-", color="#7d3c98",
             label="LO-leakage residual (QMC loop)")
    ax2.set_xlabel("signal block (drift state 0 → 1)")
    ax2.set_ylabel("residual (dBc)")
    ax2.grid(alpha=0.3)
    ax2.legend(loc="center right", fontsize=9)

    fig.tight_layout()
    fig.savefig(args.out, dpi=100, facecolor="white")
    print(f"figure -> {args.out}")


if __name__ == "__main__":
    main()
