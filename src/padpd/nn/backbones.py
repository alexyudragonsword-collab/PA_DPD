"""Neural backbones for PA/DPD modeling, structurally matching OpenDPD.

GRUBackbone : raw (I,Q) -> nn.GRU -> Linear -> (I,Q)
DGRUBackbone: 6 engineered features -> nn.GRU -> ReLU(Linear) ->
              concat(features) -> Linear -> (I,Q)   (OpenDPD v1 best)

Hidden state is zero-initialized per forward call (per frame), as in
OpenDPD's CoreModel.
"""

from __future__ import annotations

import torch
from torch import nn

from .features import iq_features


def count_params(net: nn.Module) -> int:
    return sum(p.numel() for p in net.parameters())


def _init_gru(rnn: nn.GRU, hidden_size: int) -> None:
    for name, param in rnn.named_parameters():
        num_gates = param.shape[0] // hidden_size
        if "bias" in name:
            nn.init.constant_(param, 0)
        if "weight" in name:
            for i in range(num_gates):
                nn.init.orthogonal_(
                    param[i * hidden_size:(i + 1) * hidden_size, :])
        if "weight_ih_l0" in name:
            for i in range(num_gates):
                nn.init.xavier_uniform_(
                    param[i * hidden_size:(i + 1) * hidden_size, :])


def _init_linear(fc: nn.Linear, kind: str = "xavier") -> None:
    if kind == "xavier":
        nn.init.xavier_uniform_(fc.weight)
    else:
        nn.init.kaiming_uniform_(fc.weight)
    if fc.bias is not None:
        nn.init.constant_(fc.bias, 0)


class GRUBackbone(nn.Module):
    def __init__(self, hidden_size: int = 11, num_layers: int = 1):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.rnn = nn.GRU(input_size=2, hidden_size=hidden_size,
                          num_layers=num_layers, batch_first=True)
        self.fc_out = nn.Linear(hidden_size, 2)
        _init_gru(self.rnn, hidden_size)
        _init_linear(self.fc_out)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h_0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size,
                          device=x.device)
        out, _ = self.rnn(x, h_0)
        return self.fc_out(out)


class DGRUBackbone(nn.Module):
    def __init__(self, hidden_size: int = 8, num_layers: int = 1):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.rnn = nn.GRU(input_size=6, hidden_size=hidden_size,
                          num_layers=num_layers, batch_first=True)
        self.fc_hid = nn.Linear(hidden_size, hidden_size)
        self.fc_out = nn.Linear(hidden_size + 6, 2)
        _init_gru(self.rnn, hidden_size)
        _init_linear(self.fc_hid, kind="kaiming")
        _init_linear(self.fc_out)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feats = iq_features(x)
        h_0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size,
                          device=x.device)
        out, _ = self.rnn(feats, h_0)
        out = torch.relu(self.fc_hid(out))
        out = torch.cat((out, feats), dim=-1)
        return self.fc_out(out)


BACKBONES = {"gru": GRUBackbone, "dgru": DGRUBackbone}
