"""Tests for the physical drain-efficiency model in co-design."""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from padpd.codesign import drain_efficiency, saturation_amplitude
from padpd.pa import ReferencePA
from padpd.waveform import OFDMConfig, generate_ofdm


def _sig():
    return generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                    n_symbols=4, seed=0)).x


def test_cw_saturation_reaches_class_peak():
    pa = ReferencePA(drive=1.0)
    knee = 1 / np.sqrt(pa.saleh.beta_a)          # Saleh AM-AM peak
    cw = np.full(1000, knee, dtype=complex)
    assert abs(drain_efficiency(pa, cw, "B") - np.pi / 4) < 0.02
    assert abs(drain_efficiency(pa, cw, "A") - 0.5) < 0.02


def test_efficiency_rises_with_drive():
    x = _sig()
    etas = [drain_efficiency(ReferencePA(drive=d), x, "B")
            for d in (0.08, 0.12, 0.16, 0.20)]
    assert all(0 < e < np.pi / 4 for e in etas)
    assert etas == sorted(etas)                  # monotone increasing


def test_class_a_below_class_b_at_backoff():
    x = _sig()
    pa = ReferencePA(drive=0.14)
    assert drain_efficiency(pa, x, "A") < drain_efficiency(pa, x, "B")


def test_works_on_hb_imported_pa():
    # efficiency must be computable from any PAModel, incl. WH from HB
    from padpd.pa import WienerHammersteinPA, SalehPA
    saleh = SalehPA()
    r = np.linspace(1e-3, 2.0, 200)
    y = saleh(r.astype(complex))
    pa = WienerHammersteinPA(r, np.abs(y), np.rad2deg(np.angle(y)),
                             drive=0.14)
    e = drain_efficiency(pa, _sig(), "B")
    assert 0 < e < np.pi / 4
    assert saturation_amplitude(pa) > 0
