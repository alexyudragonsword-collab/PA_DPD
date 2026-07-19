"""Unit tests: two-tone memory diagnostics and DPD budgeting.

A memoryless nonlinearity must read as zero memory (symmetric,
spacing-independent IM3); a dynamic PA must read as nonzero; and the
budget must grow monotonically with memory strength and agree with the
GMP coefficient count it recommends.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from padpd.pa import GMPModel, ReferencePA, SalehPA
from padpd.two_tone import (TwoToneResult, measure_imd,
                            memory_strength_from_table, recommend_dpd_budget,
                            sweep_two_tone, two_tone_signal)

FS = 320e6
SPAC = [0.5e6, 1e6, 2e6, 5e6, 10e6, 20e6, 40e6]
# strongly dispersive input/output matching -> clear electrical memory
FIR_IN = np.array([1.0, 0.35 - 0.22j, 0.18 + 0.15j, -0.10 + 0.08j,
                   0.06 - 0.05j])
FIR_OUT = np.array([1.0, 0.28 + 0.18j, 0.12 - 0.10j, 0.05 + 0.04j])


def test_two_tone_signal_bins_and_guards():
    x, k = two_tone_signal(10e6, FS, n=8192, amp=1.0)
    assert k == round(10e6 / FS * 8192 / 2)
    assert len(x) == 8192
    with pytest.raises(ValueError):
        two_tone_signal(1e3, FS, n=8192)          # too few bins
    with pytest.raises(ValueError):
        two_tone_signal(100e6, FS, n=8192)        # IM5 past Nyquist


def test_memoryless_pa_reads_zero_memory():
    r = sweep_two_tone(SalehPA(), SPAC, FS, n=8192, amp=0.6)
    assert r.im3_spread_db < 0.05
    assert r.im3_asym_db < 0.05
    assert r.memory_strength_db < 0.05
    assert not r.thermal_suspected
    b = recommend_dpd_budget(r)
    assert b["memory_depth"] == 1
    assert b["use_cross_terms"] is False


def test_measure_imd_products_below_tone():
    m = measure_imd(ReferencePA(drive=0.16, fir_in=FIR_IN, fir_out=FIR_OUT),
                    5e6, FS, n=16384, amp=1.6)
    # IM products sit below the fundamental of a compressing PA
    assert m["im3_avg_dbc"] < 0
    assert m["im5_avg_dbc"] < m["im3_avg_dbc"]
    # average lies between the two sidebands
    lo, hi, avg = m["im3_lower_dbc"], m["im3_upper_dbc"], m["im3_avg_dbc"]
    assert min(lo, hi) - 1e-6 <= avg <= max(lo, hi) + 1e-6


def test_dynamic_pa_reads_nonzero_memory():
    pa = ReferencePA(drive=0.16, fir_in=FIR_IN, fir_out=FIR_OUT)
    r = sweep_two_tone(pa, SPAC, FS, n=16384, amp=1.6)
    assert r.im3_spread_db > 1.0        # IM3 clearly varies with spacing
    assert r.im3_asym_db > 0.5          # and is asymmetric
    b = recommend_dpd_budget(r)
    assert b["memory_depth"] >= 2       # memory must be reserved
    assert b["use_cross_terms"] is True


def test_budget_monotonic_in_strength():
    depths = [recommend_dpd_budget(s)["memory_depth"]
              for s in (0.1, 1.0, 2.0, 4.0, 8.0)]
    assert depths == sorted(depths)     # non-decreasing
    assert depths[0] == 1 and depths[-1] == 5


def test_budget_coeff_count_matches_gmp():
    r = sweep_two_tone(
        ReferencePA(drive=0.16, fir_in=FIR_IN, fir_out=FIR_OUT),
        SPAC, FS, n=16384, amp=1.6)
    b = recommend_dpd_budget(r)
    gmp = GMPModel(**b["gmp_config"])
    assert gmp.n_coeffs == b["est_coeffs"]


def test_from_table_and_thermal_signature():
    spac = np.array([0.5e6, 1e6, 2e6, 5e6, 10e6])
    lo = np.array([-30.0, -34.0, -37.0, -39.0, -40.0])   # asym at 0.5 MHz
    hi = np.array([-40.0, -39.0, -38.5, -39.2, -40.0])
    r = memory_strength_from_table(spac, lo, hi)
    assert isinstance(r, TwoToneResult)
    assert r.im3_asym_db == pytest.approx(10.0, abs=1e-6)  # 0.5 MHz gap
    assert r.thermal_suspected                              # peaks at min df
    b = recommend_dpd_budget(r)
    assert b["thermal_suspected"] and b["use_cross_terms"]


def test_table_sorts_by_spacing():
    # unordered input must not change the metrics
    r1 = memory_strength_from_table([10e6, 1e6, 5e6],
                                    [-40, -30, -38], [-40, -35, -39])
    r2 = memory_strength_from_table([1e6, 5e6, 10e6],
                                    [-30, -38, -40], [-35, -39, -40])
    assert r1.memory_strength_db == pytest.approx(r2.memory_strength_db)
    assert np.allclose(r1.spacings_hz, r2.spacings_hz)
