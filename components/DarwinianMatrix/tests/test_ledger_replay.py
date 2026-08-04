from __future__ import annotations

import json
import tempfile

import torch

from DarwinianMatrix.ecology.engine import (
    CONSUMER,
    PRODUCER,
    STRUCTURE,
    EcologyState,
)
from DarwinianMatrix.ecology.transaction import (
    EcologyTransactionConfig,
    advance_ecology_transaction,
)
from DarwinianMatrix.evaluation.replay import replay_frame
from DarwinianMatrix.geometry import (
    MATRIX_CELLS,
    ClimateSidecar,
    build_neighbor_table,
    build_region_map,
)
from DarwinianMatrix.ledger.records import (
    GENESIS_RECORD_DIGEST,
    EcologyFrameRecord,
    build_frame_record,
    read_jsonl_records,
    verify_record_chain,
    write_jsonl_record,
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


def fixture():
    sidecar = ClimateSidecar()
    sidecar.trm_write(GRID)

    climate = sidecar.lattice_read_view(
        build_region_map()
    )
    neighbors = build_neighbor_table()
    ages = torch.zeros(MATRIX_CELLS)
    config = EcologyTransactionConfig()

    state = EcologyState()

    for index, ctype in (
        (3280, PRODUCER),
        (3281, CONSUMER),
        (3361, STRUCTURE),
    ):
        state.ctype[index] = ctype
        state.genome[index] = 0.5
        state.energy[index] = 1.0
        state.lineage[index] = index

    state.res_a[3281] = 1.0
    state.validate()

    return state, climate, ages, neighbors, config


def make_record(
    *,
    frame_index=0,
    previous=GENESIS_RECORD_DIGEST,
):
    state, climate, ages, neighbors, config = fixture()

    after, telemetry = advance_ecology_transaction(
        state=state,
        climate=climate,
        transition_age=ages,
        neighbors=neighbors,
        config=config,
    )

    record = build_frame_record(
        episode_id="episode-ledger",
        frame_index=frame_index,
        random_seed=717,
        state_before=state,
        state_after=after,
        climate=climate,
        transition_age=ages,
        neighbors=neighbors,
        config=config,
        telemetry=telemetry,
        previous_record_digest=previous,
    )

    return (
        record,
        state,
        after,
        climate,
        ages,
        neighbors,
        config,
        telemetry,
    )


def test_record_digest_is_valid_and_deterministic():
    first = make_record()[0]
    second = make_record()[0]

    assert first.validate_digest()
    assert first.record_digest == second.record_digest


def test_record_json_round_trip():
    record = make_record()[0]
    restored = EcologyFrameRecord.from_dict(
        json.loads(
            json.dumps(
                record.to_dict(),
                sort_keys=True,
            )
        )
    )

    assert restored == record
    assert restored.validate_digest()


def test_jsonl_round_trip():
    record = make_record()[0]

    with tempfile.NamedTemporaryFile(
        mode="w",
        delete=False,
    ) as handle:
        path = handle.name

    write_jsonl_record(path, record)
    restored = read_jsonl_records(path)

    assert restored == (record,)


def test_replay_passes_exactly():
    (
        record,
        state,
        _,
        climate,
        ages,
        neighbors,
        config,
        _,
    ) = make_record()

    _, _, result = replay_frame(
        expected_record=record,
        state_before=state,
        climate=climate,
        transition_age=ages,
        neighbors=neighbors,
        config=config,
    )

    assert result.passed
    assert (
        result.observed_state_digest
        == result.expected_state_digest
    )
    assert (
        result.observed_record_digest
        == result.expected_record_digest
    )


def test_replay_rejects_changed_config():
    (
        record,
        state,
        _,
        climate,
        ages,
        neighbors,
        _,
        _,
    ) = make_record()

    changed = EcologyTransactionConfig(
        diffusion_rate=0.20,
    )

    _, _, result = replay_frame(
        expected_record=record,
        state_before=state,
        climate=climate,
        transition_age=ages,
        neighbors=neighbors,
        config=changed,
    )

    assert not result.passed


def test_replay_rejects_changed_state():
    (
        record,
        state,
        _,
        climate,
        ages,
        neighbors,
        config,
        _,
    ) = make_record()

    state.energy[3280] += 0.1

    _, _, result = replay_frame(
        expected_record=record,
        state_before=state,
        climate=climate,
        transition_age=ages,
        neighbors=neighbors,
        config=config,
    )

    assert not result.passed


def test_record_chain():
    first = make_record()[0]
    second = make_record(
        frame_index=1,
        previous=first.record_digest,
    )[0]

    assert verify_record_chain((first, second))


def test_chain_rejects_wrong_previous_digest():
    first = make_record()[0]
    second = make_record(
        frame_index=1,
        previous="f" * 64,
    )[0]

    assert not verify_record_chain((first, second))


def test_chain_rejects_wrong_frame_index():
    first = make_record(frame_index=1)[0]

    assert not verify_record_chain((first,))


def test_record_is_sensitive_to_seed():
    first = make_record()[0]
    payload = first.to_dict()
    payload["random_seed"] = 0

    tampered = EcologyFrameRecord.from_dict(payload)

    assert not tampered.validate_digest()


def test_repeated_transaction_telemetry_is_bit_identical():
    (
        _,
        state,
        _,
        climate,
        ages,
        neighbors,
        config,
        _,
    ) = make_record()

    state_digests = set()
    telemetry_digests = set()

    for _ in range(16):
        after, telemetry = advance_ecology_transaction(
            state=state,
            climate=climate,
            transition_age=ages,
            neighbors=neighbors,
            config=config,
        )

        state_digests.add(after.digest())
        telemetry_digests.add(telemetry.digest())

    assert len(state_digests) == 1
    assert len(telemetry_digests) == 1
