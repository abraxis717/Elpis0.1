from __future__ import annotations

from DarwinianMatrix.projector.constraints import (
    ClampOperation,
    ClampProposal,
    ClampState,
    ClampTransaction,
    apply_clamp_transaction,
)
from DarwinianMatrix.projector.gaps import (
    EvidenceSlot,
    detect_gaps,
)


EVIDENCE_A = "a" * 64
EVIDENCE_B = "b" * 64


def proposal(
    proposal_id: str,
    operation: ClampOperation,
    slot_id: str,
    cell_index: int,
    value: int | None = None,
    evidence_digest: str = EVIDENCE_A,
) -> ClampProposal:
    return ClampProposal(
        proposal_id=proposal_id,
        operation=operation,
        slot_id=slot_id,
        evidence_digest=evidence_digest,
        cell_index=cell_index,
        value=value,
    )


def transaction(
    state: ClampState,
    *proposals: ClampProposal,
    transaction_id: str = "tx-1",
    close_episode: bool = False,
) -> ClampTransaction:
    return ClampTransaction(
        transaction_id=transaction_id,
        episode_id=state.episode_id,
        expected_state_digest=state.digest(),
        proposals=tuple(proposals),
        close_episode=close_episode,
    )


def asserted_state() -> ClampState:
    state = ClampState.empty("episode-projector")

    result = apply_clamp_transaction(
        state=state,
        transaction=transaction(
            state,
            proposal(
                "proposal-1",
                ClampOperation.ASSERT,
                "slot-a",
                10,
                5,
            ),
        ),
    )

    assert result.accepted
    return result.state


def test_empty_state_is_canonical() -> None:
    first = ClampState.empty("episode-projector")
    second = ClampState.empty("episode-projector")

    assert first.digest() == second.digest()
    assert first.active_count == 0
    assert first.version == 0
    assert not first.closed


def test_assert_transaction_commits_atomically() -> None:
    state = ClampState.empty("episode-projector")

    result = apply_clamp_transaction(
        state=state,
        transaction=transaction(
            state,
            proposal(
                "proposal-1",
                ClampOperation.ASSERT,
                "slot-a",
                10,
                5,
            ),
        ),
    )

    assert result.accepted
    assert state.active_count == 0
    assert result.state.active_count == 1
    assert int(result.state.values[10]) == 5
    assert result.state.owners[10] == "slot-a"
    assert result.state.version == 1
    assert result.receipt.validate_digest()


def test_proposal_order_is_canonical() -> None:
    state = ClampState.empty("episode-projector")

    first_transaction = transaction(
        state,
        proposal(
            "proposal-b",
            ClampOperation.ASSERT,
            "slot-b",
            20,
            7,
            EVIDENCE_B,
        ),
        proposal(
            "proposal-a",
            ClampOperation.ASSERT,
            "slot-a",
            10,
            5,
        ),
        transaction_id="tx-canonical",
    )

    second_transaction = transaction(
        state,
        proposal(
            "proposal-a",
            ClampOperation.ASSERT,
            "slot-a",
            10,
            5,
        ),
        proposal(
            "proposal-b",
            ClampOperation.ASSERT,
            "slot-b",
            20,
            7,
            EVIDENCE_B,
        ),
        transaction_id="tx-canonical",
    )

    first = apply_clamp_transaction(
        state=state,
        transaction=first_transaction,
    )
    second = apply_clamp_transaction(
        state=state,
        transaction=second_transaction,
    )

    assert first_transaction.digest() == (
        second_transaction.digest()
    )
    assert first.state.digest() == second.state.digest()
    assert (
        first.receipt.receipt_digest
        == second.receipt.receipt_digest
    )


def test_duplicate_cell_target_rejects_without_mutation() -> None:
    state = ClampState.empty("episode-projector")

    result = apply_clamp_transaction(
        state=state,
        transaction=transaction(
            state,
            proposal(
                "proposal-a",
                ClampOperation.ASSERT,
                "slot-a",
                10,
                5,
            ),
            proposal(
                "proposal-b",
                ClampOperation.ASSERT,
                "slot-b",
                10,
                7,
                EVIDENCE_B,
            ),
        ),
    )

    assert not result.accepted
    assert result.state is state
    assert result.state.digest() == state.digest()
    assert result.receipt.reason_codes == (
        "DUPLICATE_CELL_TARGET",
    )


def test_assert_occupied_rejects() -> None:
    state = asserted_state()

    result = apply_clamp_transaction(
        state=state,
        transaction=transaction(
            state,
            proposal(
                "proposal-2",
                ClampOperation.ASSERT,
                "slot-a",
                10,
                6,
            ),
        ),
    )

    assert not result.accepted
    assert result.receipt.reason_codes == (
        "ASSERT_TARGET_OCCUPIED",
    )
    assert int(result.state.values[10]) == 5


def test_replace_by_owner_is_explicit() -> None:
    state = asserted_state()

    result = apply_clamp_transaction(
        state=state,
        transaction=transaction(
            state,
            proposal(
                "proposal-2",
                ClampOperation.REPLACE,
                "slot-a",
                10,
                8,
            ),
        ),
    )

    assert result.accepted
    assert int(result.state.values[10]) == 8
    assert result.state.owners[10] == "slot-a"


