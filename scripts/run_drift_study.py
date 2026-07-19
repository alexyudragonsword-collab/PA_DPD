"""PA drift tracking study: adaptive DPD vs a frozen batch DPD.

A PA drifts (temperature/aging) across a capture. Two predistorters run
against the same drifting PA over a sequence of signal blocks:

- **frozen batch DPD** — identified once at t=0 (cold PA) and never
  updated; the field-staleness baseline.
- **adaptive RLS DPD** — re-updates every block from the loopback
  observation, tracking the drift.

Prints per-block EVM/ACLR for both and the final gap, quantifying how
much linearization a field unit loses without adaptation.

Usage:  python scripts/run_drift_study.py [--fast]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from padpd.dpd import AdaptiveDPD, ILAPredistorter
from padpd.metrics import aclr, evm
from padpd.pa import DriftingReferencePA, GMPModel
from padpd.waveform import OFDMConfig, demodulate_ofdm, generate_ofdm

BW = 80e6


def _evm_aclr(pa, sig, wf, fs):
    y = pa(sig)
    g = np.vdot(wf.x, y) / np.vdot(wf.x, wf.x)
    e = evm(demodulate_ofdm(y / g, wf), wf.tx_symbols).db
    a = aclr(y, fs, BW)["upper_dbc"]
    return e, a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    args = ap.parse_args()
    n_blocks = 8 if args.fast else 14

    cfg = OFDMConfig(bandwidth_hz=BW, qam_order=1024, n_symbols=6, seed=0)
    fs = cfg.sample_rate_hz
    # distinct signal block per step (fresh random data, like a real stream)
    blocks = [generate_ofdm(replace(cfg, seed=s)) for s in range(n_blocks)]

    drift = DriftingReferencePA(drive0=0.13, drive_span=0.02,
                                beta_a_span=0.2, alpha_p_span=0.5)

    # frozen batch DPD identified on the cold PA
    drift.set_state(0.0)
    cold_pa = drift.pa()
    batch = ILAPredistorter(
        lambda: GMPModel(order=7, memory_depth=4), n_iterations=3)
    batch.fit(cold_pa, blocks[0].x)

    # adaptive DPD, warm-started on the cold PA
    adapt = AdaptiveDPD(lambda: GMPModel(order=7, memory_depth=4),
                        forget=0.6)
    adapt.warm_start(cold_pa, blocks[0].x, blocks=6)

    print(f"drift study: {n_blocks} blocks, PA drifts cold->hot "
          f"(drive {drift.drive0:.3f}->{drift.drive0 + drift.drive_span:.3f})")
    print(f"{'blk':>3} {'state':>6} | {'frozen EVM':>10} {'ACLR':>7} | "
          f"{'adapt EVM':>10} {'ACLR':>7}")
    print("-" * 58)

    gaps = []
    for i, wf in enumerate(blocks):
        drift.set_state(i / (n_blocks - 1))
        pa = drift.pa()
        eb, ab = _evm_aclr(pa, batch(wf.x), wf, fs)
        # adaptive: apply current DPD, then update from this block's loopback
        ea, aa = _evm_aclr(pa, adapt(wf.x), wf, fs)
        adapt.update(pa, wf.x)
        gaps.append(eb - ea)
        print(f"{i:>3} {drift.state:>6.2f} | {eb:>10.1f} {ab:>7.1f} | "
              f"{ea:>10.1f} {aa:>7.1f}", flush=True)

    print("-" * 58)
    print(f"at full drift: frozen EVM {eb:.1f} dB vs adaptive {ea:.1f} dB "
          f"-> adaptation saves {eb - ea:.1f} dB EVM")
    print(f"mean EVM gap (frozen worse by): {np.mean(gaps):.1f} dB")


if __name__ == "__main__":
    main()
