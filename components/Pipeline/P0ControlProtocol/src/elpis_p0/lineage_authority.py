"""Controller-associated in-memory lineage issuance registry.

Supported construction creates this registry internally inside ``P0Controller``.
There is no supported caller-supplied issuer/verifier hook. Receipts are
one-shot bearer records whose authority comes from membership in this private
registry, not from their ordinary SHA-256 digest.

This is a Python in-memory control boundary. It is not hostile same-process
isolation, external attestation, cross-process durability, or hardware-backed
provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import secrets
import threading

from .artifact_lineage import P0ArtifactProposalLineageV1, build_artifact_proposal_lineage
from .contracts import P0Result

RECEIPT_DOMAIN = "elpis.p0-lineage-authority-receipt.c2r6ca.v2"
CONSUMPTION_DOMAIN = "elpis.p0-lineage-authority-consumption.c2r6ca.v2"
INSTANCE_DOMAIN = "elpis.p0-lineage-authority-instance.c2r6ca.v2"


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
        domain.encode("utf-8") + b"\x00" + _canonical_bytes(payload)
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
    if receipt.issuance_sequence < 0:
        raise P0LineageAuthorityError("receipt issuance sequence must be non-negative")
    if receipt.validator_index < 0:
        raise P0LineageAuthorityError("receipt validator index must be non-negative")
    expected = _domain_digest(RECEIPT_DOMAIN, _receipt_payload(receipt))
    if expected != receipt.receipt_digest:
        raise P0LineageAuthorityError("authority receipt digest mismatch")


class _ControllerLineageAuthority:
    """One controller-associated issuer/consumer state machine.

    The class and constructor are module-private. Supported callers reach it
    only through ``P0Controller`` methods. Python reflection can still inspect
    private implementation state; hostile same-process isolation is excluded.
    """

    __slots__ = ("__instance_id", "__active", "__pending", "__sequence", "__lock")

    def __init__(self) -> None:
        seed = secrets.token_hex(32)
        self.__instance_id = _domain_digest(INSTANCE_DOMAIN, {"seed": seed})
        self.__active: dict[str, str] = {}
        self.__pending: dict[
            int,
            tuple[
                P0Result,
                dict[int, tuple[P0ArtifactProposalLineageV1, P0LineageAuthorityReceiptV1]],
            ],
        ] = {}
        self.__sequence = 0
        self.__lock = threading.RLock()

    def _issue_from_run(self, result: P0Result) -> None:
        key = id(result)
        with self.__lock:
            if key in self.__pending:
                raise P0LineageAuthorityError("result already precommitted")
            pending: dict[
                int,
                tuple[P0ArtifactProposalLineageV1, P0LineageAuthorityReceiptV1],
            ] = {}
            for index, evidence in enumerate(result.evidence):
                if evidence.passed:
                    continue
                lineage = build_artifact_proposal_lineage(result, validator_index=index)
                capability = secrets.token_hex(32)
                while capability in self.__active:
                    capability = secrets.token_hex(32)
                _require_digest("capability_id", capability)
                sequence = self.__sequence
                self.__sequence += 1
                base = {
                    "authority_instance_id": self.__instance_id,
                    "capability_id": capability,
                    "issuance_sequence": sequence,
                    "lineage_digest": lineage.lineage_digest,
                    "p0_result_digest": lineage.p0_result_digest,
                    "request_id": lineage.request_id,
                    "validator_evidence_digest": lineage.validator_evidence_digest,
                    "validator_index": lineage.validator_index,
                }
                receipt = P0LineageAuthorityReceiptV1(
                    **base,
                    receipt_digest=_domain_digest(RECEIPT_DOMAIN, base),
                )
                _validate_receipt(receipt)
                self.__active[capability] = receipt.receipt_digest
                pending[index] = (lineage, receipt)
            if pending:
                self.__pending[key] = (result, pending)

    def _reveal_from_controller(
        self,
        result: P0Result,
        *,
        validator_index: int,
    ) -> P0AuthorizedArtifactLineageV1:
        if validator_index < 0 or validator_index >= len(result.evidence):
            raise P0LineageAuthorityError("validator index is out of range")
        if result.evidence[validator_index].passed:
            raise P0LineageAuthorityError("validator index did not reject")
        with self.__lock:
            entry = self.__pending.get(id(result))
            if entry is None:
                raise P0LineageAuthorityError(
                    "result was not precommitted by this authority instance"
                )
            stored, pending = entry
            if stored is not result:
                raise P0LineageAuthorityError("result object differs from precommit")
            pair = pending.get(validator_index)
            if pair is None:
                raise P0LineageAuthorityError("validator authority was already revealed")
            expected, receipt = pair
            actual = build_artifact_proposal_lineage(result, validator_index=validator_index)
            if actual != expected:
                raise P0LineageAuthorityError("lineage changed after precommit")
            del pending[validator_index]
            # Exhausted entries remain tombstones. This deliberately retains
            # rejecting P0Result graphs for the controller lifetime.
            return P0AuthorizedArtifactLineageV1(lineage=actual, receipt=receipt)

    def _consume_from_controller(
        self,
        authorized: P0AuthorizedArtifactLineageV1,
    ) -> P0LineageAuthorityConsumptionV1:
        receipt = authorized.receipt
        lineage = authorized.lineage
        _validate_receipt(receipt)
        with self.__lock:
            if receipt.authority_instance_id != self.__instance_id:
                raise P0LineageAuthorityError(
                    "receipt belongs to another authority instance"
                )
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
            active = self.__active.get(receipt.capability_id)
            if active is None:
                raise P0LineageAuthorityError("authority capability is not active")
            if active != receipt.receipt_digest:
                raise P0LineageAuthorityError("authority capability receipt mismatch")
            del self.__active[receipt.capability_id]
        payload = {
            "authority_instance_id": receipt.authority_instance_id,
            "capability_id": receipt.capability_id,
            "lineage_digest": lineage.lineage_digest,
            "receipt_digest": receipt.receipt_digest,
        }
        return P0LineageAuthorityConsumptionV1(
            authority_instance_id=receipt.authority_instance_id,
            capability_id=receipt.capability_id,
            lineage_digest=lineage.lineage_digest,
            receipt_digest=receipt.receipt_digest,
            consumption_digest=_domain_digest(CONSUMPTION_DOMAIN, payload),
        )


def _new_controller_lineage_authority() -> _ControllerLineageAuthority:
    return _ControllerLineageAuthority()
