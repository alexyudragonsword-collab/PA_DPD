"""Why online DPD uses RLS, not LMS/NLMS: a side-by-side on one PA.

The adaptive predistorter learns a linear-in-parameters GMP over |x|^k
regressors. Those columns are strongly correlated, so the regressor
covariance is ill-conditioned (condition number ~1e10). This script runs
three online estimators from the same pass-through start against the same
(static) ReferencePA and reports per-block linearization EVM:

- **RLS** (``padpd.dpd.AdaptiveDPD``): implicitly inverts the covariance
  each block -> reaches the least-squares floor in ~1 block, and stays.
- **NLMS** (per-sample, power-normalized): a tuned gradient method. It
  survives but crawls up erratically and plateaus well short of the RLS
  floor -- the ill-conditioned modes barely move.
- **LMS** (plain, un-normalized): one common step choice and it diverges
  to NaN on the first block.

The takeaway is the online twin of the batch law "linear-in-params models
need LS, not SGD": gradient methods are fragile and slow on this basis;
(recursive) least squares is immediate and robust. Writes the figure to
``manual/assets/lms_vs_rls.png``.

Usage:  python scripts/run_lms_vs_rls.py [--fast]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from padpd.dpd import AdaptiveDPD
from padpd.metrics import evm
from padpd.pa import GMPModel, ReferencePA
from padpd.waveform import OFDMConfig, demodulate_ofdm, generate_ofdm

BW = 80e6
CEILING = 3.0   # plot cap for the diverging curve (dB)


def _factory():
    return GMPModel(order=7, memory_depth=4)


class BlockNLMS:
    """Per-sample (N)LMS on the same post-inverse regressors AdaptiveDPD
    uses, so the only difference from RLS is gradient-step vs covariance
    inversion."""

    def __init__(self, mu: float, normalized: bool = True):
        self.t = _factory()
        self.mu = mu
        self.normalized = normalized
        self.w = None
        self.g = None

    def _phi(self, x):
        return self.t.basis_matrix(x)

    def predistort(self, x):
        if self.w is None:
            return np.asarray(x, dtype=complex)
        return self._phi(x) @ self.w

    __call__ = predistort

    def update(self, pa, x):
        u = self.predistort(x)
        y = pa(u)
        if self.g is None:
            self.g = np.vdot(x, y) / np.vdot(x, x)
        phi = self._phi(y / self.g)
        if self.w is None:
            self.w = np.zeros(phi.shape[1], dtype=complex)
            self.w[0] = 1.0
        for n in range(phi.shape[0]):
            pn = phi[n]
            e = u[n] - pn @ self.w
            denom = (np.vdot(pn, pn).real + 1e-6) if self.normalized else 1.0
            self.w = self.w + self.mu * np.conj(pn) * e / denom
            if not np.all(np.isfinite(self.w)):
                return  # diverged


def evm_db(pa, sig, wf):
    y = pa(sig)
    if not np.all(np.isfinite(y)):
        return np.nan
    g = np.vdot(wf.x, y) / np.vdot(wf.x, wf.x)
    return evm(demodulate_ofdm(y / g, wf), wf.tx_symbols).db


def run(estimator, pa, blocks):
    """Per-block EVM: measure with the current DPD, then adapt."""
    curve = []
    for wf in blocks:
        curve.append(evm_db(pa, estimator(wf.x), wf))
        estimator.update(pa, wf.x)
    return curve


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    args = ap.parse_args()
    n_blocks = 6 if args.fast else 10

    cfg = OFDMConfig(bandwidth_hz=BW, qam_order=1024, n_symbols=6, seed=0)
    blocks = [generate_ofdm(replace(cfg, seed=s)) for s in range(n_blocks)]
    pa = ReferencePA(drive=0.13)

    runs = {
        "RLS": AdaptiveDPD(_factory, forget=0.98, ridge=1e-6),
        "NLMS (normalized, mu=0.7)": BlockNLMS(0.7, normalized=True),
        "LMS (plain, mu=3e-3)": BlockNLMS(3e-3, normalized=False),
    }
    curves = {name: run(est, pa, blocks) for name, est in runs.items()}

    print("online DPD estimators on an ill-conditioned GMP basis "
          "(static ReferencePA)")
    print(f"per-block linearization EVM (dB), {n_blocks} blocks:\n")
    hdr = "  ".join(f"b{i}" for i in range(n_blocks))
    print(f"{'estimator':<28} {hdr}")
    for name, c in curves.items():
        cells = "  ".join(f"{v:5.0f}" if np.isfinite(v) else "  NaN"
                          for v in c)
        print(f"{name:<28} {cells}", flush=True)
    rls = np.array(curves["RLS"])
    print(f"\nRLS reaches {np.nanmin(rls):.1f} dB EVM in "
          f"{int(np.nanargmin(rls))} block(s); NLMS plateaus well short "
          "and LMS diverges to NaN.")

    _plot(curves, n_blocks)


def _plot(curves, n_blocks):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = ROOT / "manual" / "assets" / "lms_vs_rls.png"
    colors = {"RLS": "#1f9d57",
              "NLMS (normalized, mu=0.7)": "#c9721f",
              "LMS (plain, mu=3e-3)": "#d3402f"}
    fig, ax = plt.subplots(figsize=(8.6, 4.6), dpi=100)
    fig.patch.set_facecolor("white")
    x = np.arange(n_blocks)
    for name, c in curves.items():
        c = np.array(c, dtype=float)
        finite = np.isfinite(c)
        ax.plot(x[finite], c[finite], "o-", lw=1.8, ms=5,
                color=colors[name], label=name)
        # mark the first diverged (NaN) block
        if not finite.all():
            k = int(np.argmax(~finite))
            ax.plot(k, CEILING, "x", ms=11, mew=2.6, color=colors[name])
            ax.annotate("diverges -> NaN", (k, CEILING),
                        textcoords="offset points", xytext=(10, -4),
                        color=colors[name], fontsize=9, weight="bold")
    ax.axhline(0, color="#9aa4bd", lw=0.8, ls=":")
    ax.set_xlabel("adaptation block")
    ax.set_ylabel("linearization EVM (dB)  —  lower is better")
    ax.set_title("Online DPD on the ill-conditioned GMP basis: "
                 "RLS vs LMS/NLMS")
    ax.set_ylim(-58, 8)
    ax.grid(True, alpha=0.4)
    ax.legend(loc="center right", fontsize=9, framealpha=0.95)
    fig.tight_layout()
    fig.savefig(out, dpi=100, facecolor="white")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
