import hashlib

import pytest

from elpis_reference.semantic_refinement import (
    SEMANTIC_OBJECT,
    STRUCTURAL_REJECTION,
    TASK_REJECTION,
    ReverseTraceIndex,
    StructuralObservationRecord,
    TaskDiagnosticV1,
)


SEMANTIC_OBJECT_DIGEST = (
    "ebb230bb511a7814a12b4e9aeb003950"
    "6fcafc611980ee70f195e97fbbfc624e"
)

TOPOLOGY_VERTEX_DIGEST = (
    "fc17f4e70e407b09089e3ed592970270"
    "c6302057df9a9f2f9c55383272b88e48"
)

P7_CAPSULE_DIGEST = (
    "0901164d98cb08a92a73015168110c37"
    "cc649f90df6711833d6402f4af954d26"
)

EXPECTED_DIAGNOSTIC_DIGEST = (
    "052b2c00b422f9ec9190150e4e862bb7"
    "d9ff149d82fd162426351e187bb6036a"
)

EXPECTED_RESIDUAL_DIGEST = (
    "80991a0ed7d7743ba54e40d8e23656c9"
    "bb74decce623aa55171f726d166c105f"
)

EXPECTED_RESOLUTION_DIGEST = (
    "54ccfa855ff5a7ee7ece43e4d577ea52"
    "c24e4f22feeb6ebc7f037f5f87c00816"
)


def _h(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def _diagnostic(
    diagnostic_class: str = TASK_REJECTION,
) -> TaskDiagnosticV1:
    return TaskDiagnosticV1(
        diagnostic_class=diagnostic_class,
        task_scope_id="r7cr3-sample-352455",
        frame_index=0,
        subject_digest=_h(
            "r7cr3-generic-task-output"
        ),
        producer_id="r7cr3.generic-task-validator.v1",
        locus_namespace=SEMANTIC_OBJECT,
        locus_identity=SEMANTIC_OBJECT_DIGEST,
        reason_codes=(
            "TASK_REQUIREMENT_UNSATISFIED",
        ),
        details_digest=_h(
            "r7cr3-task-validator-evidence"
        ),
    )


def test_r7cr3r1_frozen_digest_reproduction():
    diagnostic = _diagnostic()
    residual = diagnostic.to_task_residual()

    observation = StructuralObservationRecord.create(
        source_semantic_object_digest=SEMANTIC_OBJECT_DIGEST,
        topology_vertex_digest=TOPOLOGY_VERTEX_DIGEST,
        P7_capsule_digest=P7_CAPSULE_DIGEST,
        P7_primary_cell_index=13,
    )

    resolved = ReverseTraceIndex(
        (observation,)
    ).resolve(residual)

    assert diagnostic.digest() == EXPECTED_DIAGNOSTIC_DIGEST
    assert residual.digest() == EXPECTED_RESIDUAL_DIGEST
    assert resolved.resolution_digest == EXPECTED_RESOLUTION_DIGEST
    assert resolved.P7_cell_indices == (13,)


def test_task_diagnostic_has_no_grid81_selection():
    payload = _diagnostic().payload()

    for forbidden in (
        "grid81_cell_index",
        "grid81_digit",
        "grid81_value",
        "sudoku_error",
        "clamp_operation",
        "clamp_value",
    ):
        assert forbidden not in payload


def test_structural_rejection_cannot_become_task_residual():
    with pytest.raises(
        ValueError,
        match="structural rejection cannot become a task residual",
    ):
        _diagnostic(
            STRUCTURAL_REJECTION
        ).to_task_residual()


def test_unknown_locus_fails_closed():
    residual = _diagnostic().to_task_residual()

    with pytest.raises(
        LookupError,
        match="semantic locus has no structural trace",
    ):
        ReverseTraceIndex(
            ()
        ).resolve(residual)
