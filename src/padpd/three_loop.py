"""Three-loop joint operation: QMC + observation de-embedding + DPD.

Each dedicated loop was validated in isolation (padpd.dpd.qmc,
padpd.data.deembed, padpd.dpd.adaptive). A product runs them
*simultaneously* against a PA that drifts underneath: the division of
labor only holds up if the loops stay stable while coupled through the
same loopback. :func:`run_three_loop` is that system experiment:

    TX chain:    x -> adaptive DPD -> QMC pre-inverse -> TX front end
                 (I/Q image + LO leakage) -> drifting PA -> on air
    observation: coupler -> LoopbackChannel (delay, CFO, phase noise,
                 RX I/Q, ripple, noise) -> ObservationDeembedder
    loops/block: de-embed the capture, update QMC (b, c) from the
                 residual's conj/DC projections, update the RLS DPD
                 around the QMC-corrected front end.

Roles that make the coupling stable (each loop owns one mechanism and
is blind to the others'):

- the de-embedder's RX widely-linear + FIR stages come from a PA-BYPASS
  calibration (``calibrate_rx_path``), so the *TX* image survives in
  the corrected observation — exactly what the QMC loop must see;
- QMC owns the TX image and LO leakage (exact pre-inverse, no
  structural ceiling), so the DPD basis stays purely phase-equivariant;
- the DPD owns the PA nonlinearity and, through RLS forgetting, its
  drift; PA distortion projects onto none of the other loops' terms.

Three configurations run over the same drift trajectory to isolate
each loop's contribution: adapting from the raw loopback (broken),
de-embedding without QMC (drift tracked, EVM pinned at the TX IRR),
and all three loops (pinned floor broken).
"""

from __future__ import annotations

import numpy as np

from .data.align import align_delay
from .data.deembed import ObservationDeembedder
from .dpd.adaptive import AdaptiveDPD
from .dpd.qmc import QMCCorrector
from .loopback import LoopbackChannel
from .metrics import evm
from .pa import DriftingReferencePA, TxFrontEndPA
from .pa.gmp import GMPModel
from .waveform import OFDMConfig, demodulate_ofdm, generate_ofdm

# observation-path impairments used by the demo (the validated set from
# tests/test_deembed.py plus the calibratable in-band ripple)
DEFAULT_CHANNEL = dict(iq_gain_imbalance_db=0.3, iq_phase_imbalance_deg=3.0,
                       lo_leakage_dbc=-40.0, cfo_hz=8e3,
                       phase_noise_rms_deg=1.0, ripple_db=1.0,
                       gd_ripple_ns=2.0, delay_samples=7.3, snr_db=45.0)


def rx_evm_db(wf, y: np.ndarray) -> float:
    """Receiver-style EVM: timing sync before demodulation, scalar EQ."""
    _, y_a, _ = align_delay(wf.x, y)
    if len(y_a) < len(wf.x):
        y_a = np.concatenate([y_a, np.zeros(len(wf.x) - len(y_a),
                                            dtype=complex)])
    return float(evm(demodulate_ofdm(y_a, wf), wf.tx_symbols).db)


