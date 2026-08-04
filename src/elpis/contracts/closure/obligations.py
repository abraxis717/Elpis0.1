from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .identity import content_checksum


class ObligationError(RuntimeError):
    pass


class MissingRequiredObligation(ObligationError):
    pass


class UnsatisfiedRequiredObligation(ObligationError):
    pass


class ObligationKind(str, Enum):
    PROJECTION = "projection"
    REFINEMENT = "refinement"
    MATERIALIZATION = "materialization"
    SYNTAX_VALIDATION = "syntax_validation"
    EXECUTION_VALIDATION = "execution_validation"
    SECURITY_VALIDATION = "security_validation"
    AUDIT = "audit"
    GOVERNANCE = "governance"
    EMISSION = "emission"
    MEMORY_CANDIDACY = "memory_candidacy"


class ObligationStatus(str, Enum):
    SATISFIED = "satisfied"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ObligationRequirement:
    obligation_id: str
    kind: ObligationKind
    required: bool
    route_scope: tuple[str, ...]
    domain_scope: tuple[str, ...]
    policy_version: str

    def __post_init__(self) -> None:
        if not self.obligation_id:
            raise ValueError("obligation_id is required")
        if not self.route_scope:
            raise ValueError("route_scope must not be empty")
        if not self.domain_scope:
            raise ValueError("domain_scope must not be empty")
        if not self.policy_version:
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class ObligationEvidence:
    obligation_id: str
    status: ObligationStatus
    evidence_ref: str | None
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ObligationManifest:
    request_id: str
    route_family: str
    domain: str
    requirements: tuple[ObligationRequirement, ...]

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("request_id is required")
        identifiers = [item.obligation_id for item in self.requirements]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("obligation identifiers must be unique")

    @property
    def manifest_checksum(self) -> str:
        return content_checksum("elpis-obligation-manifest-v1", self)


@dataclass(frozen=True, slots=True)
class ObligationCertificate:
    request_id: str
    manifest_checksum: str
    satisfied_obligation_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    certificate_checksum: str


def certify_obligations(
    manifest: ObligationManifest,
    evidence: tuple[ObligationEvidence, ...],
) -> ObligationCertificate:
    by_id: dict[str, ObligationEvidence] = {}

    for item in evidence:
        if item.obligation_id in by_id:
            raise ObligationError(
                f"duplicate evidence for {item.obligation_id!r}"
            )
        by_id[item.obligation_id] = item

    declared = {
        requirement.obligation_id: requirement
        for requirement in manifest.requirements
    }

    undeclared = sorted(set(by_id) - set(declared))
    if undeclared:
        raise ObligationError(
            f"evidence exists for undeclared obligations: {undeclared}"
        )

    missing = sorted(
        identifier
        for identifier, requirement in declared.items()
        if requirement.required and identifier not in by_id
    )
    if missing:
        raise MissingRequiredObligation(
            f"missing required obligation evidence: {missing}"
        )

    unsatisfied = sorted(
        identifier
        for identifier, requirement in declared.items()
        if requirement.required
        and by_id[identifier].status is not ObligationStatus.SATISFIED
    )
    if unsatisfied:
        raise UnsatisfiedRequiredObligation(
            f"required obligations are not satisfied: {unsatisfied}"
        )

    satisfied = tuple(sorted(
        identifier
        for identifier, item in by_id.items()
        if item.status is ObligationStatus.SATISFIED
    ))
    refs = tuple(sorted(
        item.evidence_ref
        for item in by_id.values()
        if item.evidence_ref is not None
    ))

    body = {
        "request_id": manifest.request_id,
        "manifest_checksum": manifest.manifest_checksum,
        "satisfied_obligation_ids": satisfied,
        "evidence_refs": refs,
    }
    checksum = content_checksum("elpis-obligation-certificate-v1", body)

    return ObligationCertificate(
        request_id=manifest.request_id,
        manifest_checksum=manifest.manifest_checksum,
        satisfied_obligation_ids=satisfied,
        evidence_refs=refs,
        certificate_checksum=checksum,
    )
