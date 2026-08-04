"""G5.3B Structural influence artifact compilation.

Produces BOUNDED_STRUCTURAL_INFLUENCE_ARTIFACT_V1 with UNAPPLIED state.
No activation, no selection, no ranking. Complete authorized proposal set preserved.
"""
from .canonical import canonical_digest, domain_digest
from .validation import FORBIDDEN_FIELDS, check_forbidden_fields


def create_structural_influence_artifact(capability: dict, lifecycle: dict,
                                         request: dict, compiler_contract: dict) -> dict:
    """Create an inert structural-influence artifact.

    Artifact contains ALL authorized proposal digests — no dropping, adding,
    ranking, scoring, weighting, or selection.
    """
    authorized_proposals = sorted(capability.get("authorized_proposal_digests", []))

    # Build proposal bindings — one per proposal
    proposal_bindings = []
    for proposal_digest in authorized_proposals:
        binding_payload = {
            "proposal_digest": proposal_digest,
            "source_capability_digest": capability["capability_digest"],
        }
        binding = {
            "schema_version": "structural-influence-proposal-binding.v1",
            "proposal_digest": proposal_digest,
            "source_capability_digest": capability["capability_digest"],
            "binding_state": "INCLUDED_UNAPPLIED",
            "binding_digest": canonical_digest(binding_payload),
        }
        proposal_bindings.append(binding)

    # Compute scope digest
    proposal_binding_digests = sorted([b["binding_digest"] for b in proposal_bindings])
    scope_payload = {
        "authorized_proposal_digests": authorized_proposals,
        "proposal_binding_digests": proposal_binding_digests,
        "source_capability_digest": capability["capability_digest"],
    }
    scope_digest = canonical_digest(scope_payload)

    # Claims not made — avoid forbidden-field substrings
    claims = sorted([
        "artifact does not enforce structural influence",
        "artifact does not activate runtime components",
        "artifact does not dispatch execution",
        "artifact does not load models",
        "artifact does not load adapters",
        "artifact does not choose a preferred proposal",
        "artifact does not order proposals by preference",
        "artifact does not evaluate proposal quality",
    ])

    # Compute consumption_receipt_digest placeholder (filled after receipt creation)
    artifact = {
        "schema_version": "structural-influence-artifact.v1",
        "artifact_class": "BOUNDED_STRUCTURAL_INFLUENCE_ARTIFACT_V1",
        "materialization_class": "MATERIALIZE_AUTHORIZED_STRUCTURAL_INFLUENCE_SET_V1",
        "target_domain_class": "GRID81_STRUCTURAL_PROPOSAL_DOMAIN_V1",
        "source_capability_digest": capability["capability_digest"],
        "source_capability_semantic_digest": capability["capability_semantic_digest"],
        "source_request_digest": capability["source_request_digest"],
        "source_adjudication_record_digest": capability["source_adjudication_record_digest"],
        "source_proposal_set_digest": capability["source_proposal_set_digest"],
        "authorized_proposal_digests": authorized_proposals,
        "proposal_bindings": proposal_bindings,
        "structural_influence_scope_digest": scope_digest,
        "consumer_class": "STRUCTURAL_INFLUENCE_COMPILER_V1",
        "consumer_contract_digest": request["consumer_contract_digest"],
        "consumption_request_digest": request["consumption_request_digest"],
        "consumption_receipt_digest": "",
        "logical_tick": request["logical_tick"],
        "application_state": "UNAPPLIED",
        "compiler_contract_digest": compiler_contract["compiler_contract_digest"],
        "artifact_semantic_digest": "",
        "artifact_digest": "",
        "claims_not_made": claims,
    }

    # Compute semantic digest (excludes artifact_digest)
    semantic_payload = {
        "artifact_class": artifact["artifact_class"],
        "authorized_proposal_digests": artifact["authorized_proposal_digests"],
        "consumer_class": artifact["consumer_class"],
        "materialization_class": artifact["materialization_class"],
        "target_domain_class": artifact["target_domain_class"],
        "application_state": artifact["application_state"],
        "source_capability_digest": artifact["source_capability_digest"],
        "source_capability_semantic_digest": artifact["source_capability_semantic_digest"],
        "structural_influence_scope_digest": artifact["structural_influence_scope_digest"],
        "proposal_bindings": artifact["proposal_bindings"],
        "consumption_request_digest": artifact["consumption_request_digest"],
        "compiler_contract_digest": artifact["compiler_contract_digest"],
    }
    artifact["artifact_semantic_digest"] = canonical_digest(semantic_payload)

    # Compute artifact digest (full record minus artifact_digest itself)
    digest_fields = {k: v for k, v in artifact.items() if k != "artifact_digest"}
    artifact["artifact_digest"] = canonical_digest(digest_fields)

    # Check for forbidden fields
    forbidden = check_forbidden_fields(artifact)
    if forbidden:
        from .errors import ForbiddenFieldError
        raise ForbiddenFieldError(f"Forbidden fields in artifact: {forbidden}")

    return artifact
