"""Loopback observation-path budget study.

Quantifies how each observation-path impairment degrades data-driven
DPD: the predistorter is identified from (x, loopback(y)) pairs, then
evaluated on the TRUE PA output. The gap to the clean-observation
baseline is that impairment's cost, which is exactly the number an RF
budget needs.

Chain: 80 MHz / 1024-QAM OFDM -> ReferencePA (drive 0.14) -> loopback
channel -> ILA-GMP identification (fit_measured) -> apply DPD -> true
PA -> constellation EVM + ACLR.

Usage:  python scripts/run_loopback_study.py [--fast]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from padpd.data import align_delay
from padpd.dpd import ILAPredistorter
from padpd.loopback import LoopbackChannel
from padpd.metrics import aclr, evm
from padpd.pa import GMPModel, ReferencePA
from padpd.waveform import (OFDMConfig, demodulate_ofdm,
                            generate_ofdm)

DRIVE = 0.14
BW = 80e6


def evaluate(dpd, pa, wf_val, fs):
    """Receiver-style evaluation: timing sync before demodulation.

    The identified DPD may absorb a fraction of a sample of the
    observation path's delay; without sync that turns into a phase ramp
    across subcarriers and caps EVM near -20 dB even though the
    linearization itself is fine (ACLR unaffected) - exactly what a lab
    post-processing chain must also do.
    """
    from padpd.data.align import _fractional_advance
    x = wf_val.x
    y = pa(dpd(x)) if dpd is not None else pa(x)
    _, _, info = align_delay(x, y, max_lag=16)
    y_sync = _fractional_advance(y, info["lag_total"])  # length-preserving
    rx = demodulate_ofdm(y_sync / info["gain"], wf_val)
    e = evm(rx, wf_val.tx_symbols).db
    a = aclr(y, fs, BW)
    return e, a["upper_dbc"]


def identify(x, y_obs, align: bool):
    if align:
        x_a, y_a, _ = align_delay(x, y_obs, max_lag=256)
    else:
        x_a, y_a = x, y_obs
    dpd = ILAPredistorter(
        model_factory=lambda: GMPModel(order=7, memory_depth=4))
    dpd.fit_measured(x_a, y_a)
    return dpd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    args = ap.parse_args()

    n_sym = 4 if args.fast else 8
    cfg = OFDMConfig(bandwidth_hz=BW, qam_order=1024, n_symbols=n_sym,
                     seed=0)
    wf_tr = generate_ofdm(cfg)
    wf_val = generate_ofdm(replace(cfg, seed=1))
    fs = cfg.sample_rate_hz
    pa = ReferencePA(drive=DRIVE)
    y_clean = pa(wf_tr.x)

    e0, a0 = evaluate(None, pa, wf_val, fs)
    print(f"no DPD                          EVM {e0:6.1f} dB   "
          f"ACLR {a0:6.1f} dBc")

    cases = [
        ("clean observation (baseline)", LoopbackChannel(), False),
        ("SNR 50 dB", LoopbackChannel(snr_db=50), False),
        ("SNR 40 dB", LoopbackChannel(snr_db=40), False),
        ("SNR 30 dB", LoopbackChannel(snr_db=30), False),
        ("IRR 40 dB (0.1 dB / 1.1 deg)",
         LoopbackChannel(iq_gain_imbalance_db=0.1,
                         iq_phase_imbalance_deg=1.1), False),
        ("IRR 30 dB (0.3 dB / 3.5 deg)",
         LoopbackChannel(iq_gain_imbalance_db=0.3,
                         iq_phase_imbalance_deg=3.5), False),
        ("RX IM3 -50 dBc", LoopbackChannel(rx_im3_dbc=-50), False),
        ("RX IM3 -40 dBc", LoopbackChannel(rx_im3_dbc=-40), False),
        ("RX IM3 -30 dBc", LoopbackChannel(rx_im3_dbc=-30), False),
        ("ripple 0.5 dB / gd 0.5 ns",
         LoopbackChannel(ripple_db=0.5, gd_ripple_ns=0.5), False),
        ("ripple 2 dB / gd 2 ns",
         LoopbackChannel(ripple_db=2.0, gd_ripple_ns=2.0), False),
        ("phase noise 1 deg rms",
         LoopbackChannel(phase_noise_rms_deg=1.0), False),
        ("phase noise 3 deg rms",
         LoopbackChannel(phase_noise_rms_deg=3.0), False),
        ("delay 7.3 samp (aligned)",
         LoopbackChannel(delay_samples=7.3), True),
        ("delay 7.3 samp (NOT aligned)",
         LoopbackChannel(delay_samples=7.3), False),
        ("delay drift 0.5 samp/capture",
         LoopbackChannel(delay_drift_samples=0.5), True),
        ("LO leakage -30 dBc", LoopbackChannel(lo_leakage_dbc=-30), False),
        ("budget set: SNR40+IRR40+IM3-50+ripple0.5+pn1",
         LoopbackChannel(snr_db=40, iq_gain_imbalance_db=0.1,
                         iq_phase_imbalance_deg=1.1, rx_im3_dbc=-50,
                         ripple_db=0.5, gd_ripple_ns=0.5,
                         phase_noise_rms_deg=1.0, delay_samples=7.3),
         True),
    ]

    print(f"{'observation path':<44}{'EVM dB':>8}{'ACLR dBc':>10}")
    print("-" * 62)
    results = []
    for name, ch, align in cases:
        y_obs = ch(y_clean, fs)
        dpd = identify(wf_tr.x, y_obs, align)
        e, a = evaluate(dpd, pa, wf_val, fs)
        results.append((name, e, a))
        print(f"{name:<44}{e:>8.1f}{a:>10.1f}", flush=True)

    base = results[0]
    print("\ncost vs clean baseline (dB):")
    for name, e, a in results[1:]:
        print(f"  {name:<42}dEVM {e - base[1]:+5.1f}   "
              f"dACLR {a - base[2]:+5.1f}")


if __name__ == "__main__":
    main()
