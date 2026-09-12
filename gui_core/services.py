"""Computation services shared by both GUIs.

Every function is pure Python over the padpd API - no GUI imports. Data
sources are plain dicts (JSON-friendly metadata + numpy arrays) with two
shapes:

synthetic source:
    {kind:"synthetic", name, fs, bw, x_train, y_train, x_val, y_val,
     wf_val (OFDMWaveform for constellation EVM), drive, cfr_papr}
measured source (OpenDPD folder / Cadence CSV / .mat / .npz):
    {kind:"opendpd"|"cadence"|"mat"|"npz", name, fs, bw?, spec?,
     x_train, y_train, x_val, y_val, x_test, y_test}

Linearization metrics are chosen automatically: constellation EVM + WiFi
ACLR/mask for synthetic sources, OpenDPD conventions for measured ones.
"""

from __future__ import annotations

import os

import numpy as np

from padpd.cfr import cfr_clip_filter
from padpd.data import (IQDataset, align_delay, load_cadence_csv,
                        load_matlab_mat, load_opendpd_dataset)
from padpd.dpd import ILAPredistorter
from padpd.metrics import (aclr, aclr_opendpd, ccdf, check_mask,
                           default_wifi_mask, evm_of_signal, evm_spectral,
                           psd, target_gain_opendpd)
from padpd.metrics.amam import am_am_am_pm
from padpd.pa import (DDRVolterraModel, GMPModel, MemoryPolynomialModel,
                      ReferencePA, SplineGMP, SplineMemoryPolynomial,
                      ddr_volterra_default, gmp_opendpd_510,
                      load_model, mp_opendpd_500, nmse_db)
from padpd.waveform import OFDMConfig, generate_ofdm, papr_db

WARMUP = 200

from pathlib import Path  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent


def default_opendpd_dir() -> str:
    """Best-guess OpenDPD ``datasets`` directory, cross-platform.

    The GUI ships to any OS (notably the packaged Windows exe), so the
    default must not be a hardcoded Linux path. Checks the OPENDPD_DIR
    env var, then common locations relative to the repo, the working
    directory and the user's home; returns the first that exists, else
    a home-relative hint that is at least valid on the current OS.
    """
    env = os.environ.get("OPENDPD_DIR", "").strip()
    candidates = [Path(env)] if env else []
    candidates += [
        _REPO_ROOT.parent / "OpenDPD" / "datasets",   # sibling of repo
        _REPO_ROOT / "OpenDPD" / "datasets",           # inside repo
        Path.cwd() / "OpenDPD" / "datasets",
        Path.home() / "OpenDPD" / "datasets",
        Path.home() / "Downloads" / "OpenDPD" / "datasets",
    ]
    for c in candidates:
        try:
            if c.is_dir():
                return str(c)
        except OSError:
            continue
    return str(Path.home() / "OpenDPD" / "datasets")


# Values take (params, x_train): spline entries place their knots from the
# training signal; polynomial entries ignore the second argument.
CLASSICAL_MODELS = {
    "MP": lambda p, x: MemoryPolynomialModel(
        order=p.get("order", 7), memory_depth=p.get("memory", 4)),
    "GMP": lambda p, x: GMPModel(order=p.get("order", 7),
                                 memory_depth=p.get("memory", 4)),
    "DDR": lambda p, x: DDRVolterraModel(
        order=p.get("order", 5), memory_depth=p.get("memory", 15),
        dynamic_order=p.get("dynamic_order", 1)),
    # parametric spline: the GUI "order" slider doubles as the knot count
    "Spline-MP": lambda p, x: SplineMemoryPolynomial.from_signal(
        x, n_knots=p.get("order", 8), memory_depth=p.get("memory", 4)),
    "MP-500 (OpenDPD)": lambda p, x: mp_opendpd_500(),
    "GMP-510 (OpenDPD)": lambda p, x: gmp_opendpd_510(),
    "DDR-140 (preset)": lambda p, x: ddr_volterra_default(),
    "Spline-MP (K8,M4)": lambda p, x: SplineMemoryPolynomial.from_signal(
        x, n_knots=8, memory_depth=4),
    "Spline-GMP (K8)": lambda p, x: SplineGMP.from_signal(x, n_knots=8),
    # widely-linear / phase-harmonic variants for front-end-impaired DUTs
    # (image -> conj branches, LO leakage -> dc column, C-IM3 -> conj^3)
    "Spline-MP-WL (conj+dc)": lambda p, x: SplineMemoryPolynomial.from_signal(
        x, n_knots=p.get("order", 8), memory_depth=p.get("memory", 4),
        conjugate=True, dc_term=True),
    "Spline-MP-CIM3 (conj3+dc)": lambda p, x:
        SplineMemoryPolynomial.from_signal(
            x, n_knots=p.get("order", 8), memory_depth=p.get("memory", 4),
            conjugate=True, cim3=True, dc_term=True),
}

# TX front-end impairment presets for the synthetic DUT (manual 5.9):
# levels are the validated demo settings — IQ 0.3 dB/3 deg (IRR ~30 dB),
# LO leakage -35 dBc, counter-IM3 -32 dBc.
FRONTEND_DUTS = ("none", "iq", "iq+lo", "iq+lo+cim3")


def _wrap_frontend(pa, frontend: str):
    from padpd.pa import TxFrontEndPA
    if frontend == "none":
        return pa
    if frontend == "iq":
        return TxFrontEndPA(pa)
    if frontend == "iq+lo":
        return TxFrontEndPA(pa, lo_leakage_dbc=-35.0)
    if frontend == "iq+lo+cim3":
        return TxFrontEndPA(pa, lo_leakage_dbc=-35.0, cim3_dbc=-32.0)
    raise ValueError(f"frontend must be one of {FRONTEND_DUTS}")


