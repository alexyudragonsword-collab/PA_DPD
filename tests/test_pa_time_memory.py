"""PA memory defined in time, tap-spaced basis models, and CascadePA.

Issue #4, from mmw60_trx: a 60 GHz link clocks the same PHY K times
faster, so the PA runs at K x the sample rate on a K x wider signal.
ReferencePA's taps were one sample apart at any rate, i.e. its memory
shrank with 1/fs. These tests pin the three things the issue asked for
and the acceptance numbers agreed on it, all measured on 2026-11-11:

- default construction is bit-identical to before;
- the same signal upsampled K times sees the same memory (the model is
  invariant to the sample rate): -20.1 dB at K = 1 / 8 / 32;
- a 20 MHz x K signal with taps fixed at 12.5 ns sees heavier memory,
  -11.0 dB at K = 4, where sample-spaced taps stay at -19.9 dB;
- a DPD needs tap-spaced memory to follow: GMP-ILA at K = 4 reaches an
  EVM of -46.4 dB with tap_spacing 4 and -28.6 dB without. The DPD drives
  the PA directly here; with a per-sample TX lowpass in between the cost
  of time-defined memory was 0.5-2.3 dB of extra backoff for the same EVM
  (issue #4 follow-ups; see padpd.pa.memory_polynomial);
- CascadePA is one PAModel whose interstage backoff changes only the
  level between the stages, and reports each stage's own backoff.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from padpd.dpd import ILAPredistorter  # noqa: E402
from padpd.metrics.evm import evm_of_signal  # noqa: E402
from padpd.pa import (  # noqa: E402
    CascadePA,
    DriftingReferencePA,
    GMPModel,
    MemoryPolynomialModel,
    ReferencePA,
    ThermalReferencePA,
    load_model,
    nmse_db,
)
from padpd.waveform import OFDMConfig, generate_ofdm  # noqa: E402


def _ofdm(bw, n_symbols=8, seed=0):
    return generate_ofdm(OFDMConfig(bandwidth_hz=bw, qam_order=256,
                                    n_symbols=n_symbols, seed=seed))


def _memory_db(pa, x):
    """Output difference to the same PA with each FIR collapsed to its
    DC gain: how much of the PA is memory."""
    twin = ReferencePA(drive=pa.drive, fir_in=[pa.fir_in.sum()],
                       fir_out=[pa.fir_out.sum()])
    return nmse_db(pa(x), twin(x))


# ---------------------------------------------------------------- PA side

def test_default_construction_is_bit_identical():
    x = _ofdm(80e6, n_symbols=4, seed=1).x
    before = ReferencePA()
    np.testing.assert_array_equal(before(x),
                                  ReferencePA(fs=None, fir_fs=None)(x))
    # fs == fir_fs is stride 1: the same arrays, the same output
    np.testing.assert_array_equal(before(x),
                                  ReferencePA(fs=320e6, fir_fs=320e6)(x))
    assert before.tap_stride == 1


def test_same_signal_upsampled_sees_the_same_memory():
    from scipy.signal import resample_poly
    x80 = _ofdm(20e6).x
    got = []
    for k in (1, 8):
        xk = resample_poly(x80, k, 1) if k > 1 else x80
        xk = xk / np.sqrt(np.mean(np.abs(xk) ** 2))
        got.append(_memory_db(ReferencePA(fs=80e6 * k, fir_fs=80e6), xk))
    assert got[0] == pytest.approx(got[1], abs=0.2)   # measured -20.1 both


def test_a_wider_signal_on_fixed_time_taps_sees_more_memory():
    """mmw60_trx's working point: the PHY clocked K x, so the signal is
    K x wider. Taps fixed in seconds now span more of the signal."""
    wf = _ofdm(80e6)                                   # 20 MHz x 4
    x, fs = wf.x, wf.config.sample_rate_hz
    fixed = _memory_db(ReferencePA(fs=fs, fir_fs=80e6), x)
    per_sample = _memory_db(ReferencePA(), x)
    assert -13.0 < fixed < -9.0                        # measured -11.0
    assert per_sample < -18.0                          # measured -19.9


@pytest.mark.parametrize("fs, fir_fs", [(40e6, 80e6), (120e6, 80e6)])
def test_a_non_integer_rate_ratio_is_refused(fs, fir_fs):
    with pytest.raises(ValueError, match="not a positive integer"):
        ReferencePA(fs=fs, fir_fs=fir_fs)


@pytest.mark.parametrize("kw", [{"fs": 320e6}, {"fir_fs": 80e6}])
def test_fs_and_fir_fs_come_together(kw):
    with pytest.raises(ValueError, match="both"):
        ReferencePA(**kw)


def test_drifting_and_thermal_duts_place_their_taps_too():
    d = DriftingReferencePA(fs=320e6, fir_fs=80e6)
    assert d.pa().tap_stride == 4
    assert DriftingReferencePA().pa().tap_stride == 1
    t = ThermalReferencePA(fs=320e6, fir_fs=80e6)
    assert t._drift.pa().tap_stride == 4
    # without fir_fs, fs stays the thermal clock only
    assert ThermalReferencePA(fs=320e6)._drift.pa().tap_stride == 1


# ------------------------------------------------------- model / DPD side

def test_tap_spaced_memory_polynomial_follows_time_defined_memory():
    wf = _ofdm(80e6)
    x, fs = wf.x, wf.config.sample_rate_hz
    y = ReferencePA(fs=fs, fir_fs=80e6)(x)
    plain = MemoryPolynomialModel(order=7, memory_depth=4).fit(x, y)
    spaced = MemoryPolynomialModel(order=7, memory_depth=4,
                                   tap_spacing=4).fit(x, y)
    assert nmse_db(y, spaced(x)) < nmse_db(y, plain(x)) - 5
    # measured -36.4 vs -27.3 dB


def test_gmp_ila_needs_tap_spacing_at_a_higher_clock():
    wf = _ofdm(80e6)
    x, fs = wf.x, wf.config.sample_rate_hz
    pa = ReferencePA(fs=fs, fir_fs=80e6)

    def dpd_evm(spacing):
        ila = ILAPredistorter(lambda: GMPModel(tap_spacing=spacing))
        return evm_of_signal(pa(ila.fit(pa, x).dpd_model(x)), wf).db

    assert dpd_evm(4) < -40.0                          # measured -46.4
    assert dpd_evm(1) > -35.0                          # measured -28.6


def test_tap_spacing_one_leaves_models_and_their_files_unchanged(tmp_path):
    x = _ofdm(20e6, n_symbols=4).x
    y = ReferencePA()(x)
    for cls in (MemoryPolynomialModel, GMPModel):
        a = cls().fit(x, y)
        b = cls(tap_spacing=1).fit(x, y)
        np.testing.assert_array_equal(a.coeffs, b.coeffs)
        assert "tap_spacing" not in a.get_config()


def test_tap_spacing_round_trips_through_save(tmp_path):
    x = _ofdm(80e6, n_symbols=4).x
    y = ReferencePA(fs=320e6, fir_fs=80e6)(x)
    m = GMPModel(memory_depth=3, tap_spacing=4).fit(x, y)
    m.save(str(tmp_path / "g.npz"))
    back = load_model(str(tmp_path / "g.npz"))
    assert back.tap_spacing == 4
    np.testing.assert_allclose(back(x), m(x))


def test_lut_branch_delays_follow_tap_spacing():
    m = MemoryPolynomialModel(order=5, memory_depth=3, tap_spacing=8)
    assert m.branch_delays() == [(0, 0), (8, 8), (16, 16)]


@pytest.mark.parametrize("bad", [0, 1.5, -2])
def test_tap_spacing_must_be_a_positive_integer(bad):
    with pytest.raises(ValueError):
        GMPModel(tap_spacing=bad)


# --------------------------------------------------------------- cascade

def test_interstage_backoff_changes_only_the_level_between_stages():
    """With linear stages the backoff must cancel exactly: it is a level
    between the stages, not a gain of the cascade."""
    x = _ofdm(20e6, n_symbols=2).x

    def first(v):
        return 1.5 * v

    def second(v):
        return (0.5 - 0.2j) * v

    ref = second(first(x))
    for bo in (0.0, 3.0, 10.0):
        np.testing.assert_allclose(CascadePA(first, second, bo)(x), ref)


def test_stage_backoffs_are_read_per_stage():
    x = _ofdm(20e6, n_symbols=2).x
    x = x / np.sqrt(np.mean(np.abs(x) ** 2))          # unit rms

    def first(v):
        return 2.0 * v                                 # +6.02 dB

    c = CascadePA(first, ReferencePA(), interstage_backoff_db=10.0)
    assert c.stage_backoff_db is None
    c(x)
    b1, b2 = c.stage_backoff_db
    assert b1 == pytest.approx(0.0, abs=1e-9)
    assert b2 == pytest.approx(10.0 - 20 * np.log10(2.0), abs=1e-9)


def test_more_interstage_backoff_compresses_the_second_stage_less():
    """Isolated on a memoryless second stage behind a linear first one:
    with the default stages EVM is dominated by memory, and 6 dB of
    backoff moved it by only 0.6 dB."""
    wf = _ofdm(80e6, n_symbols=4)
    second = ReferencePA(drive=0.16, fir_in=[1], fir_out=[1])

    def evm_at(bo):
        return evm_of_signal(CascadePA(lambda v: v, second, bo)(wf.x),
                             wf).db

    assert evm_at(6.0) < evm_at(0.0) - 5               # measured -32.5/-24.8


def test_a_dpd_trains_against_a_cascade_unchanged():
    wf = _ofdm(80e6, n_symbols=4)
    c = CascadePA(ReferencePA(drive=0.10), ReferencePA(drive=0.14), 3.0)
    ila = ILAPredistorter().fit(c, wf.x)
    before = evm_of_signal(c(wf.x), wf).db
    after = evm_of_signal(c(ila.dpd_model(wf.x)), wf).db
    assert after < before - 15


def test_cascade_config_needs_persistable_stages(tmp_path):
    x = _ofdm(20e6, n_symbols=2).x
    y = ReferencePA()(x)
    g1, g2 = GMPModel().fit(x, y), GMPModel(memory_depth=2).fit(x, y)
    cfg = CascadePA(g1, g2, 2.0).get_config()
    assert cfg["second"]["config"]["memory_depth"] == 2
    assert cfg["interstage_backoff_db"] == 2.0
    with pytest.raises(NotImplementedError):
        CascadePA(ReferencePA(), ReferencePA()).get_config()
    with pytest.raises(NotImplementedError, match="one coefficient array"):
        CascadePA(g1, g2).save(str(tmp_path / "c.npz"))
