from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Mapping, Protocol, Sequence


TASK_REJECTION = "TASK_REJECTION"
STRUCTURAL_REJECTION = "STRUCTURAL_REJECTION"

SEMANTIC_OBJECT = "semantic_object_sha256"
TOPOLOGY_VERTEX = "topology_vertex_sha256"
EVIDENCE_SLOT = "evidence_slot_id"

LOCUS_NAMESPACES = frozenset(
    (
        SEMANTIC_OBJECT,
        TOPOLOGY_VERTEX,
        EVIDENCE_SLOT,
    )
)


def canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def domain_digest(domain: str, payload: object) -> str:
    return hashlib.sha256(
        domain.encode("utf-8")
        + b"\x00"
        + canonical_bytes(payload)
    ).hexdigest()


def require_digest(name: str, value: str) -> None:
    if len(value) != 64:
        raise ValueError(f"{name} must contain a SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{name} must be hexadecimal") from exc


def require_reason_codes(values: Sequence[str]) -> tuple[str, ...]:
    result = tuple(values)
    if not result:
        raise ValueError("at least one reason code is required")
    if any(not isinstance(value, str) or not value for value in result):
        raise ValueError("reason codes must be non-empty strings")
    if tuple(sorted(set(result))) != result:
        raise ValueError("reason codes must be sorted and unique")
    return result


@dataclass(frozen=True)
class TaskDiagnosticV1:
    diagnostic_class: str
    task_scope_id: str
    frame_index: int
    subject_digest: str
    producer_id: str
    locus_namespace: str
    locus_identity: str
    reason_codes: tuple[str, ...]
    details_digest: str

    def __post_init__(self) -> None:
        if self.diagnostic_class not in (TASK_REJECTION, STRUCTURAL_REJECTION):
            raise ValueError("unsupported diagnostic class")
        if not self.task_scope_id:
            raise ValueError("task_scope_id cannot be empty")
        if self.frame_index < 0:
            raise ValueError("frame_index cannot be negative")
        require_digest("subject_digest", self.subject_digest)
        require_digest("details_digest", self.details_digest)
        if not self.producer_id:
            raise ValueError("producer_id cannot be empty")
        if self.locus_namespace not in LOCUS_NAMESPACES:
            raise ValueError("unknown locus namespace")
        if not self.locus_identity:
            raise ValueError("locus_identity cannot be empty")
        if self.locus_namespace in (SEMANTIC_OBJECT, TOPOLOGY_VERTEX):
            require_digest("locus_identity", self.locus_identity)
        require_reason_codes(self.reason_codes)

    def payload(self) -> dict[str, object]:
        return {
            "details_digest": self.details_digest,
            "diagnostic_class": self.diagnostic_class,
            "frame_index": self.frame_index,
            "locus_identity": self.locus_identity,
            "locus_namespace": self.locus_namespace,
            "producer_id": self.producer_id,
            "reason_codes": list(self.reason_codes),
            "subject_digest": self.subject_digest,
            "task_scope_id": self.task_scope_id,
        }

    def digest(self) -> str:
        return domain_digest("elpis.task-diagnostic.r7a.v1", self.payload())

    def to_task_residual(self) -> "TaskResidualV1":
        if self.diagnostic_class != TASK_REJECTION:
            raise ValueError("structural rejection cannot become a task residual")
        return TaskResidualV1(
            task_scope_id=self.task_scope_id,
            frame_index=self.frame_index,
            subject_digest=self.subject_digest,
            producer_id=self.producer_id,
            locus_namespace=self.locus_namespace,
            locus_identity=self.locus_identity,
            diagnostic_digest=self.digest(),
            reason_codes=self.reason_codes,
        )


@dataclass(frozen=True)
class TaskResidualV1:
    task_scope_id: str
    frame_index: int
    subject_digest: str
    producer_id: str
    locus_namespace: str
    locus_identity: str
    diagnostic_digest: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.task_scope_id:
            raise ValueError("task_scope_id cannot be empty")
        if self.frame_index < 0:
            raise ValueError("frame_index cannot be negative")
        require_digest("subject_digest", self.subject_digest)
        require_digest("diagnostic_digest", self.diagnostic_digest)
        if not self.producer_id:
            raise ValueError("producer_id cannot be empty")
        if self.locus_namespace not in LOCUS_NAMESPACES:
            raise ValueError("unknown locus namespace")
        if not self.locus_identity:
            raise ValueError("locus_identity cannot be empty")
        if self.locus_namespace in (SEMANTIC_OBJECT, TOPOLOGY_VERTEX):
            require_digest("locus_identity", self.locus_identity)
        require_reason_codes(self.reason_codes)

    def payload(self) -> dict[str, object]:
        return {
            "diagnostic_digest": self.diagnostic_digest,
            "frame_index": self.frame_index,
            "locus_identity": self.locus_identity,
            "locus_namespace": self.locus_namespace,
            "producer_id": self.producer_id,
            "reason_codes": list(self.reason_codes),
            "subject_digest": self.subject_digest,
            "task_scope_id": self.task_scope_id,
        }

    def digest(self) -> str:
        return domain_digest("elpis.task-residual.r7a.v1", self.payload())