# -- waveform ------------------------------------------------------------
def make_waveform(bandwidth_hz: float, qam: int, symbols: int, seed: int,
                  cfr_papr_db: float | None = None) -> dict:
    cfg = OFDMConfig(bandwidth_hz=bandwidth_hz, qam_order=qam,
                     n_symbols=symbols, seed=seed)
    wf = generate_ofdm(cfg)
    x = wf.x
    x_cfr = None
    if cfr_papr_db is not None:
        x_cfr = cfr_clip_filter(x, cfr_papr_db, cfg.sample_rate_hz,
                                bandwidth_hz)
    return {"wf": wf, "cfg": cfg, "x": x, "x_cfr": x_cfr,
            "fs": cfg.sample_rate_hz,
            "papr_db": papr_db(x),
            "papr_cfr_db": papr_db(x_cfr) if x_cfr is not None else None,
            "cfr_evm_db": (evm_of_signal(x_cfr, wf).db
                           if x_cfr is not None else None)}


# -- data sources --------------------------------------------------------
def make_synthetic_source(bandwidth_hz: float = 80e6, qam: int = 1024,
                          symbols: int = 8, drive: float = 0.14,
                          cfr_papr_db: float | None = None,
                          seed: int = 0, frontend: str = "none") -> dict:
    pa = _wrap_frontend(ReferencePA(drive=drive), frontend)
    tr = make_waveform(bandwidth_hz, qam, symbols, seed, cfr_papr_db)
    va = make_waveform(bandwidth_hz, qam, symbols, seed + 1, cfr_papr_db)
    xt = tr["x_cfr"] if tr["x_cfr"] is not None else tr["x"]
    xv = va["x_cfr"] if va["x_cfr"] is not None else va["x"]
    return {"kind": "synthetic",
            "name": f"ReferencePA d={drive} {bandwidth_hz/1e6:.0f}MHz/"
                    f"{qam}QAM" + (f" CFR{cfr_papr_db}" if cfr_papr_db else "")
                    + (f" FE({frontend})" if frontend != "none" else ""),
            "fs": tr["fs"], "bw": bandwidth_hz, "drive": drive,
            "cfr_papr": cfr_papr_db, "pa": pa, "frontend": frontend,
            "x_train": xt, "y_train": pa(xt),
            "x_val": xv, "y_val": pa(xv), "wf_val": va["wf"]}


from functools import lru_cache  # noqa: E402


@lru_cache(maxsize=3)
def cached_synthetic_source(bandwidth_hz: float = 80e6, qam: int = 1024,
                            symbols: int = 8, drive: float = 0.14,
                            cfr_papr_db: float | None = None,
                            seed: int = 0, frontend: str = "none") -> dict:
    """Bounded shared cache for synthetic sources.

    Both GUIs previously kept their own unbounded per-parameter caches
    (tens of MB per entry at 160/320 MHz) — an hour of slider
    exploration grew the process by GBs. Three entries cover the
    common flip-back-and-forth without hoarding.
    """
    return make_synthetic_source(bandwidth_hz, qam, symbols, drive,
                                 cfr_papr_db, seed, frontend)


def eval_source_for(meta: dict, sources: dict) -> dict:
    """Pick the evaluation source matching a fitted model.

    Prefer the exact source the model was fitted on; if that was a
    synthetic ReferencePA source (never registered), rebuild it at the
    same drive rather than silently evaluating on an unrelated dataset.
    """
    import re
    name = (meta or {}).get("source", "")
    if name in sources:
        return sources[name]
    # full form: "ReferencePA d=0.14 160MHz/4096QAM CFR8.0 FE(iq+lo)" —
    # rebuild the EXACT source; matching only drive would silently
    # evaluate the model on a different waveform (default 80 MHz /
    # 1024-QAM, no front end)
    m = re.search(r"ReferencePA d=([0-9.]+) ([0-9]+)MHz/([0-9]+)QAM"
                  r"(?: CFR([0-9.]+))?(?: FE\(([^)]+)\))?", name)
    if m:
        return make_synthetic_source(
            bandwidth_hz=float(m.group(2)) * 1e6, qam=int(m.group(3)),
            drive=float(m.group(1)),
            cfr_papr_db=float(m.group(4)) if m.group(4) else None,
            frontend=m.group(5) or "none")
    m = re.search(r"ReferencePA d=([0-9.]+)", name)
    if m:
        return make_synthetic_source(drive=float(m.group(1)))
    return next(iter(sources.values()), None) or make_synthetic_source()


def _from_dataset_splits(name, kind, fs, spec, tr, va, te) -> dict:
    return {"kind": kind, "name": name, "fs": fs, "spec": spec,
            "bw": (spec or {}).get("bw_main_ch"),
            "x_train": tr.x, "y_train": tr.y,
            "x_val": va.x, "y_val": va.y,
            "x_test": te.x, "y_test": te.y}


def load_source(kind: str, path: str, sample_rate_hz: float | None = None,
                auto_align: bool = False) -> dict:
    """Load a measured source. kind: opendpd|cadence|mat|npz."""
    name = os.path.basename(os.path.normpath(path))
    if kind == "opendpd":
        ds = load_opendpd_dataset(path)
        return _from_dataset_splits(name, kind, ds["train"].sample_rate_hz,
                                    ds["spec"], ds["train"], ds["val"],
                                    ds["test"])
    extras: dict = {}
    if kind == "cadence":
        d = load_cadence_csv(path)
    elif kind == "mat":
        d = load_matlab_mat(path)
    elif kind == "npz":
        # complete-source container (a plain IQDataset npz is the
        # degenerate case with no capture groups)
        from padpd.data import load_complete_npz
        comp = load_complete_npz(path)
        d = IQDataset(comp["x"], comp["y"], comp["fs"], comp["meta"])
        extras = comp["extras"]
    else:
        raise ValueError(f"unknown source kind: {kind}")
    if sample_rate_hz:
        d = IQDataset(d.x, d.y, sample_rate_hz, d.meta)
    info = None
    if auto_align:
        x_a, y_a, info = align_delay(d.x, d.y)
        d = IQDataset(x_a, y_a, d.sample_rate_hz, d.meta)
    tr, va, te = d.split((0.6, 0.2, 0.2))
    src = _from_dataset_splits(name, kind, d.sample_rate_hz, None,
                               tr, va, te)
    src["align_info"] = ({"lag": info["lag"],
                          "lag_total": info["lag_total"]} if info else None)
    src["extras"] = extras
    return src


