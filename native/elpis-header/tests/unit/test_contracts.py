from __future__ import annotations

import dataclasses

import pytest

from elpis_header.contracts import (
    DraftStateLease,
    InvalidDraftLeaseError,
    LeaseInvalidationReason,
    ObservationWindow,
    RoleSource,
    SealedHeaderState,
    TokenObservation,
)
from elpis_header.core import HeaderDisposition


def d(char: str) -> str:
    return char * 64


def token(*, ordinal: int = 0, position: int = 10, epoch: int = 0) -> TokenObservation:
    return TokenObservation(
        epoch_ordinal=epoch,
        within_epoch_ordinal=ordinal,
        accepted_target_position=position,
        role_mass=(1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        role_sources=(RoleSource.TEMPLATE,) * 9,
        semantic_residual=(0.0,) * 6,
        confidence=1.0,
        source_token_digest=d("1"),
        source_hidden_digest=d("2"),
        observer_policy_digest=d("3"),
        semantic_basis_digest=d("4"),
    )


def test_token_observation_is_frozen_and_deterministic() -> None:
    first = token()
    assert first.identity() == token().identity()
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.confidence = 0.5  # type: ignore[misc]


def test_token_observation_rejects_non_normalized_role_mass() -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        TokenObservation(
            epoch_ordinal=0,
            within_epoch_ordinal=0,
            accepted_target_position=0,
            role_mass=(0.0,) * 9,
            role_sources=(RoleSource.PROBE,) * 9,
            semantic_residual=(0.0,) * 6,
            confidence=0.5,
            source_token_digest=d("1"),
            source_hidden_digest=d("2"),
            observer_policy_digest=d("3"),
            semantic_basis_digest=d("4"),
        )


def test_window_requires_contiguous_ordinals_and_positions() -> None:
    with pytest.raises(ValueError, match="contiguous"):
        ObservationWindow(
            epoch_ordinal=0,
            host_identity_digest=d("5"),
            observer_policy_digest=d("3"),
            semantic_basis_digest=d("4"),
            records=(token(ordinal=1),),
        )

    with pytest.raises(ValueError, match="strictly increasing"):
        ObservationWindow(
            epoch_ordinal=0,
            host_identity_digest=d("5"),
            observer_policy_digest=d("3"),
            semantic_basis_digest=d("4"),
            records=(token(ordinal=0, position=10), token(ordinal=1, position=10)),
        )


def state(*, refresh_policy: str = "8") -> SealedHeaderState:
    return SealedHeaderState(
        epoch_ordinal=0,
        grid81_state_digest=d("1"),
        observation_window_digest=d("2"),
        previous_state_digest=None,
        core_config_digest=d("3"),
        semantic_basis_digest=d("4"),
        refresh_policy_digest=d(refresh_policy),
        lease_policy_digest=d("6"),
        boundary_detector_policy_digest=d("7"),
        inner_recursion_policy_digest=d("9"),
        outer_stability_policy_digest=d("a"),
        population_digest=d("b"),
        selection_receipt_digest=d("c"),
    )


def test_state_identity_binds_policy_digests() -> None:
    assert (
        state(refresh_policy="8").identity().canonical_payload_digest
        != state(refresh_policy="d").identity().canonical_payload_digest
    )


def lease() -> DraftStateLease:
    return DraftStateLease(
        epoch_ordinal=0,
        lease_ordinal=0,
        state_digest=d("1"),
        host_identity_digest=d("2"),
        sealed_at_target_position=100,
        max_draft_token_age=8,
        actuation_ordinal_at_issue=0,
        refresh_policy_digest=d("3"),
        lease_policy_digest=d("4"),
        boundary_detector_policy_digest=d("5"),
    )


def test_lease_valid_at_inclusive_age_bound() -> None:
    lease().validate_context(
        current_target_position=108,
        current_state_digest=d("1"),
        current_host_identity_digest=d("2"),
        current_actuation_ordinal=0,
    )


def test_lease_invalidates_after_actuation() -> None:
    with pytest.raises(InvalidDraftLeaseError) as exc:
        lease().validate_context(
            current_target_position=101,
            current_state_digest=d("1"),
            current_host_identity_digest=d("2"),
            current_actuation_ordinal=1,
        )
    assert exc.value.reason is LeaseInvalidationReason.ACTUATION_OCCURRED


def test_lease_invalidates_after_age_bound() -> None:
    with pytest.raises(InvalidDraftLeaseError) as exc:
        lease().validate_context(
            current_target_position=109,
            current_state_digest=d("1"),
            current_host_identity_digest=d("2"),
            current_actuation_ordinal=0,
        )
    assert exc.value.reason is LeaseInvalidationReason.AGE_EXCEEDED


def test_dispositions_do_not_conflate_activity_with_quiescence() -> None:
    assert HeaderDisposition.CONTROL_STILL_ACTIVE != HeaderDisposition.SEALED
    assert HeaderDisposition.OSCILLATORY != HeaderDisposition.OUTER_BUDGET_EXHAUSTED
