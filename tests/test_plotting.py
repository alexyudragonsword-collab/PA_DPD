"""Smoke tests for padpd.plotting (previously untested).

Each figure function must save a nonempty file under the Agg backend —
these are the demo scripts' output path.
"""

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest

from padpd.plotting import (plot_am_curves, plot_ccdf,
                            plot_constellation, plot_psd_comparison)

RNG = np.random.default_rng(0)
X = (RNG.standard_normal(4096) + 1j * RNG.standard_normal(4096)) / 2 ** 0.5


@pytest.mark.parametrize("fn,args", [
    (plot_psd_comparison, ({"a": X, "b": 0.5 * X}, 100e6)),
    (plot_constellation, ({"a": X[:512]},)),
    (plot_ccdf, ({"a": X},)),
    (plot_am_curves, ({"a": (np.abs(X), np.abs(0.8 * X))},)),
])
def test_plot_saves_nonempty_file(tmp_path, fn, args):
    out = tmp_path / f"{fn.__name__}.png"
    fn(*args, path=str(out))
    assert out.exists() and out.stat().st_size > 1000
