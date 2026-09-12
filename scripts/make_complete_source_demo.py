"""Generate the complete measured-source demo file (examples/).

Builds every capture group of the complete-source container from the
virtual DUTs, so users have a reference file for the format and the
GUI has a loadable example:

- main (x, y): OFDM through a TX front end (image + LO leakage) around
  a self-heating PA — exercises the widely-linear model entries;
- burst / step: the bare self-heating PA (state modeling and tau
  identification are normally done after QMC calibration);
- cal_rx / atten: observation-path captures through a LoopbackChannel
  with ripple and a physical (frozen-kappa) RX IM3;
- operating_points: three drift states of DriftingReferencePA.

Usage:  python scripts/make_complete_source_demo.py [--out PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from padpd.data import load_complete_npz, save_complete_npz
from padpd.gain_modulation import step_probe_drive
from padpd.loopback import LoopbackChannel
from padpd.pa import (
    DriftingReferencePA,
    ThermalReferencePA,
    TxFrontEndPA,
    burst_stimulus,
)
from padpd.waveform import OFDMConfig, generate_ofdm

OUT_DEFAULT = str(Path(__file__).resolve().parent.parent / "examples"
                  / "complete_source_demo.npz")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_DEFAULT)
    args = ap.parse_args()

    cfg = OFDMConfig(bandwidth_hz=20e6, qam_order=1024, n_symbols=4,
                     seed=0)
    fs = cfg.sample_rate_hz
    wf = generate_ofdm(cfg)

    # main stationary capture: front end (image + LO) + self-heating PA
    pa_main = TxFrontEndPA(ThermalReferencePA(drive0=0.13, fs=fs),
                           gain_db=0.3, phase_deg=3.0,
                           lo_leakage_dbc=-35.0)
    y_main = pa_main(wf.x)

    # burst capture: bare thermal PA (post-QMC reference plane);
    # segments must exceed the slowest tau (30 us) to be observable
    wf_b = generate_ofdm(OFDMConfig(bandwidth_hz=20e6, qam_order=1024,
                                    n_symbols=16, seed=3))
    xb = burst_stimulus(wf_b.x, n_bursts=4, low_scale=0.3)
    yb = ThermalReferencePA(drive0=0.13, fs=fs)(xb)

    # step-probe capture for offline tau identification. The virtual
    # DUT calibrates its dissipated-power reference on the FIRST call —
    # feed it the full-power reference burst alone first (as the
    # interactive experiment does), or the long low-power settle would
    # dilute p_ref and saturate the state.
    xs = step_probe_drive(fs, settle_factor=4.0)
    pa_step = ThermalReferencePA(drive0=0.13, fs=fs)
    pa_step(np.full(2048, 1.5, dtype=complex))
    pa_step.reset()                     # cold start, reference kept
    ys = pa_step(xs)

    # observation-path calibration captures
    ch = LoopbackChannel(iq_gain_imbalance_db=0.3,
                         iq_phase_imbalance_deg=3.0, lo_leakage_dbc=-40.0,
                         cfo_hz=8e3, phase_noise_rms_deg=1.0,
                         ripple_db=1.0, gd_ripple_ns=2.0,
                         delay_samples=7.3, rx_im3_dbc=-28.0,
                         rx_im3_freeze=True, snr_db=45.0)
    # calibration captures need length: the per-capture CFO/drift
    # estimates of the hi/lo pair must agree well enough for the
    # difference to isolate the RX cubic
    wf_cal = generate_ofdm(OFDMConfig(bandwidth_hz=20e6, qam_order=1024,
                                      n_symbols=12, seed=7))
    wf_at = generate_ofdm(OFDMConfig(bandwidth_hz=20e6, qam_order=1024,
                                     n_symbols=12, seed=21))
    y_at = TxFrontEndPA(ThermalReferencePA(drive0=0.13, fs=fs),
                        gain_db=0.3, phase_deg=3.0,
                        lo_leakage_dbc=-35.0)(wf_at.x)
    # freeze the channel's RX-IM3 kappa at the NOMINAL level before any
    # capture — the first call calibrates it, and letting the backed-off
    # cal capture go first would freeze kappa ~100x too hot
    ch(y_at, fs)
    cal_obs = ch(0.1 * wf_cal.x, fs)              # backed-off bypass
    atten_hi = ch(y_at, fs)
    atten_lo = ch(10 ** (-6.0 / 20) * y_at, fs)

    # operating points: three drift states (condition = state scalar)
    drift = DriftingReferencePA(drive0=0.13, drive_span=0.03)
    ops, conditions = [], [0.0, 0.5, 1.0]
    for i, s in enumerate(conditions):
        drift.set_state(s)
        wf_i = generate_ofdm(OFDMConfig(bandwidth_hz=20e6, qam_order=1024,
                                        n_symbols=4, seed=10 + i))
        ops.append((wf_i.x, drift.pa()(wf_i.x)))

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    save_complete_npz(
        args.out, wf.x, y_main, fs,
        burst=(xb, yb), step=(xs, ys),
        cal_rx=(0.1 * wf_cal.x, cal_obs),
        atten=(wf_at.x, atten_hi, atten_lo, 6.0),
        operating_points=(conditions, ops),
        meta={"center_freq_hz": 5.5e9, "reference_plane": "pa_output",
              "shared_lo": False, "bandwidth_hz": 20e6,
              "note": "synthetic demo of the complete-source container"})

    comp = load_complete_npz(args.out)
    kb = Path(args.out).stat().st_size / 1024
    print(f"wrote {args.out} ({kb:.0f} KiB)")
    print(f"fs = {comp['fs']/1e6:.0f} MHz, main n = {len(comp['x'])}")
    for g, e in comp["extras"].items():
        n = (len(e["pairs"]) if g == "operating_points"
             else len(next(iter(e.values()))))
        print(f"  group {g:16s} present (n = {n})")


if __name__ == "__main__":
    main()