@dataclass(frozen=True)
class StructuralObservationRecord:
    source_semantic_object_digest: str
    topology_vertex_digest: str
    P7_capsule_digest: str
    P7_primary_cell_index: int
    observation_digest: str

    def __post_init__(self) -> None:
        for name in (
            "source_semantic_object_digest",
            "topology_vertex_digest",
            "P7_capsule_digest",
            "observation_digest",
        ):
            require_digest(name, getattr(self, name))
        if not 0 <= self.P7_primary_cell_index < 81:
            raise ValueError("P7 cell must be in 0..80")

    @classmethod
    def create(
        cls,
        *,
        source_semantic_object_digest: str,
        topology_vertex_digest: str,
        P7_capsule_digest: str,
        P7_primary_cell_index: int,
    ) -> "StructuralObservationRecord":
        payload = {
            "P7_capsule_digest": P7_capsule_digest,
            "P7_primary_cell_index": P7_primary_cell_index,
            "source_semantic_object_digest": source_semantic_object_digest,
            "topology_vertex_digest": topology_vertex_digest,
        }
        return cls(
            source_semantic_object_digest=source_semantic_object_digest,
            topology_vertex_digest=topology_vertex_digest,
            P7_capsule_digest=P7_capsule_digest,
            P7_primary_cell_index=P7_primary_cell_index,
            observation_digest=domain_digest(
                "elpis.structural-observation-fixture.r7a.v1",
                payload,
            ),
        )


@dataclass(frozen=True)
class ResolvedTaskResidualV1:
    task_residual_digest: str
    source_semantic_object_digests: tuple[str, ...]
    topology_vertex_digests: tuple[str, ...]
    P7_capsule_digests: tuple[str, ...]
    P7_cell_indices: tuple[int, ...]
    trace_proof_digests: tuple[str, ...]
    resolution_digest: str


class EvidenceSlotLike(Protocol):
    slot_id: str
    cell_indices: Sequence[int]
    minimum_claimed: int
    question_template: str


class ReverseTraceIndex:
    def __init__(self, observations: Iterable[StructuralObservationRecord]) -> None:
        records = tuple(
            sorted(
                observations,
                key=lambda record: (
                    record.source_semantic_object_digest,
                    record.topology_vertex_digest,
                    record.P7_primary_cell_index,
                    record.P7_capsule_digest,
                    record.observation_digest,
                ),
            )
        )
        semantic_work: dict[str, list[StructuralObservationRecord]] = {}
        topology_work: dict[str, list[StructuralObservationRecord]] = {}
        for record in records:
            semantic_work.setdefault(
                record.source_semantic_object_digest,
                [],
            ).append(record)
            topology_work.setdefault(
                record.topology_vertex_digest,
                [],
            ).append(record)
        self._semantic = {
            key: tuple(value)
            for key, value in semantic_work.items()
        }
        self._topology = {
            key: tuple(value)
            for key, value in topology_work.items()
        }

    def resolve(
        self,
        residual: TaskResidualV1,
        *,
        evidence_slots: Sequence[EvidenceSlotLike] = (),
    ) -> ResolvedTaskResidualV1:
        if residual.locus_namespace == SEMANTIC_OBJECT:
            records = self._semantic.get(residual.locus_identity, ())
            if not records:
                raise LookupError("semantic locus has no structural trace")
            semantic = tuple(sorted({x.source_semantic_object_digest for x in records}))
            topology = tuple(sorted({x.topology_vertex_digest for x in records}))
            capsules = tuple(sorted({x.P7_capsule_digest for x in records}))
            cells = tuple(sorted({x.P7_primary_cell_index for x in records}))
            proofs = tuple(sorted({x.observation_digest for x in records}))
        elif residual.locus_namespace == TOPOLOGY_VERTEX:
            records = self._topology.get(residual.locus_identity, ())
            if not records:
                raise LookupError("topology locus has no structural trace")
            semantic = tuple(sorted({x.source_semantic_object_digest for x in records}))
            topology = tuple(sorted({x.topology_vertex_digest for x in records}))
            capsules = tuple(sorted({x.P7_capsule_digest for x in records}))
            cells = tuple(sorted({x.P7_primary_cell_index for x in records}))
            proofs = tuple(sorted({x.observation_digest for x in records}))
        elif residual.locus_namespace == EVIDENCE_SLOT:
            matching = tuple(
                slot
                for slot in evidence_slots
                if slot.slot_id == residual.locus_identity
            )
            if len(matching) != 1:
                raise LookupError("evidence slot must resolve exactly once")
            slot = matching[0]
            semantic = ()
            topology = ()
            capsules = ()
            cells = tuple(sorted(set(int(cell) for cell in slot.cell_indices)))
            proofs = (
                domain_digest(
                    "elpis.evidence-slot-binding.r7a.v1",
                    {
                        "cell_indices": list(slot.cell_indices),
                        "minimum_claimed": slot.minimum_claimed,
                        "question_template": slot.question_template,
                        "slot_id": slot.slot_id,
                    },
                ),
            )
        else:
            raise ValueError("unsupported task locus namespace")

        if not cells:
            raise LookupError("residual resolved to empty support")

        payload = {
            "P7_capsule_digests": list(capsules),
            "P7_cell_indices": list(cells),
            "source_semantic_object_digests": list(semantic),
            "task_residual_digest": residual.digest(),
            "topology_vertex_digests": list(topology),
            "trace_proof_digests": list(proofs),
        }
        return ResolvedTaskResidualV1(
            task_residual_digest=residual.digest(),
            source_semantic_object_digests=semantic,
            topology_vertex_digests=topology,
            P7_capsule_digests=capsules,
            P7_cell_indices=cells,
            trace_proof_digests=proofs,
            resolution_digest=domain_digest(
                "elpis.resolved-task-residual.r7a.v1",
                payload,
            ),
        )
