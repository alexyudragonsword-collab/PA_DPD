"""Two-tone memory diagnostics -> DPD resource budget, and its validation.

Idea (the workflow this answers): a pre-tapeout circuit simulator gives
two-tone IM3 cheaply at a few tone spacings, but not a full
modulated-signal memory characterization. So instead of forcing the
two-tone to hand over complete memory kernels, use *multiple tone
spacings* to gauge how STRONG the memory is, decide how much DPD memory
to reserve, and leave the actual coefficient training to measured data.

This script:

1. reads the memory strength of three PAs (memoryless Saleh, a mildly
   dynamic ReferencePA, a strongly dispersive ReferencePA) from a
   two-tone spacing sweep, and prints the recommended DPD budget;
2. VALIDATES the budget on the strong PA: it sweeps a real ILA-GMP DPD
   over memory depth on a modulated 802.11 signal and shows the EVM knee
   lands at the depth the cheap two-tone predicted -- deeper buys little.

Usage:  python scripts/run_two_tone_study.py [--fast]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from padpd.data import align_delay
from padpd.data.align import _fractional_advance
from padpd.dpd import ILAPredistorter
from padpd.metrics import aclr, evm
from padpd.pa import GMPModel, ReferencePA, SalehPA
from padpd.two_tone import recommend_dpd_budget, sweep_two_tone
from padpd.waveform import OFDMConfig, demodulate_ofdm, generate_ofdm

FS = 320e6
SPACINGS = [0.5e6, 1e6, 2e6, 5e6, 10e6, 20e6, 40e6]
# a strongly dispersive matching network -> real electrical memory
FIR_IN = np.array([1.0, 0.35 - 0.22j, 0.18 + 0.15j, -0.10 + 0.08j,
                   0.06 - 0.05j])
FIR_OUT = np.array([1.0, 0.28 + 0.18j, 0.12 - 0.10j, 0.05 + 0.04j])


def diagnose(name: str, pa, amp: float, n: int) -> None:
    r = sweep_two_tone(pa, SPACINGS, FS, n=n, amp=amp)
    b = recommend_dpd_budget(r)
    print(f"\n=== {name} ===")
    print("  tone spacing (MHz): "
          + " ".join(f"{s / 1e6:>6g}" for s in r.spacings_hz))
    print("  IM3 lower   (dBc) : "
          + " ".join(f"{v:>6.1f}" for v in r.im3_lower_dbc))
    print("  IM3 upper   (dBc) : "
          + " ".join(f"{v:>6.1f}" for v in r.im3_upper_dbc))
    print(f"  spacing spread {r.im3_spread_db:4.1f} dB | "
          f"peak asymmetry {r.im3_asym_db:4.1f} dB | "
          f"MEMORY STRENGTH {r.memory_strength_db:4.1f} dB")
    print(f"  -> reserve memory_depth {b['memory_depth']}, "
          f"cross terms: {b['use_cross_terms']} "
          f"(~{b['est_coeffs']} GMP coeffs)")
    print(f"     {b['rationale']}")


def validate_budget(fast: bool) -> None:
    """Sweep a real DPD over memory depth on the strong PA; the EVM knee
    should sit at the two-tone-recommended depth."""
    pa = ReferencePA(drive=0.12, fir_in=FIR_IN, fir_out=FIR_OUT)
    r = sweep_two_tone(pa, SPACINGS, FS, n=16384, amp=1.6)
    rec = recommend_dpd_budget(r)["memory_depth"]

    bw = 80e6
    n_sym = 6 if fast else 10
    cfg = OFDMConfig(bandwidth_hz=bw, qam_order=1024, n_symbols=n_sym, seed=0)
    w_tr = generate_ofdm(cfg)
    w_val = generate_ofdm(replace(cfg, seed=1))
    fs = cfg.sample_rate_hz

    def measure(dpd):
        y = pa(dpd(w_val.x)) if dpd is not None else pa(w_val.x)
        _, _, info = align_delay(w_val.x, y, max_lag=16)
        rx = demodulate_ofdm(_fractional_advance(y, info["lag_total"])
                             / info["gain"], w_val)
        return evm(rx, w_val.tx_symbols).db, aclr(y, fs, bw)["upper_dbc"]

    e0, a0 = measure(None)
    print("\n=== budget validation (strong PA, 80 MHz / 1024-QAM) ===")
    print(f"  two-tone predicted memory_depth = {rec}")
    print(f"  {'DPD depth':<12}{'coeffs':>7}{'EVM dB':>9}{'ACLR dBc':>10}"
          f"{'d(EVM)':>9}")
    print(f"  {'no DPD':<12}{'-':>7}{e0:>9.1f}{a0:>10.1f}{'-':>9}")
    prev = e0
    for d in [1, 2, 3, 4, 6]:
        dpd = ILAPredistorter(
            model_factory=lambda d=d: GMPModel(order=5, memory_depth=d,
                                               lag_memory=0, lead_memory=0),
            n_iterations=3)
        dpd.fit(pa, w_tr.x)
        e, a = measure(dpd)
        mark = "  <- recommended" if d == rec else ""
        print(f"  depth {d:<6}{5 * d:>7}{e:>9.1f}{a:>10.1f}"
              f"{e - prev:>+9.1f}{mark}", flush=True)
        prev = e
    print("  reading: memoryless DPD (depth 1) barely helps -- the PA's "
          "memory\n  needs memory taps; the big EVM gains are banked by the "
          "predicted\n  depth, and going deeper yields diminishing returns.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    args = ap.parse_args()
    n = 8192 if args.fast else 16384

    print("Two-tone memory diagnostics: how much DPD memory to reserve")
    print("(coefficients are still trained on measured data; this sizes "
          "the hardware)")
    diagnose("memoryless PA (Saleh)", SalehPA(), amp=0.6, n=n)
    diagnose("mildly dynamic PA (ReferencePA, default matching)",
             ReferencePA(drive=0.14), amp=1.6, n=n)
    diagnose("strongly dispersive PA (ReferencePA, long matching FIRs)",
             ReferencePA(drive=0.16, fir_in=FIR_IN, fir_out=FIR_OUT),
             amp=1.6, n=n)
    validate_budget(args.fast)


if __name__ == "__main__":
    main()
