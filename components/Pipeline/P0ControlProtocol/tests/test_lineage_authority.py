from __future__ import annotations

import hashlib
import json
import pytest

import elpis_p0.lineage_authority as authority_module
from elpis_p0.canonical import digest
from elpis_p0.contracts import ArtifactCandidate, RequestContext
from elpis_p0.factory import build_default_controller
from elpis_p0.lineage_authority import (
    P0LineageAuthorityError,
    P0LineageAuthorityReceiptV1,
    RECEIPT_DOMAIN,
)


class RejectingDecoder:
    def decode(self, context, plan):
        source="def solution(:\n    return 1\n"
        return ArtifactCandidate(
            language="python",
            source=source,
            digest=digest({"plan_digest":plan.plan_digest,"source":source}),
        )


def ctx():
    return RequestContext(
        request_id="c2r6ca-authority",
        prompt="write deterministic python and validate it",
        domain="python",
        entrypoint="solution",
        parameters=("x",),
    )


def rejected():
    c=build_default_controller(); c.decoder=RejectingDecoder(); r=c.run(ctx())
    assert not r.accepted and r.evidence[0].code=="SYNTAX_ERROR"
    return c,r


def d(domain,payload):
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
    return hashlib.sha256(domain.encode()+b"\\x00"+raw).hexdigest()


def test_precommit_occurs_during_run_not_reveal(monkeypatch):
    c=build_default_controller(); c.decoder=RejectingDecoder(); calls=[]
    def token(n):
        calls.append(n); return f"{len(calls):064x}"
    monkeypatch.setattr(authority_module.secrets,"token_hex",token)
    r=c.run(ctx())
    after=tuple(calls)
    assert after==(32,)
    a=c.authorized_artifact_lineage(r,validator_index=0)
    assert tuple(calls)==after
    assert a.receipt.capability_id=="1".zfill(64)


def test_real_receipt_consumes_once_and_replay_rejects():
    c,r=rejected(); a=c.authorized_artifact_lineage(r,validator_index=0); v=c.lineage_authority_verifier()
    consumption=v.consume(receipt=a.receipt,lineage=a.lineage)
    assert consumption.lineage_digest==a.lineage.lineage_digest
    with pytest.raises(P0LineageAuthorityError,match="not active"):
        v.consume(receipt=a.receipt,lineage=a.lineage)


def test_cross_controller_verifier_rejects_receipt():
    c,r=rejected(); a=c.authorized_artifact_lineage(r,validator_index=0); other=build_default_controller()
    with pytest.raises(P0LineageAuthorityError,match="another authority"):
        other.lineage_authority_verifier().consume(receipt=a.receipt,lineage=a.lineage)


def test_self_consistent_unissued_receipt_rejects_registry_membership():
    c,r=rejected(); a=c.authorized_artifact_lineage(r,validator_index=0); v=c.lineage_authority_verifier()
    base={
        "authority_instance_id":v.authority_instance_id,
        "capability_id":"a"*64,
        "issuance_sequence":999,
        "lineage_digest":a.lineage.lineage_digest,
        "p0_result_digest":a.lineage.p0_result_digest,
        "request_id":a.lineage.request_id,
        "validator_evidence_digest":a.lineage.validator_evidence_digest,
        "validator_index":a.lineage.validator_index,
    }
    fake=P0LineageAuthorityReceiptV1(**base,receipt_digest=d(RECEIPT_DOMAIN,base))
    with pytest.raises(P0LineageAuthorityError,match="not active"):
        v.consume(receipt=fake,lineage=a.lineage)


def test_same_precommit_cannot_be_revealed_twice():
    c,r=rejected(); c.authorized_artifact_lineage(r,validator_index=0)
    with pytest.raises(P0LineageAuthorityError,match="absent or already revealed"):
        c.authorized_artifact_lineage(r,validator_index=0)


def test_foreign_controller_cannot_reveal_result():
    _,r=rejected(); other=build_default_controller()
    with pytest.raises(P0LineageAuthorityError,match="not precommitted"):
        other.authorized_artifact_lineage(r,validator_index=0)
