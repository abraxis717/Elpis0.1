"""Production P0 validator ingress into the public semantic refinement seam.

C2R4 binds the real P0/R0 validator boundary to the already-qualified semantic
residual and canonical Projector RELEASE path.

Authority constraints:
- validator failures select a semantic object, never a Grid81 cell/value;
- projection trace is frozen from the P0 projection before validation;
- structural/scope refinement rejection remains STRUCTURAL_REJECTION and cannot
  become a task residual;
- this module does not invoke a learned model and does not grant task or
  structural authority to a proposer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from .semantic_refinement import (
    SEMANTIC_OBJECT,
    STRUCTURAL_REJECTION,
    TASK_REJECTION,
    ReverseTraceIndex,
    StructuralObservationRecord,
    TaskDiagnosticV1,
    domain_digest,
    require_digest,
)


P0_VALIDATION_SEMANTIC_ROW = "validation"


class P0ValidatorEvidenceLike(Protocol):
    validator_id: str
    passed: bool
    code: str
    message: str
    details: Sequence[tuple[str, object]]


class P0RefinementValidationLike(Protocol):
    proposal_digest: str
    transition_kind: str
    changed_cells: Sequence[int]
    scope_validity: str
    status: str
    validation_digest: str


P0_ARTIFACT_PROPOSAL_LINEAGE_DOMAIN = "elpis.p0-artifact-proposal-lineage.c2r5.v1"
P0_VALIDATOR_EVIDENCE_DOMAIN = "elpis.p0-validator-evidence-binding.c2r5.v1"


class P0ArtifactProposalLineageLike(Protocol):
    request_id: str
    p0_result_digest: str
    projection_digest: str
    structural_proposal_digest: str
    decoder_plan_digest: str
    artifact_digest: str
    validator_index: int
    validator_evidence_digest: str
    validator_id: str
    validator_code: str
    lineage_digest: str


def _lineage_payload(lineage: P0ArtifactProposalLineageLike) -> dict[str, object]:
    return {
        "artifact_digest": lineage.artifact_digest,
        "decoder_plan_digest": lineage.decoder_plan_digest,
        "p0_result_digest": lineage.p0_result_digest,
        "projection_digest": lineage.projection_digest,
        "request_id": lineage.request_id,
        "structural_proposal_digest": lineage.structural_proposal_digest,
        "validator_code": lineage.validator_code,
        "validator_evidence_digest": lineage.validator_evidence_digest,
        "validator_id": lineage.validator_id,
        "validator_index": lineage.validator_index,
    }


def _verify_lineage_binding(
    *,
    task_scope_id: str,
    artifact_digest: str,
    evidence: P0ValidatorEvidenceLike,
    projection_trace: "P0ProjectionTraceV1",
    lineage: P0ArtifactProposalLineageLike,
) -> None:
    for name in (
        "p0_result_digest",
        "projection_digest",
        "structural_proposal_digest",
        "decoder_plan_digest",
        "artifact_digest",
        "validator_evidence_digest",
        "lineage_digest",
    ):
        require_digest(name, getattr(lineage, name))
    if lineage.request_id != task_scope_id:
        raise ValueError("task scope does not match P0 lineage")
    if lineage.artifact_digest != artifact_digest:
        raise ValueError("artifact digest does not match P0 lineage")
    if lineage.projection_digest != projection_trace.projection_digest:
        raise ValueError("projection trace does not match P0 lineage")
    if lineage.validator_id != evidence.validator_id or lineage.validator_code != evidence.code:
        raise ValueError("validator evidence identity does not match P0 lineage")
    actual_evidence_digest = domain_digest(
        P0_VALIDATOR_EVIDENCE_DOMAIN,
        {
            "code": evidence.code,
            "details": [[str(key), value] for key, value in evidence.details],
            "message": evidence.message,
            "passed": bool(evidence.passed),
            "validator_id": evidence.validator_id,
        },
    )
    if actual_evidence_digest != lineage.validator_evidence_digest:
        raise ValueError("validator evidence payload does not match P0 lineage")
    expected = domain_digest(
        P0_ARTIFACT_PROPOSAL_LINEAGE_DOMAIN,
        _lineage_payload(lineage),
    )
    if expected != lineage.lineage_digest:
        raise ValueError("P0 artifact/proposal lineage digest mismatch")


@dataclass(frozen=True)
class P0ProjectionTraceV1:
    projection_digest: str
    semantic_rows: tuple[str, ...]
    row_semantic_digests: tuple[str, ...]
    observations: tuple[StructuralObservationRecord, ...]
    trace_digest: str

    def semantic_digest_for_row(self, row_name: str) -> str:
        matches = tuple(
            index
            for index, name in enumerate(self.semantic_rows)
            if name == row_name
        )
        if len(matches) != 1:
            raise LookupError(
                f"semantic row must resolve exactly once: {row_name}"
            )
        return self.row_semantic_digests[matches[0]]

    def reverse_trace_index(self) -> ReverseTraceIndex:
        return ReverseTraceIndex(self.observations)


def build_p0_projection_trace(
    *,
    projection_digest: str,
    grid81: Sequence[int],
    semantic_rows: Sequence[str],
) -> P0ProjectionTraceV1:
    """Freeze semantic/topology/P7 trace from an actual P0 projection."""
    require_digest("projection_digest", projection_digest)

    grid = tuple(int(value) for value in grid81)
    rows = tuple(str(name) for name in semantic_rows)

    if len(grid) != 81:
        raise ValueError("P0 projection grid81 must contain 81 cells")
    if any(value < 0 or value > 9 for value in grid):
        raise ValueError("P0 projection grid81 values must remain in 0..9")
    if len(rows) != 9:
        raise ValueError("P0 projection requires exactly nine semantic rows")
    if any(not name for name in rows):
        raise ValueError("P0 semantic row names cannot be empty")
    if len(set(rows)) != len(rows):
        raise ValueError("P0 semantic row names must be unique")

    row_digests: list[str] = []
    observations: list[StructuralObservationRecord] = []

    for row_index, row_name in enumerate(rows):
        start = row_index * 9
        row_tokens = grid[start : start + 9]

        semantic_digest = domain_digest(
            "elpis.p0-projection-semantic-object.c2r4.v1",
            {
                "projection_digest": projection_digest,
                "row_index": row_index,
                "row_name": row_name,
                "row_tokens": list(row_tokens),
            },
        )
        row_digests.append(semantic_digest)

        for column_index, token in enumerate(row_tokens):
            cell_index = start + column_index

            topology_digest = domain_digest(
                "elpis.p0-projection-topology-vertex.c2r4.v1",
                {
                    "column_index": column_index,
                    "projection_digest": projection_digest,
                    "row_index": row_index,
                    "source_semantic_object_digest": semantic_digest,
                },
            )

            capsule_digest = domain_digest(
                "elpis.p0-projection-p7-capsule.c2r4.v1",
                {
                    "cell_index": cell_index,
                    "token": token,
                    "topology_vertex_digest": topology_digest,
                },
            )

            observation_payload = {
                "P7_capsule_digest": capsule_digest,
                "P7_primary_cell_index": cell_index,
                "source_semantic_object_digest": semantic_digest,
                "topology_vertex_digest": topology_digest,
            }

            observations.append(
                StructuralObservationRecord(
                    source_semantic_object_digest=semantic_digest,
                    topology_vertex_digest=topology_digest,
                    P7_capsule_digest=capsule_digest,
                    P7_primary_cell_index=cell_index,
                    observation_digest=domain_digest(
                        "elpis.p0-projection-structural-observation.c2r4.v1",
                        observation_payload,
                    ),
                )
            )

    frozen_observations = tuple(observations)
    frozen_row_digests = tuple(row_digests)

    trace_digest = domain_digest(
        "elpis.p0-projection-trace.c2r4.v1",
        {
            "observation_digests": [
                record.observation_digest
                for record in frozen_observations
            ],
            "projection_digest": projection_digest,
            "row_semantic_digests": list(frozen_row_digests),
            "semantic_rows": list(rows),
        },
    )

    return P0ProjectionTraceV1(
        projection_digest=projection_digest,
        semantic_rows=rows,
        row_semantic_digests=frozen_row_digests,
        observations=frozen_observations,
        trace_digest=trace_digest,
    )


def task_diagnostic_from_p0_validator_failure(
    *,
    task_scope_id: str,
    frame_index: int,
    artifact_digest: str,
    evidence: P0ValidatorEvidenceLike,
    projection_trace: P0ProjectionTraceV1,
    lineage: P0ArtifactProposalLineageLike,
) -> TaskDiagnosticV1:
    """Convert one real P0 task-validator failure into a typed task diagnostic."""
    require_digest("artifact_digest", artifact_digest)
    _verify_lineage_binding(
        task_scope_id=task_scope_id,
        artifact_digest=artifact_digest,
        evidence=evidence,
        projection_trace=projection_trace,
        lineage=lineage,
    )

    if evidence.passed:
        raise ValueError("validator evidence must be a rejection")
    if not evidence.validator_id:
        raise ValueError("validator_id cannot be empty")
    if not evidence.code:
        raise ValueError("validator failure code cannot be empty")

    locus_identity = projection_trace.semantic_digest_for_row(
        P0_VALIDATION_SEMANTIC_ROW
    )

    details_digest = domain_digest(
        "elpis.p0-validator-failure-details.c2r4.v1",
        {
            "artifact_digest": artifact_digest,
            "artifact_proposal_lineage_digest": lineage.lineage_digest,
            "decoder_plan_digest": lineage.decoder_plan_digest,
            "p0_result_digest": lineage.p0_result_digest,
            "structural_proposal_digest": lineage.structural_proposal_digest,
            "validator_evidence_digest": lineage.validator_evidence_digest,
            "code": evidence.code,
            "details": [
                [str(key), value]
                for key, value in evidence.details
            ],
            "message": evidence.message,
            "projection_trace_digest": projection_trace.trace_digest,
            "validator_id": evidence.validator_id,
        },
    )

    return TaskDiagnosticV1(
        diagnostic_class=TASK_REJECTION,
        task_scope_id=task_scope_id,
        frame_index=frame_index,
        subject_digest=artifact_digest,
        producer_id=evidence.validator_id,
        locus_namespace=SEMANTIC_OBJECT,
        locus_identity=locus_identity,
        reason_codes=(evidence.code,),
        details_digest=details_digest,
    )


def structural_diagnostic_from_p0_refinement_rejection(
    *,
    task_scope_id: str,
    frame_index: int,
    validation: P0RefinementValidationLike,
    projection_trace: P0ProjectionTraceV1,
) -> TaskDiagnosticV1:
    """Preserve P0 structural/scope rejection as non-task diagnostic."""
    if validation.scope_validity != "FAIL":
        raise ValueError("P0 refinement validation is not a rejection")
    if not validation.status.startswith("REJECTED_P0_REFINEMENT_"):
        raise ValueError("unsupported P0 refinement rejection status")

    require_digest("proposal_digest", validation.proposal_digest)
    require_digest("validation_digest", validation.validation_digest)

    locus_identity = projection_trace.semantic_digest_for_row(
        P0_VALIDATION_SEMANTIC_ROW
    )

    return TaskDiagnosticV1(
        diagnostic_class=STRUCTURAL_REJECTION,
        task_scope_id=task_scope_id,
        frame_index=frame_index,
        subject_digest=validation.proposal_digest,
        producer_id="elpis.p0.refinement_validation.v1",
        locus_namespace=SEMANTIC_OBJECT,
        locus_identity=locus_identity,
        reason_codes=(validation.status,),
        details_digest=validation.validation_digest,
    )
