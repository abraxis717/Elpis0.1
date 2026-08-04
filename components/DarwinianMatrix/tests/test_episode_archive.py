from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile

import torch

from DarwinianMatrix.controller.episode import (
    DarwinianEpisodeState,
    advance_episode,
)
from DarwinianMatrix.ecology.engine import (
    PRODUCER,
    EcologyState,
)
from DarwinianMatrix.geometry import (
    build_neighbor_table,
)
from DarwinianMatrix.ledger.episode_archive import (
    EpisodeArchive,
    EpisodeAttemptCapture,
    build_episode_archive,
    episode_state_from_payload,
    episode_state_payload,
    load_episode_archive,
    replay_episode_archive,
    write_episode_archive,
)
from DarwinianMatrix.projector.constraints import (
    ClampOperation,
    ClampProposal,
    ClampState,
    ClampTransaction,
    apply_clamp_transaction,
)
from DarwinianMatrix.trm.reference_solver import (
    DeterministicSudokuReferenceAdapter,
)


GRID = torch.tensor([
    5,3,4,6,7,8,9,1,2,
    6,7,2,1,9,5,3,4,8,
    1,9,8,3,4,2,5,6,7,
    8,5,9,7,6,1,4,2,3,
    4,2,6,8,5,3,7,9,1,
    7,1,3,9,2,4,8,5,6,
    9,6,1,5,3,7,2,8,4,
    2,8,7,4,1,9,6,3,5,
    3,4,5,2,8,6,1,7,9,
])


def initial_state() -> DarwinianEpisodeState:
    clamps = ClampState.empty(
        "archive-episode"
    )

    proposal = ClampProposal(
        proposal_id="force-six",
        operation=ClampOperation.ASSERT,
        slot_id="slot-a",
        evidence_digest="a" * 64,
        cell_index=0,
        value=6,
    )

    transaction = ClampTransaction(
        transaction_id="assert-six",
        episode_id=clamps.episode_id,
        expected_state_digest=clamps.digest(),
        proposals=(proposal,),
    )

    clamps = apply_clamp_transaction(
        state=clamps,
        transaction=transaction,
    ).state

    ecology = EcologyState()
    ecology.ctype[3280] = PRODUCER
    ecology.genome[3280] = 0.5
    ecology.energy[3280] = 1.0
    ecology.lineage[3280] = 3280
    ecology.validate()

    return DarwinianEpisodeState.initial(
        episode_id="archive-episode",
        previous_grid=GRID,
        ecology_state=ecology,
        meta_attempt_budget=2,
        structural_attempt_budget=3,
        clamp_state=clamps,
    )


def capture_sequence():
    state0 = initial_state()
    neighbors = build_neighbor_table()

    rejected_adapter = (
        DeterministicSudokuReferenceAdapter(
            max_search_nodes=0
        )
    )
    accepted_adapter = (
        DeterministicSudokuReferenceAdapter()
    )

    first = advance_episode(
        state=state0,
        random_seed=717,
        adapter=rejected_adapter,
        target_viability=1_000_000.0,
        neighbors=neighbors,
    )

    second = advance_episode(
        state=first.state,
        random_seed=718,
        adapter=accepted_adapter,
        target_viability=1_000_000.0,
        neighbors=neighbors,
    )

    third = advance_episode(
        state=second.state,
        random_seed=719,
        adapter=accepted_adapter,
        target_viability=1_000_000.0,
        neighbors=neighbors,
    )

    assert third.state.closed

    captures = (
        EpisodeAttemptCapture(
            state_before=state0,
            random_seed=717,
            adapter=rejected_adapter,
            result=first,
        ),
        EpisodeAttemptCapture(
            state_before=first.state,
            random_seed=718,
            adapter=accepted_adapter,
            result=second,
        ),
        EpisodeAttemptCapture(
            state_before=second.state,
            random_seed=719,
            adapter=accepted_adapter,
            result=third,
        ),
    )

    archive = build_episode_archive(
        initial_state=state0,
        captures=captures,
        target_viability=1_000_000.0,
        neighbors=neighbors,
    )

    return archive, captures


