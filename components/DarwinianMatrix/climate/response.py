"""Continuous climate-response primitives.

Digits enter as scalar parameters. They are not semantic commands.
"""

from __future__ import annotations

import torch
from torch import Tensor

from ..geometry import directed_transition_id


def optimum(grid_value: Tensor) -> Tensor:
    """Map Grid81 values 1..9 monotonically into 0..1."""
    return (grid_value.float() - 1.0) / 8.0


def capacity(
    grid_value: Tensor,
    k_min: float = 0.35,
    k_max: float = 1.0,
) -> Tensor:
    """Non-monotonic carrying capacity peaked near climate value five."""
    distance = (grid_value.float() - 5.0).abs() / 4.0
    return k_min + (k_max - k_min) * (
        1.0 - distance.pow(2)
    )


def transition_id(previous: Tensor, current: Tensor) -> Tensor:
    """Encode directed transitions into the exact domain 0..80."""
    return directed_transition_id(previous, current)


def shock(
    previous: Tensor,
    current: Tensor,
    age: Tensor,
    tau: float = 6.0,
) -> Tensor:
    """Return a directed, exponentially decaying climate-shift pulse."""
    if tau <= 0:
        raise ValueError("tau must be positive.")

    delta = (current.float() - previous.float()) / 8.0
    return delta * torch.exp(-age.float() / tau)
