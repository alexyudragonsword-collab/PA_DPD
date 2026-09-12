"""Cadence capture directory -> complete-source npz packing."""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src"), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from pack_cadence_source import (  # noqa: E402
    PackError,
    pack_cadence_dir,
    read_capture,
)

from padpd.data import load_complete_npz  # noqa: E402

FS = 80e6


def _write(d: Path, name: str, x, y, fs: float = FS):
    t = np.arange(len(x)) / fs
    rows = np.column_stack([t, np.real(x), np.imag(x),
                            np.real(y), np.imag(y)])
    with open(d / f"{name}.csv", "w") as f:
        f.write("time,i_in,q_in,i_out,q_out\n")
        np.savetxt(f, rows, delimiter=",", fmt="%.9g")


@pytest.fixture()
def capture_dir(tmp_path):
    """A full capture set with known relative levels."""
    rng = np.random.default_rng(0)
    n = 512

    def sig(scale=1.0):
        return scale * (rng.standard_normal(n) + 1j * rng.standard_normal(n))

    d = tmp_path / "caps"
    d.mkdir()
    x = sig(2.0)                       # rms ~ 2*sqrt(2), tests the scaling
    _write(d, "main", x, 0.9 * x)
    _write(d, "burst", sig(), sig())
    _write(d, "step", sig(), sig())
    _write(d, "cal_rx", sig(0.1), sig(0.1))
    xa = sig()
    ya = 0.8 * xa
    _write(d, "atten_hi", xa, ya)
    _write(d, "atten_lo", xa, 10 ** (-6.0 / 20) * ya)
    for c in (25, 55, 85):
        _write(d, f"op_{c}", sig(), sig())
    return d


def test_pack_all_groups(capture_dir, tmp_path):
    out = tmp_path / "packed.npz"
    rep = pack_cadence_dir(capture_dir, out, atten_step_db=6.0,
                           meta={"corner": "tt"}, verbose=False)
    assert rep["fs"] == pytest.approx(FS)
    assert all(r["present"] for r in rep["checklist"])
    assert rep["op_conditions"] == [25.0, 55.0, 85.0]

    c = load_complete_npz(str(out))
    assert set(c["extras"]) == {"burst", "step", "cal_rx", "atten",
                                "operating_points"}
    assert c["meta"]["corner"] == "tt"
    assert c["meta"]["source"] == "cadence_envelope"
    assert c["meta"]["atten_step_db"] == 6.0
    # main drive normalized to unit rms, scale recoverable from meta
    assert np.sqrt(np.mean(np.abs(c["x"]) ** 2)) == pytest.approx(1.0,
                                                                  rel=1e-6)
    assert c["meta"]["norm_scale"] == pytest.approx(
        1.0 / np.sqrt(np.mean(np.abs(read_capture(
            capture_dir / "main.csv")[0]) ** 2)))


def test_one_common_scale_preserves_relative_levels(capture_dir, tmp_path):
    """The attenuator pair's 6 dB step is the whole point of that group —
    per-capture normalization would erase it."""
    out = tmp_path / "packed.npz"
    pack_cadence_dir(capture_dir, out, atten_step_db=6.0, verbose=False)
    a = load_complete_npz(str(out))["extras"]["atten"]
    step = 20 * np.log10(np.sqrt(np.mean(np.abs(a["hi"]) ** 2))
                         / np.sqrt(np.mean(np.abs(a["lo"]) ** 2)))
    assert step == pytest.approx(6.0, abs=0.01)


def test_dry_run_writes_nothing(capture_dir, tmp_path):
    out = tmp_path / "nope.npz"
    rep = pack_cadence_dir(capture_dir, None, atten_step_db=6.0,
                           verbose=False)
    assert "out" not in rep and not out.exists()


def test_main_only_is_valid(tmp_path):
    d = tmp_path / "min"
    d.mkdir()
    a = np.ones(128, dtype=complex)
    _write(d, "main", a, 0.5 * a)
    out = tmp_path / "m.npz"
    rep = pack_cadence_dir(d, out, verbose=False)
    assert not any(r["present"] for r in rep["checklist"])
    assert load_complete_npz(str(out))["extras"] == {}


def test_error_paths(capture_dir, tmp_path):
    with pytest.raises(PackError, match="atten-step-db"):
        pack_cadence_dir(capture_dir, None, verbose=False)

    (capture_dir / "atten_lo.csv").unlink()
    with pytest.raises(PackError, match="BOTH"):
        pack_cadence_dir(capture_dir, None, atten_step_db=6.0,
                         verbose=False)

    d2 = tmp_path / "fsbad"
    d2.mkdir()
    a = np.ones(128, dtype=complex)
    _write(d2, "main", a, a)
    _write(d2, "burst", a, a, fs=2 * FS)
    with pytest.raises(PackError, match="sample rate"):
        pack_cadence_dir(d2, None, verbose=False)

    d3 = tmp_path / "nomain"
    d3.mkdir()
    _write(d3, "burst", a, a)
    with pytest.raises(PackError, match="main.csv not found"):
        pack_cadence_dir(d3, None, verbose=False)


def test_non_uniform_time_column(tmp_path):
    d = tmp_path / "jitter"
    d.mkdir()
    t = np.cumsum(np.random.default_rng(0).uniform(0.5, 1.5, 128)) / FS
    rows = np.column_stack([t, np.ones(128), np.zeros(128),
                            np.ones(128), np.zeros(128)])
    with open(d / "main.csv", "w") as f:
        f.write("time,i_in,q_in,i_out,q_out\n")
        np.savetxt(f, rows, delimiter=",", fmt="%.9g")
    with pytest.raises(PackError, match="uniformly"):
        pack_cadence_dir(d, None, verbose=False)


def test_single_operating_point_dropped_with_warning(tmp_path):
    d = tmp_path / "oneop"
    d.mkdir()
    a = np.ones(128, dtype=complex)
    _write(d, "main", a, a)
    _write(d, "op_25", a, a)
    rep = pack_cadence_dir(d, None, verbose=False)
    assert any(">= 2 operating points" in w for w in rep["warnings"])
    assert not [r for r in rep["checklist"]
                if r["group"] == "operating_points" and r["present"]]
