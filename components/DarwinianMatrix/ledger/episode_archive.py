"""Self-contained deterministic Darwinian episode archive.

The archive persists every initial tensor and execution parameter required to
reconstruct and replay a complete episode from disk.

The currently qualified adapter reconstruction registry contains only the
deterministic Sudoku reference adapter. This does not qualify the production
TRM for autonomous replay.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

import torch
from torch import Tensor

from ..climate.state import ClimateDynamicsState
from ..controller.episode import (
    DarwinianEpisodeState,
    EpisodeAdvanceResult,
    EpisodeDisposition,
    advance_episode,
)
from ..controller.verdict import (
    FrameVerdict,
    MetaEpisodeState,
)
from ..ecology.engine import (
    EcologyBounds,
    EcologyState,
)
from ..ecology.transaction import (
    EcologyTransactionConfig,
)
from ..geometry import build_region_map
from ..projector.constraints import ClampState
from ..trm.contract import FrozenStructuralAdapter
from ..trm.reference_solver import (
    DeterministicSudokuReferenceAdapter,
)
from .records import config_payload


EPISODE_ARCHIVE_SCHEMA = (
    "darwinian.episode-archive.v1"
)
ARCHIVED_ATTEMPT_SCHEMA = (
    "darwinian.archived-episode-attempt.v1"
)

REFERENCE_ADAPTER_CLASS = (
    "DETERMINISTIC_SUDOKU_REFERENCE_ADAPTER"
)


_DTYPE_BY_NAME: dict[str, torch.dtype] = {
    "torch.bool": torch.bool,
    "torch.int8": torch.int8,
    "torch.int16": torch.int16,
    "torch.int32": torch.int32,
    "torch.int64": torch.int64,
    "torch.float16": torch.float16,
    "torch.float32": torch.float32,
    "torch.float64": torch.float64,
}


def canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def domain_digest(
    domain: str,
    payload: object,
) -> str:
    return hashlib.sha256(
        domain.encode("utf-8")
        + b"\x00"
        + canonical_json_bytes(payload)
    ).hexdigest()


def require_digest(
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


def optional_digest(
    value: str | None,
) -> str | None:
    if value is not None:
        require_digest("optional digest", value)

    return value


def tensor_payload(tensor: Tensor) -> dict[str, object]:
    value = tensor.detach().cpu().contiguous()

    return {
        "data": value.reshape(-1).tolist(),
        "dtype": str(value.dtype),
        "shape": list(value.shape),
    }


def tensor_from_payload(
    payload: dict[str, object],
) -> Tensor:
    dtype_name = str(payload["dtype"])

    if dtype_name not in _DTYPE_BY_NAME:
        raise ValueError(
            "Unsupported archived tensor dtype: "
            + dtype_name
        )

    shape = tuple(
        int(value)
        for value in payload["shape"]
    )

    tensor = torch.tensor(
        payload["data"],
        dtype=_DTYPE_BY_NAME[dtype_name],
    )

    expected_count = math.prod(shape)

    if tensor.numel() != expected_count:
        raise ValueError(
            "Archived tensor shape/data count mismatch."
        )

    return tensor.reshape(shape).clone()


def bounds_payload(
    bounds: EcologyBounds,
) -> dict[str, object]:
    return {
        "max_abs_energy": bounds.max_abs_energy,
        "max_population": bounds.max_population,
        "max_resource": bounds.max_resource,
    }


def bounds_from_payload(
    payload: dict[str, object],
) -> EcologyBounds:
    return EcologyBounds(
        max_abs_energy=float(
            payload["max_abs_energy"]
        ),
        max_population=int(
            payload["max_population"]
        ),
        max_resource=float(
            payload["max_resource"]
        ),
    )


def config_from_payload(
    payload: dict[str, object],
) -> EcologyTransactionConfig:
    bounds = bounds_from_payload(
        dict(payload["bounds"])
    )

    return EcologyTransactionConfig(
        diffusion_rate=float(
            payload["diffusion_rate"]
        ),
        gradient_alpha=float(
            payload["gradient_alpha"]
        ),
        producer_rate=float(
            payload["producer_rate"]
        ),
        producer_energy_efficiency=float(
            payload["producer_energy_efficiency"]
        ),
        consumer_demand=float(
            payload["consumer_demand"]
        ),
        consumer_energy_efficiency=float(
            payload["consumer_energy_efficiency"]
        ),
        structure_capacity_bonus=float(
            payload["structure_capacity_bonus"]
        ),
        max_effective_capacity=float(
            payload["max_effective_capacity"]
        ),
        producer_cost=float(
            payload["producer_cost"]
        ),
        consumer_cost=float(
            payload["consumer_cost"]
        ),
        structure_cost=float(
            payload["structure_cost"]
        ),
        adaptation_rate=float(
            payload["adaptation_rate"]
        ),
        shock_tau=float(
            payload["shock_tau"]
        ),
        shock_resource_scale=float(
            payload["shock_resource_scale"]
        ),
        shock_energy_scale=float(
            payload["shock_energy_scale"]
        ),
        structure_shock_scale=float(
            payload["structure_shock_scale"]
        ),
        death_threshold=float(
            payload["death_threshold"]
        ),
        bounds=bounds,
    )


def clamp_state_payload(
    state: ClampState,
) -> dict[str, object]:
    return {
        "active_mask": tensor_payload(
            state.active_mask
        ),
        "closed": state.closed,
        "episode_id": state.episode_id,
        "owners": list(state.owners),
        "values": tensor_payload(state.values),
        "version": state.version,
    }


def clamp_state_from_payload(
    payload: dict[str, object],
) -> ClampState:
    return ClampState(
        episode_id=str(payload["episode_id"]),
        version=int(payload["version"]),
        closed=bool(payload["closed"]),
        active_mask=tensor_from_payload(
            dict(payload["active_mask"])
        ),
        values=tensor_from_payload(
            dict(payload["values"])
        ),
        owners=tuple(payload["owners"]),
    )


def climate_state_payload(
    state: ClimateDynamicsState,
) -> dict[str, object]:
    return {
        "changed": tensor_payload(state.changed),
        "current": tensor_payload(state.current),
        "initialized": state.initialized,
        "previous": tensor_payload(state.previous),
        "transition_age": tensor_payload(
            state.transition_age
        ),
        "transition_ids": tensor_payload(
            state.transition_ids
        ),
    }


def climate_state_from_payload(
    payload: dict[str, object],
) -> ClimateDynamicsState:
    return ClimateDynamicsState(
        device="cpu",
        initialized=bool(payload["initialized"]),
        previous=tensor_from_payload(
            dict(payload["previous"])
        ),
        current=tensor_from_payload(
            dict(payload["current"])
        ),
        transition_ids=tensor_from_payload(
            dict(payload["transition_ids"])
        ),
        changed=tensor_from_payload(
            dict(payload["changed"])
        ),
        transition_age=tensor_from_payload(
            dict(payload["transition_age"])
        ),
    )


def ecology_state_payload(
    state: EcologyState,
) -> dict[str, object]:
    state_bounds = getattr(
        state,
        "bounds",
        EcologyBounds(),
    )

    return {
        "age": tensor_payload(state.age),
        "bounds": bounds_payload(state_bounds),
        "ctype": tensor_payload(state.ctype),
        "energy": tensor_payload(state.energy),
        "genome": tensor_payload(state.genome),
        "lineage": tensor_payload(state.lineage),
        "res_a": tensor_payload(state.res_a),
        "res_b": tensor_payload(state.res_b),
    }


def ecology_state_from_payload(
    payload: dict[str, object],
) -> EcologyState:
    bounds = bounds_from_payload(
        dict(payload["bounds"])
    )

    try:
        state = EcologyState(bounds=bounds)
    except TypeError:
        state = EcologyState()

    for name in (
        "ctype",
        "genome",
        "energy",
        "res_a",
        "res_b",
        "lineage",
        "age",
    ):
        archived = tensor_from_payload(
            dict(payload[name])
        )
        target = getattr(state, name)

        if target.shape != archived.shape:
            raise ValueError(
                f"Archived ecology tensor {name} "
                "has the wrong shape."
            )

        target.copy_(
            archived.to(
                dtype=target.dtype,
                device=target.device,
            )
        )

    state.validate()
    return state


def meta_state_payload(
    state: MetaEpisodeState,
) -> dict[str, object]:
    return {
        "attempt_budget": state.attempt_budget,
        "attempt_index": state.attempt_index,
        "closed": state.closed,
        "final_verdict": (
            state.final_verdict.value
            if state.final_verdict is not None
            else None
        ),
        "meta_id": state.meta_id,
        "viability_history": list(
            state.viability_history
        ),
    }


def meta_state_from_payload(
    payload: dict[str, object],
) -> MetaEpisodeState:
    final_value = payload["final_verdict"]

    final_verdict = (
        FrameVerdict(str(final_value))
        if final_value is not None
        else None
    )

    return MetaEpisodeState(
        meta_id=str(payload["meta_id"]),
        attempt_budget=int(
            payload["attempt_budget"]
        ),
        attempt_index=int(
            payload["attempt_index"]
        ),
        viability_history=tuple(
            float(value)
            for value in payload[
                "viability_history"
            ]
        ),
        closed=bool(payload["closed"]),
        final_verdict=final_verdict,
    )


def episode_state_payload(
    state: DarwinianEpisodeState,
) -> dict[str, object]:
    if str(state.ecology_state.device) != "cpu":
        raise ValueError(
            "Episode archive v1 supports CPU state only."
        )

    return {
        "clamp_state": clamp_state_payload(
            state.clamp_state
        ),
        "climate_state": climate_state_payload(
            state.climate_state
        ),
        "disposition": state.disposition.value,
        "ecology_state": ecology_state_payload(
            state.ecology_state
        ),
        "episode_id": state.episode_id,
        "meta_state": meta_state_payload(
            state.meta_state
        ),
        "previous_ecology_record_digest": (
            state.previous_ecology_record_digest
        ),
        "previous_frame_commit_digest": (
            state.previous_frame_commit_digest
        ),
        "previous_grid": tensor_payload(
            state.previous_grid
        ),
        "previous_structural_attempt_digest": (
            state.previous_structural_attempt_digest
        ),
        "structural_attempt_budget": (
            state.structural_attempt_budget
        ),
        "structural_attempt_index": (
            state.structural_attempt_index
        ),
    }


def episode_state_from_payload(
    payload: dict[str, object],
) -> DarwinianEpisodeState:
    return DarwinianEpisodeState(
        episode_id=str(payload["episode_id"]),
        previous_grid=tensor_from_payload(
            dict(payload["previous_grid"])
        ),
        clamp_state=clamp_state_from_payload(
            dict(payload["clamp_state"])
        ),
        climate_state=climate_state_from_payload(
            dict(payload["climate_state"])
        ),
        ecology_state=ecology_state_from_payload(
            dict(payload["ecology_state"])
        ),
        meta_state=meta_state_from_payload(
            dict(payload["meta_state"])
        ),
        structural_attempt_index=int(
            payload["structural_attempt_index"]
        ),
        structural_attempt_budget=int(
            payload["structural_attempt_budget"]
        ),
        previous_ecology_record_digest=str(
            payload[
                "previous_ecology_record_digest"
            ]
        ),
        previous_frame_commit_digest=str(
            payload[
                "previous_frame_commit_digest"
            ]
        ),
        previous_structural_attempt_digest=str(
            payload[
                "previous_structural_attempt_digest"
            ]
        ),
        disposition=EpisodeDisposition(
            str(payload["disposition"])
        ),
    )


def adapter_replay_spec(
    adapter: FrozenStructuralAdapter,
) -> dict[str, object]:
    if isinstance(
        adapter,
        DeterministicSudokuReferenceAdapter,
    ):
        return {
            "adapter_class": REFERENCE_ADAPTER_CLASS,
            "manifest_digest": (
                adapter.manifest.digest()
            ),
            "max_search_nodes": (
                adapter.max_search_nodes
            ),
        }

    raise TypeError(
        "Adapter is not registered for autonomous "
        "episode replay."
    )


def adapter_from_replay_spec(
    payload: dict[str, object],
) -> FrozenStructuralAdapter:
    adapter_class = str(
        payload["adapter_class"]
    )

    if adapter_class != REFERENCE_ADAPTER_CLASS:
        raise ValueError(
            "Unsupported archived adapter class: "
            + adapter_class
        )

    adapter = DeterministicSudokuReferenceAdapter(
        max_search_nodes=int(
            payload["max_search_nodes"]
        )
    )

    expected_manifest = str(
        payload["manifest_digest"]
    )

    if adapter.manifest.digest() != expected_manifest:
        raise ValueError(
            "Reconstructed adapter manifest mismatch."
        )

    return adapter


@dataclass(frozen=True)
class EpisodeAttemptCapture:
    state_before: DarwinianEpisodeState
    random_seed: int
    adapter: FrozenStructuralAdapter
    result: EpisodeAdvanceResult

    def __post_init__(self) -> None:
        if self.random_seed < 0:
            raise ValueError(
                "random_seed cannot be negative."
            )


@dataclass(frozen=True)
class ArchivedEpisodeAttempt:
    schema_version: str
    attempt_index: int
    random_seed: int

    adapter_spec: dict[str, object]

    state_before_digest: str
    state_after_digest: str

    structural_attempt_digest: str
    refinement_result_digest: str
    outcome: str

    close_receipt_digest: str | None

    def __post_init__(self) -> None:
        if (
            self.schema_version
            != ARCHIVED_ATTEMPT_SCHEMA
        ):
            raise ValueError(
                "Unsupported archived-attempt schema."
            )

        if self.attempt_index < 0:
            raise ValueError(
                "attempt_index cannot be negative."
            )

        if self.random_seed < 0:
            raise ValueError(
                "random_seed cannot be negative."
            )

        for name in (
            "state_before_digest",
            "state_after_digest",
            "structural_attempt_digest",
            "refinement_result_digest",
        ):
            require_digest(
                name,
                getattr(self, name),
            )

        optional_digest(
            self.close_receipt_digest
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "adapter_spec": self.adapter_spec,
            "attempt_index": self.attempt_index,
            "close_receipt_digest": (
                self.close_receipt_digest
            ),
            "outcome": self.outcome,
            "random_seed": self.random_seed,
            "refinement_result_digest": (
                self.refinement_result_digest
            ),
            "schema_version": self.schema_version,
            "state_after_digest": (
                self.state_after_digest
            ),
            "state_before_digest": (
                self.state_before_digest
            ),
            "structural_attempt_digest": (
                self.structural_attempt_digest
            ),
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, object],
    ) -> "ArchivedEpisodeAttempt":
        return cls(
            schema_version=str(
                payload["schema_version"]
            ),
            attempt_index=int(
                payload["attempt_index"]
            ),
            random_seed=int(
                payload["random_seed"]
            ),
            adapter_spec=dict(
                payload["adapter_spec"]
            ),
            state_before_digest=str(
                payload["state_before_digest"]
            ),
            state_after_digest=str(
                payload["state_after_digest"]
            ),
            structural_attempt_digest=str(
                payload["structural_attempt_digest"]
            ),
            refinement_result_digest=str(
                payload["refinement_result_digest"]
            ),
            outcome=str(payload["outcome"]),
            close_receipt_digest=(
                str(payload["close_receipt_digest"])
                if payload["close_receipt_digest"]
                is not None
                else None
            ),
        )


@dataclass(frozen=True)
class EpisodeArchive:
    schema_version: str
    initial_state_snapshot: dict[str, object]
    initial_state_digest: str

    execution_contract: dict[str, object]
    attempts: tuple[ArchivedEpisodeAttempt, ...]

    final_state_digest: str
    archive_digest: str

    def __post_init__(self) -> None:
        if self.schema_version != EPISODE_ARCHIVE_SCHEMA:
            raise ValueError(
                "Unsupported episode-archive schema."
            )

        if not self.attempts:
            raise ValueError(
                "A complete episode archive requires "
                "at least one attempt."
            )

        require_digest(
            "initial_state_digest",
            self.initial_state_digest,
        )
        require_digest(
            "final_state_digest",
            self.final_state_digest,
        )
        require_digest(
            "archive_digest",
            self.archive_digest,
        )

    def semantic_payload(self) -> dict[str, object]:
        return {
            "attempts": [
                attempt.canonical_payload()
                for attempt in self.attempts
            ],
            "execution_contract": (
                self.execution_contract
            ),
            "final_state_digest": (
                self.final_state_digest
            ),
            "initial_state_digest": (
                self.initial_state_digest
            ),
            "initial_state_snapshot": (
                self.initial_state_snapshot
            ),
            "schema_version": self.schema_version,
        }

    def recompute_digest(self) -> str:
        return domain_digest(
            EPISODE_ARCHIVE_SCHEMA,
            self.semantic_payload(),
        )

    def validate_digest(self) -> bool:
        return (
            self.archive_digest
            == self.recompute_digest()
        )

    def to_dict(self) -> dict[str, object]:
        payload = self.semantic_payload()
        payload["archive_digest"] = (
            self.archive_digest
        )
        return payload

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, object],
    ) -> "EpisodeArchive":
        return cls(
            schema_version=str(
                payload["schema_version"]
            ),
            initial_state_snapshot=dict(
                payload["initial_state_snapshot"]
            ),
            initial_state_digest=str(
                payload["initial_state_digest"]
            ),
            execution_contract=dict(
                payload["execution_contract"]
            ),
            attempts=tuple(
                ArchivedEpisodeAttempt.from_dict(
                    dict(attempt)
                )
                for attempt in payload["attempts"]
            ),
            final_state_digest=str(
                payload["final_state_digest"]
            ),
            archive_digest=str(
                payload["archive_digest"]
            ),
        )


@dataclass(frozen=True)
class EpisodeArchiveReplayResult:
    passed: bool
    attempts_replayed: int
    failure_codes: tuple[str, ...]

    expected_final_state_digest: str
    observed_final_state_digest: str

    final_state: DarwinianEpisodeState


def build_episode_archive(
    *,
    initial_state: DarwinianEpisodeState,
    captures: Sequence[EpisodeAttemptCapture],
    target_viability: float,
    neighbors: Tensor,
    config: EcologyTransactionConfig | None = None,
    region_map: Tensor | None = None,
    epsilon: float = 1e-3,
    window: int = 4,
) -> EpisodeArchive:
    if not captures:
        raise ValueError(
            "A complete episode archive requires captures."
        )

    config = config or EcologyTransactionConfig()

    if region_map is None:
        region_map = build_region_map()

    current_digest = initial_state.digest()
    archived_attempts: list[
        ArchivedEpisodeAttempt
    ] = []

    for expected_index, capture in enumerate(
        captures
    ):
        before_digest = (
            capture.state_before.digest()
        )

        if before_digest != current_digest:
            raise ValueError(
                "Episode capture chain is discontinuous "
                f"at attempt {expected_index}."
            )

        record = (
            capture.result.structural_result
            .attempt_record
        )

        if (
            record.structural_attempt_index
            != expected_index
        ):
            raise ValueError(
                "Captured structural-attempt index "
                "does not match archive order."
            )

        close_digest = (
            capture.result.clamp_close_receipt
            .receipt_digest
            if capture.result.clamp_close_receipt
            is not None
            else None
        )

        archived_attempts.append(
            ArchivedEpisodeAttempt(
                schema_version=(
                    ARCHIVED_ATTEMPT_SCHEMA
                ),
                attempt_index=expected_index,
                random_seed=capture.random_seed,
                adapter_spec=adapter_replay_spec(
                    capture.adapter
                ),
                state_before_digest=before_digest,
                state_after_digest=(
                    capture.result.state.digest()
                ),
                structural_attempt_digest=(
                    record.attempt_digest
                ),
                refinement_result_digest=(
                    capture.result.structural_result
                    .refinement_result.result_digest
                ),
                outcome=(
                    capture.result.structural_result
                    .outcome
                ),
                close_receipt_digest=close_digest,
            )
        )

        current_digest = (
            capture.result.state.digest()
        )

    final_state = captures[-1].result.state

    if not final_state.closed:
        raise ValueError(
            "A complete episode archive must end "
            "in a terminal episode state."
        )

    execution_contract = {
        "config": config_payload(config),
        "epsilon": float(epsilon),
        "neighbors": tensor_payload(neighbors),
        "region_map": tensor_payload(region_map),
        "target_viability": float(
            target_viability
        ),
        "window": int(window),
    }

    partial = EpisodeArchive(
        schema_version=EPISODE_ARCHIVE_SCHEMA,
        initial_state_snapshot=(
            episode_state_payload(initial_state)
        ),
        initial_state_digest=(
            initial_state.digest()
        ),
        execution_contract=execution_contract,
        attempts=tuple(archived_attempts),
        final_state_digest=final_state.digest(),
        archive_digest="0" * 64,
    )

    return EpisodeArchive(
        schema_version=partial.schema_version,
        initial_state_snapshot=(
            partial.initial_state_snapshot
        ),
        initial_state_digest=(
            partial.initial_state_digest
        ),
        execution_contract=(
            partial.execution_contract
        ),
        attempts=partial.attempts,
        final_state_digest=(
            partial.final_state_digest
        ),
        archive_digest=partial.recompute_digest(),
    )


def write_episode_archive(
    path: str | Path,
    archive: EpisodeArchive,
) -> None:
    if not archive.validate_digest():
        raise ValueError(
            "Cannot write an invalid episode archive."
        )

    destination = Path(path)
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination.write_bytes(
        canonical_json_bytes(
            archive.to_dict()
        )
        + b"\n"
    )


def load_episode_archive(
    path: str | Path,
) -> EpisodeArchive:
    payload = json.loads(
        Path(path).read_text()
    )

    archive = EpisodeArchive.from_dict(
        payload
    )

    if not archive.validate_digest():
        raise ValueError(
            "Episode archive digest mismatch."
        )

    initial = episode_state_from_payload(
        archive.initial_state_snapshot
    )

    if initial.digest() != archive.initial_state_digest:
        raise ValueError(
            "Episode archive initial-state digest mismatch."
        )

    return archive


def replay_episode_archive(
    archive: EpisodeArchive,
) -> EpisodeArchiveReplayResult:
    failures: list[str] = []

    if not archive.validate_digest():
        failures.append(
            "ARCHIVE_DIGEST_MISMATCH"
        )

    state = episode_state_from_payload(
        archive.initial_state_snapshot
    )

    if state.digest() != archive.initial_state_digest:
        failures.append(
            "INITIAL_STATE_DIGEST_MISMATCH"
        )

    execution = archive.execution_contract

    config = config_from_payload(
        dict(execution["config"])
    )
    neighbors = tensor_from_payload(
        dict(execution["neighbors"])
    )
    region_map = tensor_from_payload(
        dict(execution["region_map"])
    )

    target_viability = float(
        execution["target_viability"]
    )
    epsilon = float(execution["epsilon"])
    window = int(execution["window"])

    attempts_replayed = 0

    for expected_index, archived in enumerate(
        archive.attempts
    ):
        if archived.attempt_index != expected_index:
            failures.append(
                "ATTEMPT_INDEX_MISMATCH"
            )

        if state.digest() != archived.state_before_digest:
            failures.append(
                f"STATE_BEFORE_MISMATCH:{expected_index}"
            )

        if state.closed:
            failures.append(
                f"EARLY_TERMINAL_STATE:{expected_index}"
            )
            break

        adapter = adapter_from_replay_spec(
            archived.adapter_spec
        )

        result = advance_episode(
            state=state,
            random_seed=archived.random_seed,
            adapter=adapter,
            target_viability=target_viability,
            neighbors=neighbors,
            config=config,
            region_map=region_map,
            epsilon=epsilon,
            window=window,
        )

        attempts_replayed += 1

        observed_close = (
            result.clamp_close_receipt.receipt_digest
            if result.clamp_close_receipt is not None
            else None
        )

        comparisons = (
            (
                "STATE_AFTER",
                result.state.digest(),
                archived.state_after_digest,
            ),
            (
                "STRUCTURAL_ATTEMPT",
                result.structural_result
                .attempt_record.attempt_digest,
                archived.structural_attempt_digest,
            ),
            (
                "REFINEMENT_RESULT",
                result.structural_result
                .refinement_result.result_digest,
                archived.refinement_result_digest,
            ),
            (
                "OUTCOME",
                result.structural_result.outcome,
                archived.outcome,
            ),
            (
                "CLOSE_RECEIPT",
                observed_close,
                archived.close_receipt_digest,
            ),
        )

        for label, observed, expected in comparisons:
            if observed != expected:
                failures.append(
                    f"{label}_MISMATCH:"
                    f"{expected_index}"
                )

        state = result.state

    if state.digest() != archive.final_state_digest:
        failures.append(
            "FINAL_STATE_DIGEST_MISMATCH"
        )

    if not state.closed:
        failures.append(
            "FINAL_STATE_NOT_TERMINAL"
        )

    return EpisodeArchiveReplayResult(
        passed=not failures,
        attempts_replayed=attempts_replayed,
        failure_codes=tuple(failures),
        expected_final_state_digest=(
            archive.final_state_digest
        ),
        observed_final_state_digest=(
            state.digest()
        ),
        final_state=state,
    )