def source_preview(src: dict) -> dict:
    """PSD + AM-AM data for a source preview panel."""
    x, y, fs = src["x_train"], src["y_train"], src["fs"]
    n = min(len(x), 65536)
    f_in, p_in = psd(x[:n], fs)
    f_out, p_out = psd(y[:n], fs)
    am = am_am_am_pm(x[:n], y[:n])
    return {"freq": f_in, "psd_in": p_in, "psd_out": p_out, "amam": am,
            "n_train": len(x), "n_val": len(src["x_val"]),
            "n_test": len(src.get("x_test", []))}


# -- PA modeling ---------------------------------------------------------
def _eval_split(src: dict) -> tuple[np.ndarray, np.ndarray]:
    """(x, y) used for reporting model NMSE: test if present else val."""
    if "x_test" in src and len(src.get("x_test", [])):
        return src["x_test"], src["y_test"]
    return src["x_val"], src["y_val"]


def _warm_predict(model, src: dict, x_eval: np.ndarray) -> np.ndarray:
    ctx = src["x_val"][-WARMUP:] if len(src["x_val"]) > WARMUP else \
        src["x_train"][-WARMUP:]
    return model(np.concatenate([ctx, x_eval]))[len(ctx):]


def fit_classical(src: dict, model_name: str, params: dict | None = None,
                  regularization: float = 1e-9) -> dict:
    model = CLASSICAL_MODELS[model_name](params or {}, src["x_train"])
    model.fit(src["x_train"], src["y_train"], regularization=regularization)
    x_e, y_e = _eval_split(src)
    pred = _warm_predict(model, src, x_e)
    metrics = {"nmse_db": nmse_db(y_e, pred),
               "n_coeffs": int(np.atleast_1d(model.coeffs).size)}
    return {"model": model, "metrics": metrics, "pred": pred,
            "x_eval": x_e, "y_eval": y_e}


def fit_neural(src: dict, backbone: str = "dgru", hidden: int = 8,
               epochs: int = 20, frame_length: int = 50, stride: int = 1,
               lr: float = 1e-3, seed: int = 0, on_epoch=None) -> dict:
    from padpd.nn import NeuralPAModel
    model = NeuralPAModel(backbone=backbone, hidden_size=hidden,
                          n_epochs=epochs, frame_length=frame_length,
                          stride=stride, lr=lr, seed=seed, verbose=False)
    model.fit(src["x_train"], src["y_train"], src["x_val"], src["y_val"],
              on_epoch=on_epoch)
    x_e, y_e = _eval_split(src)
    pred = _warm_predict(model, src, x_e)
    metrics = {"nmse_db": nmse_db(y_e, pred), "n_coeffs": model.n_params}
    return {"model": model, "metrics": metrics, "pred": pred,
            "x_eval": x_e, "y_eval": y_e}


# -- DPD -----------------------------------------------------------------
def run_dpd_ila(src: dict, basis: str = "GMP-510 (OpenDPD)",
                params: dict | None = None, surrogate=None,
                n_iterations: int = 2) -> dict:
    """ILA DPD. Synthetic: closed loop against the live ReferencePA.
    Measured: single-shot fit_measured; evaluation via ``surrogate``
    (a fitted PA model; required for measured sources)."""
    factory = lambda: CLASSICAL_MODELS[basis](params or {},  # noqa: E731
                                              src["x_train"])
    if src["kind"] == "synthetic":
        pa = src["pa"]
        dpd = ILAPredistorter(model_factory=factory,
                              n_iterations=n_iterations,
                              fit_kwargs={"regularization": 1e-9})
        dpd.fit(pa, src["x_train"])
        y_before = pa(src["x_val"])
        y_after = pa(dpd(src["x_val"]))
        return _evaluate_synth(src, y_before, y_after, dpd)
    if surrogate is None:
        raise ValueError("measured source needs a surrogate PA model "
                         "for evaluation")
    g = target_gain_opendpd(src["x_train"], src["y_train"])
    dpd = ILAPredistorter(model_factory=factory, target_gain=g,
                          fit_kwargs={"regularization": 1e-9})
    dpd.fit_measured(src["x_train"], src["y_train"])
    x_e, y_meas = _eval_split(src)
    y_after = _warm_predict(surrogate,
                            src, np.asarray(dpd(np.concatenate(
                                [src["x_val"][-WARMUP:], x_e]))[WARMUP:]))
    return _evaluate_measured(src, y_meas, y_after, g, dpd)


def run_dpd_dla(src: dict, surrogate, hidden: int = 8, epochs: int = 20,
                frame_length: int = 50, stride: int = 1,
                on_epoch=None) -> dict:
    """DLA neural DPD through a differentiable NeuralPAModel surrogate."""
    from padpd.nn import DLAPredistorter
    spec = src.get("spec") or {}
    aclr_spec = ({"fs": src["fs"], "bw_main_ch": spec["bw_main_ch"],
                  "n_sub_ch": spec["n_sub_ch"], "nperseg": spec["nperseg"]}
                 if spec else None)
    g = (target_gain_opendpd(src["x_train"], src["y_train"])
         if src["kind"] != "synthetic" else None)
    dpd = DLAPredistorter(hidden_size=hidden, n_epochs=epochs,
                          frame_length=frame_length, stride=stride,
                          target_gain=g, aclr_spec=aclr_spec, verbose=False)
    dpd.fit(surrogate, src["x_train"], src["x_val"], on_epoch=on_epoch)
    if src["kind"] == "synthetic":
        pa = src["pa"]
        return _evaluate_synth(src, pa(src["x_val"]), pa(dpd(src["x_val"])),
                               dpd)
    x_e, y_meas = _eval_split(src)
    u = dpd(np.concatenate([src["x_val"][-WARMUP:], x_e]))[WARMUP:]
    y_after = _warm_predict(surrogate, src, np.asarray(u))
    return _evaluate_measured(src, y_meas, y_after, dpd.target_gain, dpd)


