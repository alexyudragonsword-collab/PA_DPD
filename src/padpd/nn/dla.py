"""Direct Learning Architecture (DLA) neural predistortion.

OpenDPD's protocol: freeze a differentiable PA model, put a neural DPD in
front, and train the cascade so that PA(DPD(x)) ~= G*x by backpropagating
THROUGH the frozen PA. This differs from classical ILA (padpd.dpd.ila),
which fits a post-inverse; both are provided so they can be compared.

The best checkpoint is selected on the validation split by ACLR_AVG
(OpenDPD convention) when the channel spec is provided, else by NMSE
against the linear target.
"""

from __future__ import annotations

import ast

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from ..metrics.opendpd_compat import aclr_opendpd
from ..pa.base import nmse_db
from .backbones import BACKBONES, count_params
from .features import complex_to_iq, iq_to_complex
from .frame_data import FrameDataset
from .torch_model import NeuralPAModel


class DLAPredistorter:
    def __init__(self, backbone: str = "dgru", hidden_size: int = 8,
                 num_layers: int = 1, frame_length: int = 50,
                 stride: int = 1, batch_size: int = 64,
                 n_epochs: int = 100, lr: float = 1e-3,
                 lr_end: float = 1e-6, decay_factor: float = 0.5,
                 patience: int = 10, grad_clip: float = 200.0,
                 val_fraction: float = 0.2, seed: int = 0,
                 target_gain: float | None = None,
                 aclr_spec: dict | None = None, verbose: bool = True):
        """``aclr_spec``: {"fs", "bw_main_ch", "n_sub_ch", "nperseg"} for
        ACLR-based checkpoint selection (pass the dataset's spec values).
        ``target_gain``: linearization target G (e.g. from
        ``target_gain_opendpd``); least-squares estimated if omitted.
        """
        self.config = {
            "backbone": backbone, "hidden_size": hidden_size,
            "num_layers": num_layers, "frame_length": frame_length,
            "stride": stride, "batch_size": batch_size,
            "n_epochs": n_epochs, "lr": lr, "lr_end": lr_end,
            "decay_factor": decay_factor, "patience": patience,
            "grad_clip": grad_clip, "val_fraction": val_fraction,
            "seed": seed,
        }
        self.target_gain = target_gain
        self.aclr_spec = aclr_spec
        self.verbose = verbose
        torch.manual_seed(seed)
        self.net = BACKBONES[backbone](hidden_size=hidden_size,
                                       num_layers=num_layers)
        self.history: list[dict] = []

    @property
    def n_params(self) -> int:
        return count_params(self.net)

    def _val_metric(self, pa: NeuralPAModel, x_val: np.ndarray) -> float:
        y = pa(self(x_val))
        if self.aclr_spec:
            s = self.aclr_spec
            return aclr_opendpd(y, s["fs"], s["bw_main_ch"], s["n_sub_ch"],
                                s["nperseg"])["avg_dbc"]
        return nmse_db(self.target_gain * x_val, y)

    def fit(self, pa: NeuralPAModel, x: np.ndarray,
            x_val: np.ndarray | None = None,
            on_epoch=None) -> DLAPredistorter:
        """Train the DPD against a frozen differentiable PA model.

        ``on_epoch``: optional callback receiving the per-epoch history
        dict - used by GUIs for live progress."""
        cfg = self.config
        if x_val is None:
            n = int(len(x) * (1 - cfg["val_fraction"]))
            x, x_val = x[:n], x[n:]

        if self.target_gain is None:
            y0 = pa(x)
            self.target_gain = float(np.abs(
                np.vdot(x, y0) / np.vdot(x, x)))

        pa_net = pa.as_tensor_fn()
        for p in pa_net.parameters():
            p.requires_grad = False
        pa_net.eval()

        target = self.target_gain * x
        loader = DataLoader(
            FrameDataset(x, target, cfg["frame_length"], cfg["stride"]),
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
                out = pa_net(self.net(feats))
                loss = criterion(out, targets)
                loss.backward()
                if cfg["grad_clip"]:
                    nn.utils.clip_grad_norm_(self.net.parameters(),
                                             cfg["grad_clip"])
                optimizer.step()
                losses.append(loss.item())

            metric = self._val_metric(pa, x_val)
            scheduler.step(metric)
            self.history.append({"epoch": epoch,
                                 "train_loss": float(np.mean(losses)),
                                 "val_metric": metric,
                                 "lr": optimizer.param_groups[0]["lr"]})
            if on_epoch is not None:
                on_epoch(self.history[-1])
            if metric < best_metric:
                best_metric = metric
                best_state = {k: v.detach().clone()
                              for k, v in self.net.state_dict().items()}
            if self.verbose and (epoch % 10 == 0
                                 or epoch == cfg["n_epochs"] - 1):
                name = "val ACLR" if self.aclr_spec else "val NMSE"
                print(f"epoch {epoch:3d}  loss {np.mean(losses):.3e}  "
                      f"{name} {metric:7.2f} dB  "
                      f"lr {optimizer.param_groups[0]['lr']:.1e}")

        if best_state is not None:
            self.net.load_state_dict(best_state)
        if self.verbose:
            print(f"best val metric: {best_metric:.2f} dB "
                  f"({self.n_params} params)")
        return self

    def __call__(self, x: np.ndarray) -> np.ndarray:
        self.net.eval()
        with torch.no_grad():
            out = self.net(complex_to_iq(x).unsqueeze(0))
        return iq_to_complex(out.squeeze(0))

    def linearize(self, pa, x: np.ndarray) -> np.ndarray:
        return pa(self(x))

    def save(self, path: str) -> None:
        torch.save({"config": repr(self.config),
                    "target_gain": self.target_gain,
                    "aclr_spec": repr(self.aclr_spec),
                    "state_dict": self.net.state_dict()}, path)

    @classmethod
    def load(cls, path: str) -> DLAPredistorter:
        d = torch.load(path, map_location="cpu", weights_only=False)
        dpd = cls(**ast.literal_eval(d["config"]), verbose=False)
        dpd.target_gain = d["target_gain"]
        dpd.aclr_spec = ast.literal_eval(str(d["aclr_spec"]))
        dpd.net.load_state_dict(d["state_dict"])
        return dpd
