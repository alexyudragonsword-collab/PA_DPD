"""Complete measured-source container: round-trip, capture-based
consumers, and the committed demo file end to end."""

import numpy as np
import pytest

from gui_core import services
from padpd.data import (IQDataset, extras_summary, load_complete_npz,
                        save_complete_npz)
from padpd.gain_modulation import (identify_gain_modulation_capture,
                                   step_probe_drive)


def test_roundtrip_all_groups(tmp_path):
    rng = np.random.default_rng(0)
    n = 512

    def sig():
        return (rng.standard_normal(n) + 1j * rng.standard_normal(n))

    p = str(tmp_path / "c.npz")
    save_complete_npz(p, sig(), sig(), 100e6,
                      burst=(sig(), sig()), step=(sig(), sig()),
                      cal_rx=(sig(), sig()),
                      atten=(sig(), sig(), sig(), 6.0),
                      operating_points=([0.0, 1.0],
                                        [(sig(), sig()), (sig(), sig())]),
                      meta={"reference_plane": "pa_output"})
    c = load_complete_npz(p)
    assert c["fs"] == 100e6
    assert c["meta"]["reference_plane"] == "pa_output"
    assert set(c["extras"]) == {"burst", "step", "cal_rx", "atten",
                                "operating_points"}
    assert c["extras"]["atten"]["step_db"] == 6.0
    assert len(c["extras"]["operating_points"]["pairs"]) == 2
    rows = extras_summary(c["extras"])
    assert all(r["present"] for r in rows)
    # complex64 storage round-trips to ~1e-7
    x2 = np.asarray(c["x"])
    assert x2.dtype == complex and len(x2) == n
    # the container is a valid plain IQDataset npz too
    ds = IQDataset.load(p)
    assert len(ds) == n and ds.sample_rate_hz == 100e6


def test_roundtrip_validation(tmp_path):
    p = str(tmp_path / "bad.npz")
    a = np.ones(128, dtype=complex)
    with pytest.raises(ValueError):
        save_complete_npz(p, a, a[:64], 1e6)          # length mismatch
    with pytest.raises(ValueError):
        save_complete_npz(p, a, a, 1e6, burst=(a, a[:64]))
    with pytest.raises(ValueError):
        save_complete_npz(p, a, a, 1e6,
                          operating_points=([0.0], [(a, a)]))
    # plain dataset npz -> degenerate load, no extras
    IQDataset(a, a, 1e6).save(p)
    c = load_complete_npz(p)
    assert c["extras"] == {}
    assert extras_summary(c["extras"]) and \
        not any(r["present"] for r in extras_summary(c["extras"]))


def test_capture_identification_rejects_stepless():
    x = np.ones(4096, dtype=complex)
    with pytest.raises(ValueError):
        identify_gain_modulation_capture(x, x, 1e6)


def test_step_probe_drive_shape():
    fs = 80e6
    xs = step_probe_drive(fs, t_obs_s=1e-4)
    lev = np.abs(xs)
    assert lev.max() == 1.5 and lev.min() == pytest.approx(1.5 * 0.35)
    # four constant-envelope segments: ref, settle, heat, cool
    changes = np.flatnonzero(np.abs(np.diff(lev)) > 0.01)
    assert len(changes) == 3


@pytest.fixture(scope="module")
def demo_src():
    return services.load_source("npz", services.EXAMPLE_COMPLETE_NPZ)


def test_demo_file_loads_with_all_groups(demo_src):
    rows = services.source_extras_rows(demo_src)
    assert all(r["present"] for r in rows)
    assert demo_src["fs"] == pytest.approx(80e6)


def test_demo_offline_tau_identification(demo_src):
    """The recorded step probe recovers the thermal DUT's ground-truth
    taus (5/30 us) offline."""
    gm = services.identify_gain_mod_from_source(demo_src)
    assert gm["significant"]
    assert abs(gm["taus_heat_us"][0] - 5.0) < 1.5
    assert abs(gm["taus_heat_us"][1] - 30.0) < 6.0


def test_demo_state_spline_from_burst(demo_src):
    """Identified alphas + burst capture -> real state-spline gain
    (measured +8.5 dB; full-capture prediction, tail-scored)."""
    st = services.fit_state_spline_from_source(demo_src)
    assert st["state_gain_db"] > 5.0


def test_demo_rx_calibrations(demo_src):
    de, info = services.deembedder_from_source(demo_src)
    assert de is not None
    assert abs(info["cal_rx"]["rx_irr_db"] - 30.06) < 1.0
    assert abs(info["atten"]["rx_im3_dbc"] - (-28.0)) < 2.0


def test_demo_scheduler(demo_src):
    sc = services.scheduler_from_source(demo_src)
    assert sc["conditions"] == [0.0, 0.5, 1.0]
    assert all(v < -40.0 for v in sc["nmse_per_point_db"])


def test_consume_source_extras_summary(demo_src):
    out = services.consume_source_extras(demo_src)
    assert {"gain_mod", "state_fit", "deembed", "scheduler"} <= set(out)
    assert not [k for k in out if k.endswith("_error")]


def test_plain_source_has_no_extras(tmp_path):
    a = (np.random.default_rng(1).standard_normal(2048)
         + 0j)
    p = str(tmp_path / "plain.npz")
    IQDataset(a, a, 1e6).save(p)
    src = services.load_source("npz", p)
    assert src["extras"] == {}
    assert services.identify_gain_mod_from_source(src) is None
    assert services.fit_state_spline_from_source(src) is None
    assert services.deembedder_from_source(src) == (None, {})
    assert services.scheduler_from_source(src) is None
