import torch
from torch import nn


class Swish(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, x: torch.tensor):
        return x * torch.sigmoid(x)
