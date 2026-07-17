"""NeuralPAModel: PyTorch PA behavioral model behind the padpd interface.

Training follows OpenDPD's recipe: sliding frames (frame_length, stride),
zero hidden state per frame, AdamW + MSE over the full frame, gradient
clipping, ReduceLROnPlateau on the validation metric, best model selected
by validation NMSE.

The public interface matches the classical models exactly (1-D complex
in/out, ``fit``/``__call__``/``save``), so metrics, ILA, and existing
scripts work unchanged.
"""

from __future__ import annotations

import ast

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from ..pa.base import PAModel, nmse_db
from .backbones import BACKBONES, count_params
from .features import complex_to_iq, iq_to_complex
from .frame_data import FrameDataset


class NeuralPAModel(PAModel):
    def __init__(self, backbone: str = "dgru", hidden_size: int = 8,
                 num_layers: int = 1, frame_length: int = 50,
                 stride: int = 1, batch_size: int = 64,
                 n_epochs: int = 100, lr: float = 1e-3,
                 lr_end: float = 1e-6, decay_factor: float = 0.5,
                 patience: int = 10, grad_clip: float = 200.0,
                 val_fraction: float = 0.2, seed: int = 0,
                 verbose: bool = True):
        if backbone not in BACKBONES:
            raise ValueError(f"backbone must be one of {list(BACKBONES)}")
        self.config = {
            "backbone": backbone, "hidden_size": hidden_size,
            "num_layers": num_layers, "frame_length": frame_length,
            "stride": stride, "batch_size": batch_size,
            "n_epochs": n_epochs, "lr": lr, "lr_end": lr_end,
            "decay_factor": decay_factor, "patience": patience,
            "grad_clip": grad_clip, "val_fraction": val_fraction,
            "seed": seed,
        }
        self.verbose = verbose
        torch.manual_seed(seed)
        self.net = BACKBONES[backbone](hidden_size=hidden_size,
                                       num_layers=num_layers)
        self.history: list[dict] = []

    @property
    def n_params(self) -> int:
        return count_params(self.net)

    # -- training -----------------------------------------------------------
    def fit(self, x: np.ndarray, y: np.ndarray,
            x_val: np.ndarray | None = None,
            y_val: np.ndarray | None = None) -> "NeuralPAModel":
        cfg = self.config
        if x_val is None:
            n = int(len(x) * (1 - cfg["val_fraction"]))
            x, x_val = x[:n], x[n:]
            y, y_val = y[:n], y[n:]

        loader = DataLoader(
            FrameDataset(x, y, cfg["frame_length"], cfg["stride"]),
            batch_size=cfg["batch_size"], shuffle=True, drop_last=False)
        optimizer = torch.optim.AdamW(self.net.parameters(), lr=cfg["lr"])
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", factor=cfg["decay_factor"],
            patience=cfg["patience"], threshold=1e-4, min_lr=cfg["lr_end"])
        criterion = nn.MSELoss()

        best_metric = np.inf
        best_state = None
        for epoch in range(cfg["n_epochs"]):
            self.net.train()
            losses = []
            for feats, targets in loader:
                optimizer.zero_grad()
                loss = criterion(self.net(feats), targets)
                loss.backward()
                if cfg["grad_clip"]:
                    nn.utils.clip_grad_norm_(self.net.parameters(),
                                             cfg["grad_clip"])
                optimizer.step()
                losses.append(loss.item())

            val_nmse = nmse_db(y_val, self(x_val))
            scheduler.step(val_nmse)
            self.history.append({"epoch": epoch,
                                 "train_loss": float(np.mean(losses)),
                                 "val_nmse_db": val_nmse,
                                 "lr": optimizer.param_groups[0]["lr"]})
            if val_nmse < best_metric:
                best_metric = val_nmse
                best_state = {k: v.detach().clone()
                              for k, v in self.net.state_dict().items()}
            if self.verbose and (epoch % 10 == 0
                                 or epoch == cfg["n_epochs"] - 1):
                print(f"epoch {epoch:3d}  loss {np.mean(losses):.3e}  "
                      f"val NMSE {val_nmse:7.2f} dB  "
                      f"lr {optimizer.param_groups[0]['lr']:.1e}")

        if best_state is not None:
            self.net.load_state_dict(best_state)
        if self.verbose:
            print(f"best val NMSE: {best_metric:.2f} dB "
                  f"({self.n_params} params)")
        return self

    # -- inference ----------------------------------------------------------
    def __call__(self, x: np.ndarray) -> np.ndarray:
        self.net.eval()
        with torch.no_grad():
            out = self.net(complex_to_iq(x).unsqueeze(0))
        return iq_to_complex(out.squeeze(0))

    def as_tensor_fn(self):
        """The underlying (B,T,2)->(B,T,2) network, for DLA cascading."""
        return self.net

    # -- persistence --------------------------------------------------------
    def save(self, path: str) -> None:
        torch.save({"config": repr(self.config),
                    "state_dict": self.net.state_dict()}, path)

    @classmethod
    def load(cls, path: str) -> "NeuralPAModel":
        d = torch.load(path, map_location="cpu", weights_only=False)
        model = cls(**ast.literal_eval(d["config"]), verbose=False)
        model.net.load_state_dict(d["state_dict"])
        return model
