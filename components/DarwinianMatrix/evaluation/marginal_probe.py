"""Climate-marginal and arrangement-sensitivity qualification.

A solved Sudoku fixes global digit counts but leaves their spatial arrangement
variable. This module distinguishes quantities fixed by those marginals from
quantities that depend on arrangement.

It does not call the TRM and does not mutate ecological state.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping

import torch
from torch import Tensor

from ..climate.response import capacity, optimum
from ..ecology.engine import EcologyState
from ..geometry import (
    GRID_CELLS,
    GRID_SIDE,
    MATRIX_CELLS,
    build_region_map,
    require_solved_grid81,
)


@dataclass(frozen=True)
class ClimateMarginals:
    digit_counts: tuple[int, ...]
    digit_sum: int
    optimum_sum: float
    capacity_sum: float

    def canonical_payload(self) -> dict[str, object]:
        return {
            "capacity_sum": self.capacity_sum,
            "digit_counts": list(self.digit_counts),
            "digit_sum": self.digit_sum,
            "optimum_sum": self.optimum_sum,
        }


@dataclass(frozen=True)
class EdgeMetrics:
    edge_count: int
    zero_gradient_edges: int
    total_abs_gradient: float
    mean_abs_gradient: float
    mean_permeability: float

    def canonical_payload(self) -> dict[str, object]:
        return {
            "edge_count": self.edge_count,
            "mean_abs_gradient": self.mean_abs_gradient,
            "mean_permeability": self.mean_permeability,
            "total_abs_gradient": self.total_abs_gradient,
            "zero_gradient_edges": self.zero_gradient_edges,
        }


@dataclass(frozen=True)
class ArrangementProbeRecord:
    arrangement_id: str
    grid_digest: str
    marginals: ClimateMarginals
    orthogonal_edges: EdgeMetrics
    diagonal_edges: EdgeMetrics
    instantaneous_suitability: float

    def canonical_payload(self) -> dict[str, object]:
        return {
            "arrangement_id": self.arrangement_id,
            "diagonal_edges": self.diagonal_edges.canonical_payload(),
            "grid_digest": self.grid_digest,
            "instantaneous_suitability": self.instantaneous_suitability,
            "marginals": self.marginals.canonical_payload(),
            "orthogonal_edges": self.orthogonal_edges.canonical_payload(),
        }


def grid_digest(grid: Tensor) -> str:
    validated = require_solved_grid81(grid)
    return hashlib.sha256(
        b"darwinian.grid81.v1\x00"
        + validated.to(torch.uint8).numpy().tobytes()
    ).hexdigest()


def _permuted_grid(
    matrix: Tensor,
    *,
    row_order: tuple[int, ...] | None = None,
    col_order: tuple[int, ...] | None = None,
) -> Tensor:
    result = matrix

    if row_order is not None:
        result = result[
            torch.tensor(row_order, dtype=torch.int64),
            :,
        ]

    if col_order is not None:
        result = result[
            :,
            torch.tensor(col_order, dtype=torch.int64),
        ]

    flattened = result.reshape(-1).clone()
    require_solved_grid81(flattened)
    return flattened


def valid_arrangements(grid: Tensor) -> Mapping[str, Tensor]:
    """Return deterministic Sudoku-preserving spatial rearrangements."""
    validated = require_solved_grid81(grid)
    matrix = validated.reshape(GRID_SIDE, GRID_SIDE)

    variants = {
        "IDENTITY": matrix.reshape(-1).clone(),
        "TRANSPOSE": matrix.T.reshape(-1).clone(),
        "SWAP_ROWS_0_1": _permuted_grid(
            matrix,
            row_order=(1, 0, 2, 3, 4, 5, 6, 7, 8),
        ),
        "SWAP_COLS_0_1": _permuted_grid(
            matrix,
            col_order=(1, 0, 2, 3, 4, 5, 6, 7, 8),
        ),
        "SWAP_BANDS_0_1": _permuted_grid(
            matrix,
            row_order=(3, 4, 5, 0, 1, 2, 6, 7, 8),
        ),
        "SWAP_STACKS_0_1": _permuted_grid(
            matrix,
            col_order=(3, 4, 5, 0, 1, 2, 6, 7, 8),
        ),
        "REVERSE_BANDS": _permuted_grid(
            matrix,
            row_order=(6, 7, 8, 3, 4, 5, 0, 1, 2),
        ),
        "REVERSE_STACKS": _permuted_grid(
            matrix,
            col_order=(6, 7, 8, 3, 4, 5, 0, 1, 2),
        ),
    }

    for candidate in variants.values():
        require_solved_grid81(candidate)

    return variants


def climate_marginals(grid: Tensor) -> ClimateMarginals:
    """Compute arrangement-invariant quantities from exact digit counts.

    Reducing float32 values in lattice order creates tiny arrangement-dependent
    round-off differences. Marginals are functions of the histogram, so they
    must be evaluated from the histogram rather than from spatial ordering.
    """
    validated = require_solved_grid81(grid)

    counts = torch.bincount(
        validated,
        minlength=10,
    )[1:10]
    counts64 = counts.to(torch.float64)

    digits = torch.arange(
        1,
        10,
        dtype=torch.float64,
    )

    optimum_values = (digits - 1.0) / 8.0

    distance = (digits - 5.0).abs() / 4.0
    capacity_values = 0.35 + (1.0 - 0.35) * (
        1.0 - distance.square()
    )

    return ClimateMarginals(
        digit_counts=tuple(int(value) for value in counts.tolist()),
        digit_sum=int((counts * torch.arange(1, 10)).sum().item()),
        optimum_sum=float(
            (counts64 * optimum_values).sum().item()
        ),
        capacity_sum=float(
            (counts64 * capacity_values).sum().item()
        ),
    )


def _region_edges(
    *,
    include_diagonal: bool,
) -> tuple[tuple[int, int], ...]:
    offsets = (
        ((0, 1), (1, 0), (1, 1), (1, -1))
        if include_diagonal
        else ((0, 1), (1, 0))
    )

    edges: list[tuple[int, int]] = []

    for row in range(GRID_SIDE):
        for col in range(GRID_SIDE):
            source = row * GRID_SIDE + col

            for delta_row, delta_col in offsets:
                neighbor_row = row + delta_row
                neighbor_col = col + delta_col

                if not (
                    0 <= neighbor_row < GRID_SIDE
                    and 0 <= neighbor_col < GRID_SIDE
                ):
                    continue

                destination = (
                    neighbor_row * GRID_SIDE + neighbor_col
                )
                edges.append((source, destination))

    return tuple(edges)


ORTHOGONAL_REGION_EDGES = _region_edges(
    include_diagonal=False,
)
MOORE_REGION_EDGES = _region_edges(
    include_diagonal=True,
)
DIAGONAL_REGION_EDGES = tuple(
    edge
    for edge in MOORE_REGION_EDGES
    if edge not in ORTHOGONAL_REGION_EDGES
)


def edge_metrics(
    grid: Tensor,
    *,
    include_diagonal: bool = False,
    alpha: float = 0.35,
) -> EdgeMetrics:
    validated = require_solved_grid81(grid).float()

    if alpha < 0.0:
        raise ValueError("alpha cannot be negative.")

    edges = (
        MOORE_REGION_EDGES
        if include_diagonal
        else ORTHOGONAL_REGION_EDGES
    )

    source = torch.tensor(
        [edge[0] for edge in edges],
        dtype=torch.int64,
    )
    destination = torch.tensor(
        [edge[1] for edge in edges],
        dtype=torch.int64,
    )

    gradients = (
        validated[destination] - validated[source]
    ).abs()
    permeability = torch.exp(-alpha * gradients)

    return EdgeMetrics(
        edge_count=len(edges),
        zero_gradient_edges=int(
            gradients.eq(0.0).sum().item()
        ),
        total_abs_gradient=float(gradients.sum().item()),
        mean_abs_gradient=float(gradients.mean().item()),
        mean_permeability=float(permeability.mean().item()),
    )


def instantaneous_suitability(
    state: EcologyState,
    grid: Tensor,
    *,
    region_map: Tensor | None = None,
) -> float:
    """Measure climate/genome alignment without mutating ecology.

    Probe reductions use float64 so spatial permutations cannot manufacture
    false arrangement effects through float32 accumulation order.
    """
    validated = require_solved_grid81(grid)
    state.validate()

    if region_map is None:
        region_map = build_region_map()

    if region_map.shape != (MATRIX_CELLS,):
        raise ValueError("Invalid region-map shape.")

    region_indices = region_map.long()

    climate = validated[region_indices].to(torch.float64)
    local_optimum = (climate - 1.0) / 8.0

    distance = (climate - 5.0).abs() / 4.0
    local_capacity = 0.35 + (1.0 - 0.35) * (
        1.0 - distance.square()
    )

    alive = state.active_mask.to(torch.float64)
    genome = state.genome.to(torch.float64)
    mismatch = (genome - local_optimum).abs()

    suitability = (
        alive
        * local_capacity
        * (1.0 - mismatch).clamp(min=0.0, max=1.0)
    )

    if not bool(torch.isfinite(suitability).all()):
        raise ValueError(
            "Instantaneous suitability became non-finite."
        )

    return float(
        suitability.sum(dtype=torch.float64).item()
    )


def run_arrangement_probe(
    state: EcologyState,
    grid: Tensor,
    *,
    alpha: float = 0.35,
) -> tuple[ArrangementProbeRecord, ...]:
    region_map = build_region_map()
    records: list[ArrangementProbeRecord] = []

    for arrangement_id, candidate in valid_arrangements(grid).items():
        records.append(
            ArrangementProbeRecord(
                arrangement_id=arrangement_id,
                grid_digest=grid_digest(candidate),
                marginals=climate_marginals(candidate),
                orthogonal_edges=edge_metrics(
                    candidate,
                    include_diagonal=False,
                    alpha=alpha,
                ),
                diagonal_edges=edge_metrics(
                    candidate,
                    include_diagonal=True,
                    alpha=alpha,
                ),
                instantaneous_suitability=instantaneous_suitability(
                    state,
                    candidate,
                    region_map=region_map,
                ),
            )
        )

    return tuple(records)


def probe_digest(
    records: tuple[ArrangementProbeRecord, ...],
) -> str:
    payload = [
        record.canonical_payload()
        for record in records
    ]

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(
        b"darwinian.arrangement-probe.v1\x00" + encoded
    ).hexdigest()
