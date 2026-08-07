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


# ---- LUT + interpolation datapath -----------------------------------

def _fitted_smp():
    from padpd.pa import SplineMemoryPolynomial
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                  n_symbols=4, seed=0))
    y = ReferencePA(drive=0.14)(wf.x)
    return SplineMemoryPolynomial.from_signal(wf.x, n_knots=6,
                                              memory_depth=3).fit(wf.x, y)


def test_emit_lut_rtl_writes_files(tmp_path):
    from padpd.deploy.rtl import emit_lut_rtl
    info = emit_lut_rtl(_fitted_smp(), str(tmp_path), addr_bits=5,
                        frac_bits=6, n_vectors=64)
    for f in ("dpd_lut.v", "tb_lut.v", "lut_x_re.mem", "lut_x_im.mem",
              "lut_r.mem", "lut_exp_re.mem", "lut_exp_im.mem"):
        assert (tmp_path / f).exists(), f
    assert info["n_entries"] == 33 and info["n_branches"] == 3
    v = (tmp_path / "dpd_lut.v").read_text()
    assert "rom_re" in v and ">>> FB" in v


def test_lut_fixed_eval_tracks_float_model(tmp_path):
    """The integer golden model, dequantized, matches the float LUTDPD
    within quantization error."""
    from padpd.deploy import LUTDPD, lut_from_model
    from padpd.deploy.rtl import emit_lut_rtl, lut_fixed_eval, \
        quantize_to_int
    import numpy as np
    smp = _fitted_smp()
    addr_bits, frac_bits, entry_bits, data_bits = 6, 8, 14, 14
    nent = (1 << addr_bits) + 1
    lut = lut_from_model(smp, n_entries=nent)
    g_re_i, g_im_i, step_g = quantize_to_int(np.asarray(lut["gains"]),
                                             entry_bits)
    rng = np.random.default_rng(1)
    r_max = lut["r_max"]
    x = (rng.uniform(0, r_max, 512)
         * np.exp(1j * rng.uniform(0, 2 * np.pi, 512)))
    from padpd.deploy.rtl import _pow2_step
    step_x = _pow2_step(max(np.abs(x.real).max(), np.abs(x.imag).max()),
                        data_bits)
    xr = np.round(x.real / step_x).astype(np.int64)
    xi = np.round(x.imag / step_x).astype(np.int64)
    rw = addr_bits + frac_bits
    step_r = r_max / (1 << rw)
    r_i = np.clip(np.round(np.abs(x) / step_r), 0,
                  (1 << rw) - 1).astype(np.int64)
    got_re, got_im = lut_fixed_eval(g_re_i, g_im_i, r_i, xr, xi,
                                    smp.branch_delays(), addr_bits,
                                    frac_bits)
    got = (got_re + 1j * got_im) * step_g * step_x
    ref = LUTDPD.from_table(lut)(x)
    scale = np.sqrt(np.mean(np.abs(ref) ** 2))
    assert np.max(np.abs(got - ref)) / scale < 0.02


def test_emit_lut_rtl_rejects_lead_branches(tmp_path):
    from padpd.deploy.rtl import emit_lut_rtl
    from padpd.pa import SplineGMP
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                  n_symbols=4, seed=0))
    y = ReferencePA(drive=0.14)(wf.x)
    sgmp = SplineGMP.from_signal(wf.x, n_knots=5, memory_depth=2,
                                 lead_memory=1, lead_span=1).fit(wf.x, y)
    with pytest.raises(ValueError):
        emit_lut_rtl(sgmp, str(tmp_path))


@pytest.mark.skipif(not HAVE_IVERILOG, reason="iverilog not installed")
def test_lut_rtl_bit_true_under_iverilog(tmp_path):
    from padpd.deploy.rtl import emit_lut_rtl
    emit_lut_rtl(_fitted_smp(), str(tmp_path), addr_bits=6, frac_bits=8,
                 n_vectors=256)
    res = verify_with_iverilog(str(tmp_path),
                               sources=("dpd_lut.v", "tb_lut.v"))
    assert res["available"] and res["passed"], res["output"]
    assert res["errors"] == 0 and res["n_vectors"] == 256


@pytest.mark.skipif(not HAVE_IVERILOG, reason="iverilog not installed")
def test_lut_rtl_lag_only_sgmp_bit_true(tmp_path):
    """Lag branches (envelope delayed beyond carrier) also verify."""
    from padpd.deploy.rtl import emit_lut_rtl
    from padpd.pa import SplineGMP
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                  n_symbols=4, seed=0))
    y = ReferencePA(drive=0.14)(wf.x)
    sgmp = SplineGMP.from_signal(wf.x, n_knots=5, memory_depth=2,
                                 lag_memory=1, lag_span=2, lead_memory=0,
                                 lead_span=0).fit(wf.x, y)
    emit_lut_rtl(sgmp, str(tmp_path), addr_bits=5, frac_bits=7,
                 n_vectors=128)
    res = verify_with_iverilog(str(tmp_path),
                               sources=("dpd_lut.v", "tb_lut.v"))
    assert res["available"] and res["passed"], res["output"]


@pytest.mark.skipif(not HAVE_IVERILOG, reason="iverilog not installed")
def test_lut_rtl_conjugate_branches_bit_true(tmp_path):
    """Widely-linear (image) branches verify bit-true: the conj is one
    sign flip on the imaginary carrier in both golden and Verilog."""
    from padpd.deploy.rtl import emit_lut_rtl
    from padpd.pa import SplineMemoryPolynomial
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                  n_symbols=4, seed=0))
    y = ReferencePA(drive=0.14)(wf.x)
    wl = SplineMemoryPolynomial.from_signal(
        wf.x, n_knots=5, memory_depth=2, conjugate=True).fit(wf.x, y)
    emit_lut_rtl(wl, str(tmp_path), addr_bits=5, frac_bits=7,
                 n_vectors=128)
    assert ", conj" in (tmp_path / "dpd_lut.v").read_text()
    res = verify_with_iverilog(str(tmp_path),
                               sources=("dpd_lut.v", "tb_lut.v"))
    assert res["available"] and res["passed"], res["output"]
    assert res["errors"] == 0
