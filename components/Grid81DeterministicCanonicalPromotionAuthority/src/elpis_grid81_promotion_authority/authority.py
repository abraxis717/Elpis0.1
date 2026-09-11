"""Grid81 canonical promotion authority R0.

This module is the explicit authority bridge between the advisory,
non-executable G5.3E promotion plan and a future canonical writer.

It does not write canonical state.  It issues a deterministic one-use
ATOMIC_GRID81_CANONICAL_PROMOTION capability only when:

* the supplied G5.3E decision is READY_FOR_CANONICAL_REVIEW;
* the decision, plan, and source chain bind each other exactly;
* the plan remains non-executable, non-self-applying, non-authoritative, and
  canonical-write-permitted=False;
* G5.3C source evidence exposes the artifact/capability/receipt/state/ledger
  identities required for a future transaction;
* current canonical Grid81 state is reader-valid and non-replayable; and
* the caller supplies an explicit external operator-approval digest.

The operator-approval digest is a binding, not authentication.  R0 does not
claim that a bare digest proves human identity, possession of a private key,
or approval provenance.  That boundary remains external to this module.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from Grid81.canonical_reader import CanonicalReadError, load_current_grid81
from elpis_grid81_promotion_planner.canonical import (
    CanonicalPromotionPlan,
    PromotionDecision,
    SourceChain,
)
from elpis_grid81_promotion_planner.decision import DECISION_READY
from elpis_grid81_promotion_planner.verifier import verify_plan_nonexecutable


_HEX64 = re.compile(r"^[0-9a-f]{64}$")

AUTHORIZED_PUBLISHER_CLASS = "GRID81_ATOMIC_CANONICAL_PUBLISHER_R0"

_EXPECTED_INTENTIONS = (
    "VERIFY_CANONICAL_LEDGER_HEAD",
    "VERIFY_CAPABILITY_GRANTED_UNCONSUMED",
    "VERIFY_ARTIFACT_CANONICALLY_UNAPPLIED",
    "RESERVE_TRANSACTION_IDENTIFIER",
    "PERFORM_CANONICAL_APPLICATION",
    "APPEND_CANONICAL_RECEIPT",
    "VERIFY_POST_COMMIT_STATE",
)

_EXPECTED_PRECONDITIONS = (
    "canonical_ledger_head_verified",
    "capability_granted_and_unconsumed",
    "artifact_canonically_unapplied",
    "transaction_identifier_reserved",
    "post_commit_state_verified",
)

_CONSTRAINTS = {
    "append_only": True,
    "atomic_staging_required": True,
    "consumption_receipt_required": True,
    "generation_verified_before_head": True,
    "generation_written_first": True,
    "head_written_last": True,
    "one_use": True,
    "post_write_verification_required": True,
    "replay_rejection_required": True,
    "rollback_required": True,
}

_GRANTS = {
    "append_grid81_canonical_generation": True,
    "create_grid81_canonical_head": True,
    "ecs_world_commit": False,
    "overwrite_existing_generation": False,
    "overwrite_existing_head": False,
}

_POLICY = {
    "schema": "elpis.grid81.promotion-authority-policy.v1",
    "authorized_publisher_class": AUTHORIZED_PUBLISHER_CLASS,
    "decision_required": DECISION_READY,
    "expected_intentions": list(_EXPECTED_INTENTIONS),
    "expected_preconditions": list(_EXPECTED_PRECONDITIONS),
    "constraints": _CONSTRAINTS,
    "grants": _GRANTS,
    "operator_approval_required": True,
    "operator_approval_authentication_provided": False,
}


class PromotionAuthorityError(ValueError):
    """Fail-closed authority rejection with a stable machine code."""

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}:{detail}")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _domain_digest(domain: str, value: Any) -> str:
    return hashlib.sha256(
        domain.encode("ascii") + b"\0" + _canonical_bytes(value)
    ).hexdigest()


AUTHORITY_POLICY_DIGEST = _domain_digest(
    "elpis.grid81.promotion-authority-policy.v1",
    _POLICY,
)


def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise PromotionAuthorityError(code, detail)


def _hex64(value: Any) -> bool:
    return type(value) is str and _HEX64.fullmatch(value) is not None


def _require_hex64(value: Any, code: str) -> None:
    _require(_hex64(value), code)


def _source_record(chain: SourceChain) -> dict:
    g53c = chain.g53c
    required = {
        "artifact_digest": g53c.artifact_digest,
        "structural_capability_digest": g53c.capability_digest,
        "application_receipt_digest": g53c.shadow_receipt_digest,
        "resulting_state_digest": g53c.resulting_state_digest,
        "source_application_ledger_head": g53c.resulting_ledger_head,
    }
    for name, value in required.items():
        _require_hex64(value, f"SOURCE_{name.upper()}_INVALID")

    _require(
        g53c.lifecycle_state == "GRANTED_UNCONSUMED",
        "SOURCE_CAPABILITY_NOT_GRANTED_UNCONSUMED",
    )

    return {
        "source_chain_digest": chain.chain_digest,
        **required,
    }


def _semantic_payload(record: dict) -> dict:
    return {
        "schema": record["schema"],
        "capability_type": record["capability_type"],
        "authorized_publisher_class": record["authorized_publisher_class"],
        "authority_policy_digest": record["authority_policy_digest"],
        "operator_approval_digest": record["operator_approval_digest"],
        "source_bindings": record["source_bindings"],
        "target_bindings": record["target_bindings"],
        "constraints": record["constraints"],
        "grants": record["grants"],
        "one_use": record["one_use"],
    }


def _capability_id(record_without_ids: dict) -> str:
    return _domain_digest(
        "elpis.grid81.atomic-promotion-capability-id.v1",
        _semantic_payload(record_without_ids),
    )


def _capability_digest(record_without_digest: dict) -> str:
    return _domain_digest(
        "elpis.grid81.atomic-promotion-capability.v1",
        record_without_digest,
    )


def _transaction_id(
    *,
    plan_digest: str,
    decision_digest: str,
    source_chain_digest: str,
    operator_approval_digest: str,
    source_canonical_digest: str,
    source_generation_semantic_digest: str,
    target_generation: int,
    expected_publication_ledger_head: str,
) -> str:
    return _domain_digest(
        "elpis.grid81.canonical-transaction-reservation.v1",
        {
            "plan_digest": plan_digest,
            "decision_digest": decision_digest,
            "source_chain_digest": source_chain_digest,
            "operator_approval_digest": operator_approval_digest,
            "source_canonical_digest": source_canonical_digest,
            "source_generation_semantic_digest": (
                source_generation_semantic_digest
            ),
            "target_generation": target_generation,
            "expected_publication_ledger_head": (
                expected_publication_ledger_head
            ),
        },
    )


def issue_promotion_capability(
    *,
    plan: CanonicalPromotionPlan,
    decision: PromotionDecision,
    chain: SourceChain,
    project_root: Path | str,
    operator_approval_digest: str,
    expected_publication_ledger_head: str,
) -> dict:
    """Issue one deterministic, non-self-executing canonical-promotion capability."""

    _require(type(chain) is SourceChain, "SOURCE_CHAIN_TYPE")
    _require(type(decision) is PromotionDecision, "DECISION_TYPE")
    _require(type(plan) is CanonicalPromotionPlan, "PLAN_TYPE")
    _require_hex64(operator_approval_digest, "OPERATOR_APPROVAL_DIGEST_INVALID")
    _require_hex64(
        expected_publication_ledger_head,
        "EXPECTED_PUBLICATION_LEDGER_HEAD_INVALID",
    )

    _require(decision.decision == DECISION_READY, "DECISION_NOT_READY")
    _require(
        decision.source_chain_digest == chain.chain_digest,
        "DECISION_SOURCE_CHAIN_MISMATCH",
    )
    _require(
        decision.expected_canonical_preconditions == _EXPECTED_PRECONDITIONS,
        "DECISION_PRECONDITIONS_MISMATCH",
    )

    _require(plan.decision_digest == decision.digest, "PLAN_DECISION_MISMATCH")
    _require(
        plan.source_chain_digest == chain.chain_digest,
        "PLAN_SOURCE_CHAIN_MISMATCH",
    )
    _require(plan.intentions == _EXPECTED_INTENTIONS, "PLAN_INTENTIONS_MISMATCH")

    plan_check = verify_plan_nonexecutable(plan)
    _require(
        plan_check.get("plan_non_executable") is True
        and plan_check.get("violations_found") == 0,
        "PLAN_AUTHORITY_BOUNDARY_INVALID",
    )

    source = _source_record(chain)

    try:
        current = load_current_grid81(Path(project_root))
    except CanonicalReadError as exc:
        raise PromotionAuthorityError(
            "CURRENT_CANONICAL_READER_REJECTED",
            exc.code,
        ) from exc

    _require(
        current.consumption_count == 1,
        "CURRENT_CANONICAL_CONSUMPTION_COUNT",
    )
    _require(
        current.replay_permitted is False,
        "CURRENT_CANONICAL_REPLAY_PERMITTED",
    )
    _require_hex64(current.canonical_digest, "CURRENT_CANONICAL_DIGEST_INVALID")
    _require_hex64(
        current.generation_semantic_digest,
        "CURRENT_GENERATION_SEMANTIC_DIGEST_INVALID",
    )

    target_generation = current.generation_number + 1
    transaction_id = _transaction_id(
        plan_digest=plan.digest,
        decision_digest=decision.digest,
        source_chain_digest=chain.chain_digest,
        operator_approval_digest=operator_approval_digest,
        source_canonical_digest=current.canonical_digest,
        source_generation_semantic_digest=(
            current.generation_semantic_digest
        ),
        target_generation=target_generation,
        expected_publication_ledger_head=(
            expected_publication_ledger_head
        ),
    )

    record = {
        "schema": "elpis.grid81.atomic-canonical-promotion-capability.v1",
        "capability_type": "ATOMIC_GRID81_CANONICAL_PROMOTION",
        "authorized_publisher_class": AUTHORIZED_PUBLISHER_CLASS,
        "authority_policy_digest": AUTHORITY_POLICY_DIGEST,
        "operator_approval_digest": operator_approval_digest,
        "source_bindings": {
            "promotion_plan_digest": plan.digest,
            "promotion_decision_digest": decision.digest,
            **source,
        },
        "target_bindings": {
            "ledger": "Grid81",
            "source_generation": current.generation_number,
            "target_generation": target_generation,
            "source_canonical_digest": current.canonical_digest,
            "source_generation_semantic_digest": (
                current.generation_semantic_digest
            ),
            "expected_publication_ledger_head": (
                expected_publication_ledger_head
            ),
            "transaction_id": transaction_id,
            "generation_target": (
                f"Canonical/Grid81/generations/{target_generation:06d}.json"
            ),
            "head_target": "Canonical/Grid81/HEAD.json",
        },
        "constraints": dict(_CONSTRAINTS),
        "grants": dict(_GRANTS),
        "one_use": True,
        "lifecycle": {
            "state": "GRANTED_UNCONSUMED",
            "consumed": False,
            "consumption_count": 0,
            "replay_permitted": False,
        },
        "claims_not_made": sorted([
            "capability does not authenticate operator identity",
            "capability does not prove possession of a private key",
            "capability does not self-apply",
            "capability does not itself write canonical state",
            "capability does not authorize ECS world mutation",
            "operator approval digest is not a digital signature",
        ]),
    }

    record["capability_id"] = _capability_id(record)
    record["capability_digest"] = _capability_digest(record)
    return record


_TOP_LEVEL_FIELDS = frozenset({
    "schema",
    "capability_type",
    "authorized_publisher_class",
    "authority_policy_digest",
    "operator_approval_digest",
    "source_bindings",
    "target_bindings",
    "constraints",
    "grants",
    "one_use",
    "lifecycle",
    "claims_not_made",
    "capability_id",
    "capability_digest",
})

_SOURCE_FIELDS = frozenset({
    "promotion_plan_digest",
    "promotion_decision_digest",
    "source_chain_digest",
    "artifact_digest",
    "structural_capability_digest",
    "application_receipt_digest",
    "resulting_state_digest",
    "source_application_ledger_head",
})

_TARGET_FIELDS = frozenset({
    "ledger",
    "source_generation",
    "target_generation",
    "source_canonical_digest",
    "source_generation_semantic_digest",
    "expected_publication_ledger_head",
    "transaction_id",
    "generation_target",
    "head_target",
})

_LIFECYCLE_FIELDS = frozenset({
    "state",
    "consumed",
    "consumption_count",
    "replay_permitted",
})


def validate_promotion_capability(capability: dict) -> tuple[bool, tuple[str, ...]]:
    """Validate exact R0 promotion-capability bytes semantically."""

    issues: list[str] = []

    if type(capability) is not dict:
        return False, ("CAPABILITY_TYPE",)

    if set(capability) != _TOP_LEVEL_FIELDS:
        issues.append("CAPABILITY_FIELDS")

    if capability.get("schema") != (
        "elpis.grid81.atomic-canonical-promotion-capability.v1"
    ):
        issues.append("SCHEMA")

    if capability.get("capability_type") != "ATOMIC_GRID81_CANONICAL_PROMOTION":
        issues.append("CAPABILITY_TYPE_VALUE")

    if capability.get("authorized_publisher_class") != AUTHORIZED_PUBLISHER_CLASS:
        issues.append("PUBLISHER_CLASS")

    if capability.get("authority_policy_digest") != AUTHORITY_POLICY_DIGEST:
        issues.append("AUTHORITY_POLICY")

    for name in (
        "operator_approval_digest",
        "capability_id",
        "capability_digest",
    ):
        if not _hex64(capability.get(name)):
            issues.append(name.upper())

    source = capability.get("source_bindings")
    if type(source) is not dict or set(source) != _SOURCE_FIELDS:
        issues.append("SOURCE_FIELDS")
    else:
        for name, value in source.items():
            if not _hex64(value):
                issues.append(f"SOURCE_{name.upper()}")

    target = capability.get("target_bindings")
    if type(target) is not dict or set(target) != _TARGET_FIELDS:
        issues.append("TARGET_FIELDS")
    else:
        if target.get("ledger") != "Grid81":
            issues.append("TARGET_LEDGER")
        source_generation = target.get("source_generation")
        target_generation = target.get("target_generation")
        if (
            type(source_generation) is not int
            or type(target_generation) is not int
            or target_generation != source_generation + 1
        ):
            issues.append("TARGET_GENERATION")
        else:
            if target.get("generation_target") != (
                f"Canonical/Grid81/generations/{target_generation:06d}.json"
            ):
                issues.append("TARGET_GENERATION_PATH")
        if target.get("head_target") != "Canonical/Grid81/HEAD.json":
            issues.append("TARGET_HEAD_PATH")
        for name in (
            "source_canonical_digest",
            "source_generation_semantic_digest",
            "expected_publication_ledger_head",
            "transaction_id",
        ):
            if not _hex64(target.get(name)):
                issues.append(name.upper())

        if (
            type(source) is dict
            and set(source) == _SOURCE_FIELDS
            and all(_hex64(value) for value in source.values())
            and _hex64(capability.get("operator_approval_digest"))
            and type(target.get("target_generation")) is int
            and _hex64(target.get("source_canonical_digest"))
            and _hex64(target.get("source_generation_semantic_digest"))
            and _hex64(target.get("expected_publication_ledger_head"))
            and _hex64(target.get("transaction_id"))
        ):
            expected_transaction_id = _transaction_id(
                plan_digest=source["promotion_plan_digest"],
                decision_digest=source["promotion_decision_digest"],
                source_chain_digest=source["source_chain_digest"],
                operator_approval_digest=capability[
                    "operator_approval_digest"
                ],
                source_canonical_digest=target[
                    "source_canonical_digest"
                ],
                source_generation_semantic_digest=target[
                    "source_generation_semantic_digest"
                ],
                target_generation=target["target_generation"],
                expected_publication_ledger_head=target[
                    "expected_publication_ledger_head"
                ],
            )
            if target["transaction_id"] != expected_transaction_id:
                issues.append("TRANSACTION_ID_RESERVATION_MISMATCH")

    if capability.get("constraints") != _CONSTRAINTS:
        issues.append("CONSTRAINTS")

    if capability.get("grants") != _GRANTS:
        issues.append("GRANTS")

    if capability.get("one_use") is not True:
        issues.append("ONE_USE")

    lifecycle = capability.get("lifecycle")
    if type(lifecycle) is not dict or set(lifecycle) != _LIFECYCLE_FIELDS:
        issues.append("LIFECYCLE_FIELDS")
    elif lifecycle != {
        "state": "GRANTED_UNCONSUMED",
        "consumed": False,
        "consumption_count": 0,
        "replay_permitted": False,
    }:
        issues.append("LIFECYCLE")

    claims = capability.get("claims_not_made")
    if (
        type(claims) is not list
        or any(type(item) is not str for item in claims)
        or claims != sorted(claims)
    ):
        issues.append("CLAIMS_NOT_MADE")

    # Identity authentication is independent of semantic rejection.
    # When the top-level record is structurally complete, recompute both
    # identities even if another binding has already failed so diagnostics
    # cannot hide a second tamper behind first-failure ordering.
    if set(capability) == _TOP_LEVEL_FIELDS:
        expected_id = _capability_id(capability)
        if capability["capability_id"] != expected_id:
            issues.append("CAPABILITY_ID_MISMATCH")

        digest_payload = {
            key: value
            for key, value in capability.items()
            if key != "capability_digest"
        }
        expected_digest = _capability_digest(digest_payload)
        if capability["capability_digest"] != expected_digest:
            issues.append("CAPABILITY_DIGEST_MISMATCH")

    return not issues, tuple(issues)


def require_promotion_capability(capability: dict) -> dict:
    """Return the exact capability or fail closed with the first issue."""

    valid, issues = validate_promotion_capability(capability)
    if not valid:
        raise PromotionAuthorityError(
            "PROMOTION_CAPABILITY_INVALID",
            issues[0] if issues else "UNKNOWN",
        )
    return capability