def _observed(de: ObservationDeembedder, channel: LoopbackChannel,
              fs: float, y_air: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """One de-embedded loopback capture, padded back to len(ref)."""
    r, y, _ = de.process(ref, channel(y_air, fs))
    if len(y) < len(ref):
        y = np.concatenate([y, np.zeros(len(ref) - len(y), dtype=complex)])
    return y


def run_three_loop(n_blocks: int = 12, drift_span: float = 0.02,
                   drive0: float = 0.13, gain_db: float = 0.3,
                   phase_deg: float = 3.0, lo_leakage_dbc: float = -35.0,
                   bw: float = 80e6, qam: int = 1024, n_symbols: int = 6,
                   forget: float = 0.6, warm_blocks: int = 6,
                   channel_kwargs: dict | None = None, seed: int = 0,
                   on_block=None) -> dict:
    """Run the three-loop system experiment; returns per-block traces.

    Modes (same drift trajectory, same waveform blocks):

    - ``raw``: adaptive RLS DPD fed the RAW loopback capture;
    - ``deembed``: DPD fed the de-embedded capture, no QMC;
    - ``full``: de-embed + QMC slow loop + adaptive DPD.

    The reported EVM is always measured ON AIR (the true front-end
    output, receiver-style sync) — the observation path corrupts only
    what the loops learn from, and that is the point.
    """
    if n_blocks < 2:
        raise ValueError("n_blocks must be >= 2")
    blocks = [generate_ofdm(OFDMConfig(bandwidth_hz=bw, qam_order=qam,
                                       n_symbols=n_symbols, seed=seed + s))
              for s in range(n_blocks)]
    fs = blocks[0].sample_rate_hz
    ch_kwargs = dict(DEFAULT_CHANNEL if channel_kwargs is None
                     else channel_kwargs)
    ch_kwargs.setdefault("seed", seed)
    channel = LoopbackChannel(**ch_kwargs)

    # RX-path calibration: one PA-bypass capture (same receiver)
    wf_cal = generate_ofdm(OFDMConfig(bandwidth_hz=bw, qam_order=qam,
                                      n_symbols=n_symbols, seed=seed + 977))
    de = ObservationDeembedder()
    de.calibrate_rx_path(wf_cal.x, channel(wf_cal.x, fs))

    def make_frontend():
        drift = DriftingReferencePA(drive0=drive0, drive_span=drift_span,
                                    beta_a_span=0.2, alpha_p_span=0.5)
        drift.set_state(0.0)
        return drift, TxFrontEndPA(drift, gain_db=gain_db,
                                   phase_deg=phase_deg,
                                   lo_leakage_dbc=lo_leakage_dbc, seed=seed)

    def factory():
        return GMPModel(order=7, memory_depth=4)

    res: dict = {"blocks": list(range(n_blocks)), "states": [],
                 "evm_raw": [], "evm_deembed": [], "evm_full": [],
                 "image_dbc": [], "dc_dbc": []}

    # ---- mode setups (each with its own front end + DPD state) -------
    drift_a, fe_a = make_frontend()
    adapt_a = AdaptiveDPD(factory, forget=forget)

    drift_b, fe_b = make_frontend()
    adapt_b = AdaptiveDPD(factory, forget=forget)
    pa_b = de.wrap(fe_b, channel, fs)

    drift_c, fe_c = make_frontend()
    adapt_c = AdaptiveDPD(factory, forget=forget)
    qmc = QMCCorrector()
    pa_c = de.wrap(lambda u: fe_c(qmc.precorrect(u)), channel, fs)

    for w in (fe_a, fe_b, fe_c):        # freeze the LO-leakage level
        w(blocks[0].x)

    for adapt, pa_obs in ((adapt_a, lambda u: channel(fe_a(u), fs)),
                          (adapt_b, pa_b), (adapt_c, pa_c)):
        adapt.warm_start(pa_obs, blocks[0].x, blocks=warm_blocks)

    # ---- drift trajectory --------------------------------------------
    for i, wf in enumerate(blocks):
        state = i / (n_blocks - 1)
        for d in (drift_a, drift_b, drift_c):
            d.set_state(state)
        x = wf.x

        res["evm_raw"].append(rx_evm_db(wf, fe_a(adapt_a(x))))
        res["evm_deembed"].append(rx_evm_db(wf, fe_b(adapt_b(x))))
        u_c = qmc.precorrect(adapt_c(x))
        y_air = fe_c(u_c)
        res["evm_full"].append(rx_evm_db(wf, y_air))
        res["states"].append(state)

        # loop updates from this block's loopback
        adapt_a.update(lambda u: channel(fe_a(u), fs), x)
        adapt_b.update(pa_b, x)
        q = qmc.update(x, _observed(de, channel, fs, y_air, u_c))
        res["image_dbc"].append(q["image_dbc"])
        res["dc_dbc"].append(q["dc_dbc"])
        adapt_c.update(pa_c, x)

        if on_block is not None:
            on_block({"block": i, "state": state,
                      "evm_raw": res["evm_raw"][-1],
                      "evm_deembed": res["evm_deembed"][-1],
                      "evm_full": res["evm_full"][-1],
                      "image_dbc": q["image_dbc"]})

    res.update({
        "final_raw": res["evm_raw"][-1],
        "final_deembed": res["evm_deembed"][-1],
        "final_full": res["evm_full"][-1],
        "final_image_dbc": res["image_dbc"][-1],
        "qmc_irr_db": qmc.irr_db,
        "n_coeffs": adapt_c.n_coeffs,
        # echo run parameters for run records
        "n_blocks": n_blocks, "drift_span": drift_span, "drive0": drive0,
        "gain_db": gain_db, "phase_deg": phase_deg,
        "lo_leakage_dbc": lo_leakage_dbc, "bw": bw, "forget": forget,
    })
    return res