def _evaluate_synth(src, y_before, y_after, dpd) -> dict:
    wf, fs, bw = src["wf_val"], src["fs"], src["bw"]
    mask = default_wifi_mask(bw)
    rows = {}
    for label, y in (("no DPD", y_before), ("DPD", y_after)):
        e = evm_of_signal(y, wf).db
        a = aclr(y, fs, bw)
        f, p = psd(y, fs)
        ok, margin, _ = check_mask(f, p, mask)
        rows[label] = {"evm_db": e, "aclr_low": a["lower_dbc"],
                       "aclr_high": a["upper_dbc"],
                       "mask": "PASS" if ok else "FAIL"}
    return {"dpd": dpd, "metrics": rows, "convention": "constellation",
            "y_before": y_before, "y_after": y_after,
            "x_ref": src["x_val"], "fs": fs, "bw": bw, "mask": mask,
            "wf": wf, "gain": dpd.target_gain}


def _evaluate_measured(src, y_before, y_after, g, dpd) -> dict:
    spec = src.get("spec") or {}
    fs = src["fs"]
    x_e, _ = _eval_split(src)
    rows = {}
    if spec:
        args = (fs, spec["bw_main_ch"], spec["n_sub_ch"], spec["nperseg"])
        for label, y in (("no DPD", y_before), ("DPD", y_after)):
            a = aclr_opendpd(y, *args)
            e = evm_spectral(y, g * x_e, *args)
            rows[label] = {"evm_db": e, "aclr_low": a["left_dbc"],
                           "aclr_high": a["right_dbc"], "mask": "-"}
        conv = "opendpd"
    else:
        for label, y in (("no DPD", y_before), ("DPD", y_after)):
            rows[label] = {"evm_db": nmse_db(g * x_e, y), "aclr_low": None,
                           "aclr_high": None, "mask": "-"}
        conv = "nmse-vs-linear"
    return {"dpd": dpd, "metrics": rows, "convention": conv,
            "y_before": y_before, "y_after": y_after, "x_ref": x_e,
            "fs": fs, "bw": spec.get("bw_main_ch"), "mask": None,
            "wf": None, "gain": g}


# -- deployment ----------------------------------------------------------
def bitwidth_sweep(model, src: dict, bits=(16, 12, 10, 8)) -> dict:
    from padpd.deploy import FixedPointPolyModel, mac_cost
    x_e, y_e = _eval_split(src)
    is_neural = hasattr(model, "net")
    out = {"float": nmse_db(y_e, _warm_predict(model, src, x_e)),
           "bits": {}}
    for b in bits:
        if is_neural:
            from padpd.nn import quantize_neural_ptq
            q = quantize_neural_ptq(model, w_bits=b, a_bits=b)
        else:
            q = FixedPointPolyModel(model, w_bits=b, sig_bits=b)
        out["bits"][b] = nmse_db(y_e, _warm_predict(q, src, x_e))
    if is_neural:
        out["macs"] = None
    else:
        nc = int(np.atleast_1d(model.coeffs).size)
        out["macs"] = mac_cost(nc, src["fs"])
    return out


def lut_sweep(model, src: dict, entries=(1024, 256, 128, 64, 32),
              entry_bits: int | None = None) -> dict:
    """LUT-depth axis of the deployment trade-off (mirrors bitwidth_sweep).

    Extracts an interpolated LUT from a branch-gain model (spline/MP) at
    each table depth and measures the NMSE vs the float model's own
    prediction target. ``entry_bits`` optionally adds entry quantization
    on top (the two axes are orthogonal).
    """
    from padpd.deploy import (LUTDPD, lut_from_model, quantize_lut,
                              spline_mac_cost)
    x_e, y_e = _eval_split(src)
    out = {"float": nmse_db(y_e, _warm_predict(model, src, x_e)),
           "entries": {}}
    for n in entries:
        lut = lut_from_model(model, n_entries=n)
        if entry_bits is not None:
            lut = quantize_lut(lut, entry_bits)
        out["entries"][n] = nmse_db(
            y_e, _warm_predict(LUTDPD.from_table(lut), src, x_e))
    out["macs"] = spline_mac_cost(len(model.branch_delays()), src["fs"],
                                  degree=getattr(model, "degree", 3))
    return out


def export_artifacts(model, src: dict, out_dir: str, w_bits: int = 16,
                     n_vectors: int = 2048) -> dict:
    from padpd.deploy import (FixedPointPolyModel, export_linear_coeffs,
                              export_reference_vectors)
    os.makedirs(out_dir, exist_ok=True)
    paths = {}
    x_e, _ = _eval_split(src)
    if hasattr(model, "net"):
        from padpd.deploy import export_onnx
        p = os.path.join(out_dir, "model.onnx")
        res = export_onnx(model, p,
                          frame_length=model.config["frame_length"])
        paths["onnx"] = p
        paths["onnx_verified"] = res.get("verified")
        vp = os.path.join(out_dir, "reference_vectors.csv")
        export_reference_vectors(model, x_e, vp, n=n_vectors)
        paths["vectors"] = vp
    else:
        cp = os.path.join(out_dir, f"coeffs_w{w_bits}.json")
        export_linear_coeffs(model, w_bits, cp)
        paths["coeffs"] = cp
        fp = FixedPointPolyModel(model, w_bits, w_bits)
        vp = os.path.join(out_dir, f"reference_vectors_w{w_bits}.csv")
        export_reference_vectors(fp, x_e, vp, n=n_vectors)
        paths["vectors"] = vp
        # synthesizable Verilog DPD MAC + bit-true testbench
        from padpd.deploy.rtl import emit_rtl, verify_with_iverilog
        rtl_dir = os.path.join(out_dir, "rtl")
        rtl = emit_rtl(model, rtl_dir, w_bits=w_bits, data_bits=w_bits)
        paths["rtl_verilog"] = rtl["verilog"]
        paths["rtl_verified"] = verify_with_iverilog(rtl_dir)["passed"]
    return paths


