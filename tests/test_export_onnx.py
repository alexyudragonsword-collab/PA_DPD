import numpy as np
import pytest

torch = pytest.importorskip("torch")

from padpd.deploy import export_onnx
from padpd.nn import NeuralPAModel
from padpd.pa import ReferencePA
from padpd.waveform import OFDMConfig, generate_ofdm


def test_export_onnx_tcn(tmp_path):
    cfg = OFDMConfig(bandwidth_hz=20e6, qam_order=256, n_symbols=4, seed=1)
    x = generate_ofdm(cfg).x
    model = NeuralPAModel(backbone="tcn", hidden_size=16, n_epochs=3,
                          verbose=False, seed=0).fit(x, ReferencePA()(x))
    p = str(tmp_path / "tcn.onnx")
    res = export_onnx(model, p, frame_length=64)
    assert res["path"] == p
    # onnxruntime is installed in CI/dev, so verification should pass
    if "max_abs_err" in res:
        assert res["verified"]
        assert res["max_abs_err"] < 1e-4
