"""Manual figure: spline knot placement + spline-vs-polynomial basis.

Produces manual/assets/spline_knots.png — left panel: an OFDM amplitude
histogram with uniform/quantile/hybrid knot ladders; right panel: the
cubic B-spline basis on the hybrid knots vs the collinear |x|^k powers
(the conditioning argument in one picture).

Run from the repo root:  python scripts/make_spline_figure.py
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from padpd.pa import bspline_design_matrix, place_knots  # noqa: E402
from padpd.waveform import OFDMConfig, generate_ofdm  # noqa: E402

OUT = ROOT / "manual" / "assets" / "spline_knots.png"


def main() -> None:
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                  n_symbols=8, seed=0))
    amps = np.abs(wf.x)
    r_max = float(amps.max())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.0))

    ax1.hist(amps, bins=120, density=True, color="#4C72B0", alpha=0.55,
             label="|x| distribution (OFDM)")
    styles = {"uniform": ("#DD8452", 1.00),
              "quantile": ("#55A868", 0.80),
              "hybrid": ("#C44E52", 0.60)}
    for name, (color, yy) in styles.items():
        ks = place_knots(amps, n_knots=8, placement=name)
        y0 = ax1.get_ylim()[1] * yy
        ax1.plot(ks, [y0] * len(ks), "|", ms=16, mew=2.2, color=color,
                 label=f"{name} knots")
    ax1.set_xlabel("amplitude r")
    ax1.set_ylabel("density")
    ax1.set_title("Knot placement: resolution where data and\n"
                  "compression actually are")
    ax1.legend(fontsize=8, loc="center right")

    ks = place_knots(amps, n_knots=8, placement="hybrid")
    r = np.linspace(0, r_max, 600)
    basis = bspline_design_matrix(r, ks, 3)
    for j in range(basis.shape[1]):
        ax2.plot(r, basis[:, j], color="#4C72B0", lw=1.4,
                 label="cubic B-splines (4 active)" if j == 0 else None)
    for k in (1, 3, 5, 7):
        ax2.plot(r, (r / r_max) ** k, "--", color="#C44E52", lw=1.2,
                 label=r"$r^k$ powers (collinear)" if k == 1 else None)
    ax2.set_xlabel("amplitude r")
    ax2.set_ylabel("basis value")
    ax2.set_title("Local B-spline basis vs global polynomial\n"
                  "powers: the conditioning difference")
    ax2.legend(fontsize=8)

    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
