"""QAT vs PTQ across bit widths on a neural PA model.

Trains a small TCN PA model, then compares, at each bit width, plain
post-training quantization against quantization-aware fine-tuning
followed by the same PTQ. QAT recovers the accuracy PTQ loses at low
bit widths.

Usage:  python scripts/run_qat_demo.py [--fast]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from padpd.deploy.neural_ptq import quantize_neural_ptq
from padpd.deploy.qat import quantize_aware_finetune
from padpd.nn.torch_model import NeuralPAModel, nmse_db
from padpd.pa import ReferencePA
from padpd.waveform import OFDMConfig, generate_ofdm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    args = ap.parse_args()

    epochs = 25 if args.fast else 60
    wf = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                  n_symbols=6, seed=0))
    wf_v = generate_ofdm(OFDMConfig(bandwidth_hz=80e6, qam_order=1024,
                                    n_symbols=6, seed=1))
    pa = ReferencePA(drive=0.14)
    x, y = wf.x, pa(wf.x)
    xv, yv = wf_v.x, pa(wf_v.x)

    model = NeuralPAModel(backbone="tcn", hidden_size=8, n_epochs=epochs,
                          frame_length=50, seed=0)
    model.fit(x, y)
    float_nmse = nmse_db(yv, model(xv))
    print(f"float TCN-H8: NMSE {float_nmse:.1f} dB ({model.n_params} params)\n")

    print(f"{'bits':>5} {'PTQ':>8} {'QAT+PTQ':>9} {'gain':>7}")
    print("-" * 32)
    for w_bits in (10, 8, 7, 6):
        ptq = quantize_neural_ptq(model, w_bits=w_bits)
        ptq_nmse = nmse_db(yv, ptq(xv))
        qat = quantize_aware_finetune(model, x, y, w_bits=w_bits,
                                      epochs=epochs // 2, lr=5e-4)
        qat_nmse = nmse_db(yv, quantize_neural_ptq(qat, w_bits=w_bits)(xv))
        print(f"W{w_bits:>3} {ptq_nmse:>8.1f} {qat_nmse:>9.1f} "
              f"{ptq_nmse - qat_nmse:>+6.1f}", flush=True)


if __name__ == "__main__":
    main()
