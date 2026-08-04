"""Atomic bounded ecological transactions.

A transaction consumes detached climate telemetry and an ecological snapshot,
runs one deterministic ecology step, validates the staged result, and returns
a new state. The input state and climate view remain unchanged.

This module does not call the projector or TRM and has no climate write path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math

import torch
from torch import Tensor

from ..climate.response import capacity, optimum, shock
from ..geometry import (
    MATRIX_CELLS,
    LatticeClimateView,
)
from ..runtime import enforce_deterministic_runtime
from .engine import (
    CONSUMER,
    PRODUCER,
    STRUCTURE,
    CommandBuffer,
    EcologyBounds,
    EcologyState,
    diffuse,
    increment_age,
    permeability_from_gradient,
    validate_climate_inputs_unchanged,
)


def _finite(name: str, value: float) -> float:
    number = float(value)

    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite.")

    return number


def _stable_sum(tensor: Tensor) -> float:
    """Reduce a tensor in a fixed serial order for ledger identity.

    Torch parallel reductions may differ in their final low-order bits across
    executions even when the resulting state tensor is byte-identical. Ledger
    telemetry must therefore avoid scheduler-dependent reduction trees.
    """
    values = (
        tensor.detach()
        .to(device="cpu", dtype=torch.float64)
        .reshape(-1)
        .tolist()
    )

    return math.fsum(values)


def _stable_mean(tensor: Tensor) -> float:
    """Return a deterministic serial mean."""
    count = tensor.numel()

    if count == 0:
        return 0.0

    return _stable_sum(tensor) / count


def _require_lattice_vector(
    name: str,
    tensor: Tensor,
) -> None:
    if tensor.shape != (MATRIX_CELLS,):
        raise ValueError(
            f"{name} must have shape ({MATRIX_CELLS},), "
            f"received {tuple(tensor.shape)}."
        )


@dataclass(frozen=True)
class EcologyTransactionConfig:
    diffusion_rate: float = 0.15
    gradient_alpha: float = 0.35

    producer_rate: float = 0.08
    producer_energy_efficiency: float = 0.60

    consumer_demand: float = 0.08
    consumer_energy_efficiency: float = 1.00

    structure_capacity_bonus: float = 0.20
    max_effective_capacity: float = 1.50

    producer_cost: float = 0.020
    consumer_cost: float = 0.030
    structure_cost: float = 0.010

    adaptation_rate: float = 0.010

    shock_tau: float = 6.0
    shock_resource_scale: float = 0.50
    shock_energy_scale: float = 0.05
    structure_shock_scale: float = 0.02

    death_threshold: float = -0.25

    bounds: EcologyBounds = field(
        default_factory=EcologyBounds
    )

    def __post_init__(self) -> None:
        unit_interval = (
            "diffusion_rate",
            "producer_rate",
            "producer_energy_efficiency",
            "consumer_demand",
            "consumer_energy_efficiency",
            "adaptation_rate",
        )

        for name in unit_interval:
            value = _finite(name, getattr(self, name))

            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{name} must remain within [0, 1]."
                )

        nonnegative = (
            "gradient_alpha",
            "structure_capacity_bonus",
            "producer_cost",
            "consumer_cost",
            "structure_cost",
            "shock_resource_scale",
            "shock_energy_scale",
            "structure_shock_scale",
        )

        for name in nonnegative:
            if _finite(name, getattr(self, name)) < 0.0:
                raise ValueError(
                    f"{name} cannot be negative."
                )

        if _finite(
            "max_effective_capacity",
            self.max_effective_capacity,
        ) <= 0.0:
            raise ValueError(
                "max_effective_capacity must be positive."
            )

        if _finite("shock_tau", self.shock_tau) <= 0.0:
            raise ValueError("shock_tau must be positive.")

        _finite("death_threshold", self.death_threshold)


@dataclass(frozen=True)
class EcologyStepTelemetry:
    before_digest: str
    after_digest: str

    population_before: int
    population_after: int
    deaths_committed: int

    resource_before: float
    resource_after: float
    resource_produced: float
    resource_consumed: float

    energy_before: float
    energy_after: float

    mean_permeability: float
    mean_suitability: float
    mean_effective_capacity: float
    mean_shock: float

    def canonical_payload(self) -> dict[str, object]:
        return {
            "after_digest": self.after_digest,
            "before_digest": self.before_digest,
            "deaths_committed": self.deaths_committed,
            "energy_after": self.energy_after,
            "energy_before": self.energy_before,
            "mean_effective_capacity": (
                self.mean_effective_capacity
            ),
            "mean_permeability": self.mean_permeability,
            "mean_shock": self.mean_shock,
            "mean_suitability": self.mean_suitability,
            "population_after": self.population_after,
            "population_before": self.population_before,
            "resource_after": self.resource_after,
            "resource_before": self.resource_before,
            "resource_consumed": self.resource_consumed,
            "resource_produced": self.resource_produced,
        }

    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

        return hashlib.sha256(
            b"darwinian.ecology-step-telemetry.v1\x00"
            + encoded
        ).hexdigest()


def _validate_climate(
    climate: LatticeClimateView,
) -> None:
    for name in (
        "previous",
        "current",
        "transition_ids",
        "changed",
    ):
        _require_lattice_vector(
            f"climate.{name}",
            getattr(climate, name),
        )

    if bool(
        (
            (climate.previous < 1)
            | (climate.previous > 9)
            | (climate.current < 1)
            | (climate.current > 9)
        ).any()
    ):
        raise ValueError(
            "Climate values must remain within Grid81 domain 1..9."
        )

    if bool(
        (
            (climate.transition_ids < 0)
            | (climate.transition_ids > 80)
        ).any()
    ):
        raise ValueError(
            "Climate transition IDs must remain within 0..80."
        )


def advance_ecology_transaction(
    *,
    state: EcologyState,
    climate: LatticeClimateView,
    transition_age: Tensor,
    neighbors: Tensor,
    config: EcologyTransactionConfig | None = None,
) -> tuple[EcologyState, EcologyStepTelemetry]:
    """Run one complete ecological step without mutating its inputs."""
    enforce_deterministic_runtime()
    config = config or EcologyTransactionConfig()

    state.validate(config.bounds)
    _validate_climate(climate)

    _require_lattice_vector(
        "transition_age",
        transition_age,
    )

    if not bool(torch.isfinite(transition_age).all()):
        raise ValueError(
            "transition_age contains NaN or infinite values."
        )

    if bool(transition_age.lt(0).any()):
        raise ValueError(
            "transition_age cannot contain negative values."
        )

    if neighbors.ndim != 2:
        raise ValueError(
            "neighbors must have shape "
            "[6561, neighbor_count]."
        )

    if neighbors.shape[0] != MATRIX_CELLS:
        raise ValueError(
            f"neighbors requires {MATRIX_CELLS} rows."
        )

    climate_before = (
        climate.previous.clone(),
        climate.current.clone(),
        climate.transition_ids.clone(),
        climate.changed.clone(),
    )
    transition_age_before = transition_age.clone()

    before_digest = state.digest()
    population_before = state.population
    resource_before = _stable_sum(state.res_a)
    energy_before = _stable_sum(state.energy)

    staged = state.clone()

    permeability = permeability_from_gradient(
        climate.current,
        neighbors,
        alpha=config.gradient_alpha,
    )

    diffuse(
        staged,
        neighbors,
        permeability,
        rate=config.diffusion_rate,
    )
    staged.swap_resource_buffers()

    current = climate.current.to(
        device=staged.device,
    )
    previous = climate.previous.to(
        device=staged.device,
    )
    age = transition_age.to(
        device=staged.device,
        dtype=torch.float32,
    )

    local_optimum = optimum(current)
    base_capacity = capacity(current)
    shock_field = shock(
        previous,
        current,
        age,
        tau=config.shock_tau,
    )

    neighbor_indices = neighbors.to(
        device=staged.device,
        dtype=torch.int64,
    )

    producer_mask = staged.ctype.eq(PRODUCER)
    consumer_mask = staged.ctype.eq(CONSUMER)
    structure_mask = staged.ctype.eq(STRUCTURE)
    active_mask = staged.active_mask

    structure_support = (
        structure_mask.to(torch.float32)[
            neighbor_indices
        ].mean(dim=1)
    )

    effective_capacity = (
        base_capacity
        + config.structure_capacity_bonus
        * structure_support
    ).clamp(
        min=0.0,
        max=config.max_effective_capacity,
    )

    mismatch = (
        staged.genome - local_optimum
    ).abs()

    suitability = (
        1.0 - mismatch
    ).clamp(
        min=0.0,
        max=1.0,
    )

    directional_resource_factor = (
        1.0
        + config.shock_resource_scale
        * shock_field
    ).clamp_min(0.0)

    production = (
        producer_mask.to(torch.float32)
        * config.producer_rate
        * effective_capacity
        * suitability
        * directional_resource_factor
    )

    staged.res_a.add_(production)

    demand = (
        consumer_mask.to(torch.float32)
        * config.consumer_demand
        * (
            0.5
            + 0.5 * suitability
        )
    )

    consumed = torch.minimum(
        staged.res_a,
        demand,
    )
    staged.res_a.sub_(consumed)

    costs = (
        producer_mask.to(torch.float32)
        * config.producer_cost
        + consumer_mask.to(torch.float32)
        * config.consumer_cost
        + structure_mask.to(torch.float32)
        * config.structure_cost
    )

    energy_delta = (
        production
        * config.producer_energy_efficiency
        + consumed
        * config.consumer_energy_efficiency
        + active_mask.to(torch.float32)
        * config.shock_energy_scale
        * shock_field
        + structure_mask.to(torch.float32)
        * config.structure_shock_scale
        * shock_field
        - costs
    )

    staged.energy.add_(energy_delta)

    adaptable = producer_mask | consumer_mask

    adapted_genome = (
        staged.genome
        + config.adaptation_rate
        * (
            local_optimum - staged.genome
        )
    ).clamp(
        min=0.0,
        max=1.0,
    )

    staged.genome.copy_(
        torch.where(
            adaptable,
            adapted_genome,
            staged.genome,
        )
    )

    increment_age(staged)

    commands = CommandBuffer()

    death_indices = torch.nonzero(
        staged.active_mask
        & staged.energy.le(
            config.death_threshold
        ),
        as_tuple=False,
    ).reshape(-1)

    for site_index in death_indices.cpu().tolist():
        commands.queue_death(int(site_index))

    command_summary = commands.flush(staged)

    staged.validate(config.bounds)

    validate_climate_inputs_unchanged(
        climate_before,
        (
            climate.previous,
            climate.current,
            climate.transition_ids,
            climate.changed,
        ),
    )

    if not torch.equal(
        transition_age,
        transition_age_before,
    ):
        raise RuntimeError(
            "Ecological transaction mutated transition_age."
        )

    if state.digest() != before_digest:
        raise RuntimeError(
            "Ecological transaction mutated its input state."
        )

    after_digest = staged.digest()

    telemetry = EcologyStepTelemetry(
        before_digest=before_digest,
        after_digest=after_digest,
        population_before=population_before,
        population_after=staged.population,
        deaths_committed=(
            command_summary.deaths_committed
        ),
        resource_before=resource_before,
        resource_after=_stable_sum(staged.res_a),
        resource_produced=_stable_sum(production),
        resource_consumed=_stable_sum(consumed),
        energy_before=energy_before,
        energy_after=_stable_sum(staged.energy),
        mean_permeability=_stable_mean(permeability),
        mean_suitability=(
            _stable_mean(suitability[active_mask])
            if bool(active_mask.any())
            else 0.0
        ),
        mean_effective_capacity=_stable_mean(
            effective_capacity
        ),
        mean_shock=_stable_mean(shock_field),
    )

    return staged, telemetry
