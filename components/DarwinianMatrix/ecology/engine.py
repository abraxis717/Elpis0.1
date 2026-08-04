"""Deterministic flat-array ecological substrate.

This module does not call the TRM, modify Grid81, or own climate state.
Climate enters only as detached read data supplied by the climate sidecar.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Iterable

import torch
from torch import Tensor

from ..geometry import MATRIX_CELLS


EMPTY = -1
PRODUCER = 0
CONSUMER = 1
STRUCTURE = 2

VALID_COMPONENT_TYPES = frozenset(
    {
        EMPTY,
        PRODUCER,
        CONSUMER,
        STRUCTURE,
    }
)


def _require_site_index(index: int) -> None:
    if not isinstance(index, int):
        raise TypeError("Ecological site index must be an integer.")
    if not 0 <= index < MATRIX_CELLS:
        raise ValueError(
            f"Ecological site index must be in [0, {MATRIX_CELLS - 1}]."
        )


def _require_vector(
    name: str,
    value: Tensor,
    *,
    length: int = MATRIX_CELLS,
) -> None:
    if value.shape != (length,):
        raise ValueError(
            f"{name} must have shape ({length},), "
            f"received {tuple(value.shape)}."
        )


def _require_finite(name: str, value: Tensor) -> None:
    if not bool(torch.isfinite(value).all()):
        raise ValueError(f"{name} contains NaN or infinite values.")


@dataclass(frozen=True)
class EcologyBounds:
    """Numerical and structural transaction limits."""

    max_population: int = MATRIX_CELLS
    max_abs_energy: float = 1_000_000.0
    max_resource: float = 1_000_000.0

    def __post_init__(self) -> None:
        if not 0 <= self.max_population <= MATRIX_CELLS:
            raise ValueError(
                "max_population must be within the lattice capacity."
            )
        if self.max_abs_energy <= 0:
            raise ValueError("max_abs_energy must be positive.")
        if self.max_resource <= 0:
            raise ValueError("max_resource must be positive.")


class EcologyState:
    """Structure-of-arrays ecological state over 6,561 sites."""

    def __init__(
        self,
        device: str | torch.device = "cpu",
    ) -> None:
        self.device = torch.device(device)

        self.ctype = torch.full(
            (MATRIX_CELLS,),
            EMPTY,
            dtype=torch.int16,
            device=self.device,
        )
        self.genome = torch.zeros(
            MATRIX_CELLS,
            dtype=torch.float32,
            device=self.device,
        )
        self.energy = torch.zeros(
            MATRIX_CELLS,
            dtype=torch.float32,
            device=self.device,
        )

        # Resource diffusion is explicitly ping-pong buffered.
        self.res_a = torch.zeros(
            MATRIX_CELLS,
            dtype=torch.float32,
            device=self.device,
        )
        self.res_b = torch.zeros_like(self.res_a)

        self.lineage = torch.full(
            (MATRIX_CELLS,),
            -1,
            dtype=torch.int32,
            device=self.device,
        )
        self.age = torch.zeros(
            MATRIX_CELLS,
            dtype=torch.int32,
            device=self.device,
        )

        if self.res_a.data_ptr() == self.res_b.data_ptr():
            raise RuntimeError("Resource buffers unexpectedly alias.")

    @property
    def active_mask(self) -> Tensor:
        return self.ctype.ne(EMPTY)

    @property
    def population(self) -> int:
        return int(self.active_mask.sum().item())

    def swap(self) -> None:
        """Compatibility alias for swapping resource buffers."""
        self.swap_resource_buffers()

    def swap_resource_buffers(self) -> None:
        """Atomically make the completed write buffer the read buffer."""
        if self.res_a.data_ptr() == self.res_b.data_ptr():
            raise RuntimeError("Cannot swap aliased resource buffers.")
        self.res_a, self.res_b = self.res_b, self.res_a

    def clear_resource_write_buffer(self) -> None:
        self.res_b.zero_()

    def clone(self) -> "EcologyState":
        duplicate = EcologyState(device=self.device)

        for field_name in (
            "ctype",
            "genome",
            "energy",
            "res_a",
            "res_b",
            "lineage",
            "age",
        ):
            getattr(duplicate, field_name).copy_(
                getattr(self, field_name)
            )

        return duplicate

    def validate(
        self,
        bounds: EcologyBounds | None = None,
    ) -> None:
        """Fail loudly on invalid or runaway ecological state."""
        bounds = bounds or EcologyBounds()

        expected_fields = {
            "ctype": self.ctype,
            "genome": self.genome,
            "energy": self.energy,
            "res_a": self.res_a,
            "res_b": self.res_b,
            "lineage": self.lineage,
            "age": self.age,
        }

        for name, tensor in expected_fields.items():
            _require_vector(name, tensor)

        if self.res_a.data_ptr() == self.res_b.data_ptr():
            raise ValueError("Resource buffers alias each other.")

        component_values = set(
            int(value)
            for value in torch.unique(self.ctype).cpu().tolist()
        )
        invalid_types = component_values - VALID_COMPONENT_TYPES

        if invalid_types:
            raise ValueError(
                f"Invalid component type IDs: {sorted(invalid_types)}."
            )

        for name in (
            "genome",
            "energy",
            "res_a",
            "res_b",
        ):
            _require_finite(name, getattr(self, name))

        if self.population > bounds.max_population:
            raise ValueError(
                f"Population {self.population} exceeds bound "
                f"{bounds.max_population}."
            )

        active = self.active_mask

        if bool(
            (
                active
                & (
                    (self.genome < 0.0)
                    | (self.genome > 1.0)
                )
            ).any()
        ):
            raise ValueError(
                "Active component genomes must remain within [0, 1]."
            )

        if bool((active & self.lineage.lt(0)).any()):
            raise ValueError(
                "Every active component must have a lineage identity."
            )

        if bool(self.age.lt(0).any()):
            raise ValueError("Component age cannot be negative.")

        if float(self.energy.abs().max().item()) > bounds.max_abs_energy:
            raise ValueError("Energy exceeded the configured bound.")

        for name in ("res_a", "res_b"):
            resource = getattr(self, name)

            if bool(resource.lt(0.0).any()):
                raise ValueError(
                    f"{name} contains negative resource."
                )

            if float(resource.max().item()) > bounds.max_resource:
                raise ValueError(
                    f"{name} exceeded the configured resource bound."
                )

    def digest(self) -> str:
        """Return a deterministic digest of the complete state."""
        digest = hashlib.sha256()

        for field_name in (
            "ctype",
            "genome",
            "energy",
            "res_a",
            "res_b",
            "lineage",
            "age",
        ):
            tensor = (
                getattr(self, field_name)
                .detach()
                .cpu()
                .contiguous()
            )

            digest.update(field_name.encode("utf-8"))
            digest.update(b"\x00")
            digest.update(str(tensor.dtype).encode("ascii"))
            digest.update(b"\x00")
            digest.update(tensor.numpy().tobytes())
            digest.update(b"\x00")

        return digest.hexdigest()


@dataclass(frozen=True, order=True)
class BirthCommand:
    site_index: int
    component_type: int
    genome: float
    energy: float
    lineage_id: int

    def __post_init__(self) -> None:
        _require_site_index(self.site_index)

        if self.component_type not in (
            PRODUCER,
            CONSUMER,
            STRUCTURE,
        ):
            raise ValueError("Invalid birth component type.")

        if not 0.0 <= self.genome <= 1.0:
            raise ValueError("Birth genome must be within [0, 1].")

        if not torch.isfinite(
            torch.tensor(self.energy)
        ):
            raise ValueError("Birth energy must be finite.")

        if self.lineage_id < 0:
            raise ValueError(
                "Birth lineage identity must be non-negative."
            )


@dataclass(frozen=True)
class CommandFlushSummary:
    births_committed: int
    deaths_committed: int


class CommandBuffer:
    """Deferred structural mutations flushed after system iteration."""

    def __init__(self) -> None:
        self.births: list[BirthCommand] = []
        self.deaths: list[int] = []

    def queue_birth(
        self,
        *,
        site_index: int,
        component_type: int,
        genome: float,
        energy: float,
        lineage_id: int,
    ) -> None:
        command = BirthCommand(
            site_index=site_index,
            component_type=component_type,
            genome=float(genome),
            energy=float(energy),
            lineage_id=int(lineage_id),
        )

        if any(
            existing.site_index == command.site_index
            for existing in self.births
        ):
            raise ValueError(
                f"Duplicate birth command for site {site_index}."
            )

        self.births.append(command)

    def queue_death(self, site_index: int) -> None:
        _require_site_index(site_index)

        if site_index in self.deaths:
            raise ValueError(
                f"Duplicate death command for site {site_index}."
            )

        self.deaths.append(site_index)

    def flush(self, state: EcologyState) -> CommandFlushSummary:
        """Apply all commands atomically in deterministic index order."""
        birth_indices = {
            command.site_index
            for command in self.births
        }
        death_indices = set(self.deaths)

        conflict = birth_indices & death_indices

        if conflict:
            raise ValueError(
                "Birth/death conflict at sites "
                f"{sorted(conflict)}."
            )

        for site_index in death_indices:
            if int(state.ctype[site_index]) == EMPTY:
                raise ValueError(
                    f"Cannot kill empty site {site_index}."
                )

        for command in self.births:
            if int(state.ctype[command.site_index]) != EMPTY:
                raise ValueError(
                    f"Cannot birth into occupied site "
                    f"{command.site_index}."
                )

        staged = state.clone()

        for site_index in sorted(death_indices):
            staged.ctype[site_index] = EMPTY
            staged.genome[site_index] = 0.0
            staged.energy[site_index] = 0.0
            staged.lineage[site_index] = -1
            staged.age[site_index] = 0

        for command in sorted(self.births):
            site_index = command.site_index
            staged.ctype[site_index] = command.component_type
            staged.genome[site_index] = command.genome
            staged.energy[site_index] = command.energy
            staged.lineage[site_index] = command.lineage_id
            staged.age[site_index] = 0

        staged.validate()

        for field_name in (
            "ctype",
            "genome",
            "energy",
            "lineage",
            "age",
        ):
            getattr(state, field_name).copy_(
                getattr(staged, field_name)
            )

        summary = CommandFlushSummary(
            births_committed=len(self.births),
            deaths_committed=len(self.deaths),
        )

        self.births.clear()
        self.deaths.clear()

        return summary


def permeability_from_gradient(
    climate_flat: Tensor,
    neighbors: Tensor,
    alpha: float = 0.35,
) -> Tensor:
    """Return edge permeability shaped ``[6561, neighbor_count]``.

    Equal climates have permeability one. Larger climate discontinuities
    reduce exchange continuously without turning region borders into walls.
    """
    _require_vector("climate_flat", climate_flat)

    if neighbors.ndim != 2:
        raise ValueError(
            "Neighbor table must have shape [6561, neighbor_count]."
        )
    if neighbors.shape[0] != MATRIX_CELLS:
        raise ValueError(
            f"Neighbor table requires {MATRIX_CELLS} rows."
        )
    if alpha < 0:
        raise ValueError("alpha cannot be negative.")

    neighbor_indices = neighbors.to(
        device=climate_flat.device,
        dtype=torch.int64,
    )

    if bool(
        (
            (neighbor_indices < 0)
            | (neighbor_indices >= MATRIX_CELLS)
        ).any()
    ):
        raise ValueError("Neighbor table contains invalid indices.")

    local = climate_flat.float().unsqueeze(1)
    remote = climate_flat[neighbor_indices].float()
    gradient = (remote - local).abs()

    permeability = torch.exp(-alpha * gradient)
    _require_finite("permeability", permeability)

    return permeability


def diffuse(
    state: EcologyState,
    neighbors: Tensor,
    permeability: Tensor,
    rate: float = 0.15,
) -> None:
    """Diffuse ``res_a`` into ``res_b`` without mutating ``res_a``.

    The caller must explicitly call ``swap_resource_buffers`` after every
    completed diffusion pass.
    """
    if not 0.0 <= rate <= 1.0:
        raise ValueError("Diffusion rate must be within [0, 1].")

    if neighbors.ndim != 2:
        raise ValueError(
            "Neighbor table must have shape [6561, neighbor_count]."
        )

    if neighbors.shape[0] != MATRIX_CELLS:
        raise ValueError(
            f"Neighbor table requires {MATRIX_CELLS} rows."
        )

    neighbor_indices = neighbors.to(
        device=state.device,
        dtype=torch.int64,
    )
    neighbor_count = neighbors.shape[1]

    if permeability.shape == (MATRIX_CELLS,):
        edge_permeability = permeability.to(
            device=state.device,
            dtype=torch.float32,
        ).unsqueeze(1).expand(
            MATRIX_CELLS,
            neighbor_count,
        )
    elif permeability.shape == (
        MATRIX_CELLS,
        neighbor_count,
    ):
        edge_permeability = permeability.to(
            device=state.device,
            dtype=torch.float32,
        )
    else:
        raise ValueError(
            "Permeability must have shape [6561] or "
            "[6561, neighbor_count]."
        )

    _require_finite("edge_permeability", edge_permeability)

    if bool(
        (
            (edge_permeability < 0.0)
            | (edge_permeability > 1.0)
        ).any()
    ):
        raise ValueError(
            "Permeability values must remain within [0, 1]."
        )

    read_before = state.res_a.clone()
    gathered = state.res_a[neighbor_indices]
    center = state.res_a.unsqueeze(1)

    pairwise_flux = edge_permeability * (gathered - center)
    delta = pairwise_flux.mean(dim=1)
    next_resource = state.res_a + rate * delta

    _require_finite("diffused resource", next_resource)

    if bool(next_resource.lt(-1e-6).any()):
        raise ValueError(
            "Diffusion produced materially negative resource."
        )

    state.res_b.copy_(next_resource.clamp_min(0.0))

    if not torch.equal(state.res_a, read_before):
        raise RuntimeError(
            "Diffusion mutated the resource read buffer."
        )


def metabolize(
    state: EcologyState,
    mu: Tensor,
    K: Tensor,
    shock_field: Tensor,
    cost: float = 0.02,
) -> None:
    """Apply local climate response without cross-site mutation."""
    for name, field in (
        ("mu", mu),
        ("K", K),
        ("shock_field", shock_field),
    ):
        _require_vector(name, field)
        _require_finite(name, field)

    if cost < 0:
        raise ValueError("Metabolic cost cannot be negative.")

    alive = state.active_mask
    mismatch = (state.genome - mu).abs()
    suitability = (1.0 - mismatch).clamp(
        min=0.0,
        max=1.0,
    )
    yield_field = K * suitability + shock_field - cost

    next_energy = torch.where(
        alive,
        state.energy + yield_field,
        state.energy,
    )

    _require_finite("metabolic energy", next_energy)
    state.energy.copy_(next_energy)


def increment_age(state: EcologyState) -> None:
    """Advance age exactly once for every active component."""
    state.age.add_(state.active_mask.to(torch.int32))


def validate_climate_inputs_unchanged(
    before: Iterable[Tensor],
    after: Iterable[Tensor],
) -> None:
    """Guard used by integration code around ecological steps."""
    before_values = tuple(before)
    after_values = tuple(after)

    if len(before_values) != len(after_values):
        raise ValueError("Climate snapshot cardinality changed.")

    for index, (previous, current) in enumerate(
        zip(before_values, after_values)
    ):
        if not torch.equal(previous, current):
            raise RuntimeError(
                f"Ecological phase mutated climate input {index}."
            )
