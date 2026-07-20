"""Online DPD estimators on an ill-conditioned GMP basis: RLS, LMS/NLMS,
and the middle grounds that trade cost for accuracy.

The adaptive predistorter learns a linear-in-parameters GMP over |x|^k
regressors whose covariance is ill-conditioned (condition number ~1e10).
This script runs several online estimators from the same pass-through
start against the same static ReferencePA and reports per-block
linearization EVM, placing the "in between RLS and NLMS" options on the
same axis:

- **RLS** (``padpd.dpd.AdaptiveDPD``): inverts the covariance each block,
  O(N^2) -> reaches the least-squares floor in ~1 block, robust.
- **Whitened NLMS**: one-time Cholesky whitening of the warm-up
  covariance, then plain NLMS in the decorrelated domain -- an "amortized
  RLS": O(N^2) once, then O(N)/sample, and it converges as fast as RLS.
- **APA(K)** (affine projection): decorrelates over a K-sample window
  (a mini-RLS), O(N*K). K=1 is NLMS, larger K approaches RLS -- the
  classic tunable middle ground.
- **NLMS** (per-sample, power-normalized): O(N), survives but crawls and
  plateaus well short -- the ill-conditioned modes barely move.
- **LMS** (plain, un-normalized): O(N), diverges to NaN on block 1.

Note (reported honestly, not plotted to avoid clutter): naive *diagonal*
preconditioning -- normalizing each column by its own power -- also
diverges here, because it amplifies the weak, collinear high-order
columns. On this basis the killer is column *correlation*, not scale, so
only methods that use the off-diagonal covariance (whitening / APA / RLS)
survive. Writes the figure to ``manual/assets/lms_vs_rls.png``.

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
CEILING = 6.0   # plot cap for the diverging curve (dB)


def _factory():
    return GMPModel(order=7, memory_depth=4)


class _LinBase:
    def __init__(self):
        self.t = _factory()
        self.w = None
        self.g = None

    def _phi(self, x):
        return self.t.basis_matrix(x)

    def predistort(self, x):
        if self.w is None:
            return np.asarray(x, dtype=complex)
        return self._phi(x) @ self.w

    __call__ = predistort

    def _prep(self, pa, x):
        """Common post-inverse setup: regressors phi = basis(y/G), target u."""
        u = self.predistort(x)
        y = pa(u)
        if self.g is None:
            self.g = np.vdot(x, y) / np.vdot(x, x)
        phi = self._phi(y / self.g)
        if self.w is None:
            self.w = np.zeros(phi.shape[1], dtype=complex)
            self.w[0] = 1.0
        return u, phi


class BlockNLMS(_LinBase):
    """Per-sample (N)LMS on the same post-inverse regressors as RLS."""

    def __init__(self, mu: float, normalized: bool = True):
        super().__init__()
        self.mu = mu
        self.normalized = normalized

    def update(self, pa, x):
        u, phi = self._prep(pa, x)
        for n in range(phi.shape[0]):
            pn = phi[n]
            e = u[n] - pn @ self.w
            denom = (np.vdot(pn, pn).real + 1e-6) if self.normalized else 1.0
            self.w = self.w + self.mu * np.conj(pn) * e / denom
            if not np.all(np.isfinite(self.w)):
                return


class APA(_LinBase):
    """Affine projection: decorrelate over the last K regressor rows."""

    def __init__(self, K: int = 4, mu: float = 0.3, delta: float = 1e-3):
        super().__init__()
        self.K = K
        self.mu = mu
        self.delta = delta

    def update(self, pa, x):
        u, phi = self._prep(pa, x)
        K = self.K
        for n in range(K, phi.shape[0]):
            P = phi[n - K:n]                       # K x N window
            e = u[n - K:n] - P @ self.w
            gram = P @ P.conj().T + self.delta * np.eye(K)
            self.w = self.w + self.mu * P.conj().T @ np.linalg.solve(gram, e)
            if not np.all(np.isfinite(self.w)):
                return


class WhitenedNLMS(_LinBase):
    """One-time whitening (Cholesky of the warm-up covariance) then NLMS
    in the decorrelated domain: an amortized RLS."""

    def __init__(self, mu: float = 0.5, ridge: float = 1e-3):
        super().__init__()
        self.mu = mu
        self.ridge = ridge
        self.Linv = None

    def update(self, pa, x):
        u, phi = self._prep(pa, x)
        n_dim = phi.shape[1]
        if self.Linv is None:
            R = phi.conj().T @ phi / phi.shape[0]
            lam = self.ridge * np.trace(R).real / n_dim
            L = np.linalg.cholesky(R + lam * np.eye(n_dim))
            self.Linv = np.linalg.inv(L.conj().T)   # cov(phi @ Linv) ~ I
        Z = phi @ self.Linv
        v = np.linalg.solve(self.Linv, self.w)      # whitened-domain weights
        for n in range(Z.shape[0]):
            zn = Z[n]
            e = u[n] - zn @ v
            v = v + self.mu * np.conj(zn) * e / (np.vdot(zn, zn).real + 1e-6)
            if not np.all(np.isfinite(v)):
                self.w = self.Linv @ v
                return
        self.w = self.Linv @ v


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


# name -> (estimator, cost tag, plot color)
def _estimators():
    return {
        "RLS  (O(N^2)/block)":
            (AdaptiveDPD(_factory, forget=0.98, ridge=1e-6), "#1f9d57"),
        "whitened NLMS  (O(N^2) once, then O(N))":
            (WhitenedNLMS(mu=0.5), "#3b6fd4"),
        "APA K=4  (O(N*K))": (APA(K=4, mu=0.3), "#8a55e0"),
        "NLMS  (O(N))": (BlockNLMS(0.7, normalized=True), "#c9721f"),
        "LMS plain  (O(N))": (BlockNLMS(3e-3, normalized=False), "#d3402f"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    args = ap.parse_args()
    n_blocks = 6 if args.fast else 10

    cfg = OFDMConfig(bandwidth_hz=BW, qam_order=1024, n_symbols=6, seed=0)
    blocks = [generate_ofdm(replace(cfg, seed=s)) for s in range(n_blocks)]
    pa = ReferencePA(drive=0.13)

    ests = _estimators()
    curves = {name: run(est, pa, blocks) for name, (est, _) in ests.items()}

    print("online DPD estimators on an ill-conditioned GMP basis "
          "(static ReferencePA)")
    print(f"per-block linearization EVM (dB), {n_blocks} blocks:\n")
    hdr = "  ".join(f"b{i}" for i in range(n_blocks))
    print(f"{'estimator':<42} {hdr}")
    for name, c in curves.items():
        cells = "  ".join(f"{v:5.0f}" if np.isfinite(v) else "  NaN"
                          for v in c)
        print(f"{name:<42} {cells}", flush=True)
    print("\nmiddle grounds: whitened-NLMS matches RLS at O(N) per sample "
          "after a one-time O(N^2) whitening; APA(K) tunes cost vs speed "
          "between NLMS and RLS.")

    _plot(curves, ests, n_blocks)


def _plot(curves, ests, n_blocks):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = ROOT / "manual" / "assets" / "lms_vs_rls.png"
    fig, ax = plt.subplots(figsize=(9.2, 5.0), dpi=100)
    fig.patch.set_facecolor("white")
    x = np.arange(n_blocks)
    for name, (_, color) in ests.items():
        c = np.array(curves[name], dtype=float)
        finite = np.isfinite(c)
        ax.plot(x[finite], c[finite], "o-", lw=1.8, ms=5, color=color,
                label=name)
        if not finite.all():
            k = int(np.argmax(~finite))
            ax.plot(k, CEILING, "x", ms=11, mew=2.6, color=color)
            ax.annotate("diverges -> NaN", (k, CEILING),
                        textcoords="offset points", xytext=(10, -4),
                        color=color, fontsize=9, weight="bold")
    ax.axhline(0, color="#9aa4bd", lw=0.8, ls=":")
    ax.set_xlabel("adaptation block")
    ax.set_ylabel("linearization EVM (dB)  —  lower is better")
    ax.set_title("Online DPD on the ill-conditioned GMP basis: "
                 "RLS, NLMS, and the middle grounds")
    ax.set_ylim(-72, 10)
    ax.grid(True, alpha=0.4)
    ax.legend(loc="lower left", fontsize=8.5, framealpha=0.95, ncol=2)
    fig.tight_layout()
    fig.savefig(out, dpi=100, facecolor="white")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
