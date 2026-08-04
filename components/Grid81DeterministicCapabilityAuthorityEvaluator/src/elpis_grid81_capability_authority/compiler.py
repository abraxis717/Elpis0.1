"""G5.2B Capability Compiler.

Compiles the complete canonical corpus: authority contexts, evaluation inputs,
decisions, capabilities, scopes, limits, abstentions, lifecycle entries, row index.
"""
import json
import os

from .canonical import canonical_json, sha256_file, sha256_bytes
from .source_join import load_jsonl, perform_source_join
from .authority_context import create_authority_context
from .policy import create_canonical_policy
from .evaluation_input import create_evaluation_input
from .decision import evaluate_authority, get_grant_claims_not_made
from .abstention import create_grant_abstention, create_abstention
from .scope import create_capability_scope
from .limits import create_capability_limit
from .capability import create_capability
from .lifecycle import create_lifecycle_entry
from .revocation_policy import create_revocation_policy


def write_jsonl(records: list, path: str):
    """Write records as canonical JSONL (sorted keys, no whitespace, newline-terminated)."""
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(canonical_json(record) + "\n")


def write_json(obj: dict, path: str):
    """Write canonical JSON."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(canonical_json(obj) + "\n")


def compile_one(source_request: dict, policy: dict, reports_dir: str) -> dict:
    """Compile a single row through the full authority pipeline."""
    # Authority context
    context = create_authority_context(source_request.get("request_digest", ""))

    # Evaluation input
    manifest_sha = source_request.get("source_manifest_sha256", "")
    eval_input = create_evaluation_input(
        source_request,
        policy["policy_digest"],
        context["authority_context_digest"],
        manifest_sha,
    )

    # Decision
    decision = evaluate_authority(eval_input, context, policy)

    # Abstention
    if decision["decision_outcome"] == "GRANT_CAPABILITY":
        abstention = create_grant_abstention()
    else:
        abstention = create_abstention(
            abstained=True,
            abstention_kind="NONE",
        )

    # Update decision with abstention digest
    decision["abstention_digest"] = abstention["abstention_digest"]

    # Capability (if granted)
    capability = None
    scope = None
    limit = None
    lifecycle = None

    if decision["decision_outcome"] == "GRANT_CAPABILITY":
        scope = create_capability_scope(source_request.get("referred_proposal_digests", []))
        limit = create_capability_limit()
        capability = create_capability(
            source_request_digest=source_request.get("request_digest", ""),
            source_adjudication_record_digest=source_request.get("adjudication_record_digest", ""),
            source_proposal_set_digest=source_request.get("proposal_set_digest", ""),
            authorized_proposal_digests=source_request.get("referred_proposal_digests", []),
            authority_policy_digest=policy["policy_digest"],
            authority_context=context,
        )
        lifecycle = create_lifecycle_entry(
            capability_digest=capability["capability_digest"],
            nonce_digest=capability["nonce_digest"],
        )

        decision["capability_digest"] = capability["capability_digest"]

    # Recompute decision digests after backfilling
    decision = recompute_decision(decision, abstention, capability)

    return {
        "context": context,
        "eval_input": eval_input,
        "decision": decision,
        "abstention": abstention,
        "scope": scope,
        "limit": limit,
        "capability": capability,
        "lifecycle": lifecycle,
    }


def recompute_decision(decision: dict, abstention: dict, capability: dict) -> dict:
    """Recompute decision digests after backfilling capability_digest."""
    from .canonical import canonical_digest

    decision["abstention_digest"] = abstention["abstention_digest"]
    if capability:
        decision["capability_digest"] = capability["capability_digest"]

    decision["authority_semantic_digest"] = canonical_digest({
        k: v for k, v in decision.items()
        if k not in ("authority_semantic_digest", "authority_decision_digest")
    })
    decision["authority_decision_digest"] = canonical_digest(decision)
    return decision


def compile_canonical_corpus(requests_path: str, adjudications_path: str,
                            dispositions_path: str, row_index_path: str,
                            reports_dir: str, manifest_sha: str) -> dict:
    """Compile the complete canonical G5.2B corpus."""

    # Load source data
    source_requests = load_jsonl(requests_path)

    # Create canonical policy
    policy = create_canonical_policy()

    # Create revocation policy
    revocation_policy = create_revocation_policy()

    # Compile all rows
    contexts = []
    eval_inputs = []
    decisions = []
    abstentions = []
    scopes = []
    limits = []
    capabilities = []
    lifecycles = []
    row_authority_index = []

    for req in source_requests:
        result = compile_one(req, policy, reports_dir)

        contexts.append(result["context"])
        eval_inputs.append(result["eval_input"])

        # For row authority index, bind to source row
        row_index_record = {
            "adjudication_record_digest": req.get("adjudication_record_digest", ""),
            "authority_context_digest": result["context"]["authority_context_digest"],
            "authority_decision_digest": result["decision"]["authority_decision_digest"],
            "capability_digest": result["capability"]["capability_digest"] if result["capability"] else None,
            "decision_outcome": result["decision"]["decision_outcome"],
            "evaluation_input_digest": result["eval_input"]["evaluation_input_digest"],
            "nonce_digest": result["capability"]["nonce_digest"] if result["capability"] else None,
            "request_digest": req.get("request_digest", ""),
            "scope_digest": result["scope"]["scope_digest"] if result["scope"] else None,
            "schema_version": "row-authority-index.v1",
        }
        row_authority_index.append(row_index_record)

        decisions.append(result["decision"])
        abstentions.append(result["abstention"])
        if result["scope"]:
            scopes.append(result["scope"])
        if result["limit"]:
            limits.append(result["limit"])
        if result["capability"]:
            capabilities.append(result["capability"])
        if result["lifecycle"]:
            lifecycles.append(result["lifecycle"])

    # Write inventories
    write_jsonl(contexts, os.path.join(reports_dir, "G52B_AUTHORITY_CONTEXT_INVENTORY.jsonl"))
    write_jsonl(eval_inputs, os.path.join(reports_dir, "G52B_AUTHORITY_EVALUATION_INPUT_INVENTORY.jsonl"))
    write_jsonl(decisions, os.path.join(reports_dir, "G52B_AUTHORITY_DECISION_INVENTORY.jsonl"))
    write_jsonl(abstentions, os.path.join(reports_dir, "G52B_CAPABILITY_ABSTENTION_INVENTORY.jsonl"))
    write_jsonl(scopes, os.path.join(reports_dir, "G52B_CAPABILITY_SCOPE_INVENTORY.jsonl"))
    write_jsonl(limits, os.path.join(reports_dir, "G52B_CAPABILITY_LIMIT_INVENTORY.jsonl"))
    write_jsonl(capabilities, os.path.join(reports_dir, "G52B_STRUCTURAL_INFLUENCE_CAPABILITY_INVENTORY.jsonl"))
    write_jsonl(lifecycles, os.path.join(reports_dir, "G52B_CAPABILITY_LIFECYCLE_INDEX.jsonl"))
    write_jsonl(row_authority_index, os.path.join(reports_dir, "G52B_ROW_AUTHORITY_INDEX.jsonl"))

    # Write policy and revocation policy
    write_json(policy, os.path.join(reports_dir, "G52B_CANONICAL_AUTHORITY_POLICY.json"))
    write_json(revocation_policy, os.path.join(reports_dir, "G52B_REVOCATION_POLICY.json"))

    # Compute canonical counts
    grant_count = sum(1 for d in decisions if d["decision_outcome"] == "GRANT_CAPABILITY")
    deny_count = sum(1 for d in decisions if d["decision_outcome"] == "DENY_CAPABILITY")
    defer_count = sum(1 for d in decisions if d["decision_outcome"] == "DEFER_AUTHORITY_EVALUATION")
    abstain_count = sum(1 for d in decisions if d["decision_outcome"] == "ABSTAIN_AUTHORITY_CONFLICT")
    reject_count = sum(1 for d in decisions if d["decision_outcome"] == "REJECT_INVALID_REQUEST")

    total_authorized_proposals = sum(len(c["authorized_proposal_digests"]) for c in capabilities)
    scope_size_1 = sum(1 for s in scopes if len(s["authorized_proposal_digests"]) == 1)
    scope_size_2 = sum(1 for s in scopes if len(s["authorized_proposal_digests"]) == 2)

    unique_nonces = set(c["nonce_digest"] for c in capabilities)
    duplicate_nonces = len(capabilities) - len(unique_nonces)

    lifecycle_states = {}
    for lc in lifecycles:
        state = lc["initial_lifecycle_state"]
        lifecycle_states[state] = lifecycle_states.get(state, 0) + 1

    return {
        "policy": policy,
        "revocation_policy": revocation_policy,
        "source_requests": len(source_requests),
        "evaluation_inputs": len(eval_inputs),
        "authority_contexts": len(contexts),
        "decisions": len(decisions),
        "capabilities": len(capabilities),
        "scopes": len(scopes),
        "limits": len(limits),
        "abstentions": len(abstentions),
        "lifecycles": len(lifecycles),
        "grant_count": grant_count,
        "deny_count": deny_count,
        "defer_count": defer_count,
        "abstain_count": abstain_count,
        "reject_count": reject_count,
        "total_authorized_proposals": total_authorized_proposals,
        "scope_size_1": scope_size_1,
        "scope_size_2": scope_size_2,
        "unique_nonces": len(unique_nonces),
        "duplicate_nonces": duplicate_nonces,
        "lifecycle_states": lifecycle_states,
        "single_use_count": sum(1 for l in limits if l["single_use"]),
        "nontransferable_count": sum(1 for c in capabilities if c["nontransferable"]),
        "logical_interval_0_0": sum(1 for l in limits if l["valid_from_logical_tick"] == 0 and l["valid_through_logical_tick"] == 0),
        "abstention_none_count": sum(1 for a in abstentions if a["abstention_kind"] == "NONE"),
    }