def test_replace_by_other_owner_rejects() -> None:
    state = asserted_state()

    result = apply_clamp_transaction(
        state=state,
        transaction=transaction(
            state,
            proposal(
                "proposal-2",
                ClampOperation.REPLACE,
                "slot-b",
                10,
                8,
            ),
        ),
    )

    assert not result.accepted
    assert result.receipt.reason_codes == (
        "CLAMP_OWNER_MISMATCH",
    )
    assert int(result.state.values[10]) == 5


def test_release_by_owner() -> None:
    state = asserted_state()

    result = apply_clamp_transaction(
        state=state,
        transaction=transaction(
            state,
            proposal(
                "proposal-2",
                ClampOperation.RELEASE,
                "slot-a",
                10,
            ),
        ),
    )

    assert result.accepted
    assert result.state.active_count == 0
    assert int(result.state.values[10]) == 0
    assert result.state.owners[10] is None


def test_close_episode_releases_every_clamp() -> None:
    state = ClampState.empty("episode-projector")

    asserted = apply_clamp_transaction(
        state=state,
        transaction=transaction(
            state,
            proposal(
                "proposal-a",
                ClampOperation.ASSERT,
                "slot-a",
                10,
                5,
            ),
            proposal(
                "proposal-b",
                ClampOperation.ASSERT,
                "slot-b",
                20,
                7,
                EVIDENCE_B,
            ),
        ),
    ).state

    closed = apply_clamp_transaction(
        state=asserted,
        transaction=transaction(
            asserted,
            transaction_id="tx-close",
            close_episode=True,
        ),
    )

    assert closed.accepted
    assert closed.state.closed
    assert closed.state.active_count == 0
    assert closed.receipt.reason_codes == (
        "META_EPISODE_CLOSED",
        "TASK_CLAMPS_RELEASED",
    )


def test_closed_state_rejects_further_mutation() -> None:
    state = ClampState.empty("episode-projector")

    closed = apply_clamp_transaction(
        state=state,
        transaction=transaction(
            state,
            transaction_id="tx-close",
            close_episode=True,
        ),
    ).state

    result = apply_clamp_transaction(
        state=closed,
        transaction=transaction(
            closed,
            proposal(
                "proposal-late",
                ClampOperation.ASSERT,
                "slot-a",
                10,
                5,
            ),
        ),
    )

    assert not result.accepted
    assert result.receipt.reason_codes == (
        "CLAMP_STATE_CLOSED",
    )


def test_stale_state_digest_rejects() -> None:
    state = ClampState.empty("episode-projector")

    stale_transaction = ClampTransaction(
        transaction_id="tx-stale",
        episode_id=state.episode_id,
        expected_state_digest="f" * 64,
        proposals=(
            proposal(
                "proposal-1",
                ClampOperation.ASSERT,
                "slot-a",
                10,
                5,
            ),
        ),
    )

    result = apply_clamp_transaction(
        state=state,
        transaction=stale_transaction,
    )

    assert not result.accepted
    assert result.receipt.reason_codes == (
        "STALE_CLAMP_STATE",
    )


def test_trm_inputs_are_detached() -> None:
    state = asserted_state()

    values, mask = state.trm_inputs()

    values[10] = 9
    mask[10] = False

    assert int(state.values[10]) == 5
    assert bool(state.active_mask[10])


def test_gap_detection_uses_declared_slot_ownership() -> None:
    state = asserted_state()

    schema = (
        EvidenceSlot(
            slot_id="slot-a",
            cell_indices=(10, 11),
            question_template="Provide evidence A.",
        ),
        EvidenceSlot(
            slot_id="slot-b",
            cell_indices=(20, 21),
            question_template="Provide evidence B.",
        ),
    )

    gaps = detect_gaps(
        schema=schema,
        clamp_state=state,
    )

    assert len(gaps) == 1
    assert gaps[0].slot_id == "slot-b"
    assert gaps[0].signal_codes == (
        "MISSING_EVIDENCE",
    )


def test_wrong_owner_does_not_fill_evidence_slot() -> None:
    state = ClampState.empty("episode-projector")

    state = apply_clamp_transaction(
        state=state,
        transaction=transaction(
            state,
            proposal(
                "proposal-1",
                ClampOperation.ASSERT,
                "slot-other",
                10,
                5,
            ),
        ),
    ).state

    gaps = detect_gaps(
        schema=(
            EvidenceSlot(
                slot_id="slot-a",
                cell_indices=(10,),
                question_template="Provide evidence A.",
            ),
        ),
        clamp_state=state,
    )

    assert len(gaps) == 1
    assert gaps[0].claimed_count == 0


def test_gap_signals_include_frame_and_sensitivity() -> None:
    state = ClampState.empty("episode-projector")

    gaps = detect_gaps(
        schema=(
            EvidenceSlot(
                slot_id="slot-a",
                cell_indices=(10,),
                question_template="Provide evidence A.",
            ),
        ),
        clamp_state=state,
        cascade_magnitudes=(0.02, 0.01),
        verdict="STALLED",
        low_sensitivity_threshold=0.05,
    )

    assert gaps[0].signal_codes == (
        "FRAME_STALLED",
        "LOW_CASCADE_SENSITIVITY",
        "MISSING_EVIDENCE",
    )
