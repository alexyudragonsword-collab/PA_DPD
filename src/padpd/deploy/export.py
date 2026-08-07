"""Deployment hand-off: fixed-point coefficient and reference-vector export.

Produces artifacts a hardware team consumes directly:

- ``export_linear_coeffs``: integer coefficient codes + power-of-two scale
  for a linear-params model (MP/GMP/DDR). Hardware computes
  ``acc += code_w * code_x`` then arithmetic-shifts by the scale exponents
  - no floating point on chip.
- ``export_reference_vectors``: input/output IQ from the bit-true Python
  model, so an RTL/HLS implementation can be checked sample-for-sample.

ONNX export for neural models lives in ``export_onnx`` (needs torch).
"""

from __future__ import annotations

import json

import numpy as np

from .fixed_point import _pow2_step


def _int_codes(x: np.ndarray, n_bits: int):
    """Integer codes and scale exponent e such that value ~= code * 2**e.

    Complex ``x`` shares one exponent across real and imag. Returns
    ``(codes_real, codes_imag, e)`` with codes as python ints.
    """
    x = np.asarray(x)
    qmax = 2 ** (n_bits - 1) - 1
    qmin = -(2 ** (n_bits - 1))
    if np.iscomplexobj(x):
        peak = max(np.abs(x.real).max(), np.abs(x.imag).max())
        step = _pow2_step(peak, n_bits)
        cr = np.clip(np.round(x.real / step), qmin, qmax).astype(int)
        ci = np.clip(np.round(x.imag / step), qmin, qmax).astype(int)
        return cr, ci, int(np.log2(step))
    peak = np.abs(x).max()
    step = _pow2_step(peak, n_bits)
    c = np.clip(np.round(x / step), qmin, qmax).astype(int)
    return c, None, int(np.log2(step))


def export_linear_coeffs(model, w_bits: int, path: str) -> dict:
    """Write quantized integer coefficients of a linear-params model to JSON.

    Includes the model class/config, bit width, scale exponent, and the
    integer real/imag coefficient codes. Returns the written dict.
    """
    if getattr(model, "coeffs", None) is None:
        raise ValueError("model must be fitted before export")
    cr, ci, e = _int_codes(model.coeffs, w_bits)
    payload = {
        "model_class": type(model).__name__,
        "config": model.get_config(),
        "n_coeffs": len(model.coeffs),
        "w_bits": w_bits,
        "coeff_scale_exp": e,
        "note": "coeff_value = code * 2**coeff_scale_exp; "
                "hardware: acc += code_w*code_x, shift by exponents",
        "coeffs_real": cr.tolist(),
        "coeffs_imag": ci.tolist(),
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=1)
    return payload


def export_lut(lut: dict, w_bits: int, path: str) -> dict:
    """Write per-branch integer LUT entry codes to JSON.

    ``lut`` comes from :func:`padpd.deploy.lut.lut_from_model`. Each
    branch gets its own scale exponent (per-tap hardware formats).
    Hardware reconstructs ``gain = code * 2**scale_exp`` and linearly
    interpolates between adjacent entries.
    """
    branches = []
    orders = lut.get("phase_orders")
    if orders is None:
        orders = [-1 if c else 1
                  for c in lut.get("conjugate",
                                   [False] * len(lut["delays"]))]
    for g, (mc, me), order in zip(lut["gains"], lut["delays"], orders):
        cr, ci, e = _int_codes(np.asarray(g), w_bits)
        branches.append({"carrier_delay": int(mc), "envelope_delay": int(me),
                         "phase_order": int(order),
                         "conjugate": bool(order < 0),
                         "scale_exp": e, "gains_real": cr.tolist(),
                         "gains_imag": ci.tolist()})
    dc = complex(lut.get("dc", 0j))
    payload = {
        "n_branches": len(branches),
        "n_entries": int(len(lut["r_grid"])),
        "r_max": float(lut["r_max"]),
        "w_bits": w_bits,
        "dc_real": dc.real,
        "dc_imag": dc.imag,
        "note": "gain_value = code * 2**scale_exp; uniform amplitude grid "
                "0..r_max; linear interpolation between entries, clamp "
                "beyond r_max; carrier = x^phase_order (negative order = "
                "conjugated power); dc adds as a constant output offset",
        "branches": branches,
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=1)
    return payload


def export_reference_vectors(model, x: np.ndarray, path: str,
                             n: int = 4096) -> None:
    """Run ``model`` on the first ``n`` samples of ``x`` and dump the
    input/output IQ as CSV for bit-true RTL verification."""
    x = np.asarray(x, dtype=complex)[:n]
    y = model(x)
    with open(path, "w") as f:
        f.write("i_in,q_in,i_out,q_out\n")
        for xi, yi in zip(x, y):
            f.write(f"{xi.real:.10e},{xi.imag:.10e},"
                    f"{yi.real:.10e},{yi.imag:.10e}\n")


def export_onnx(neural_model, path: str, frame_length: int = 200,
                verify: bool = True) -> dict:
    """Export a NeuralPAModel / DLAPredistorter's network to ONNX.

    The network maps (batch, T, 2) I/Q frames to (batch, T, 2). Returns
    a dict with the path and, if ``onnxruntime`` is available and
    ``verify`` is set, the max abs error vs the torch forward.
    """
    import torch

    net = neural_model.net.eval()
    dummy = torch.randn(1, frame_length, 2)
    torch.onnx.export(
        net, (dummy,), path, input_names=["iq_in"], output_names=["iq_out"],
        dynamic_axes={"iq_in": {0: "batch", 1: "time"},
                      "iq_out": {0: "batch", 1: "time"}},
        opset_version=17)

    result = {"path": path, "verified": False}
    if verify:
        try:
            import onnxruntime as ort
            sess = ort.InferenceSession(
                path, providers=["CPUExecutionProvider"])
            with torch.no_grad():
                ref = net(dummy).numpy()
            got = sess.run(None, {"iq_in": dummy.numpy()})[0]
            result["max_abs_err"] = float(np.abs(ref - got).max())
            result["verified"] = result["max_abs_err"] < 1e-4
        except ImportError:
            result["note"] = "onnxruntime not installed; skipped verify"
    return result
