from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import torch

from DarwinianMatrix.runtime import (
    RUNTIME_POLICY,
    assert_deterministic_runtime,
    enforce_deterministic_runtime,
)


PROBE = r'''
import json
import torch

from DarwinianMatrix.ecology.engine import (
    PRODUCER,
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
from DarwinianMatrix.ledger.records import build_frame_record
from DarwinianMatrix.runtime import RUNTIME_POLICY

grid = torch.tensor([
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

sidecar = ClimateSidecar()
sidecar.trm_write(grid)

climate = sidecar.lattice_read_view(
    build_region_map()
)
neighbors = build_neighbor_table()
ages = torch.zeros(MATRIX_CELLS)
config = EcologyTransactionConfig()

state = EcologyState()
state.ctype[3280] = PRODUCER
state.genome[3280] = 0.5
state.energy[3280] = 1.0
state.lineage[3280] = 3280

after, telemetry = advance_ecology_transaction(
    state=state,
    climate=climate,
    transition_age=ages,
    neighbors=neighbors,
    config=config,
)

record = build_frame_record(
    episode_id="cross-process-probe",
    frame_index=0,
    random_seed=717,
    state_before=state,
    state_after=after,
    climate=climate,
    transition_age=ages,
    neighbors=neighbors,
    config=config,
    telemetry=telemetry,
)

_, replay_telemetry, replay = replay_frame(
    expected_record=record,
    state_before=state,
    climate=climate,
    transition_age=ages,
    neighbors=neighbors,
    config=config,
)

print(json.dumps(
    {
        "record": record.record_digest,
        "record_valid": record.validate_digest(),
        "replay": replay.passed,
        "replay_telemetry": replay_telemetry.digest(),
        "runtime_policy": RUNTIME_POLICY.digest(),
        "state": after.digest(),
        "telemetry": telemetry.digest(),
    },
    sort_keys=True,
    separators=(",", ":"),
))
'''


def test_runtime_policy_is_enforced() -> None:
    enforce_deterministic_runtime()
    assert_deterministic_runtime()

    assert torch.get_num_threads() == 1
    assert torch.are_deterministic_algorithms_enabled()
    assert not torch.backends.mkldnn.enabled
    assert len(RUNTIME_POLICY.digest()) == 64


def test_cross_process_three_seed_identity() -> None:
    project_root = Path(__file__).resolve().parents[2]
    outputs = []

    for seed in ("0", "1", "717"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        environment["PYTHONPATH"] = str(project_root)

        completed = subprocess.run(
            [sys.executable, "-c", PROBE],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )

        payload = json.loads(
            completed.stdout.strip()
        )

        assert payload["record_valid"]
        assert payload["replay"]
        assert (
            payload["telemetry"]
            == payload["replay_telemetry"]
        )

        outputs.append(payload)

    assert outputs[0] == outputs[1] == outputs[2]
