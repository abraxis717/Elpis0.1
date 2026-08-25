from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .canonical import digest
from .contracts import P0Result


_LINEAGE_DOMAIN = "elpis.p0-artifact-proposal-lineage.c2r5.v1"

_VALIDATOR_EVIDENCE_DOMAIN = "elpis.p0-validator-evidence-binding.c2r5.v1"


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _domain_digest(domain: str, payload: object) -> str:
    return hashlib.sha256(
        domain.encode("utf-8") + b"\x00" + _canonical_bytes(payload)
    ).hexdigest()




def _validator_evidence_binding_digest(evidence) -> str:
    return _domain_digest(
        _VALIDATOR_EVIDENCE_DOMAIN,
        {
            "code": evidence.code,
            "details": [[str(key), value] for key, value in evidence.details],
            "message": evidence.message,
            "passed": bool(evidence.passed),
            "validator_id": evidence.validator_id,
        },
    )

def _result_payload(result: P0Result) -> dict[str, object]:
    return {
        "request_id": result.request_id,
        "accepted": result.accepted,
        "projection": result.projection.digest,
        "trm": result.trm_proposal.digest,
        "experts": result.expert_proposal.digest,
        "plan": result.decoder_plan.plan_digest,
        "artifact": result.artifact.digest,
        "evidence": result.evidence,
        "accounting": result.accounting,
        "trace": result.trace,
        "expansion_executed": result.expansion_executed,
        "executed_experts": result.executed_experts,
        "governance_invoked": result.governance_invoked,
    }


def _trm_payload(result: P0Result) -> dict[str, object]:
    proposal = result.trm_proposal
    return {
        "input_digest": proposal.input_digest,
        "proposed_grid81": proposal.proposed_grid81,
        "residual81": proposal.residual81,
        "halt_score": proposal.halt_score,
        "expansion_cells": proposal.expansion_cells,
        "rationale": proposal.rationale,
        "request_id": result.request_id,
    }


def _plan_payload(result: P0Result) -> dict[str, object]:
    plan = result.decoder_plan
    return {
        "backend": plan.backend,
        "language": plan.language,
        "temperature": plan.temperature,
        "max_tokens": plan.max_tokens,
        "selected_experts": plan.selected_experts,
        "function_name": plan.function_name,
        "parameters": plan.parameters,
        "body_lines": plan.body_lines,
        "structural_digest": plan.structural_digest,
        "structural_proposal_digest": plan.structural_proposal_digest,
    }


@dataclass(frozen=True, slots=True)
class P0ArtifactProposalLineageV1:
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


def build_artifact_proposal_lineage(
    result: P0Result,
    *,
    validator_index: int,
) -> P0ArtifactProposalLineageV1:
    if not result.request_id:
        raise ValueError("P0 result request_id cannot be empty")

    if digest(_result_payload(result)) != result.result_digest:
        raise ValueError("P0 result digest does not match result contents")

    proposal = result.trm_proposal
    proposal.validate()
    if proposal.input_digest != result.projection.digest:
        raise ValueError("P0 structural proposal is not bound to the projection")
    if digest(_trm_payload(result)) != proposal.digest:
        raise ValueError("P0 structural proposal digest does not match proposal contents")

    plan = result.decoder_plan
    if plan.structural_digest != result.projection.digest:
        raise ValueError("decoder plan is not bound to the P0 projection")
    if not plan.structural_proposal_digest:
        raise ValueError("decoder plan is missing structural proposal binding")
    if plan.structural_proposal_digest != proposal.digest:
        raise ValueError("decoder plan structural proposal binding mismatch")
    if digest(_plan_payload(result)) != plan.plan_digest:
        raise ValueError("decoder plan digest does not match plan contents")

    expected_artifact = digest(
        {
            "plan_digest": plan.plan_digest,
            "source": result.artifact.source,
        }
    )
    if expected_artifact != result.artifact.digest:
        raise ValueError("artifact digest does not match decoder plan and source")

    if validator_index < 0 or validator_index >= len(result.evidence):
        raise IndexError("validator_index outside P0 evidence")
    evidence = result.evidence[validator_index]
    if evidence.passed:
        raise ValueError("artifact lineage requires rejecting validator evidence")
    if not evidence.validator_id or not evidence.code:
        raise ValueError("validator evidence identity is incomplete")

    evidence_digest = _validator_evidence_binding_digest(evidence)
    payload = {
        "artifact_digest": result.artifact.digest,
        "decoder_plan_digest": plan.plan_digest,
        "p0_result_digest": result.result_digest,
        "projection_digest": result.projection.digest,
        "request_id": result.request_id,
        "structural_proposal_digest": proposal.digest,
        "validator_code": evidence.code,
        "validator_evidence_digest": evidence_digest,
        "validator_id": evidence.validator_id,
        "validator_index": validator_index,
    }
    lineage_digest = _domain_digest(_LINEAGE_DOMAIN, payload)

    return P0ArtifactProposalLineageV1(
        request_id=result.request_id,
        p0_result_digest=result.result_digest,
        projection_digest=result.projection.digest,
        structural_proposal_digest=proposal.digest,
        decoder_plan_digest=plan.plan_digest,
        artifact_digest=result.artifact.digest,
        validator_index=validator_index,
        validator_evidence_digest=evidence_digest,
        validator_id=evidence.validator_id,
        validator_code=evidence.code,
        lineage_digest=lineage_digest,
    )