def test_episode_snapshot_round_trip_exact() -> None:
    state = initial_state()

    restored = episode_state_from_payload(
        episode_state_payload(state)
    )

    assert restored.digest() == state.digest()
    assert torch.equal(
        restored.previous_grid,
        state.previous_grid,
    )
    assert (
        restored.ecology_state.digest()
        == state.ecology_state.digest()
    )


def test_archive_build_is_deterministic() -> None:
    first, _ = capture_sequence()
    second, _ = capture_sequence()

    assert first.validate_digest()
    assert second.validate_digest()
    assert first.archive_digest == second.archive_digest
    assert (
        first.final_state_digest
        == second.final_state_digest
    )


def test_archive_write_load_round_trip() -> None:
    archive, _ = capture_sequence()

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "episode.json"

        write_episode_archive(path, archive)
        loaded = load_episode_archive(path)

    assert loaded == archive
    assert loaded.validate_digest()


def test_autonomous_multiframe_replay_passes() -> None:
    archive, _ = capture_sequence()

    replay = replay_episode_archive(archive)

    assert replay.passed
    assert replay.failure_codes == ()
    assert replay.attempts_replayed == 3
    assert (
        replay.observed_final_state_digest
        == archive.final_state_digest
    )
    assert replay.final_state.closed


def test_replay_preserves_rejected_attempt_semantics() -> None:
    archive, captures = capture_sequence()

    first = archive.attempts[0]

    assert (
        first.outcome
        == captures[0].result
        .structural_result.outcome
    )
    assert (
        first.state_before_digest
        != first.state_after_digest
    )

    replay = replay_episode_archive(archive)

    assert replay.passed
    assert replay.final_state.meta_state.attempt_index == 2
    assert replay.final_state.structural_attempt_index == 3


def test_archive_binds_each_adapter_manifest() -> None:
    archive, _ = capture_sequence()

    specs = [
        attempt.adapter_spec
        for attempt in archive.attempts
    ]

    assert specs[0]["max_search_nodes"] == 0
    assert specs[1]["max_search_nodes"] == 1_000_000
    assert specs[2]["max_search_nodes"] == 1_000_000

    for spec in specs:
        assert len(spec["manifest_digest"]) == 64


def test_tampered_archive_digest_is_rejected() -> None:
    archive, _ = capture_sequence()
    payload = archive.to_dict()

    payload["initial_state_snapshot"][
        "previous_grid"
    ]["data"][0] = 9

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "tampered.json"
        path.write_text(
            json.dumps(payload)
        )

        try:
            load_episode_archive(path)
        except ValueError:
            pass
        else:
            raise AssertionError(
                "Tampered archive was accepted."
            )


def test_rehashed_seed_tamper_fails_replay() -> None:
    archive, _ = capture_sequence()

    altered_attempt = replace(
        archive.attempts[1],
        random_seed=0,
    )

    partial = replace(
        archive,
        attempts=(
            archive.attempts[0],
            altered_attempt,
            archive.attempts[2],
        ),
        archive_digest="0" * 64,
    )

    altered = replace(
        partial,
        archive_digest=partial.recompute_digest(),
    )

    assert altered.validate_digest()

    replay = replay_episode_archive(altered)

    assert not replay.passed
    assert any(
        code.startswith(
            "STRUCTURAL_ATTEMPT_MISMATCH:"
        )
        for code in replay.failure_codes
    )


def test_terminal_archive_binds_close_receipt() -> None:
    archive, captures = capture_sequence()

    terminal = archive.attempts[-1]

    assert terminal.close_receipt_digest is not None
    assert (
        terminal.close_receipt_digest
        == captures[-1].result
        .clamp_close_receipt.receipt_digest
    )

    replay = replay_episode_archive(archive)

    assert replay.passed
    assert replay.final_state.clamp_state.closed
    assert replay.final_state.clamp_state.active_count == 0


def test_archive_builder_rejects_broken_capture_chain() -> None:
    archive, captures = capture_sequence()

    broken = (
        captures[0],
        replace(
            captures[1],
            state_before=initial_state(),
        ),
        captures[2],
    )

    try:
        build_episode_archive(
            initial_state=initial_state(),
            captures=broken,
            target_viability=1_000_000.0,
            neighbors=build_neighbor_table(),
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Discontinuous capture chain was accepted."
        )

    assert archive.validate_digest()
