from __future__ import annotations

from dataclasses import replace
import pytest

from elpis_p0.artifact_lineage import build_artifact_proposal_lineage
from elpis_p0.canonical import digest
from elpis_p0.contracts import ArtifactCandidate, RequestContext
from elpis_p0.factory import build_default_controller


class RejectingDecoder:
    def decode(self, context, plan):
        source = "def solution(:\n    return 1\n"
        return ArtifactCandidate(
            language="python",
            source=source,
            digest=digest({"plan_digest": plan.plan_digest, "source": source}),
        )


def rejected_result():
    controller = build_default_controller()
    controller.decoder = RejectingDecoder()
    result = controller.run(
        RequestContext(
            request_id="c2r5-lineage",
            prompt="write deterministic typed python solution and validate without imports",
            domain="python",
            entrypoint="solution",
            parameters=("x",),
        )
    )
    assert not result.accepted
    assert len(result.evidence) == 1
    assert not result.evidence[0].passed
    return result


def test_lineage_binds_real_p0_proposal_plan_artifact_and_validator():
    result = rejected_result()
    lineage = build_artifact_proposal_lineage(result, validator_index=0)
    assert lineage.request_id == result.request_id
    assert lineage.p0_result_digest == result.result_digest
    assert lineage.projection_digest == result.projection.digest
    assert lineage.structural_proposal_digest == result.trm_proposal.digest
    assert lineage.decoder_plan_digest == result.decoder_plan.plan_digest
    assert lineage.artifact_digest == result.artifact.digest
    assert lineage.validator_id == result.evidence[0].validator_id
    assert lineage.validator_code == result.evidence[0].code
    assert len(lineage.lineage_digest) == 64


def test_tampered_artifact_source_fails_before_lineage():
    result = rejected_result()
    tampered = replace(
        result,
        artifact=replace(result.artifact, source=result.artifact.source + "\n"),
    )
    with pytest.raises(ValueError, match="artifact digest does not match decoder plan and source"):
        build_artifact_proposal_lineage(tampered, validator_index=0)


def test_tampered_structural_proposal_fails_before_lineage():
    result = rejected_result()
    proposal = result.trm_proposal
    changed = list(proposal.proposed_grid81)
    changed[0] = (changed[0] + 1) % 10
    tampered = replace(
        result,
        trm_proposal=replace(proposal, proposed_grid81=tuple(changed)),
    )
    with pytest.raises(ValueError, match="structural proposal digest does not match proposal contents"):
        build_artifact_proposal_lineage(tampered, validator_index=0)


def test_plan_must_bind_exact_structural_proposal():
    result = rejected_result()
    tampered = replace(
        result,
        decoder_plan=replace(
            result.decoder_plan,
            structural_proposal_digest="0" * 64,
        ),
    )
    with pytest.raises(ValueError, match="decoder plan structural proposal binding mismatch"):
        build_artifact_proposal_lineage(tampered, validator_index=0)


def test_tampered_result_receipt_fails_closed():
    result = rejected_result()
    tampered = replace(result, result_digest="f" * 64)
    with pytest.raises(ValueError, match="P0 result digest does not match result contents"):
        build_artifact_proposal_lineage(tampered, validator_index=0)