# -- adaptive / online DPD (drift tracking) ------------------------------
ADAPTIVE_METHODS = ("rls", "whitened", "apa")
ADAPTIVE_BASES = ("gmp", "spline")
ADAPTIVE_DUTS = ("drift", "thermal")


def _evm_drift(pa, sig, wf) -> float:
    """Constellation EVM of a signal through ``pa``, per-block gain-fit."""
    from padpd.metrics import evm
    from padpd.waveform import demodulate_ofdm
    y = pa(sig)
    if not np.all(np.isfinite(y)):
        return float("nan")
    g = np.vdot(wf.x, y) / np.vdot(wf.x, wf.x)
    return evm(demodulate_ofdm(y / g, wf), wf.tx_symbols).db


def run_adaptive_dpd(method: str = "rls", n_blocks: int = 10,
                     drift_span: float = 0.02, drive0: float = 0.13,
                     forget: float = 0.6, mu: float = 0.5, apa_k: int = 4,
                     bw: float = 80e6, qam: int = 1024, n_symbols: int = 6,
                     warm_blocks: int = 6, seed: int = 0,
                     basis: str = "gmp", dut: str = "drift") -> dict:
    """Drift-tracking demo: an adaptive DPD vs a frozen batch DPD on a
    PA that changes underneath it across ``n_blocks`` signal blocks.

    ``method`` is one of :data:`ADAPTIVE_METHODS` (rls / whitened / apa);
    ``basis`` one of :data:`ADAPTIVE_BASES` (gmp = polynomial GMP,
    spline = SplineMemoryPolynomial, knots placed on block 0); ``dut``
    one of :data:`ADAPTIVE_DUTS` — "drift" ramps DriftingReferencePA
    cold->hot externally, "thermal" runs the self-heating
    ThermalReferencePA whose state follows its own dissipated power.
    Returns per-block linearization EVM for both the frozen baseline and
    the adaptive predistorter, plus the final gap — the field value of
    adaptation. No data source needed.
    """
    if method not in ADAPTIVE_METHODS:
        raise ValueError(f"method must be one of {ADAPTIVE_METHODS}")
    if basis not in ADAPTIVE_BASES:
        raise ValueError(f"basis must be one of {ADAPTIVE_BASES}")
    if dut not in ADAPTIVE_DUTS:
        raise ValueError(f"dut must be one of {ADAPTIVE_DUTS}")
    if n_blocks < 2:
        raise ValueError("n_blocks must be >= 2")
    from padpd.dpd import AdaptiveDPD, ILAPredistorter
    from padpd.pa import (DriftingReferencePA, SplineMemoryPolynomial,
                          ThermalReferencePA)

    blocks = [generate_ofdm(OFDMConfig(bandwidth_hz=bw, qam_order=qam,
                                       n_symbols=n_symbols, seed=seed + s))
              for s in range(n_blocks)]
    drift = DriftingReferencePA(drive0=drive0, drive_span=drift_span,
                                beta_a_span=0.2, alpha_p_span=0.5)
    drift.set_state(0.0)
    cold = drift.pa()
    thermal = None
    if dut == "thermal":
        # time constants scaled to the block length so the self-heating
        # actually accumulates ACROSS blocks (visible drift to track)
        fs = blocks[0].sample_rate_hz
        t_block = len(blocks[0].x) / fs
        thermal = ThermalReferencePA(drive0=drive0, fs=fs,
                                     taus_s=(0.5 * t_block, 3.0 * t_block),
                                     heat_gain=0.5)

    if basis == "spline":
        def factory():
            return SplineMemoryPolynomial.from_signal(blocks[0].x,
                                                      n_knots=8,
                                                      memory_depth=4)
    else:
        def factory():
            return GMPModel(order=7, memory_depth=4)

    frozen = ILAPredistorter(factory, n_iterations=3)
    frozen.fit(cold, blocks[0].x)
    adapt = AdaptiveDPD(factory, method=method, forget=forget, mu=mu,
                        apa_k=apa_k)
    adapt.warm_start(cold, blocks[0].x, blocks=warm_blocks)

    states, e_frozen, e_adapt = [], [], []
    for i, wf in enumerate(blocks):
        if thermal is not None:
            pa = thermal              # stateful: every pass heats it
        else:
            drift.set_state(i / (n_blocks - 1))
            pa = drift.pa()
        e_frozen.append(_evm_drift(pa, frozen(wf.x), wf))
        e_adapt.append(_evm_drift(pa, adapt(wf.x), wf))
        adapt.update(pa, wf.x)
        states.append(thermal.state if thermal is not None else drift.state)

    return {"method": method, "blocks": list(range(n_blocks)),
            "states": states, "evm_frozen": e_frozen, "evm_adaptive": e_adapt,
            "final_frozen": e_frozen[-1], "final_adaptive": e_adapt[-1],
            "gap_db": e_frozen[-1] - e_adapt[-1], "n_coeffs": adapt.n_coeffs,
            "drive_cold": drive0, "drive_hot": drive0 + drift_span,
            # echo the run parameters so callers can register a run
            "n_blocks": n_blocks, "drift_span": drift_span,
            "forget": forget, "apa_k": apa_k, "bw": bw,
            "basis": basis, "dut": dut}


