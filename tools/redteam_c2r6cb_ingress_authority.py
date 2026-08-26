#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import replace
import inspect
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for rel in (
    "runtime/R0/src",
    "components/TRMFractalSpine/src",
    "components/Grid81DeterministicStructuralAdjudicator/src",
    "components/Grid81StructuralSemantics/src",
    "components/Pipeline/P0ControlProtocol/src",
    "components",
    "src",
):
    sys.path.insert(0, str(REPO / rel))

from elpis_p0.canonical import digest
from elpis_p0.contracts import ArtifactCandidate, RequestContext
from elpis_p0.factory import build_default_controller
from elpis_reference import p0_validator_ingress as ingress_module
from elpis_reference.p0_validator_ingress import (
    P0ValidatorIngressContractError,
    P0ValidatorIngressV1,
    bind_p0_validator_ingress_to_controller,
    build_p0_projection_trace,
)

FINDINGS = []
EXPLOITS = []


def record(check, status, detail):
    FINDINGS.append(
        {"check": check, "status": status, "detail": detail}
    )
    if status == "EXPLOIT":
        EXPLOITS.append(check)


class RejectingDecoder:
    def decode(self, context, plan):
        source = "def solution(:\n    return 1\n"
        return ArtifactCandidate(
            language="python",
            source=source,
            digest=digest(
                {"plan_digest": plan.plan_digest, "source": source}
            ),
        )


def fixture(request_id):
    ctx = RequestContext(
        request_id=request_id,
        prompt="write deterministic typed python solution and validate without imports",
        domain="python",
        entrypoint="solution",
        parameters=("x",),
    )
    controller = build_default_controller()
    controller.decoder = RejectingDecoder()
    ingress = bind_p0_validator_ingress_to_controller(controller)
    result = controller.run(ctx)
    authorized = controller.authorized_artifact_lineage(
        result, validator_index=0
    )
    trace = build_p0_projection_trace(
        projection_digest=result.projection.digest,
        grid81=result.projection.grid81,
        semantic_rows=result.projection.semantic_rows,
    )
    return ctx, controller, ingress, result, authorized, trace


def invoke(ingress, ctx, result, authorized, trace, evidence=None):
    return ingress.task_diagnostic_from_validator_failure(
        task_scope_id=ctx.request_id,
        frame_index=0,
        artifact_digest=result.artifact.digest,
        evidence=result.evidence[0] if evidence is None else evidence,
        projection_trace=trace,
        authorized=authorized,
    )


def check_surface():
    legacy = hasattr(
        ingress_module, "task_diagnostic_from_p0_validator_failure"
    )
    params = set(
        inspect.signature(
            P0ValidatorIngressV1.task_diagnostic_from_validator_failure
        ).parameters
    )
    forbidden = sorted(
        params.intersection(
            {"controller", "verifier", "authority", "authority_consumer", "consume"}
        )
    )
    direct = False
    try:
        P0ValidatorIngressV1()
        direct = True
    except TypeError:
        pass
    record(
        "request_surface_has_no_authority_selector",
        "DEFENSE_HOLDS" if not legacy and not forbidden and not direct else "EXPLOIT",
        {
            "legacy_bare_lineage_function": legacy,
            "forbidden_parameters": forbidden,
            "direct_construct_succeeded": direct,
        },
    )


def check_fake_composition():
    rejected = False
    error = None
    try:
        bind_p0_validator_ingress_to_controller(object())
    except P0ValidatorIngressContractError as exc:
        rejected = True
        error = str(exc)
    record(
        "composition_rejects_non_controller",
        "DEFENSE_HOLDS" if rejected else "EXPLOIT",
        {"rejected": rejected, "error": error},
    )


def check_cross_controller():
    ctx, _, ingress_a, result, authorized, trace = fixture("c2r6cb-rt-a")
    _, _, ingress_b, _, _, _ = fixture("c2r6cb-rt-b")
    rejected = False
    try:
        invoke(ingress_b, ctx, result, authorized, trace)
    except Exception:
        rejected = True
    if rejected:
        invoke(ingress_a, ctx, result, authorized, trace)
    record(
        "cross_controller_authorization_rejected",
        "DEFENSE_HOLDS" if rejected else "EXPLOIT",
        {"wrong_ingress_rejected": rejected, "real_capability_remained_live": rejected},
    )


def check_preconsumption_semantics():
    ctx, _, ingress, result, authorized, trace = fixture("c2r6cb-rt-sem")
    bad = replace(result.evidence[0], code="UNKNOWN_FAILURE")
    rejected = False
    try:
        invoke(
            ingress, ctx, result, authorized, trace, evidence=bad
        )
    except P0ValidatorIngressContractError:
        rejected = True
    real_live = False
    if rejected:
        invoke(ingress, ctx, result, authorized, trace)
        real_live = True
    record(
        "unsupported_evidence_precedes_consumption",
        "DEFENSE_HOLDS" if rejected and real_live else "EXPLOIT",
        {"unsupported_rejected": rejected, "real_capability_remained_live": real_live},
    )


def check_replay():
    ctx, _, ingress, result, authorized, trace = fixture("c2r6cb-rt-replay")
    invoke(ingress, ctx, result, authorized, trace)
    rejected = False
    try:
        invoke(ingress, ctx, result, authorized, trace)
    except Exception:
        rejected = True
    record(
        "production_ingress_replay_rejected",
        "DEFENSE_HOLDS" if rejected else "EXPLOIT",
        {"rejected": rejected},
    )


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    for check in (
        check_surface,
        check_fake_composition,
        check_cross_controller,
        check_preconsumption_semantics,
        check_replay,
    ):
        try:
            check()
        except Exception as exc:
            record(
                check.__name__,
                "HARNESS_ERROR",
                f"{type(exc).__name__}: {exc}",
            )

    report = {
        "schema": "elpis.redteam-c2r6cb-trusted-controller-ingress.v1",
        "base": "f3e1d67ec0e26a01fa8d5aca33c488ddea862c8f",
        "role": "READ_ONLY_ADVERSARIAL_DIAGNOSTIC",
        "findings": FINDINGS,
        "exploits": EXPLOITS,
        "exploit_count": len(EXPLOITS),
        "observations": {
            "hostile_same_process_isolation_claimed": False,
            "composition_code_can_construct_its_own_controller": True,
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    if not args.quiet:
        print(text)
    return 1 if EXPLOITS else 0


if __name__ == "__main__":
    raise SystemExit(main())
