from __future__ import annotations

import hashlib
import inspect
import json

import elpis_p0.lineage_authority as authority_module
from elpis_p0.canonical import digest
from elpis_p0.contracts import ArtifactCandidate, RequestContext
from elpis_p0.controller import P0Controller
from elpis_p0.factory import build_default_controller
from elpis_p0.lineage_authority import (
    P0AuthorizedArtifactLineageV1,
    P0LineageAuthorityError,
    P0LineageAuthorityReceiptV1,
    RECEIPT_DOMAIN,
)


class RejectingDecoder:
    def decode(self, context, plan):
        source = "def solution(:\n    return 1\n"
        return ArtifactCandidate(
            language="python",
            source=source,
            digest=digest({"plan_digest": plan.plan_digest, "source": source}),
        )


def dd(domain, payload):
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(domain.encode("utf-8") + b"\x00" + raw).hexdigest()


def main():
    if "lineage_authority" in inspect.signature(P0Controller).parameters:
        raise RuntimeError("caller authority injection survived")
    if hasattr(P0Controller, "lineage_authority_verifier"):
        raise RuntimeError("public verifier selector survived")
    if hasattr(authority_module, "P0LineageAuthorityV1"):
        raise RuntimeError("public standalone issuer survived")

    context = RequestContext(
        request_id="c2r6ca-corrected-e2e",
        prompt="write deterministic python and validate it",
        domain="python",
        entrypoint="solution",
        parameters=("x",),
    )
    controller = build_default_controller()
    controller.decoder = RejectingDecoder()
    result = controller.run(context)
    if result.accepted:
        raise RuntimeError("fixture accepted")

    authorized = controller.authorized_artifact_lineage(result, validator_index=0)
    controller.consume_authorized_artifact_lineage(authorized)

    replay_rejected = False
    try:
        controller.consume_authorized_artifact_lineage(authorized)
    except P0LineageAuthorityError:
        replay_rejected = True
    if not replay_rejected:
        raise RuntimeError("replay accepted")

    other = build_default_controller()
    distinct_rejected = False
    try:
        other.consume_authorized_artifact_lineage(authorized)
    except P0LineageAuthorityError:
        distinct_rejected = True
    if not distinct_rejected:
        raise RuntimeError("distinct authority instance accepted receipt")

    base = {
        "authority_instance_id": authorized.receipt.authority_instance_id,
        "capability_id": "c" * 64,
        "issuance_sequence": 777,
        "lineage_digest": authorized.lineage.lineage_digest,
        "p0_result_digest": authorized.lineage.p0_result_digest,
        "request_id": authorized.lineage.request_id,
        "validator_evidence_digest": authorized.lineage.validator_evidence_digest,
        "validator_index": authorized.lineage.validator_index,
    }
    forged = P0AuthorizedArtifactLineageV1(
        lineage=authorized.lineage,
        receipt=P0LineageAuthorityReceiptV1(
            **base,
            receipt_digest=dd(RECEIPT_DOMAIN, base),
        ),
    )
    unissued_rejected = False
    try:
        controller.consume_authorized_artifact_lineage(forged)
    except P0LineageAuthorityError:
        unissued_rejected = True
    if not unissued_rejected:
        raise RuntimeError("unissued self-consistent receipt accepted")

    print(
        json.dumps(
            {
                "schema": "elpis.public-c2r6ca-controller-associated-issuance-registry.v2",
                "status": "PASS",
                "claims": {
                    "controller_precommit_before_result_return": True,
                    "supported_authority_injection_removed": True,
                    "public_standalone_issuer_removed": True,
                    "public_verifier_selector_removed": True,
                    "one_shot_registry_consumption": True,
                    "replay_rejected": replay_rejected,
                    "distinct_authority_instance_rejected": distinct_rejected,
                    "self_consistent_unissued_receipt_rejected": unissued_rejected,
                    "hostile_same_process_isolation": False,
                    "retention_lifecycle_bounded": False,
                    "production_validator_ingress_requires_receipt": False,
                    "external_attestation": False,
                    "cross_process_durability": False,
                    "runtime_admission": False,
                },
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
