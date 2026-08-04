"""Atomic pre-TRM Darwinian Matrix frame transaction.

The caller supplies one already-solved Grid81. This module advances persistent
climate dynamics, executes one ecological transaction, assesses viability,
advances the immutable meta-episode clock, and produces chained ledger records.

No projector, TRM inference, clamp mutation, or authority-chain operation is
implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Sequence

import torch
from torch import Tensor

from ..climate.response import capacity
from ..climate.state import ClimateDynamicsState
from ..ecology.engine import EcologyState
from ..ecology.transaction import (
    EcologyStepTelemetry,
    EcologyTransactionConfig,
    advance_ecology_transaction,
)
from ..geometry import (
    MATRIX_CELLS,
    build_region_map,
    require_solved_grid81,
)
from ..ledger.records import (
    GENESIS_RECORD_DIGEST,
    EcologyFrameRecord,
    build_frame_record,
    tensor_digest,
)
from ..runtime import RUNTIME_POLICY
from .verdict import (
    FrameAssessment,
    MetaEpisodeState,
    viability,
)


FRAME_COMMIT_SCHEMA = "darwinian.frame-commit.v1"


def _canonical_json_bytes(
    payload: object,
) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _domain_digest(
    domain: str,
    payload: object,
) -> str:
    return hashlib.sha256(
        domain.encode("utf-8")
        + b"\x00"
        + _canonical_json_bytes(payload)
    ).hexdigest()


def _require_digest(
    name: str,
    value: str,
) -> None:
    if len(value) != 64:
        raise ValueError(
            f"{name} must be a 64-character SHA-256 digest."
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(
            f"{name} is not hexadecimal."
        ) from exc


def solved_grid_digest(
    grid: Tensor | Sequence[int] | Iterable[int],
) -> str:
    validated = require_solved_grid81(grid)

    return tensor_digest(
        "darwinian.solved-grid81-output.v1",
        validated.to(torch.int8),
    )


@dataclass(frozen=True)
class FrameCommitRecord:
    schema_version: str

    episode_id: str
    frame_index: int
    random_seed: int

    grid_digest: str
    region_map_digest: str

    climate_before_digest: str
    climate_after_digest: str

    ecology_record_digest: str
    assessment_digest: str

    meta_before_digest: str
    meta_after_digest: str

    runtime_policy_digest: str
    previous_commit_digest: str
    commit_digest: str

    def __post_init__(self) -> None:
        if self.schema_version != FRAME_COMMIT_SCHEMA:
            raise ValueError(
                "Unsupported frame-commit schema."
            )

        if not self.episode_id:
            raise ValueError(
                "episode_id cannot be empty."
            )

        if self.frame_index < 0:
            raise ValueError(
                "frame_index cannot be negative."
            )

        if self.random_seed < 0:
            raise ValueError(
                "random_seed cannot be negative."
            )

        for name in (
            "grid_digest",
            "region_map_digest",
            "climate_before_digest",
            "climate_after_digest",
            "ecology_record_digest",
            "assessment_digest",
            "meta_before_digest",
            "meta_after_digest",
            "runtime_policy_digest",
            "previous_commit_digest",
            "commit_digest",
        ):
            _require_digest(
                name,
                getattr(self, name),
            )

    def semantic_payload(self) -> dict[str, object]:
        return {
            "assessment_digest": self.assessment_digest,
            "climate_after_digest": (
                self.climate_after_digest
            ),
            "climate_before_digest": (
                self.climate_before_digest
            ),
            "ecology_record_digest": (
                self.ecology_record_digest
            ),
            "episode_id": self.episode_id,
            "frame_index": self.frame_index,
            "grid_digest": self.grid_digest,
            "meta_after_digest": self.meta_after_digest,
            "meta_before_digest": (
                self.meta_before_digest
            ),
            "previous_commit_digest": (
                self.previous_commit_digest
            ),
            "random_seed": self.random_seed,
            "region_map_digest": (
                self.region_map_digest
            ),
            "runtime_policy_digest": (
                self.runtime_policy_digest
            ),
            "schema_version": self.schema_version,
        }

    def recompute_digest(self) -> str:
        return _domain_digest(
            FRAME_COMMIT_SCHEMA,
            self.semantic_payload(),
        )

    def validate_digest(self) -> bool:
        return (
            self.commit_digest
            == self.recompute_digest()
        )

    def to_dict(self) -> dict[str, object]:
        payload = self.semantic_payload()
        payload["commit_digest"] = self.commit_digest
        return payload

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, object],
    ) -> "FrameCommitRecord":
        return cls(
            schema_version=str(
                payload["schema_version"]
            ),
            episode_id=str(payload["episode_id"]),
            frame_index=int(payload["frame_index"]),
            random_seed=int(payload["random_seed"]),
            grid_digest=str(payload["grid_digest"]),
            region_map_digest=str(
                payload["region_map_digest"]
            ),
            climate_before_digest=str(
                payload["climate_before_digest"]
            ),
            climate_after_digest=str(
                payload["climate_after_digest"]
            ),
            ecology_record_digest=str(
                payload["ecology_record_digest"]
            ),
            assessment_digest=str(
                payload["assessment_digest"]
            ),
            meta_before_digest=str(
                payload["meta_before_digest"]
            ),
            meta_after_digest=str(
                payload["meta_after_digest"]
            ),
            runtime_policy_digest=str(
                payload["runtime_policy_digest"]
            ),
            previous_commit_digest=str(
                payload["previous_commit_digest"]
            ),
            commit_digest=str(
                payload["commit_digest"]
            ),
        )


def build_frame_commit(
    *,
    episode_id: str,
    frame_index: int,
    random_seed: int,
    grid_digest: str,
    region_map_digest: str,
    climate_before_digest: str,
    climate_after_digest: str,
    ecology_record_digest: str,
    assessment_digest: str,
    meta_before_digest: str,
    meta_after_digest: str,
    previous_commit_digest: str,
) -> FrameCommitRecord:
    partial = FrameCommitRecord(
        schema_version=FRAME_COMMIT_SCHEMA,
        episode_id=episode_id,
        frame_index=frame_index,
        random_seed=random_seed,
        grid_digest=grid_digest,
        region_map_digest=region_map_digest,
        climate_before_digest=climate_before_digest,
        climate_after_digest=climate_after_digest,
        ecology_record_digest=ecology_record_digest,
        assessment_digest=assessment_digest,
        meta_before_digest=meta_before_digest,
        meta_after_digest=meta_after_digest,
        runtime_policy_digest=RUNTIME_POLICY.digest(),
        previous_commit_digest=previous_commit_digest,
        commit_digest=GENESIS_RECORD_DIGEST,
    )

    payload = partial.to_dict()
    payload["commit_digest"] = (
        partial.recompute_digest()
    )

    return FrameCommitRecord.from_dict(payload)


@dataclass(frozen=True)
class FrameTransactionResult:
    climate_state: ClimateDynamicsState
    ecology_state: EcologyState
    meta_state: MetaEpisodeState

    assessment: FrameAssessment
    ecology_telemetry: EcologyStepTelemetry
    ecology_record: EcologyFrameRecord
    commit_record: FrameCommitRecord


@dataclass(frozen=True)
class FrameReplayResult:
    passed: bool

    expected_commit_digest: str
    observed_commit_digest: str

    expected_ecology_record_digest: str
    observed_ecology_record_digest: str

    expected_climate_digest: str
    observed_climate_digest: str

    expected_ecology_digest: str
    observed_ecology_digest: str

    expected_meta_digest: str
    observed_meta_digest: str


def advance_frame_transaction(
    *,
    episode_id: str,
    random_seed: int,
    grid: Tensor | Sequence[int] | Iterable[int],
    climate_state: ClimateDynamicsState,
    ecology_state: EcologyState,
    meta_state: MetaEpisodeState,
    target_viability: float,
    neighbors: Tensor,
    config: EcologyTransactionConfig | None = None,
    region_map: Tensor | None = None,
    previous_ecology_record_digest: str = (
        GENESIS_RECORD_DIGEST
    ),
    previous_commit_digest: str = (
        GENESIS_RECORD_DIGEST
    ),
    epsilon: float = 1e-3,
    window: int = 4,
) -> FrameTransactionResult:
    """Advance one complete bounded pre-TRM frame."""
    if not episode_id:
        raise ValueError(
            "episode_id cannot be empty."
        )

    if meta_state.meta_id != episode_id:
        raise ValueError(
            "Meta-episode identity does not match "
            "the frame episode identity."
        )

    if meta_state.closed:
        raise RuntimeError(
            "Cannot advance a closed meta-episode."
        )

    if random_seed < 0:
        raise ValueError(
            "random_seed cannot be negative."
        )

    _require_digest(
        "previous_ecology_record_digest",
        previous_ecology_record_digest,
    )
    _require_digest(
        "previous_commit_digest",
        previous_commit_digest,
    )

    config = config or EcologyTransactionConfig()

    if region_map is None:
        region_map = build_region_map(
            device=ecology_state.device
        )

    if region_map.shape != (MATRIX_CELLS,):
        raise ValueError(
            f"region_map must have shape ({MATRIX_CELLS},)."
        )

    frame_index = meta_state.attempt_index

    climate_before_digest = (
        climate_state.digest()
    )
    ecology_before_digest = (
        ecology_state.digest()
    )
    meta_before_digest = meta_state.digest()

    validated_grid = require_solved_grid81(grid)
    next_climate = climate_state.advance(
        validated_grid
    )

    lattice_dynamics = (
        next_climate.lattice_read_view(
            region_map
        )
    )
    climate_view, transition_age = (
        lattice_dynamics.ecology_inputs()
    )

    next_ecology, ecology_telemetry = (
        advance_ecology_transaction(
            state=ecology_state,
            climate=climate_view,
            transition_age=transition_age,
            neighbors=neighbors,
            config=config,
        )
    )

    capacity_field = capacity(
        climate_view.current
    )

    viability_value = viability(
        next_ecology,
        capacity_field,
    )

    next_meta, assessment = (
        meta_state.record_frame(
            viability_value=viability_value,
            target_viability=target_viability,
            epsilon=epsilon,
            window=window,
        )
    )

    ecology_record = build_frame_record(
        episode_id=episode_id,
        frame_index=frame_index,
        random_seed=random_seed,
        state_before=ecology_state,
        state_after=next_ecology,
        climate=climate_view,
        transition_age=transition_age,
        neighbors=neighbors,
        config=config,
        telemetry=ecology_telemetry,
        previous_record_digest=(
            previous_ecology_record_digest
        ),
    )

    commit_record = build_frame_commit(
        episode_id=episode_id,
        frame_index=frame_index,
        random_seed=random_seed,
        grid_digest=solved_grid_digest(
            validated_grid
        ),
        region_map_digest=tensor_digest(
            "darwinian.region-map.v1",
            region_map,
        ),
        climate_before_digest=(
            climate_before_digest
        ),
        climate_after_digest=(
            next_climate.digest()
        ),
        ecology_record_digest=(
            ecology_record.record_digest
        ),
        assessment_digest=assessment.digest(),
        meta_before_digest=meta_before_digest,
        meta_after_digest=next_meta.digest(),
        previous_commit_digest=(
            previous_commit_digest
        ),
    )

    if (
        climate_state.digest()
        != climate_before_digest
    ):
        raise RuntimeError(
            "Frame transaction mutated its input "
            "climate state."
        )

    if (
        ecology_state.digest()
        != ecology_before_digest
    ):
        raise RuntimeError(
            "Frame transaction mutated its input "
            "ecological state."
        )

    if meta_state.digest() != meta_before_digest:
        raise RuntimeError(
            "Frame transaction mutated its input "
            "meta-episode state."
        )

    return FrameTransactionResult(
        climate_state=next_climate,
        ecology_state=next_ecology,
        meta_state=next_meta,
        assessment=assessment,
        ecology_telemetry=ecology_telemetry,
        ecology_record=ecology_record,
        commit_record=commit_record,
    )


def replay_frame_transaction(
    *,
    expected_result: FrameTransactionResult,
    episode_id: str,
    random_seed: int,
    grid: Tensor | Sequence[int] | Iterable[int],
    climate_state: ClimateDynamicsState,
    ecology_state: EcologyState,
    meta_state: MetaEpisodeState,
    target_viability: float,
    neighbors: Tensor,
    config: EcologyTransactionConfig | None = None,
    region_map: Tensor | None = None,
    epsilon: float = 1e-3,
    window: int = 4,
) -> tuple[
    FrameTransactionResult,
    FrameReplayResult,
]:
    observed = advance_frame_transaction(
        episode_id=episode_id,
        random_seed=random_seed,
        grid=grid,
        climate_state=climate_state,
        ecology_state=ecology_state,
        meta_state=meta_state,
        target_viability=target_viability,
        neighbors=neighbors,
        config=config,
        region_map=region_map,
        previous_ecology_record_digest=(
            expected_result.ecology_record
            .previous_record_digest
        ),
        previous_commit_digest=(
            expected_result.commit_record
            .previous_commit_digest
        ),
        epsilon=epsilon,
        window=window,
    )

    replay = FrameReplayResult(
        passed=(
            expected_result.commit_record
            .validate_digest()
            and expected_result.ecology_record
            .validate_digest()
            and observed.commit_record.commit_digest
            == expected_result.commit_record.commit_digest
            and observed.ecology_record.record_digest
            == expected_result.ecology_record.record_digest
            and observed.climate_state.digest()
            == expected_result.climate_state.digest()
            and observed.ecology_state.digest()
            == expected_result.ecology_state.digest()
            and observed.meta_state.digest()
            == expected_result.meta_state.digest()
            and observed.assessment.digest()
            == expected_result.assessment.digest()
        ),
        expected_commit_digest=(
            expected_result.commit_record.commit_digest
        ),
        observed_commit_digest=(
            observed.commit_record.commit_digest
        ),
        expected_ecology_record_digest=(
            expected_result.ecology_record.record_digest
        ),
        observed_ecology_record_digest=(
            observed.ecology_record.record_digest
        ),
        expected_climate_digest=(
            expected_result.climate_state.digest()
        ),
        observed_climate_digest=(
            observed.climate_state.digest()
        ),
        expected_ecology_digest=(
            expected_result.ecology_state.digest()
        ),
        observed_ecology_digest=(
            observed.ecology_state.digest()
        ),
        expected_meta_digest=(
            expected_result.meta_state.digest()
        ),
        observed_meta_digest=(
            observed.meta_state.digest()
        ),
    )

    return observed, replay


def verify_frame_commit_chain(
    records: tuple[FrameCommitRecord, ...],
) -> bool:
    previous = GENESIS_RECORD_DIGEST
    episode_id: str | None = None

    for expected_index, record in enumerate(records):
        if record.frame_index != expected_index:
            return False

        if episode_id is None:
            episode_id = record.episode_id
        elif record.episode_id != episode_id:
            return False

        if record.previous_commit_digest != previous:
            return False

        if not record.validate_digest():
            return False

        previous = record.commit_digest

    return True
