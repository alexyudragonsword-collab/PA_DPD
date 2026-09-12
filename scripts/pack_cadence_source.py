"""Pack a directory of Cadence CSV exports into a complete-source npz.

Closes the last manual step of the pre-tapeout flow: Spectre envelope
runs export one CSV per capture, this packs them into the single
container the platform consumes (padpd.data.complete).

Expected files in the capture directory (all Cadence Envelope CSVs with
columns ``time, i_in, q_in, i_out, q_out``; only ``main.csv`` is
required):

===================  =====================================================
file                 role
===================  =====================================================
main.csv             the stationary (x, y) capture
burst.csv            burst stimulus capture -> state-conditioned spline
step.csv             constant-envelope step probe -> tau identification
cal_rx.csv           PA-BYPASS capture: in = cal drive, out = RX output
atten_hi.csv         attenuator-step pair, nominal level
atten_lo.csv         attenuator-step pair, attenuated (see --atten-step-db)
op_<cond>.csv        one per operating point; <cond> is the condition
                     scalar parsed from the name (op_25.csv, op_-40.csv,
                     op_1.8.csv). Two or more make a scheduler.
===================  =====================================================

Scaling: every capture is scaled by ONE common factor (derived from
main.csv's input rms) and the factor is recorded in ``meta`` as
``norm_scale``. Per-capture normalization would be wrong — the
attenuator-step pair and the burst's high/low segments carry *relative
power* information, which is exactly what those groups exist to convey.

Usage:
    python scripts/pack_cadence_source.py CAPTURE_DIR -o chip_tt_25c.npz \\
        --atten-step-db 6 --meta center_freq_hz=5.955e9 corner=tt
    python scripts/pack_cadence_source.py CAPTURE_DIR --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from padpd.data import extras_summary, save_complete_npz
from padpd.data.io import read_csv_columns

REQUIRED_COLS = ("time", "i_in", "q_in", "i_out", "q_out")
OP_RE = re.compile(r"^op_(-?\d+(?:\.\d+)?)$")


class PackError(Exception):
    """Actionable packing error (missing file, inconsistent fs, ...)."""


def read_capture(path: Path) -> tuple[np.ndarray, np.ndarray, float]:
    """Read one Cadence CSV -> (x, y, fs), checking uniform sampling."""
    cols = read_csv_columns(str(path))
    missing = [c for c in REQUIRED_COLS if c not in cols]
    if missing:
        raise PackError(f"{path.name}: missing columns {missing} "
                        f"(expected {', '.join(REQUIRED_COLS)})")
    t = cols["time"]
    if len(t) < 16:
        raise PackError(f"{path.name}: only {len(t)} rows")
    dt = np.diff(t)
    # atol=0: the default 1e-8 s is LARGER than the sample period above
    # ~100 MHz, which would wave a jittered export through and derive a
    # wrong fs from its first step
    if not np.allclose(dt, dt[0], rtol=1e-6, atol=0.0):
        raise PackError(f"{path.name}: time column is not uniformly "
                        "sampled (export with a fixed strobe period)")
    x = cols["i_in"] + 1j * cols["q_in"]
    y = cols["i_out"] + 1j * cols["q_out"]
    return x, y, 1.0 / float(dt[0])


def scan_dir(capture_dir: Path) -> dict:
    """Map recognized file names to paths; unknown names are reported."""
    if not capture_dir.is_dir():
        raise PackError(f"{capture_dir}: not a directory")
    found: dict = {"op": {}, "unknown": []}
    for p in sorted(capture_dir.glob("*.csv")):
        stem = p.stem.lower()
        m = OP_RE.match(stem)
        if m:
            found["op"][float(m.group(1))] = p
        elif stem in ("main", "burst", "step", "cal_rx", "atten_hi",
                      "atten_lo"):
            found[stem] = p
        else:
            found["unknown"].append(p.name)
    if "main" not in found:
        raise PackError(f"{capture_dir}: main.csv not found "
                        "(the stationary capture is required)")
    return found


def pack_cadence_dir(capture_dir: str | Path, out_path: str | Path | None,
                     atten_step_db: float | None = None,
                     normalize: bool = True, meta: dict | None = None,
                     fs_rtol: float = 1e-6, verbose: bool = True) -> dict:
    """Read a capture directory and write the complete-source npz.

    Returns a report dict (fs, per-group sample counts, scale factor,
    warnings). With ``out_path=None`` nothing is written (dry run).
    """
    capture_dir = Path(capture_dir)
    found = scan_dir(capture_dir)
    report: dict = {"dir": str(capture_dir), "warnings": [],
                    "groups": {}, "unknown_files": found["unknown"]}
    if found["unknown"]:
        report["warnings"].append(
            f"ignored unrecognized files: {', '.join(found['unknown'])}")

    x, y, fs = read_capture(found["main"])
    report["fs"] = fs
    report["groups"]["main"] = len(x)

    def load(key: str):
        """Read an optional capture, enforcing a consistent sample rate."""
        if key not in found:
            return None
        xi, yi, fsi = read_capture(found[key])
        if abs(fsi - fs) > fs_rtol * fs:
            raise PackError(
                f"{found[key].name}: sample rate {fsi/1e6:.4f} MHz differs "
                f"from main.csv's {fs/1e6:.4f} MHz — resample or re-export "
                "with a common strobe period")
        report["groups"][key] = len(xi)
        return xi, yi

    burst = load("burst")
    step = load("step")
    cal = load("cal_rx")
    hi = load("atten_hi")
    lo = load("atten_lo")

    if (hi is None) != (lo is None):
        raise PackError("attenuator step needs BOTH atten_hi.csv and "
                        "atten_lo.csv (the difference isolates the RX "
                        "cubic; one capture alone cannot)")
    if hi is not None and atten_step_db is None:
        raise PackError("--atten-step-db is required with an "
                        "atten_hi/atten_lo pair (the known attenuation "
                        "is what scales the RX cubic)")

    ops = None
    if found["op"]:
        if len(found["op"]) < 2:
            report["warnings"].append(
                "only one op_*.csv: a scheduler needs >= 2 operating "
                "points, group dropped")
        else:
            conds = sorted(found["op"])
            pairs = []
            for c in conds:
                xi, yi, fsi = read_capture(found["op"][c])
                if abs(fsi - fs) > fs_rtol * fs:
                    raise PackError(
                        f"{found['op'][c].name}: sample rate differs from "
                        "main.csv")
                pairs.append((xi, yi))
            ops = (conds, pairs)
            report["groups"]["operating_points"] = len(conds)
            report["op_conditions"] = conds

    # ---- one common scale for every capture --------------------------
    scale = 1.0
    if normalize:
        rms = float(np.sqrt(np.mean(np.abs(x) ** 2)))
        if rms <= 0:
            raise PackError("main.csv input is all zeros")
        scale = 1.0 / rms
    report["norm_scale"] = scale

    def s(pair):
        return None if pair is None else (pair[0] * scale, pair[1] * scale)

    meta_out = dict(meta or {})
    meta_out.setdefault("source", "cadence_envelope")
    meta_out["norm_scale"] = scale          # multiply back to recover volts
    if hi is not None:
        meta_out.setdefault("atten_step_db", float(atten_step_db))

    if out_path is not None:
        hi_s = s(hi)
        lo_s = s(lo)
        save_complete_npz(
            str(out_path), x * scale, y * scale, fs,
            burst=s(burst), step=s(step),
            cal_rx=(None if cal is None
                    else (cal[0] * scale, cal[1] * scale)),
            atten=(None if hi is None
                   else (hi_s[0], hi_s[1], lo_s[1], float(atten_step_db))),
            operating_points=(None if ops is None
                              else (ops[0], [(xi * scale, yi * scale)
                                             for xi, yi in ops[1]])),
            meta=meta_out)
        report["out"] = str(out_path)

    extras = {}
    for key, present in (("burst", burst), ("step", step),
                         ("cal_rx", cal), ("atten", hi)):
        if present is not None:
            extras[key] = {"x": present[0]}
    if ops is not None:
        extras["operating_points"] = {"pairs": ops[1]}
    report["checklist"] = extras_summary(extras)

    if verbose:
        _print_report(report)
    return report


def _print_report(r: dict) -> None:
    print(f"capture dir : {r['dir']}")
    print(f"sample rate : {r['fs']/1e6:.4f} MHz")
    print(f"scale factor: {r['norm_scale']:.6g}  "
          "(multiply back for volts; recorded in meta['norm_scale'])")
    print(f"main capture: {r['groups']['main']} samples")
    print("capture groups:")
    for row in r["checklist"]:
        mark = "OK " if row["present"] else "-- "
        n = f"n={row['n']}" if row["present"] else ""
        print(f"  {mark}{row['group']:<18}{n:<12}{row['unlocks']}")
    if r.get("op_conditions"):
        print(f"  operating conditions: {r['op_conditions']}")
    for w in r["warnings"]:
        print(f"  ! {w}")
    if "out" in r:
        print(f"wrote {r['out']}")
    else:
        print("(dry run — nothing written)")


def _parse_meta(items) -> dict:
    """`key=value` pairs; numeric-looking values become floats."""
    out = {}
    for item in items or []:
        if "=" not in item:
            raise PackError(f"--meta expects key=value, got {item!r}")
        k, v = item.split("=", 1)
        try:
            out[k] = float(v)
        except ValueError:
            out[k] = {"true": True, "false": False}.get(v.lower(), v)
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capture_dir", help="directory of Cadence CSV exports")
    ap.add_argument("-o", "--out", help="output .npz (omit with --dry-run)")
    ap.add_argument("--atten-step-db", type=float,
                    help="attenuation between atten_hi and atten_lo (dB)")
    ap.add_argument("--no-normalize", action="store_true",
                    help="keep raw export units instead of scaling all "
                         "captures to unit-rms drive")
    ap.add_argument("--meta", nargs="*", metavar="K=V",
                    help="extra metadata, e.g. center_freq_hz=5.955e9 "
                         "reference_plane=pa_output corner=tt")
    ap.add_argument("--dry-run", action="store_true",
                    help="scan and validate only")
    args = ap.parse_args()

    if not args.dry_run and not args.out:
        ap.error("-o/--out is required unless --dry-run")
    try:
        pack_cadence_dir(args.capture_dir,
                         None if args.dry_run else args.out,
                         atten_step_db=args.atten_step_db,
                         normalize=not args.no_normalize,
                         meta=_parse_meta(args.meta))
    except PackError as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