def adaptive_run_record(res: dict) -> tuple[str, dict, dict]:
    """Build (name, config, metrics) to register an adaptive run so it
    compares alongside batch DPD (evm_db = adaptive, evm_before_db =
    frozen)."""
    tag = res["method"].upper()
    if res["method"] == "apa":
        tag += f"(K{res['apa_k']})"
    if res.get("basis", "gmp") == "spline":
        tag += "-Spl"
    name = f"Adapt-{tag} @ {res.get('dut', 'drift')}"
    config = {"algo": "adaptive", "method": res["method"],
              "basis": res.get("basis", "gmp"), "dut": res.get("dut",
                                                               "drift"),
              "apa_k": res["apa_k"], "n_blocks": res["n_blocks"],
              "drift_span": res["drift_span"], "forget": res["forget"],
              "bw_mhz": res.get("bw", 80e6) / 1e6}
    metrics = {"evm_db": res["final_adaptive"],
               "evm_before_db": res["final_frozen"],
               "gap_db": res["gap_db"], "n_coeffs": res["n_coeffs"]}
    return name, config, metrics


# -- power-gain-modulation identification (tau characterization) ---------
GAIN_MOD_DUTS = ("thermal", "static")


def _gain_mod_dict(res, dut: str, drive: float | None, fs: float) -> dict:
    """GUI-friendly dict from a GainModulationResult (shared by the
    virtual-DUT experiment and the measured-capture path)."""
    def _bins(v, n=400):
        m = len(v) - len(v) % n
        return v[:m].reshape(n, -1).mean(axis=1)

    g0 = res.gain_heat[0]
    return {"dut": dut, "drive": drive, "fs": fs,
            "significant": res.significant,
            "droop_db": res.droop_db,
            "phase_drift_deg": res.phase_drift_deg,
            "taus_heat_us": [t * 1e6 for t in res.taus_heat_s],
            "weights_heat": res.weights_heat,
            "taus_cool_us": [t * 1e6 for t in res.taus_cool_s],
            "weights_cool": res.weights_cool,
            "hysteresis_ratio": res.hysteresis_ratio,
            "hysteresis_reliable": res.hysteresis_reliable,
            "observation_us": res.observation_s * 1e6,
            "state_alphas": list(res.state_alphas(fs)),
            "rationale": res.rationale(),
            "t_us": _bins(res.t_s) * 1e6,
            "heat_db": 20 * np.log10(np.abs(_bins(res.gain_heat)
                                            / abs(g0))),
            "cool_db": 20 * np.log10(np.abs(_bins(res.gain_cool)
                                            / abs(g0))),
            "heat_deg": np.degrees(np.angle(_bins(res.gain_heat) / g0)),
            "nmse_plain_db": None, "nmse_state_db": None,
            "state_gain_db": None}


def run_gain_modulation(dut: str = "thermal", drive: float = 0.13,
                        fit_state_model: bool = True,
                        bw: float = 80e6, qam: int = 1024,
                        n_symbols: int = 6, seed: int = 0) -> dict:
    """Step-response characterization of power-gain modulation
    (padpd.gain_modulation, manual 5.9): identify the heating/cooling
    time constants of a virtual DUT, then (optionally) close the loop —
    fit a plain SMP and a StateConditionedSpline configured with the
    IDENTIFIED state_alphas on a burst stimulus and report the gain.

    ``dut``: "thermal" = self-heating ThermalReferencePA (taus 5/30 us
    ground truth), "static" = plain ReferencePA (control: the probe
    must report no modulation).
    """
    if dut not in GAIN_MOD_DUTS:
        raise ValueError(f"dut must be one of {GAIN_MOD_DUTS}")
    from padpd.gain_modulation import identify_gain_modulation
    from padpd.pa import ThermalReferencePA
    from padpd.pa.spline_state import StateConditionedSpline
    from padpd.pa.thermal import burst_stimulus

    fs = OFDMConfig(bandwidth_hz=bw, qam_order=qam,
                    n_symbols=n_symbols, seed=seed).sample_rate_hz
    pa = (ThermalReferencePA(drive0=drive, fs=fs) if dut == "thermal"
          else ReferencePA(drive=drive))
    res = identify_gain_modulation(pa, fs=fs)

    out = _gain_mod_dict(res, dut, drive, fs)

    if fit_state_model and res.significant:
        # burst stimulus long enough for the slowest identified state to
        # evolve within a segment (12 symbols ~ 163 us at 80 MHz)
        wf_t = generate_ofdm(OFDMConfig(bandwidth_hz=bw, qam_order=qam,
                                        n_symbols=max(n_symbols, 12),
                                        seed=seed))
        wf_v = generate_ofdm(OFDMConfig(bandwidth_hz=bw, qam_order=qam,
                                        n_symbols=max(n_symbols, 12),
                                        seed=seed + 1))
        xb_t = burst_stimulus(wf_t.x, n_bursts=6, low_scale=0.3)
        xb_v = burst_stimulus(wf_v.x, n_bursts=6, low_scale=0.3)
        # fresh DUT: ThermalReferencePA freezes its dissipated-power
        # reference on the first capture, and the CW identification
        # probe (|a_hi|^2 = 2.25) would mis-scale it for the ~0.55-power
        # burst waveform, muting the very dynamics being modeled
        pa2 = ThermalReferencePA(drive0=drive, fs=fs)
        y_t = pa2(xb_t)
        pa2.reset()
        y_v = pa2(xb_v)
        plain = SplineMemoryPolynomial.from_signal(xb_t, n_knots=8,
                                                   memory_depth=4)
        plain.fit(xb_t, y_t, regularization=1e-9)
        state = StateConditionedSpline.from_signal(
            xb_t, n_knots=8, memory_depth=4,
            state_alphas=res.state_alphas(fs))
        state.fit(xb_t, y_t, regularization=1e-9)
        w = WARMUP
        out["nmse_plain_db"] = nmse_db(y_v[w:], plain(xb_v)[w:])
        out["nmse_state_db"] = nmse_db(y_v[w:], state(xb_v)[w:])
        out["state_gain_db"] = (out["nmse_plain_db"]
                                - out["nmse_state_db"])
    return out


