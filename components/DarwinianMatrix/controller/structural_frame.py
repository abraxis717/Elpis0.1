"""Atomic structural-frame composition.

This layer joins projector-owned clamps, the frozen structural-adapter
contract, and the existing ecological frame transaction.

A rejected structural refinement does not advance climate, ecology, or the
meta-episode. An accepted refinement supplies the solved Grid81 consumed by
the existing frame transaction.

The production TRM is not implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Sequence

from torch import Tensor

from ..climate.state import ClimateDynamicsState
from ..ecology.engine import EcologyState
from ..ecology.transaction import EcologyTransactionConfig
from ..geometry import require_solved_grid81
from ..ledger.records import GENESIS_RECORD_DIGEST
from ..projector.constraints import ClampState
from ..runtime import RUNTIME_POLICY
from ..trm.contract import (
    REFINEMENT_ACCEPTED,
    REFINEMENT_REJECTED,
    FrozenStructuralAdapter,
    StructuralRefinementRequest,
    StructuralRefinementResult,
    execute_refinement,
)
from .frame import (
    FrameTransactionResult,
    advance_frame_transaction,
    solved_grid_digest,
)
from .verdict import MetaEpisodeState


STRUCTURAL_ATTEMPT_SCHEMA = (
    "darwinian.structural-frame-attempt.v1"
)

STRUCTURAL_FRAME_COMMITTED = (
    "STRUCTURAL_FRAME_COMMITTED"
)
STRUCTURAL_REFINEMENT_REJECTED = (
    "STRUCTURAL_REFINEMENT_REJECTED"
)


def _canonical_json_bytes(payload: object) -> bytes:
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
            f"{name} must be hexadecimal."
        ) from exc


def _require_optional_digest(
    name: str,
    value: str | None,
) -> None:
    if value is not None:
        _require_digest(name, value)


@dataclass(frozen=True)
class StructuralFrameAttemptRecord:
    schema_version: str

    episode_id: str
    structural_attempt_index: int
    frame_index: int
    random_seed: int

    outcome: str
    refinement_outcome: str

    previous_grid_digest: str
    clamp_state_digest: str
    request_digest: str
    adapter_manifest_digest: str
    refinement_result_digest: str

    output_grid_digest: str | None
    ecology_record_digest: str | None
    frame_commit_digest: str | None

    climate_before_digest: str
    climate_after_digest: str
    ecology_before_digest: str
    ecology_after_digest: str
    meta_before_digest: str
    meta_after_digest: str

    runtime_policy_digest: str
    previous_attempt_digest: str
    attempt_digest: str

    def __post_init__(self) -> None:
        if self.schema_version != STRUCTURAL_ATTEMPT_SCHEMA:
            raise ValueError(
                "Unsupported structural-attempt schema."
            )

        if not self.episode_id:
            raise ValueError(
                "episode_id cannot be empty."
            )

        if self.structural_attempt_index < 0:
            raise ValueError(
                "structural_attempt_index cannot be negative."
            )

        if self.frame_index < 0:
            raise ValueError(
                "frame_index cannot be negative."
            )

        if self.random_seed < 0:
            raise ValueError(
                "random_seed cannot be negative."
            )

        if self.outcome not in (
            STRUCTURAL_FRAME_COMMITTED,
            STRUCTURAL_REFINEMENT_REJECTED,
        ):
            raise ValueError(
                "Unsupported structural-attempt outcome."
            )

        if self.refinement_outcome not in (
            REFINEMENT_ACCEPTED,
            REFINEMENT_REJECTED,
        ):
            raise ValueError(
                "Unsupported refinement outcome."
            )

        for name in (
            "previous_grid_digest",
            "clamp_state_digest",
            "request_digest",
            "adapter_manifest_digest",
            "refinement_result_digest",
            "climate_before_digest",
            "climate_after_digest",
            "ecology_before_digest",
            "ecology_after_digest",
            "meta_before_digest",
            "meta_after_digest",
            "runtime_policy_digest",
            "previous_attempt_digest",
            "attempt_digest",
        ):
            _require_digest(
                name,
                getattr(self, name),
            )

        _require_optional_digest(
            "output_grid_digest",
            self.output_grid_digest,
        )
        _require_optional_digest(
            "ecology_record_digest",
            self.ecology_record_digest,
        )
        _require_optional_digest(
            "frame_commit_digest",
            self.frame_commit_digest,
        )

        if self.outcome == STRUCTURAL_FRAME_COMMITTED:
            if self.refinement_outcome != REFINEMENT_ACCEPTED:
                raise ValueError(
                    "Committed structural frame requires "
                    "accepted refinement."
                )

            if self.output_grid_digest is None:
                raise ValueError(
                    "Committed frame requires output_grid_digest."
                )

            if self.ecology_record_digest is None:
                raise ValueError(
                    "Committed frame requires ecology_record_digest."
                )

            if self.frame_commit_digest is None:
                raise ValueError(
                    "Committed frame requires frame_commit_digest."
                )

        if self.outcome == STRUCTURAL_REFINEMENT_REJECTED:
            if self.refinement_outcome != REFINEMENT_REJECTED:
                raise ValueError(
                    "Rejected structural frame requires "
                    "rejected refinement."
                )

            if self.output_grid_digest is not None:
                raise ValueError(
                    "Rejected refinement cannot bind an output grid."
                )

            if self.ecology_record_digest is not None:
                raise ValueError(
                    "Rejected refinement cannot bind an ecology record."
                )

            if self.frame_commit_digest is not None:
                raise ValueError(
                    "Rejected refinement cannot bind a frame commit."
                )

            if (
                self.climate_before_digest
                != self.climate_after_digest
            ):
                raise ValueError(
                    "Rejected refinement changed climate identity."
                )

            if (
                self.ecology_before_digest
                != self.ecology_after_digest
            ):
                raise ValueError(
                    "Rejected refinement changed ecology identity."
                )

            if (
                self.meta_before_digest
                != self.meta_after_digest
            ):
                raise ValueError(
                    "Rejected refinement changed meta identity."
                )

    def semantic_payload(self) -> dict[str, object]:
        return {
            "adapter_manifest_digest": (
                self.adapter_manifest_digest
            ),
            "clamp_state_digest": self.clamp_state_digest,
            "climate_after_digest": (
                self.climate_after_digest
            ),
            "climate_before_digest": (
                self.climate_before_digest
            ),
            "ecology_after_digest": (
                self.ecology_after_digest
            ),
            "ecology_before_digest": (
                self.ecology_before_digest
            ),
            "ecology_record_digest": (
                self.ecology_record_digest
            ),
            "episode_id": self.episode_id,
            "frame_commit_digest": (
                self.frame_commit_digest
            ),
            "frame_index": self.frame_index,
            "meta_after_digest": self.meta_after_digest,
            "meta_before_digest": self.meta_before_digest,
            "outcome": self.outcome,
            "output_grid_digest": self.output_grid_digest,
            "previous_attempt_digest": (
                self.previous_attempt_digest
            ),
            "previous_grid_digest": (
                self.previous_grid_digest
            ),
            "random_seed": self.random_seed,
            "refinement_outcome": (
                self.refinement_outcome
            ),
            "refinement_result_digest": (
                self.refinement_result_digest
            ),
            "request_digest": self.request_digest,
            "runtime_policy_digest": (
                self.runtime_policy_digest
            ),
            "schema_version": self.schema_version,
            "structural_attempt_index": (
                self.structural_attempt_index
            ),
        }

    def recompute_digest(self) -> str:
        return _domain_digest(
            STRUCTURAL_ATTEMPT_SCHEMA,
            self.semantic_payload(),
        )

    def validate_digest(self) -> bool:
        return (
            self.attempt_digest
            == self.recompute_digest()
        )

    def to_dict(self) -> dict[str, object]:
        payload = self.semantic_payload()
        payload["attempt_digest"] = self.attempt_digest
        return payload

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, object],
    ) -> "StructuralFrameAttemptRecord":
        return cls(
            schema_version=str(
                payload["schema_version"]
            ),
            episode_id=str(payload["episode_id"]),
            structural_attempt_index=int(
                payload["structural_attempt_index"]
            ),
            frame_index=int(payload["frame_index"]),
            random_seed=int(payload["random_seed"]),
            outcome=str(payload["outcome"]),
            refinement_outcome=str(
                payload["refinement_outcome"]
            ),
            previous_grid_digest=str(
                payload["previous_grid_digest"]
            ),
            clamp_state_digest=str(
                payload["clamp_state_digest"]
            ),
            request_digest=str(
                payload["request_digest"]
            ),
            adapter_manifest_digest=str(
                payload["adapter_manifest_digest"]
            ),
            refinement_result_digest=str(
                payload["refinement_result_digest"]
            ),
            output_grid_digest=(
                str(payload["output_grid_digest"])
                if payload["output_grid_digest"] is not None
                else None
            ),
            ecology_record_digest=(
                str(payload["ecology_record_digest"])
                if payload["ecology_record_digest"] is not None
                else None
            ),
            frame_commit_digest=(
                str(payload["frame_commit_digest"])
                if payload["frame_commit_digest"] is not None
                else None
            ),
            climate_before_digest=str(
                payload["climate_before_digest"]
            ),
            climate_after_digest=str(
                payload["climate_after_digest"]
            ),
            ecology_before_digest=str(
                payload["ecology_before_digest"]
            ),
            ecology_after_digest=str(
                payload["ecology_after_digest"]
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
            previous_attempt_digest=str(
                payload["previous_attempt_digest"]
            ),
            attempt_digest=str(
                payload["attempt_digest"]
            ),
        )


@dataclass(frozen=True)
class StructuralFrameTransactionResult:
    outcome: str

    refinement_request: StructuralRefinementRequest
    refinement_result: StructuralRefinementResult

    climate_state: ClimateDynamicsState
    ecology_state: EcologyState
    meta_state: MetaEpisodeState

    frame_result: FrameTransactionResult | None
    attempt_record: StructuralFrameAttemptRecord

    @property
    def committed(self) -> bool:
        return self.outcome == STRUCTURAL_FRAME_COMMITTED


@dataclass(frozen=True)
class StructuralFrameReplayResult:
    passed: bool

    expected_attempt_digest: str
    observed_attempt_digest: str

    expected_request_digest: str
    observed_request_digest: str

    expected_refinement_digest: str
    observed_refinement_digest: str

    expected_climate_digest: str
    observed_climate_digest: str

    expected_ecology_digest: str
    observed_ecology_digest: str

    expected_meta_digest: str
    observed_meta_digest: str


def _build_attempt_record(
    *,
    episode_id: str,
    structural_attempt_index: int,
    frame_index: int,
    random_seed: int,
    previous_grid_digest: str,
    clamp_state_digest: str,
    request: StructuralRefinementRequest,
    refinement: StructuralRefinementResult,
    climate_before_digest: str,
    ecology_before_digest: str,
    meta_before_digest: str,
    climate_after_digest: str,
    ecology_after_digest: str,
    meta_after_digest: str,
    frame_result: FrameTransactionResult | None,
    previous_attempt_digest: str,
) -> StructuralFrameAttemptRecord:
    committed = frame_result is not None

    output_grid_digest: str | None = None
    ecology_record_digest: str | None = None
    frame_commit_digest: str | None = None

    if committed:
        output = refinement.output_grid()

        if output is None:
            raise RuntimeError(
                "Committed structural frame has no output grid."
            )

        output_grid_digest = solved_grid_digest(output)
        ecology_record_digest = (
            frame_result.ecology_record.record_digest
        )
        frame_commit_digest = (
            frame_result.commit_record.commit_digest
        )

        if (
            frame_result.commit_record.grid_digest
            != output_grid_digest
        ):
            raise RuntimeError(
                "Inner frame commit is bound to the wrong "
                "refinement output."
            )

    partial = StructuralFrameAttemptRecord(
        schema_version=STRUCTURAL_ATTEMPT_SCHEMA,
        episode_id=episode_id,
        structural_attempt_index=(
            structural_attempt_index
        ),
        frame_index=frame_index,
        random_seed=random_seed,
        outcome=(
            STRUCTURAL_FRAME_COMMITTED
            if committed
            else STRUCTURAL_REFINEMENT_REJECTED
        ),
        refinement_outcome=refinement.outcome,
        previous_grid_digest=previous_grid_digest,
        clamp_state_digest=clamp_state_digest,
        request_digest=request.digest(),
        adapter_manifest_digest=(
            refinement.adapter_manifest_digest
        ),
        refinement_result_digest=(
            refinement.result_digest
        ),
        output_grid_digest=output_grid_digest,
        ecology_record_digest=ecology_record_digest,
        frame_commit_digest=frame_commit_digest,
        climate_before_digest=climate_before_digest,
        climate_after_digest=climate_after_digest,
        ecology_before_digest=ecology_before_digest,
        ecology_after_digest=ecology_after_digest,
        meta_before_digest=meta_before_digest,
        meta_after_digest=meta_after_digest,
        runtime_policy_digest=RUNTIME_POLICY.digest(),
        previous_attempt_digest=previous_attempt_digest,
        attempt_digest=GENESIS_RECORD_DIGEST,
    )

    payload = partial.to_dict()
    payload["attempt_digest"] = (
        partial.recompute_digest()
    )

    return StructuralFrameAttemptRecord.from_dict(
        payload
    )


def advance_structural_frame_transaction(
    *,
    episode_id: str,
    structural_attempt_index: int,
    random_seed: int,
    previous_grid: Tensor | Sequence[int] | Iterable[int],
    clamp_state: ClampState,
    adapter: FrozenStructuralAdapter,
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
    previous_frame_commit_digest: str = (
        GENESIS_RECORD_DIGEST
    ),
    previous_structural_attempt_digest: str = (
        GENESIS_RECORD_DIGEST
    ),
    epsilon: float = 1e-3,
    window: int = 4,
) -> StructuralFrameTransactionResult:
    """Advance one structural attempt atomically."""
    if not episode_id:
        raise ValueError(
            "episode_id cannot be empty."
        )

    if structural_attempt_index < 0:
        raise ValueError(
            "structural_attempt_index cannot be negative."
        )

    if random_seed < 0:
        raise ValueError(
            "random_seed cannot be negative."
        )

    if clamp_state.episode_id != episode_id:
        raise ValueError(
            "Clamp-state episode identity mismatch."
        )

    if meta_state.meta_id != episode_id:
        raise ValueError(
            "Meta-state episode identity mismatch."
        )

    if meta_state.closed:
        raise RuntimeError(
            "Cannot advance a closed meta-episode."
        )

    _require_digest(
        "previous_structural_attempt_digest",
        previous_structural_attempt_digest,
    )

    validated_previous = require_solved_grid81(
        previous_grid
    )

    previous_grid_identity = solved_grid_digest(
        validated_previous
    )
    clamp_identity = clamp_state.digest()
    climate_before = climate_state.digest()
    ecology_before = ecology_state.digest()
    meta_before = meta_state.digest()

    request = StructuralRefinementRequest.from_clamp_state(
        previous_grid=validated_previous,
        clamp_state=clamp_state,
        frame_index=meta_state.attempt_index,
    )

    refinement = execute_refinement(
        adapter=adapter,
        request=request,
    )

    if refinement.outcome == REFINEMENT_REJECTED:
        attempt_record = _build_attempt_record(
            episode_id=episode_id,
            structural_attempt_index=(
                structural_attempt_index
            ),
            frame_index=meta_state.attempt_index,
            random_seed=random_seed,
            previous_grid_digest=(
                previous_grid_identity
            ),
            clamp_state_digest=clamp_identity,
            request=request,
            refinement=refinement,
            climate_before_digest=climate_before,
            ecology_before_digest=ecology_before,
            meta_before_digest=meta_before,
            climate_after_digest=climate_before,
            ecology_after_digest=ecology_before,
            meta_after_digest=meta_before,
            frame_result=None,
            previous_attempt_digest=(
                previous_structural_attempt_digest
            ),
        )

        if clamp_state.digest() != clamp_identity:
            raise RuntimeError(
                "Rejected refinement mutated clamp state."
            )

        return StructuralFrameTransactionResult(
            outcome=STRUCTURAL_REFINEMENT_REJECTED,
            refinement_request=request,
            refinement_result=refinement,
            climate_state=climate_state,
            ecology_state=ecology_state,
            meta_state=meta_state,
            frame_result=None,
            attempt_record=attempt_record,
        )

    if refinement.outcome != REFINEMENT_ACCEPTED:
        raise RuntimeError(
            "Adapter returned an unsupported outcome."
        )

    output_grid = refinement.output_grid()

    if output_grid is None:
        raise RuntimeError(
            "Accepted refinement contains no output grid."
        )

    frame_result = advance_frame_transaction(
        episode_id=episode_id,
        random_seed=random_seed,
        grid=output_grid,
        climate_state=climate_state,
        ecology_state=ecology_state,
        meta_state=meta_state,
        target_viability=target_viability,
        neighbors=neighbors,
        config=config,
        region_map=region_map,
        previous_ecology_record_digest=(
            previous_ecology_record_digest
        ),
        previous_commit_digest=(
            previous_frame_commit_digest
        ),
        epsilon=epsilon,
        window=window,
    )

    attempt_record = _build_attempt_record(
        episode_id=episode_id,
        structural_attempt_index=(
            structural_attempt_index
        ),
        frame_index=meta_state.attempt_index,
        random_seed=random_seed,
        previous_grid_digest=previous_grid_identity,
        clamp_state_digest=clamp_identity,
        request=request,
        refinement=refinement,
        climate_before_digest=climate_before,
        ecology_before_digest=ecology_before,
        meta_before_digest=meta_before,
        climate_after_digest=(
            frame_result.climate_state.digest()
        ),
        ecology_after_digest=(
            frame_result.ecology_state.digest()
        ),
        meta_after_digest=(
            frame_result.meta_state.digest()
        ),
        frame_result=frame_result,
        previous_attempt_digest=(
            previous_structural_attempt_digest
        ),
    )

    if clamp_state.digest() != clamp_identity:
        raise RuntimeError(
            "Structural frame mutated clamp state."
        )

    if climate_state.digest() != climate_before:
        raise RuntimeError(
            "Structural frame mutated input climate state."
        )

    if ecology_state.digest() != ecology_before:
        raise RuntimeError(
            "Structural frame mutated input ecology state."
        )

    if meta_state.digest() != meta_before:
        raise RuntimeError(
            "Structural frame mutated input meta state."
        )

    return StructuralFrameTransactionResult(
        outcome=STRUCTURAL_FRAME_COMMITTED,
        refinement_request=request,
        refinement_result=refinement,
        climate_state=frame_result.climate_state,
        ecology_state=frame_result.ecology_state,
        meta_state=frame_result.meta_state,
        frame_result=frame_result,
        attempt_record=attempt_record,
    )


def replay_structural_frame_transaction(
    *,
    expected_result: StructuralFrameTransactionResult,
    episode_id: str,
    structural_attempt_index: int,
    random_seed: int,
    previous_grid: Tensor | Sequence[int] | Iterable[int],
    clamp_state: ClampState,
    adapter: FrozenStructuralAdapter,
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
    previous_frame_commit_digest: str = (
        GENESIS_RECORD_DIGEST
    ),
    previous_structural_attempt_digest: str = (
        GENESIS_RECORD_DIGEST
    ),
    epsilon: float = 1e-3,
    window: int = 4,
) -> tuple[
    StructuralFrameTransactionResult,
    StructuralFrameReplayResult,
]:
    observed = advance_structural_frame_transaction(
        episode_id=episode_id,
        structural_attempt_index=(
            structural_attempt_index
        ),
        random_seed=random_seed,
        previous_grid=previous_grid,
        clamp_state=clamp_state,
        adapter=adapter,
        climate_state=climate_state,
        ecology_state=ecology_state,
        meta_state=meta_state,
        target_viability=target_viability,
        neighbors=neighbors,
        config=config,
        region_map=region_map,
        previous_ecology_record_digest=(
            previous_ecology_record_digest
        ),
        previous_frame_commit_digest=(
            previous_frame_commit_digest
        ),
        previous_structural_attempt_digest=(
            previous_structural_attempt_digest
        ),
        epsilon=epsilon,
        window=window,
    )

    passed = (
        expected_result.attempt_record.validate_digest()
        and observed.outcome == expected_result.outcome
        and observed.refinement_request.digest()
        == expected_result.refinement_request.digest()
        and observed.refinement_result.result_digest
        == expected_result.refinement_result.result_digest
        and observed.attempt_record.attempt_digest
        == expected_result.attempt_record.attempt_digest
        and observed.climate_state.digest()
        == expected_result.climate_state.digest()
        and observed.ecology_state.digest()
        == expected_result.ecology_state.digest()
        and observed.meta_state.digest()
        == expected_result.meta_state.digest()
    )

    if (
        expected_result.frame_result is None
        or observed.frame_result is None
    ):
        passed = (
            passed
            and expected_result.frame_result is None
            and observed.frame_result is None
        )
    else:
        passed = (
            passed
            and observed.frame_result.commit_record.commit_digest
            == expected_result.frame_result.commit_record.commit_digest
            and observed.frame_result.ecology_record.record_digest
            == expected_result.frame_result.ecology_record.record_digest
        )

    replay = StructuralFrameReplayResult(
        passed=passed,
        expected_attempt_digest=(
            expected_result.attempt_record.attempt_digest
        ),
        observed_attempt_digest=(
            observed.attempt_record.attempt_digest
        ),
        expected_request_digest=(
            expected_result.refinement_request.digest()
        ),
        observed_request_digest=(
            observed.refinement_request.digest()
        ),
        expected_refinement_digest=(
            expected_result.refinement_result.result_digest
        ),
        observed_refinement_digest=(
            observed.refinement_result.result_digest
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


def verify_structural_attempt_chain(
    records: tuple[StructuralFrameAttemptRecord, ...],
) -> bool:
    previous = GENESIS_RECORD_DIGEST
    episode_id: str | None = None
    expected_frame_index = 0

    for expected_attempt_index, record in enumerate(records):
        if (
            record.structural_attempt_index
            != expected_attempt_index
        ):
            return False

        if record.frame_index != expected_frame_index:
            return False

        if episode_id is None:
            episode_id = record.episode_id
        elif record.episode_id != episode_id:
            return False

        if record.previous_attempt_digest != previous:
            return False

        if not record.validate_digest():
            return False

        previous = record.attempt_digest

        if record.outcome == STRUCTURAL_FRAME_COMMITTED:
            expected_frame_index += 1

    return True
