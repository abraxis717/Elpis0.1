from __future__ import annotations

import torch

from elpis_reference.model import (
    MODEL_FILENAME,
    MODEL_SHA256,
    UPSTREAM_MODEL_FILENAME,
)
from elpis_reference.refinement import (
    FPRM_RUNTIME_BATCH_SIZE,
    _build_fprm_batch,
    _encode_fprm_input,
)


def test_fprm_canonical_checkpoint_identity():
    assert MODEL_FILENAME == "FPRM.Samsung_TRM"
    assert UPSTREAM_MODEL_FILENAME == "sudoku/step_78120"
    assert MODEL_FILENAME != UPSTREAM_MODEL_FILENAME
    assert MODEL_SHA256 == (
        "6daec5f499d115beb14e23f3a9cf56d1166b99c1ccd36b185a19ea5dfec9a137"
    )


def test_fprm_native_sudoku_token_encoding():
    puzzle = tuple([0, 1, 2, 3, 4, 5, 6, 7, 8, 9] + [0] * 71)
    encoded = _encode_fprm_input(puzzle)

    assert encoded[:10] == (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    assert len(encoded) == 81


def test_fprm_qualified_padded32_geometry():
    puzzle = tuple([0, 3, 4] + [0] * 78)

    batch = _build_fprm_batch(
        puzzle,
        torch.device("cpu"),
    )

    inputs = batch["inputs"]
    pids = batch["puzzle_identifiers"]

    assert FPRM_RUNTIME_BATCH_SIZE == 32
    assert inputs.shape == (32, 81)
    assert inputs.dtype == torch.int32

    assert inputs[0].tolist() == list(_encode_fprm_input(puzzle))
    assert bool(inputs[1:].eq(0).all())

    assert pids.shape == (32,)
    assert pids.dtype == torch.int32
    assert bool(pids.eq(0).all())