def gain_mod_run_record(res: dict) -> tuple[str, dict, dict]:
    """Build (name, config, metrics) to register an identification run."""
    name = f"GainMod @ {res['dut']}"
    config = {"algo": "gain_modulation", "dut": res["dut"],
              "drive": res["drive"], "fs_mhz": res["fs"] / 1e6}
    metrics = {"droop_db": res["droop_db"],
               "phase_drift_deg": res["phase_drift_deg"],
               "hysteresis_ratio": res["hysteresis_ratio"]}
    for i, (t, w) in enumerate(zip(res["taus_heat_us"],
                                   res["weights_heat"], strict=True)):
        metrics[f"tau{i+1}_us"] = t
        metrics[f"w{i+1}"] = w
    if res["state_gain_db"] is not None:
        metrics.update({"nmse_db": res["nmse_state_db"],
                        "nmse_plain_db": res["nmse_plain_db"],
                        "state_gain_db": res["state_gain_db"]})
    return name, config, metrics


# -- complete measured source: capture-group consumers -------------------
EXAMPLE_COMPLETE_NPZ = str(_REPO_ROOT / "examples"
                           / "complete_source_demo.npz")


def source_extras_rows(src: dict) -> list[dict]:
    """Checklist rows for a source's optional capture groups."""
    from padpd.data import extras_summary
    return extras_summary(src.get("extras"))


def consume_source_extras(src: dict) -> dict:
    """Run every consumer the source's capture groups allow; returns a
    summary dict (missing groups are skipped, per-group errors are
    reported as strings rather than raised)."""
    out: dict = {}
    gm = None
    try:
        gm = identify_gain_mod_from_source(src)
        if gm is not None:
            out["gain_mod"] = {k: gm[k] for k in
                               ("significant", "droop_db",
                                "phase_drift_deg", "taus_heat_us",
                                "weights_heat", "hysteresis_ratio",
                                "state_alphas")}
    except Exception as e:  # noqa: BLE001
        out["gain_mod_error"] = str(e)
    try:
        alphas = (tuple(gm["state_alphas"])
                  if gm is not None and gm["significant"] else None)
        st = fit_state_spline_from_source(src, state_alphas=alphas)
        if st is not None:
            out["state_fit"] = {k: st[k] for k in
                                ("nmse_plain_db", "nmse_state_db",
                                 "state_gain_db", "state_alphas")}
    except Exception as e:  # noqa: BLE001
        out["state_fit_error"] = str(e)
    try:
        de, info = deembedder_from_source(src)
        if de is not None:
            out["deembed"] = {
                "rx_irr_db": info.get("cal_rx", {}).get("rx_irr_db"),
                "fir_fit_nmse_db": info.get("cal_rx",
                                            {}).get("fir_fit_nmse_db"),
                "rx_im3_dbc": info.get("atten", {}).get("rx_im3_dbc")}
    except Exception as e:  # noqa: BLE001
        out["deembed_error"] = str(e)
    try:
        sc = scheduler_from_source(src)
        if sc is not None:
            out["scheduler"] = {"conditions": sc["conditions"],
                                "nmse_per_point_db":
                                    sc["nmse_per_point_db"]}
    except Exception as e:  # noqa: BLE001
        out["scheduler_error"] = str(e)
    return out


def deembedder_from_source(src: dict, n_taps: int = 33):
    """Build an ObservationDeembedder calibrated from the source's
    ``cal_rx`` (PA-bypass) and ``atten`` (attenuator-step) groups.

    Returns ``(deembedder, info)`` or ``(None, {})`` when the source
    carries neither calibration group.
    """
    from padpd.data import ObservationDeembedder
    ex = src.get("extras") or {}
    if "cal_rx" not in ex and "atten" not in ex:
        return None, {}
    de = ObservationDeembedder()
    info: dict = {}
    if "cal_rx" in ex:
        info["cal_rx"] = de.calibrate_rx_path(
            ex["cal_rx"]["ref"], ex["cal_rx"]["obs"], n_taps=n_taps)
    if "atten" in ex:
        a = ex["atten"]
        info["atten"] = de.calibrate_rx_im3(a["ref"], a["hi"], a["lo"],
                                            step_db=a["step_db"])
    return de, info


def identify_gain_mod_from_source(src: dict) -> dict | None:
    """Offline tau identification from the source's ``step`` capture
    (same output schema as :func:`run_gain_modulation`; None when the
    source has no step group)."""
    ex = src.get("extras") or {}
    if "step" not in ex:
        return None
    from padpd.gain_modulation import identify_gain_modulation_capture
    res = identify_gain_modulation_capture(ex["step"]["x"],
                                           ex["step"]["y"], src["fs"])
    return _gain_mod_dict(res, dut="measured", drive=None, fs=src["fs"])


def fit_state_spline_from_source(src: dict,
                                 state_alphas=None) -> dict | None:
    """Fit plain SMP vs StateConditionedSpline on the source's burst
    capture (train/val = contiguous 60/40 split of the burst).

    ``state_alphas`` defaults to the taus identified from the source's
    own ``step`` capture. Returns None when the burst group is missing;
    raises when alphas are needed but the step capture shows no
    significant modulation.
    """
    from padpd.pa.spline_state import StateConditionedSpline
    ex = src.get("extras") or {}
    if "burst" not in ex:
        return None
    if state_alphas is None:
        gm = identify_gain_mod_from_source(src)
        if gm is None or not gm["significant"]:
            raise ValueError("no state_alphas given and the step capture "
                             "shows no significant gain modulation")
        state_alphas = tuple(gm["state_alphas"])
    xb, yb = ex["burst"]["x"], ex["burst"]["y"]
    n_tr = int(len(xb) * 0.6)
    x_t, y_t = xb[:n_tr], yb[:n_tr]
    plain = SplineMemoryPolynomial.from_signal(x_t, n_knots=8,
                                               memory_depth=4)
    plain.fit(x_t, y_t, regularization=1e-9)
    state = StateConditionedSpline.from_signal(
        x_t, n_knots=8, memory_depth=4, state_alphas=state_alphas)
    state.fit(x_t, y_t, regularization=1e-9)
    # evaluate as full-capture prediction, scored on the held-out tail:
    # the model's causal state recursion must see the same power
    # history the DUT did — predicting on the tail alone would assume
    # a cold start that the recorded tail did not have
    out = {"state_alphas": list(state_alphas),
           "nmse_plain_db": nmse_db(yb[n_tr:], plain(xb)[n_tr:]),
           "nmse_state_db": nmse_db(yb[n_tr:], state(xb)[n_tr:]),
           "model": state}
    out["state_gain_db"] = out["nmse_plain_db"] - out["nmse_state_db"]
    return out


