"""Exact ecological fitness observations for Darwinian organisms."""

from __future__ import annotations

from dataclasses import dataclass

from .canonical import (
    payload_digest,
    require_sha256,
)
from .organism import OrganismState


FITNESS_OBSERVATION_SCHEMA = (
    "darwinian.life.fitness-observation.v1"
)

FITNESS_POLICY_SCHEMA = (
    "darwinian.life.fitness-policy.v1"
)

FITNESS_RECORD_SCHEMA = (
    "darwinian.life.fitness-record.v1"
)

PPM_SCALE = 1_000_000


def _require_integer(
    value: object,
    *,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(
        value,
        int,
    ):
        raise TypeError(
            field_name + " must be an integer."
        )

    return value


def _require_nonnegative_integer(
    value: object,
    *,
    field_name: str,
) -> int:
    result = _require_integer(
        value,
        field_name=field_name,
    )

    if result < 0:
        raise ValueError(
            field_name + " cannot be negative."
        )

    return result


@dataclass(frozen=True)
class FitnessObservation:
    """Measured ecological consequences over a closed tick interval."""

    window_start_tick: int
    window_end_tick: int
    energy_delta: int
    survival_ticks: int
    viable_offspring: int
    resource_efficiency_ppm: int
    ecological_damage: int
    failed_actions: int = 0
    schema: str = FITNESS_OBSERVATION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != FITNESS_OBSERVATION_SCHEMA:
            raise ValueError(
                "Unsupported fitness-observation schema."
            )

        start = _require_nonnegative_integer(
            self.window_start_tick,
            field_name="window_start_tick",
        )

        end = _require_nonnegative_integer(
            self.window_end_tick,
            field_name="window_end_tick",
        )

        if end < start:
            raise ValueError(
                "Fitness observation end tick cannot "
                "precede its start tick."
            )

        _require_integer(
            self.energy_delta,
            field_name="energy_delta",
        )

        _require_nonnegative_integer(
            self.survival_ticks,
            field_name="survival_ticks",
        )

        _require_nonnegative_integer(
            self.viable_offspring,
            field_name="viable_offspring",
        )

        efficiency = _require_nonnegative_integer(
            self.resource_efficiency_ppm,
            field_name="resource_efficiency_ppm",
        )

        if efficiency > PPM_SCALE:
            raise ValueError(
                "resource_efficiency_ppm cannot exceed "
                "one million."
            )

        _require_nonnegative_integer(
            self.ecological_damage,
            field_name="ecological_damage",
        )

        _require_nonnegative_integer(
            self.failed_actions,
            field_name="failed_actions",
        )

        interval_length = end - start

        if self.survival_ticks > interval_length:
            raise ValueError(
                "survival_ticks cannot exceed the "
                "observation interval."
            )

    @property
    def interval_ticks(self) -> int:
        return (
            self.window_end_tick
            - self.window_start_tick
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "window_start_tick": (
                self.window_start_tick
            ),
            "window_end_tick": (
                self.window_end_tick
            ),
            "interval_ticks": (
                self.interval_ticks
            ),
            "energy_delta": self.energy_delta,
            "survival_ticks": (
                self.survival_ticks
            ),
            "viable_offspring": (
                self.viable_offspring
            ),
            "resource_efficiency_ppm": (
                self.resource_efficiency_ppm
            ),
            "ecological_damage": (
                self.ecological_damage
            ),
            "failed_actions": (
                self.failed_actions
            ),
        }

    def digest(self) -> str:
        return payload_digest(
            self.canonical_payload()
        )


@dataclass(frozen=True)
class FitnessPolicyV1:
    """Exact integer scalarization of measured ecological outcomes."""

    energy_delta_weight: int = 1
    survival_tick_weight: int = 1
    viable_offspring_weight: int = 10
    resource_efficiency_weight: int = 0
    ecological_damage_weight: int = 1
    failed_action_weight: int = 1
    schema: str = FITNESS_POLICY_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != FITNESS_POLICY_SCHEMA:
            raise ValueError(
                "Unsupported fitness-policy schema."
            )

        for field_name, value in (
            (
                "energy_delta_weight",
                self.energy_delta_weight,
            ),
            (
                "survival_tick_weight",
                self.survival_tick_weight,
            ),
            (
                "viable_offspring_weight",
                self.viable_offspring_weight,
            ),
            (
                "resource_efficiency_weight",
                self.resource_efficiency_weight,
            ),
            (
                "ecological_damage_weight",
                self.ecological_damage_weight,
            ),
            (
                "failed_action_weight",
                self.failed_action_weight,
            ),
        ):
            _require_nonnegative_integer(
                value,
                field_name=field_name,
            )

    def score(
        self,
        observation: FitnessObservation,
    ) -> int:
        if not isinstance(
            observation,
            FitnessObservation,
        ):
            raise TypeError(
                "observation must be a "
                "FitnessObservation."
            )

        positive = (
            observation.energy_delta
            * self.energy_delta_weight
            + observation.survival_ticks
            * self.survival_tick_weight
            + observation.viable_offspring
            * self.viable_offspring_weight
            + observation.resource_efficiency_ppm
            * self.resource_efficiency_weight
        )

        negative = (
            observation.ecological_damage
            * self.ecological_damage_weight
            + observation.failed_actions
            * self.failed_action_weight
        )

        return positive - negative

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "energy_delta_weight": (
                self.energy_delta_weight
            ),
            "survival_tick_weight": (
                self.survival_tick_weight
            ),
            "viable_offspring_weight": (
                self.viable_offspring_weight
            ),
            "resource_efficiency_weight": (
                self.resource_efficiency_weight
            ),
            "ecological_damage_weight": (
                self.ecological_damage_weight
            ),
            "failed_action_weight": (
                self.failed_action_weight
            ),
            "arithmetic": "EXACT_INTEGER",
            "novelty_included": False,
        }

    def digest(self) -> str:
        return payload_digest(
            self.canonical_payload()
        )


