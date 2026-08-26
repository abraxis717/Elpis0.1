"""Controller-owned process-local lineage authority primitive.

C2R6C-A intentionally lands this primitive before production validator ingress
is allowed to depend on it.  It proves precommit-before-return, one-shot reveal,
registry-backed verification, replay rejection, and cross-controller isolation.

It is not external attestation, cross-process durable provenance, OS/hardware
isolation, or production ingress admission.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import secrets

from .artifact_lineage import (
    P0ArtifactProposalLineageV1,
    build_artifact_proposal_lineage,
)
from .contracts import P0Result

RECEIPT_DOMAIN = "elpis.p0-lineage-authority-receipt.c2r6ca.v1"
CONSUMPTION_DOMAIN = "elpis.p0-lineage-authority-consumption.c2r6ca.v1"
INSTANCE_DOMAIN = "elpis.p0-lineage-authority-instance.c2r6ca.v1"


class P0LineageAuthorityError(ValueError):
    pass


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _domain_digest(domain: str, payload: object) -> str:
    return hashlib.sha256(
        domain.encode("utf-8") + b"\\x00" + _canonical_bytes(payload)
    ).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise P0LineageAuthorityError(f"{name} must be SHA-256 hex")
    try:
        int(value, 16)
    except ValueError as exc:
        raise P0LineageAuthorityError(f"{name} must be SHA-256 hex") from exc


@dataclass(frozen=True, slots=True)
class P0LineageAuthorityReceiptV1:
    authority_instance_id: str
    capability_id: str
    issuance_sequence: int
    lineage_digest: str
    p0_result_digest: str
    request_id: str
    validator_index: int
    validator_evidence_digest: str
    receipt_digest: str


@dataclass(frozen=True, slots=True)
class P0LineageAuthorityConsumptionV1:
    authority_instance_id: str
    capability_id: str
    lineage_digest: str
    receipt_digest: str
    consumption_digest: str


@dataclass(frozen=True, slots=True)
class P0AuthorizedArtifactLineageV1:
    lineage: P0ArtifactProposalLineageV1
    receipt: P0LineageAuthorityReceiptV1


def _receipt_payload(receipt: P0LineageAuthorityReceiptV1) -> dict[str, object]:
    return {
        "authority_instance_id": receipt.authority_instance_id,
        "capability_id": receipt.capability_id,
        "issuance_sequence": receipt.issuance_sequence,
        "lineage_digest": receipt.lineage_digest,
        "p0_result_digest": receipt.p0_result_digest,
        "request_id": receipt.request_id,
        "validator_evidence_digest": receipt.validator_evidence_digest,
        "validator_index": receipt.validator_index,
    }


def _validate_receipt(receipt: P0LineageAuthorityReceiptV1) -> None:
    for name in (
        "authority_instance_id",
        "capability_id",
        "lineage_digest",
        "p0_result_digest",
        "validator_evidence_digest",
        "receipt_digest",
    ):
        _require_digest(name, getattr(receipt, name))
    if not receipt.request_id:
        raise P0LineageAuthorityError("request_id cannot be empty")
    if receipt.issuance_sequence < 0 or receipt.validator_index < 0:
        raise P0LineageAuthorityError("receipt sequence/index must be non-negative")
    expected=_domain_digest(RECEIPT_DOMAIN, _receipt_payload(receipt))
    if expected != receipt.receipt_digest:
        raise P0LineageAuthorityError("authority receipt digest mismatch")


class _AuthorityState:
    def __init__(self, instance_id: str) -> None:
        self.instance_id=instance_id
        self.active: dict[str,str]={}


class P0LineageAuthorityVerifierV1:
    __slots__=("__state",)

    def __init__(self, state: _AuthorityState) -> None:
        self.__state=state

    @property
    def authority_instance_id(self) -> str:
        return self.__state.instance_id

    def consume(self, *, receipt: P0LineageAuthorityReceiptV1,
                lineage: P0ArtifactProposalLineageV1) -> P0LineageAuthorityConsumptionV1:
        _validate_receipt(receipt)
        if receipt.authority_instance_id != self.__state.instance_id:
            raise P0LineageAuthorityError("receipt belongs to another authority instance")
        if receipt.lineage_digest != lineage.lineage_digest:
            raise P0LineageAuthorityError("receipt lineage mismatch")
        if receipt.p0_result_digest != lineage.p0_result_digest:
            raise P0LineageAuthorityError("receipt P0 result mismatch")
        if receipt.request_id != lineage.request_id:
            raise P0LineageAuthorityError("receipt request mismatch")
        if receipt.validator_index != lineage.validator_index:
            raise P0LineageAuthorityError("receipt validator index mismatch")
        if receipt.validator_evidence_digest != lineage.validator_evidence_digest:
            raise P0LineageAuthorityError("receipt validator evidence mismatch")
        active=self.__state.active.get(receipt.capability_id)
        if active is None:
            raise P0LineageAuthorityError("authority capability is not active")
        if active != receipt.receipt_digest:
            raise P0LineageAuthorityError("authority capability receipt mismatch")
        del self.__state.active[receipt.capability_id]
        payload={
            "authority_instance_id":receipt.authority_instance_id,
            "capability_id":receipt.capability_id,
            "lineage_digest":lineage.lineage_digest,
            "receipt_digest":receipt.receipt_digest,
        }
        return P0LineageAuthorityConsumptionV1(
            authority_instance_id=receipt.authority_instance_id,
            capability_id=receipt.capability_id,
            lineage_digest=lineage.lineage_digest,
            receipt_digest=receipt.receipt_digest,
            consumption_digest=_domain_digest(CONSUMPTION_DOMAIN,payload),
        )


class P0LineageAuthorityV1:
    def __init__(self) -> None:
        seed=secrets.token_hex(32)
        instance_id=_domain_digest(INSTANCE_DOMAIN,{"seed":seed})
        self.__state=_AuthorityState(instance_id)
        self.__verifier=P0LineageAuthorityVerifierV1(self.__state)
        self.__pending: dict[int, tuple[P0Result, dict[int, tuple[P0ArtifactProposalLineageV1,P0LineageAuthorityReceiptV1]]]]={}
        self.__sequence=0

    def verifier(self) -> P0LineageAuthorityVerifierV1:
        return self.__verifier

    def precommit_result(self, result: P0Result) -> None:
        key=id(result)
        if key in self.__pending:
            raise P0LineageAuthorityError("result already precommitted")
        pending={}
        for index,evidence in enumerate(result.evidence):
            if evidence.passed:
                continue
            lineage=build_artifact_proposal_lineage(result,validator_index=index)
            capability=secrets.token_hex(32)
            while capability in self.__state.active:
                capability=secrets.token_hex(32)
            _require_digest("capability_id",capability)
            base={
                "authority_instance_id":self.__state.instance_id,
                "capability_id":capability,
                "issuance_sequence":self.__sequence,
                "lineage_digest":lineage.lineage_digest,
                "p0_result_digest":lineage.p0_result_digest,
                "request_id":lineage.request_id,
                "validator_evidence_digest":lineage.validator_evidence_digest,
                "validator_index":lineage.validator_index,
            }
            self.__sequence += 1
            receipt=P0LineageAuthorityReceiptV1(
                **base,
                receipt_digest=_domain_digest(RECEIPT_DOMAIN,base),
            )
            _validate_receipt(receipt)
            self.__state.active[capability]=receipt.receipt_digest
            pending[index]=(lineage,receipt)
        if pending:
            # Strong reference prevents object-id reuse while authority is pending.
            self.__pending[key]=(result,pending)

    def reveal(self, result: P0Result, *, validator_index: int) -> P0AuthorizedArtifactLineageV1:
        entry=self.__pending.get(id(result))
        if entry is None:
            raise P0LineageAuthorityError("result was not precommitted by this authority")
        stored,pending=entry
        if stored is not result:
            raise P0LineageAuthorityError("result object differs from precommit")
        pair=pending.get(validator_index)
        if pair is None:
            raise P0LineageAuthorityError("validator authority absent or already revealed")
        expected,receipt=pair
        actual=build_artifact_proposal_lineage(result,validator_index=validator_index)
        if actual != expected:
            raise P0LineageAuthorityError("lineage changed after precommit")
        del pending[validator_index]

        # Retain an exhausted (result, {}) entry as a consumed tombstone for
        # this authority instance. This preserves the distinction between a
        # result never precommitted here and one whose reveal authority is
        # already exhausted. The strong reference also prevents Python object-id
        # reuse from aliasing authority state.
        #
        # Prototype boundary: completed rejecting P0Result objects remain
        # retained for the lifetime of this controller authority.
        return P0AuthorizedArtifactLineageV1(lineage=actual,receipt=receipt)
