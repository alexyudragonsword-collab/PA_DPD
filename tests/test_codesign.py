import numpy as np

from padpd.codesign import codesign_point, pae_proxy, saturation_amplitude
from padpd.pa import ReferencePA
from padpd.waveform import OFDMConfig, generate_ofdm


def _wf(seed):
    return generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=256,
                                    n_symbols=4, seed=seed))


def test_pae_increases_with_drive():
    x = _wf(0).x
    p_lo = pae_proxy(ReferencePA(drive=0.10), x)
    p_hi = pae_proxy(ReferencePA(drive=0.20), x)
    assert 0 < p_lo < p_hi <= 0.70  # harder drive -> higher efficiency


def test_saturation_amplitude_positive():
    assert saturation_amplitude(ReferencePA()) > 0


def test_codesign_point_feasible_at_low_drive():
    tr, va = _wf(0), _wf(1)
    r = codesign_point(0.10, tr.x, va.x, va, evm_spec_db=-40.0,
                       fs=tr.sample_rate_hz, bw=80e6)
    assert r["feasible"]
    assert r["evm_dpd"] <= -40.0
    assert r["dpd_cost"] > 0


def test_codesign_high_drive_harder_or_infeasible():
    tr, va = _wf(0), _wf(1)
    lo = codesign_point(0.10, tr.x, va.x, va, -40.0, tr.sample_rate_hz, 80e6)
    hi = codesign_point(0.24, tr.x, va.x, va, -40.0, tr.sample_rate_hz, 80e6)
    assert hi["pae"] > lo["pae"]
    # higher drive costs more DPD to meet spec, or cannot meet it at all
    assert (not hi["feasible"]) or (hi["dpd_cost"] >= lo["dpd_cost"])