@dataclass(frozen=True)
class OrganismFitnessRecord:
    """A fitness observation bound to one exact organism revision."""

    organism_id: str
    organism_state_digest: str
    genotype_digest: str
    lifecycle: str
    observation: FitnessObservation
    observation_digest: str
    fitness_policy_digest: str
    scalar_fitness: int
    schema: str = FITNESS_RECORD_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != FITNESS_RECORD_SCHEMA:
            raise ValueError(
                "Unsupported fitness-record schema."
            )

        for field_name, digest in (
            (
                "organism_id",
                self.organism_id,
            ),
            (
                "organism_state_digest",
                self.organism_state_digest,
            ),
            (
                "genotype_digest",
                self.genotype_digest,
            ),
            (
                "observation_digest",
                self.observation_digest,
            ),
            (
                "fitness_policy_digest",
                self.fitness_policy_digest,
            ),
        ):
            require_sha256(
                digest,
                field_name=field_name,
            )

        if not isinstance(
            self.lifecycle,
            str,
        ) or not self.lifecycle:
            raise ValueError(
                "lifecycle must be non-empty."
            )

        if not isinstance(
            self.observation,
            FitnessObservation,
        ):
            raise TypeError(
                "observation must be a "
                "FitnessObservation."
            )

        if (
            self.observation_digest
            != self.observation.digest()
        ):
            raise ValueError(
                "Fitness observation digest mismatch."
            )

        _require_integer(
            self.scalar_fitness,
            field_name="scalar_fitness",
        )

    @classmethod
    def evaluate(
        cls,
        *,
        organism: OrganismState,
        observation: FitnessObservation,
        policy: FitnessPolicyV1,
    ) -> "OrganismFitnessRecord":
        if not isinstance(
            organism,
            OrganismState,
        ):
            raise TypeError(
                "organism must be an OrganismState."
            )

        if not isinstance(
            observation,
            FitnessObservation,
        ):
            raise TypeError(
                "observation must be a "
                "FitnessObservation."
            )

        if not isinstance(
            policy,
            FitnessPolicyV1,
        ):
            raise TypeError(
                "policy must be a FitnessPolicyV1."
            )

        return cls(
            organism_id=organism.organism_id,
            organism_state_digest=(
                organism.digest()
            ),
            genotype_digest=(
                organism.genotype.digest()
            ),
            lifecycle=organism.lifecycle.value,
            observation=observation,
            observation_digest=(
                observation.digest()
            ),
            fitness_policy_digest=(
                policy.digest()
            ),
            scalar_fitness=(
                policy.score(observation)
            ),
        )

    def validate_organism(
        self,
        organism: OrganismState,
    ) -> bool:
        if not isinstance(
            organism,
            OrganismState,
        ):
            raise TypeError(
                "organism must be an OrganismState."
            )

        return (
            self.organism_id
            == organism.organism_id
            and self.organism_state_digest
            == organism.digest()
            and self.genotype_digest
            == organism.genotype.digest()
            and self.lifecycle
            == organism.lifecycle.value
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "organism_id": self.organism_id,
            "organism_state_digest": (
                self.organism_state_digest
            ),
            "genotype_digest": (
                self.genotype_digest
            ),
            "lifecycle": self.lifecycle,
            "observation": (
                self.observation.canonical_payload()
            ),
            "observation_digest": (
                self.observation_digest
            ),
            "fitness_policy_digest": (
                self.fitness_policy_digest
            ),
            "scalar_fitness": (
                self.scalar_fitness
            ),
        }

    def digest(self) -> str:
        return payload_digest(
            self.canonical_payload()
        )


__all__ = (
    "FITNESS_OBSERVATION_SCHEMA",
    "FITNESS_POLICY_SCHEMA",
    "FITNESS_RECORD_SCHEMA",
    "FitnessObservation",
    "FitnessPolicyV1",
    "OrganismFitnessRecord",
)
