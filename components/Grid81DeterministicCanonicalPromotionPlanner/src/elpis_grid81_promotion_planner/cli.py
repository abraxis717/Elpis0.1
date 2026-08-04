"""CLI entry point — side-effect-free promotion planner interface."""

import argparse
import json
import sys
from .canonical import AuthorityAudit, GateResult, REJECTION_PRECEDENCE
from .source_binding import build_source_chain
from .gates import evaluate_gates, GATE_DEFINITIONS, first_failure
from .decision import make_decision, DECISION_READY
from .plan import render_plan, get_intentions
from .verifier import (
    verify_source_nonmutation,
    run_adversarial_tests,
    verify_three_seed_determinism,
    verify_plan_nonexecutable,
    generate_authority_audit,
)


def _load_config(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def _census(config: dict) -> dict:
    chain = build_source_chain(config)
    return {
        "g53b1": {
            "phase_id": chain.g53b1.phase_id,
            "source_directory": chain.g53b1.source_directory,
            "manifest_digest": chain.g53b1.manifest_digest,
            "disposition": chain.g53b1.disposition,
            "evidence_file_count": len(chain.g53b1.evidence_files),
        },
        "g53c": {
            "phase_id": chain.g53c.phase_id,
            "source_directory": chain.g53c.source_directory,
            "manifest_digest": chain.g53c.manifest_digest,
            "disposition": chain.g53c.disposition,
            "evidence_file_count": len(chain.g53c.evidence_files),
            "artifact_digest": chain.g53c.artifact_digest,
            "capability_digest": chain.g53c.capability_digest,
            "lifecycle_state": chain.g53c.lifecycle_state,
            "shadow_receipt_digest": chain.g53c.shadow_receipt_digest,
            "resulting_state_digest": chain.g53c.resulting_state_digest,
            "resulting_ledger_head": chain.g53c.resulting_ledger_head,
        },
        "g53d": {
            "phase_id": chain.g53d.phase_id,
            "source_directory": chain.g53d.source_directory,
            "manifest_digest": chain.g53d.manifest_digest,
            "disposition": chain.g53d.disposition,
            "evidence_file_count": len(chain.g53d.evidence_files),
            "bundle_digest": chain.g53d.bundle_digest,
        },
        "chain_digest": chain.chain_digest,
    }


def _verify_chain(config: dict) -> dict:
    census = _census(config)
    chain = build_source_chain(config)
    return {
        "census": census,
        "chain_digest": chain.chain_digest,
        "chain_version": chain.chain_version,
    }


def _gates(config: dict) -> list:
    chain = build_source_chain(config)
    results = evaluate_gates(chain)
    return [
        {
            "gate_id": r.gate_id,
            "gate_ordinal": r.gate_ordinal,
            "gate_version": r.gate_version,
            "passed": r.passed,
            "rejection_code": r.rejection_code,
            "observed_value": r.observed_value,
            "expected_value": r.expected_value,
            "gate_digest": r.digest,
        }
        for r in results
    ]


def _decide(config: dict) -> dict:
    chain = build_source_chain(config)
    results = evaluate_gates(chain)
    decision = make_decision(results, chain)
    return {
        "decision": decision.decision,
        "gate_vector": list(decision.gate_vector),
        "source_chain_digest": decision.source_chain_digest,
        "expected_canonical_preconditions": list(decision.expected_canonical_preconditions),
        "planner_version": decision.planner_version,
        "decision_digest": decision.digest,
        "first_failure": first_failure(results),
    }


def _render_plan(config: dict) -> dict:
    chain = build_source_chain(config)
    results = evaluate_gates(chain)
    decision = make_decision(results, chain)
    plan = render_plan(decision, chain)

    if plan is None:
        return {
            "plan": None,
            "reason": f"Decision is {decision.decision}, not {DECISION_READY}",
            "decision_digest": decision.digest,
        }

    return {
        "plan": {
            "intentions": list(plan.intentions),
            "decision_digest": plan.decision_digest,
            "source_chain_digest": plan.source_chain_digest,
            "planner_version": plan.planner_version,
            "executable": plan.executable,
            "self_applying": plan.self_applying,
            "authoritative": plan.authoritative,
            "canonical_write_permitted": plan.canonical_write_permitted,
            "plan_digest": plan.digest,
        },
        "intentions_detail": [
            {
                "intention_type": i.intention_type,
                "description": i.description,
                "precondition": i.precondition,
                "parameter_digest": i.parameter_digest,
            }
            for i in get_intentions()
        ],
    }


def _authority(config: dict) -> dict:
    audit = generate_authority_audit(config)
    plan_check = verify_plan_nonexecutable()
    return {
        **audit.__dict__,
        "authority_digest": audit.digest,
        "plan_non_executable": plan_check["plan_non_executable"],
        "plan_violations": plan_check["violation_details"],
    }


def _json_output(obj: any) -> str:
    return json.dumps(obj, sort_keys=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        prog="g53e-plan",
        description="G5.3E Deterministic Canonical Promotion Planner",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # census
    p_census = subparsers.add_parser("census", help="Perform source chain census")
    p_census.add_argument("--source-config", required=True, help="Path to source config JSON")
    p_census.add_argument("--output", help="Output path (default: stdout)")

    # verify-chain
    p_verify = subparsers.add_parser("verify-chain", help="Verify source chain binding")
    p_verify.add_argument("--source-config", required=True, help="Path to source config JSON")
    p_verify.add_argument("--output", help="Output path (default: stdout)")

    # gates
    p_gates = subparsers.add_parser("gates", help="Evaluate promotion gates")
    p_gates.add_argument("--source-config", required=True, help="Path to source config JSON")
    p_gates.add_argument("--output", help="Output path (default: stdout)")

    # decide
    p_decide = subparsers.add_parser("decide", help="Make promotion decision")
    p_decide.add_argument("--source-config", required=True, help="Path to source config JSON")
    p_decide.add_argument("--output", help="Output path (default: stdout)")

    # render-plan
    p_plan = subparsers.add_parser("render-plan", help="Render canonical promotion plan")
    p_plan.add_argument("--source-config", required=True, help="Path to source config JSON")
    p_plan.add_argument("--output", help="Output path (default: stdout)")

    # authority
    p_authority = subparsers.add_parser("authority", help="Display authority audit")
    p_authority.add_argument("--source-config", required=True, help="Path to source config JSON")
    p_authority.add_argument("--output", help="Output path (default: stdout)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    config = _load_config(args.source_config)

    dispatch = {
        "census": _census,
        "verify-chain": _verify_chain,
        "gates": _gates,
        "decide": _decide,
        "render-plan": _render_plan,
        "authority": _authority,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)

    result = handler(config)
    output = _json_output(result)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
            f.write("\n")
    else:
        print(output)


if __name__ == "__main__":
    main()