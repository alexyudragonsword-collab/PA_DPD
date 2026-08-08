"""Three-loop joint operation: stability and division of labor.

Small-config version of scripts/run_three_loop_demo.py (official
12-block run: raw +33 dB / de-embed-only -29.3 / three loops -35.1 on
the hot PA, image sustained below -60 dBc under drift).
"""

import numpy as np
import pytest

from padpd.pa.iq import irr_db
from padpd.three_loop import run_three_loop


@pytest.fixture(scope="module")
def result():
    return run_three_loop(n_blocks=5, n_symbols=4)


def test_raw_loopback_breaks_dpd(result):
    """Adapting from the uncorrected loopback never recovers."""
    assert min(result["evm_raw"]) > -10.0


def test_deembed_only_pins_at_tx_irr(result):
    """De-embedding rescues adaptation but the phase-equivariant DPD
    cannot touch the TX image: EVM pinned near the IRR (~30 dB)."""
    pinned = result["evm_deembed"][1:]
    assert max(pinned) < -25.0
    assert min(pinned) > -33.0


def test_three_loops_break_the_pin_and_track_drift(result):
    """With QMC owning image/DC, the coupled system beats the pinned
    floor on every post-convergence block and stays stable to full
    drift."""
    full = np.array(result["evm_full"][1:])
    deembed = np.array(result["evm_deembed"][1:])
    assert np.all(full < deembed - 2.0)
    assert result["final_full"] < result["final_deembed"] - 3.0
    assert min(result["evm_full"]) < -36.0


def test_qmc_converges_inside_the_coupled_system(result):
    """The slow loop reads the front end's ground truth while the DPD
    and de-embedder run around it."""
    assert result["image_dbc"][-1] < -50.0
    assert result["dc_dbc"][-1] < -55.0
    truth = irr_db(result["gain_db"], result["phase_deg"])
    assert abs(result["qmc_irr_db"] - truth) < 1.5
