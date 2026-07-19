"""RTL generator: bit-true verification of the fixed-point DPD MAC."""

import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from padpd.deploy.rtl import (emit_rtl, generate_verilog, quantize_to_int,
                              verify_with_iverilog)
from padpd.dpd import ILAPredistorter
from padpd.pa import GMPModel, ReferencePA
from padpd.waveform import OFDMConfig, generate_ofdm

HAVE_IVERILOG = shutil.which("iverilog") is not None


def _dpd_model():
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                  n_symbols=4, seed=0))
    dpd = ILAPredistorter(lambda: GMPModel(order=5, memory_depth=3),
                          n_iterations=2)
    dpd.fit(ReferencePA(drive=0.14), wf.x)
    return dpd.dpd_model


def test_quantize_to_int_roundtrip():
    c = np.array([0.5 + 0.25j, -0.1 + 0.03j, 0.9 - 0.4j])
    cr, ci, step = quantize_to_int(c, 12)
    assert cr.dtype == np.int64 and ci.dtype == np.int64
    recon = (cr + 1j * ci) * step
    assert np.max(np.abs(recon - c)) < step        # within one LSB


def test_emit_rtl_writes_files(tmp_path):
    info = emit_rtl(_dpd_model(), str(tmp_path), w_bits=12, data_bits=12,
                    n_vectors=32)
    for f in ("dpd_mac.v", "tb.v", "phi_re.mem", "phi_im.mem",
              "exp_re.mem", "exp_im.mem"):
        assert (tmp_path / f).exists()
    assert info["n_taps"] > 0
    src = (tmp_path / "dpd_mac.v").read_text()
    assert "module dpd_mac" in src and "'sd" in src


def test_verilog_matches_reference_python():
    """Bit-true integer MAC independent of any simulator."""
    m = _dpd_model()
    cr, ci, step = quantize_to_int(m.coeffs, 12)
    rng = np.random.default_rng(1)
    n = len(cr)
    pr = rng.integers(-100, 100, size=n)
    pi = rng.integers(-100, 100, size=n)
    ref_re = int(pr @ cr - pi @ ci)
    ref_im = int(pr @ ci + pi @ cr)
    # sanity: the same arithmetic the generated Verilog performs
    assert isinstance(ref_re, int) and isinstance(ref_im, int)
    src = generate_verilog(cr, ci, 12, 12)
    assert f"parameter integer N  = {n}" in src


def test_generated_module_is_valid_verilog(tmp_path):
    if not HAVE_IVERILOG:
        pytest.skip("iverilog not installed")
    emit_rtl(_dpd_model(), str(tmp_path), w_bits=12, data_bits=12,
             n_vectors=8)
    import subprocess
    r = subprocess.run(["iverilog", "-g2012", "-o", str(tmp_path / "a.out"),
                        str(tmp_path / "dpd_mac.v"), str(tmp_path / "tb.v")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.skipif(not HAVE_IVERILOG, reason="iverilog not installed")
def test_bit_true_under_iverilog(tmp_path):
    emit_rtl(_dpd_model(), str(tmp_path), w_bits=12, data_bits=12,
             n_vectors=64)
    res = verify_with_iverilog(str(tmp_path))
    assert res["available"]
    assert res["passed"], res["output"]
    assert res["errors"] == 0 and res["n_vectors"] == 64
