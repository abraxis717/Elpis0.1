"""Persistent Darwinian Matrix episode ownership.

This module owns:

- the current solved Grid81;
- projector clamp state;
- climate, ecology, and meta-episode state;
- structural-attempt indexing;
- structural-attempt budget;
- ecology, frame, and structural ledger heads;
- deterministic clamp release when the episode closes.

A rejected structural refinement consumes one structural attempt but does not
advance the ecological frame index.

The production TRM remains outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Iterable, Sequence

import torch
from torch import Tensor

from ..climate.state import ClimateDynamicsState
from ..ecology.engine import EcologyState
from ..ecology.transaction import EcologyTransactionConfig
from ..geometry import require_solved_grid81
from ..ledger.records import GENESIS_RECORD_DIGEST
from ..projector.constraints import (
    ClampState,
    ClampTransaction,
    ClampTransactionReceipt,
    apply_clamp_transaction,
)
from ..trm.contract import FrozenStructuralAdapter
from .structural_frame import (
    StructuralFrameTransactionResult,
    advance_structural_frame_transaction,
)
from .verdict import MetaEpisodeState


EPISODE_STATE_SCHEMA = "darwinian.episode-state.v1"


class EpisodeDisposition(str, Enum):
    RUNNING = "RUNNING"
    META_EPISODE_TERMINAL = "META_EPISODE_TERMINAL"
    STRUCTURAL_ATTEMPT_BUDGET_EXHAUSTED = (
        "STRUCTURAL_ATTEMPT_BUDGET_EXHAUSTED"
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


def _clone_clamp_state(
    state: ClampState,
) -> ClampState:
    return ClampState(
        episode_id=state.episode_id,
        version=state.version,
        closed=state.closed,
        active_mask=state.active_mask,
        values=state.values,
        owners=state.owners,
    )


class DarwinianEpisodeState:
    """Immutable-by-interface persistent episode state."""

    __slots__ = (
        "_episode_id",
        "_previous_grid",
        "_clamp_state",
        "_climate_state",
        "_ecology_state",
        "_meta_state",
        "_structural_attempt_index",
        "_structural_attempt_budget",
        "_previous_ecology_record_digest",
        "_previous_frame_commit_digest",
        "_previous_structural_attempt_digest",
        "_disposition",
    )

    def __init__(
        self,
        *,
        episode_id: str,
        previous_grid: Tensor | Sequence[int] | Iterable[int],
        clamp_state: ClampState,
        climate_state: ClimateDynamicsState,
        ecology_state: EcologyState,
        meta_state: MetaEpisodeState,
        structural_attempt_index: int,
        structural_attempt_budget: int,
        previous_ecology_record_digest: str = (
            GENESIS_RECORD_DIGEST
        ),
        previous_frame_commit_digest: str = (
            GENESIS_RECORD_DIGEST
        ),
        previous_structural_attempt_digest: str = (
            GENESIS_RECORD_DIGEST
        ),
        disposition: EpisodeDisposition = (
            EpisodeDisposition.RUNNING
        ),
    ) -> None:
        if not episode_id:
            raise ValueError(
                "episode_id cannot be empty."
            )

        if structural_attempt_index < 0:
            raise ValueError(
                "structural_attempt_index cannot be negative."
            )

        if structural_attempt_budget <= 0:
            raise ValueError(
                "structural_attempt_budget must be positive."
            )

        if (
            structural_attempt_index
            > structural_attempt_budget
        ):
            raise ValueError(
                "structural_attempt_index cannot exceed "
                "the structural-attempt budget."
            )

        for name, value in (
            (
                "previous_ecology_record_digest",
                previous_ecology_record_digest,
            ),
            (
                "previous_frame_commit_digest",
                previous_frame_commit_digest,
            ),
            (
                "previous_structural_attempt_digest",
                previous_structural_attempt_digest,
            ),
        ):
            _require_digest(name, value)

        validated_grid = require_solved_grid81(
            previous_grid
        )

        self._episode_id = episode_id
        self._previous_grid = tuple(
            int(value)
            for value in validated_grid.tolist()
        )
        self._clamp_state = _clone_clamp_state(
            clamp_state
        )
        self._climate_state = climate_state.clone()
        self._ecology_state = ecology_state.clone()
        self._meta_state = meta_state
        self._structural_attempt_index = int(
            structural_attempt_index
        )
        self._structural_attempt_budget = int(
            structural_attempt_budget
        )
        self._previous_ecology_record_digest = (
            previous_ecology_record_digest
        )
        self._previous_frame_commit_digest = (
            previous_frame_commit_digest
        )
        self._previous_structural_attempt_digest = (
            previous_structural_attempt_digest
        )
        self._disposition = EpisodeDisposition(
            disposition
        )

        self._validate()

    @classmethod
    def initial(
        cls,
        *,
        episode_id: str,
        previous_grid: Tensor | Sequence[int] | Iterable[int],
        ecology_state: EcologyState,
        meta_attempt_budget: int,
        structural_attempt_budget: int,
        clamp_state: ClampState | None = None,
        climate_state: ClimateDynamicsState | None = None,
    ) -> "DarwinianEpisodeState":
        if clamp_state is None:
            clamp_state = ClampState.empty(
                episode_id
            )

        if climate_state is None:
            climate_state = ClimateDynamicsState.empty(
                device=ecology_state.device
            )

        meta_state = MetaEpisodeState(
            meta_id=episode_id,
            attempt_budget=meta_attempt_budget,
        )

        return cls(
            episode_id=episode_id,
            previous_grid=previous_grid,
            clamp_state=clamp_state,
            climate_state=climate_state,
            ecology_state=ecology_state,
            meta_state=meta_state,
            structural_attempt_index=0,
            structural_attempt_budget=(
                structural_attempt_budget
            ),
        )

    def _validate(self) -> None:
        if self._clamp_state.episode_id != self._episode_id:
            raise ValueError(
                "Clamp-state episode identity mismatch."
            )

        if self._meta_state.meta_id != self._episode_id:
            raise ValueError(
                "Meta-state episode identity mismatch."
            )

        if (
            self._meta_state.attempt_index
            > self._structural_attempt_index
        ):
            raise ValueError(
                "Committed frame count cannot exceed "
                "structural-attempt count."
            )

        if self._structural_attempt_index == 0:
            if (
                self._previous_structural_attempt_digest
                != GENESIS_RECORD_DIGEST
            ):
                raise ValueError(
                    "Unstarted episode must use the genesis "
                    "structural-attempt digest."
                )
        elif (
            self._previous_structural_attempt_digest
            == GENESIS_RECORD_DIGEST
        ):
            raise ValueError(
                "Started episode cannot retain the genesis "
                "structural-attempt digest."
            )

        if self._meta_state.attempt_index == 0:
            if (
                self._previous_ecology_record_digest
                != GENESIS_RECORD_DIGEST
            ):
                raise ValueError(
                    "Episode with no committed frames must use "
                    "the genesis ecology-record digest."
                )

            if (
                self._previous_frame_commit_digest
                != GENESIS_RECORD_DIGEST
            ):
                raise ValueError(
                    "Episode with no committed frames must use "
                    "the genesis frame-commit digest."
                )
        else:
            if (
                self._previous_ecology_record_digest
                == GENESIS_RECORD_DIGEST
            ):
                raise ValueError(
                    "Committed episode frames require a non-genesis "
                    "ecology-record digest."
                )

            if (
                self._previous_frame_commit_digest
                == GENESIS_RECORD_DIGEST
            ):
                raise ValueError(
                    "Committed episode frames require a non-genesis "
                    "frame-commit digest."
                )

        if self._disposition == EpisodeDisposition.RUNNING:
            if self._clamp_state.closed:
                raise ValueError(
                    "Running episode cannot have closed clamps."
                )

            if self._meta_state.closed:
                raise ValueError(
                    "Running episode cannot contain a terminal "
                    "meta-episode."
                )

            if (
                self._structural_attempt_index
                >= self._structural_attempt_budget
            ):
                raise ValueError(
                    "Running episode has exhausted its structural "
                    "attempt budget."
                )

        elif (
            self._disposition
            == EpisodeDisposition.META_EPISODE_TERMINAL
        ):
            if not self._meta_state.closed:
                raise ValueError(
                    "META_EPISODE_TERMINAL requires a closed "
                    "meta-episode."
                )

            if not self._clamp_state.closed:
                raise ValueError(
                    "Terminal episode must close its clamp state."
                )

        elif (
            self._disposition
            == EpisodeDisposition
            .STRUCTURAL_ATTEMPT_BUDGET_EXHAUSTED
        ):
            if (
                self._structural_attempt_index
                < self._structural_attempt_budget
            ):
                raise ValueError(
                    "Structural-budget disposition requires "
                    "budget exhaustion."
                )

            if not self._clamp_state.closed:
                raise ValueError(
                    "Budget-exhausted episode must close clamps."
                )

        if self.closed and self._clamp_state.active_count != 0:
            raise ValueError(
                "Closed episode retained active task clamps."
            )

    @property
    def episode_id(self) -> str:
        return self._episode_id

    @property
    def previous_grid(self) -> Tensor:
        return torch.tensor(
            self._previous_grid,
            dtype=torch.int64,
        )

    @property
    def clamp_state(self) -> ClampState:
        return _clone_clamp_state(
            self._clamp_state
        )

    @property
    def climate_state(self) -> ClimateDynamicsState:
        return self._climate_state.clone()

    @property
    def ecology_state(self) -> EcologyState:
        return self._ecology_state.clone()

    @property
    def meta_state(self) -> MetaEpisodeState:
        return self._meta_state

    @property
    def structural_attempt_index(self) -> int:
        return self._structural_attempt_index

    @property
    def structural_attempt_budget(self) -> int:
        return self._structural_attempt_budget

    @property
    def previous_ecology_record_digest(self) -> str:
        return self._previous_ecology_record_digest

    @property
    def previous_frame_commit_digest(self) -> str:
        return self._previous_frame_commit_digest

    @property
    def previous_structural_attempt_digest(self) -> str:
        return self._previous_structural_attempt_digest

    @property
    def disposition(self) -> EpisodeDisposition:
        return self._disposition

    @property
    def closed(self) -> bool:
        return self._disposition != EpisodeDisposition.RUNNING

    def canonical_payload(self) -> dict[str, object]:
        return {
            "clamp_state_digest": (
                self._clamp_state.digest()
            ),
            "climate_state_digest": (
                self._climate_state.digest()
            ),
            "disposition": self._disposition.value,
            "ecology_state_digest": (
                self._ecology_state.digest()
            ),
            "episode_id": self._episode_id,
            "meta_state_digest": (
                self._meta_state.digest()
            ),
            "previous_ecology_record_digest": (
                self._previous_ecology_record_digest
            ),
            "previous_frame_commit_digest": (
                self._previous_frame_commit_digest
            ),
            "previous_grid": list(
                self._previous_grid
            ),
            "previous_structural_attempt_digest": (
                self._previous_structural_attempt_digest
            ),
            "schema_version": EPISODE_STATE_SCHEMA,
            "structural_attempt_budget": (
                self._structural_attempt_budget
            ),
            "structural_attempt_index": (
                self._structural_attempt_index
            ),
        }

    def digest(self) -> str:
        return _domain_digest(
            EPISODE_STATE_SCHEMA,
            self.canonical_payload(),
        )


@dataclass(frozen=True)
class EpisodeAdvanceResult:
    state: DarwinianEpisodeState
    structural_result: StructuralFrameTransactionResult
    clamp_close_receipt: ClampTransactionReceipt | None

    @property
    def closed(self) -> bool:
        return self.state.closed


@dataclass(frozen=True)
class EpisodeAdvanceReplayResult:
    passed: bool

    expected_state_digest: str
    observed_state_digest: str

    expected_structural_attempt_digest: str
    observed_structural_attempt_digest: str

    expected_close_receipt_digest: str | None
    observed_close_receipt_digest: str | None


def advance_episode(
    *,
    state: DarwinianEpisodeState,
    random_seed: int,
    adapter: FrozenStructuralAdapter,
    target_viability: float,
    neighbors: Tensor,
    config: EcologyTransactionConfig | None = None,
    region_map: Tensor | None = None,
    epsilon: float = 1e-3,
    window: int = 4,
) -> EpisodeAdvanceResult:
    """Advance one structural attempt owned by the episode."""
    if state.closed:
        raise RuntimeError(
            "Cannot advance a closed Darwinian episode."
        )

    before_digest = state.digest()

    clamp_state = state.clamp_state
    climate_state = state.climate_state
    ecology_state = state.ecology_state
    meta_state = state.meta_state
    previous_grid = state.previous_grid

    structural_result = (
        advance_structural_frame_transaction(
            episode_id=state.episode_id,
            structural_attempt_index=(
                state.structural_attempt_index
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
                state.previous_ecology_record_digest
            ),
            previous_frame_commit_digest=(
                state.previous_frame_commit_digest
            ),
            previous_structural_attempt_digest=(
                state.previous_structural_attempt_digest
            ),
            epsilon=epsilon,
            window=window,
        )
    )

    next_attempt_index = (
        state.structural_attempt_index + 1
    )

    next_grid = previous_grid
    next_climate = structural_result.climate_state
    next_ecology = structural_result.ecology_state
    next_meta = structural_result.meta_state

    next_ecology_record_digest = (
        state.previous_ecology_record_digest
    )
    next_frame_commit_digest = (
        state.previous_frame_commit_digest
    )

    if structural_result.committed:
        output = (
            structural_result.refinement_result
            .output_grid()
        )

        if output is None:
            raise RuntimeError(
                "Committed structural attempt has no output Grid81."
            )

        if structural_result.frame_result is None:
            raise RuntimeError(
                "Committed structural attempt has no inner frame."
            )

        next_grid = output
        next_ecology_record_digest = (
            structural_result.frame_result
            .ecology_record.record_digest
        )
        next_frame_commit_digest = (
            structural_result.frame_result
            .commit_record.commit_digest
        )

    next_structural_attempt_digest = (
        structural_result.attempt_record.attempt_digest
    )

    disposition = EpisodeDisposition.RUNNING

    if next_meta.closed:
        disposition = (
            EpisodeDisposition.META_EPISODE_TERMINAL
        )
    elif (
        next_attempt_index
        >= state.structural_attempt_budget
    ):
        disposition = (
            EpisodeDisposition
            .STRUCTURAL_ATTEMPT_BUDGET_EXHAUSTED
        )

    next_clamp = clamp_state
    close_receipt: ClampTransactionReceipt | None = None

    if disposition != EpisodeDisposition.RUNNING:
        close_transaction = ClampTransaction(
            transaction_id=(
                f"{state.episode_id}:close:"
                f"{next_attempt_index}:"
                f"{disposition.value}"
            ),
            episode_id=state.episode_id,
            expected_state_digest=(
                next_clamp.digest()
            ),
            close_episode=True,
        )

        close_result = apply_clamp_transaction(
            state=next_clamp,
            transaction=close_transaction,
        )

        if not close_result.accepted:
            raise RuntimeError(
                "Episode closure failed to release task clamps: "
                + repr(
                    close_result.receipt.reason_codes
                )
            )

        next_clamp = close_result.state
        close_receipt = close_result.receipt

    next_state = DarwinianEpisodeState(
        episode_id=state.episode_id,
        previous_grid=next_grid,
        clamp_state=next_clamp,
        climate_state=next_climate,
        ecology_state=next_ecology,
        meta_state=next_meta,
        structural_attempt_index=(
            next_attempt_index
        ),
        structural_attempt_budget=(
            state.structural_attempt_budget
        ),
        previous_ecology_record_digest=(
            next_ecology_record_digest
        ),
        previous_frame_commit_digest=(
            next_frame_commit_digest
        ),
        previous_structural_attempt_digest=(
            next_structural_attempt_digest
        ),
        disposition=disposition,
    )

    if state.digest() != before_digest:
        raise RuntimeError(
            "Episode advance mutated its input state."
        )

    return EpisodeAdvanceResult(
        state=next_state,
        structural_result=structural_result,
        clamp_close_receipt=close_receipt,
    )


def replay_episode_advance(
    *,
    expected_result: EpisodeAdvanceResult,
    state: DarwinianEpisodeState,
    random_seed: int,
    adapter: FrozenStructuralAdapter,
    target_viability: float,
    neighbors: Tensor,
    config: EcologyTransactionConfig | None = None,
    region_map: Tensor | None = None,
    epsilon: float = 1e-3,
    window: int = 4,
) -> tuple[
    EpisodeAdvanceResult,
    EpisodeAdvanceReplayResult,
]:
    observed = advance_episode(
        state=state,
        random_seed=random_seed,
        adapter=adapter,
        target_viability=target_viability,
        neighbors=neighbors,
        config=config,
        region_map=region_map,
        epsilon=epsilon,
        window=window,
    )

    expected_close_digest = (
        expected_result.clamp_close_receipt
        .receipt_digest
        if expected_result.clamp_close_receipt
        is not None
        else None
    )

    observed_close_digest = (
        observed.clamp_close_receipt.receipt_digest
        if observed.clamp_close_receipt is not None
        else None
    )

    passed = (
        observed.state.digest()
        == expected_result.state.digest()
        and observed.structural_result
        .attempt_record.attempt_digest
        == expected_result.structural_result
        .attempt_record.attempt_digest
        and observed.structural_result
        .refinement_result.result_digest
        == expected_result.structural_result
        .refinement_result.result_digest
        and observed_close_digest
        == expected_close_digest
    )

    return (
        observed,
        EpisodeAdvanceReplayResult(
            passed=passed,
            expected_state_digest=(
                expected_result.state.digest()
            ),
            observed_state_digest=(
                observed.state.digest()
            ),
            expected_structural_attempt_digest=(
                expected_result.structural_result
                .attempt_record.attempt_digest
            ),
            observed_structural_attempt_digest=(
                observed.structural_result
                .attempt_record.attempt_digest
            ),
            expected_close_receipt_digest=(
                expected_close_digest
            ),
            observed_close_receipt_digest=(
                observed_close_digest
            ),
        ),
    )
