"""Replay verification for one ecological transaction frame."""

from __future__ import annotations

from dataclasses import dataclass

from torch import Tensor

from ..ecology.engine import EcologyState
from ..ecology.transaction import (
    EcologyStepTelemetry,
    EcologyTransactionConfig,
    advance_ecology_transaction,
)
from ..geometry import LatticeClimateView
from ..ledger.records import (
    EcologyFrameRecord,
    build_frame_record,
)


@dataclass(frozen=True)
class ReplayResult:
    passed: bool
    observed_state_digest: str
    expected_state_digest: str
    observed_telemetry_digest: str
    expected_telemetry_digest: str
    observed_record_digest: str
    expected_record_digest: str


def replay_frame(
    *,
    expected_record: EcologyFrameRecord,
    state_before: EcologyState,
    climate: LatticeClimateView,
    transition_age: Tensor,
    neighbors: Tensor,
    config: EcologyTransactionConfig,
) -> tuple[
    EcologyState,
    EcologyStepTelemetry,
    ReplayResult,
]:
    state_after, telemetry = advance_ecology_transaction(
        state=state_before,
        climate=climate,
        transition_age=transition_age,
        neighbors=neighbors,
        config=config,
    )

    observed_record = build_frame_record(
        episode_id=expected_record.episode_id,
        frame_index=expected_record.frame_index,
        random_seed=expected_record.random_seed,
        state_before=state_before,
        state_after=state_after,
        climate=climate,
        transition_age=transition_age,
        neighbors=neighbors,
        config=config,
        telemetry=telemetry,
        previous_record_digest=(
            expected_record.previous_record_digest
        ),
    )

    passed = (
        expected_record.validate_digest()
        and state_after.digest()
        == expected_record.state_after_digest
        and telemetry.digest()
        == expected_record.telemetry_digest
        and observed_record.record_digest
        == expected_record.record_digest
    )

    return (
        state_after,
        telemetry,
        ReplayResult(
            passed=passed,
            observed_state_digest=state_after.digest(),
            expected_state_digest=(
                expected_record.state_after_digest
            ),
            observed_telemetry_digest=telemetry.digest(),
            expected_telemetry_digest=(
                expected_record.telemetry_digest
            ),
            observed_record_digest=(
                observed_record.record_digest
            ),
            expected_record_digest=(
                expected_record.record_digest
            ),
        ),
    )