def scheduler_from_source(src: dict, n_knots: int = 8,
                          memory_depth: int = 4) -> dict | None:
    """Fit one spline model per operating point and build a
    CoefficientScheduler over the source's ``operating_points`` group.

    All models share the first point's configuration (knots included) —
    the scheduler interpolates coefficients, so the basis must be
    common. Returns None when the group is missing.
    """
    from padpd.pa.spline_state import CoefficientScheduler
    ex = src.get("extras") or {}
    if "operating_points" not in ex:
        return None
    conditions = ex["operating_points"]["conditions"]
    pairs = ex["operating_points"]["pairs"]
    base = SplineMemoryPolynomial.from_signal(
        np.concatenate([p[0] for p in pairs]), n_knots=n_knots,
        memory_depth=memory_depth)
    models, nmses = [], []
    for xi, yi in pairs:
        m = type(base)(**base.get_config())
        m.fit(xi, yi, regularization=1e-9)
        models.append(m)
        nmses.append(nmse_db(yi[WARMUP:], m(xi)[WARMUP:]))
    sched = CoefficientScheduler(models, conditions)
    return {"scheduler": sched, "conditions": list(map(float, conditions)),
            "nmse_per_point_db": nmses}


# -- three-loop joint demo (QMC + de-embed + adaptive DPD) ---------------
def run_three_loop_demo(n_blocks: int = 10, drift_span: float = 0.02,
                        gain_db: float = 0.3, phase_deg: float = 3.0,
                        lo_leakage_dbc: float = -35.0, bw: float = 80e6,
                        forget: float = 0.6, n_symbols: int = 4,
                        on_block=None) -> dict:
    """System demo: QMC + observation de-embedding + adaptive RLS DPD
    running simultaneously on a drifting PA behind a TX front end,
    observed through a corrupted loopback (padpd.three_loop, manual
    5.9). Returns per-block on-air EVM for the raw / de-embed-only /
    three-loop configurations plus the QMC residual traces."""
    from padpd.three_loop import run_three_loop
    return run_three_loop(n_blocks=n_blocks, drift_span=drift_span,
                          gain_db=gain_db, phase_deg=phase_deg,
                          lo_leakage_dbc=lo_leakage_dbc, bw=bw,
                          forget=forget, n_symbols=n_symbols,
                          on_block=on_block)


def three_loop_run_record(res: dict) -> tuple[str, dict, dict]:
    """Build (name, config, metrics) to register a three-loop run
    (evm_db = three loops, evm_before_db = de-embed-only pin)."""
    name = "3Loop QMC+Deembed+RLS @ drift"
    config = {"algo": "three_loop", "n_blocks": res["n_blocks"],
              "drift_span": res["drift_span"], "gain_db": res["gain_db"],
              "phase_deg": res["phase_deg"],
              "lo_leakage_dbc": res["lo_leakage_dbc"],
              "forget": res["forget"], "bw_mhz": res["bw"] / 1e6}
    metrics = {"evm_db": res["final_full"],
               "evm_before_db": res["final_deembed"],
               "evm_raw_db": res["final_raw"],
               "image_dbc": res["final_image_dbc"],
               "n_coeffs": res["n_coeffs"]}
    return name, config, metrics


# -- two-tone memory diagnostics -----------------------------------------
EXAMPLE_TWO_TONE_CSV = str(_REPO_ROOT / "examples" / "two_tone_example.csv")


def analyze_two_tone_csv(path: str) -> dict:
    """Load a two-tone IM3-vs-spacing CSV and derive the DPD budget.

    Returns a display-ready dict: the parsed sweep arrays, the condensed
    memory metrics, and the recommended DPD sizing (GMP memory depth,
    cross terms, coefficient count, rationale). Used by both GUIs' Data
    Manager two-tone panel; the coefficients themselves are still trained
    on measured data.
    """
    from padpd.two_tone import load_two_tone_csv, recommend_dpd_budget
    r = load_two_tone_csv(path)
    b = recommend_dpd_budget(r)
    return {"result": r, "budget": b,
            "spacings_hz": r.spacings_hz,
            "im3_lower_dbc": r.im3_lower_dbc,
            "im3_upper_dbc": r.im3_upper_dbc,
            "im3_avg_dbc": r.im3_avg_dbc,
            "memory_strength_db": r.memory_strength_db,
            "im3_spread_db": r.im3_spread_db,
            "im3_asym_db": r.im3_asym_db,
            "thermal_suspected": r.thermal_suspected,
            "memory_depth": b["memory_depth"],
            "use_cross_terms": b["use_cross_terms"],
            "est_coeffs": b["est_coeffs"],
            "spline_config": b["spline_config"],
            "spline_est_coeffs": b["spline_est_coeffs"],
            "spline_runtime_macs": b["spline_runtime_macs"],
            "rationale": b["rationale"]}


# -- misc plot data ------------------------------------------------------
def psd_pair(y_dict: dict, fs: float) -> dict:
    return {label: psd(y, fs) for label, y in y_dict.items()}


def ccdf_curves(x_dict: dict) -> dict:
    return {label: ccdf(x) for label, x in x_dict.items()}


def constellation_points(y: np.ndarray, wf, gain) -> np.ndarray:
    from padpd.waveform import demodulate_ofdm
    return demodulate_ofdm(np.asarray(y) / gain, wf).ravel()


def load_saved_model(path: str):
    if path.endswith(".pt"):
        from padpd.nn import NeuralPAModel
        return NeuralPAModel.load(path)
    return load_model(path)
