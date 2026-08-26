#!/usr/bin/env python3
"""Read-only C2R7-A relational semantic IR adversarial diagnostic."""
from __future__ import annotations

from dataclasses import replace
import argparse
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

from elpis_p0.contracts import RequestContext
from elpis_p0.projector import DeterministicPythonProjector
from elpis_p0.semantic_ir import (
    P0SemanticRequestContractError,
    SemanticConstraintV1,
    SemanticDependencyV1,
    SemanticEntityV1,
    SemanticOperationV1,
    SemanticQuantityV1,
    SemanticRelationV1,
    build_semantic_request_v1,
)

FINDINGS = []
EXPLOITS = []


def record(check, status, detail):
    FINDINGS.append(
        {"check": check, "status": status, "detail": detail}
    )
    if status == "EXPLOIT":
        EXPLOITS.append(check)


def build(
    *,
    reverse_relation=False,
    reverse_dependency=False,
    negated=False,
    count=5,
    data_type="str",
    input_order=("path", "dsn"),
    reverse_declarations=False,
):
    entities = (
        SemanticEntityV1("path", "resource", "file", data_type),
        SemanticEntityV1("dsn", "resource", "database", data_type),
        SemanticEntityV1("record", "value", "record", "dict"),
    )
    operations = (
        SemanticOperationV1(
            "read",
            "read",
            input_entity_ids=input_order,
            output_entity_ids=("record",),
        ),
        SemanticOperationV1(
            "write",
            "write",
            input_entity_ids=("record", "dsn"),
        ),
    )
    if reverse_declarations:
        entities = tuple(reversed(entities))
        operations = tuple(reversed(operations))
    return build_semantic_request_v1(
        request_id="c2r7a-redteam",
        entities=entities,
        operations=operations,
        constraints=(
            SemanticConstraintV1(
                "constraint",
                "network_access",
                "read",
                negated=negated,
            ),
        ),
        relations=(
            SemanticRelationV1(
                "relation",
                "dsn" if reverse_relation else "path",
                "feeds",
                "path" if reverse_relation else "dsn",
            ),
        ),
        dependencies=(
            SemanticDependencyV1(
                "dependency",
                "write" if reverse_dependency else "read",
                "read" if reverse_dependency else "write",
            ),
        ),
        quantities=(
            SemanticQuantityV1(
                "quantity",
                "read",
                "input_arity",
                "eq",
                count,
            ),
        ),
        output_entity_ids=("record",),
    )


def distinction(name, mutated):
    base = build()
    changed = mutated()
    record(
        name,
        "DEFENSE_HOLDS"
        if base.digest != changed.digest
        else "EXPLOIT",
        {
            "base_digest": base.digest,
            "changed_digest": changed.digest,
        },
    )


def declaration_order():
    base = build()
    reordered = build(reverse_declarations=True)
    record(
        "declaration_order_canonicalized",
        "DEFENSE_HOLDS"
        if base.digest == reordered.digest
        else "EXPLOIT",
        {
            "base_digest": base.digest,
            "reordered_digest": reordered.digest,
        },
    )


def invalid_graphs():
    cycle_rejected = False
    dangling_rejected = False
    tamper_rejected = False

    try:
        build_semantic_request_v1(
            request_id="cycle",
            entities=(
                SemanticEntityV1("x", "value", "x"),
            ),
            operations=(
                SemanticOperationV1("a", "step"),
                SemanticOperationV1("b", "step"),
            ),
            dependencies=(
                SemanticDependencyV1("ab", "a", "b"),
                SemanticDependencyV1("ba", "b", "a"),
            ),
        )
    except P0SemanticRequestContractError:
        cycle_rejected = True

    try:
        build_semantic_request_v1(
            request_id="dangling",
            entities=(
                SemanticEntityV1("x", "value", "x"),
            ),
            operations=(
                SemanticOperationV1(
                    "a",
                    "step",
                    input_entity_ids=("missing",),
                ),
            ),
        )
    except P0SemanticRequestContractError:
        dangling_rejected = True

    forged = replace(build(), digest="0" * 64)
    try:
        forged.validate()
    except P0SemanticRequestContractError:
        tamper_rejected = True

    record(
        "invalid_graphs_fail_closed",
        "DEFENSE_HOLDS"
        if cycle_rejected and dangling_rejected and tamper_rejected
        else "EXPLOIT",
        {
            "cycle_rejected": cycle_rejected,
            "dangling_rejected": dangling_rejected,
            "digest_tamper_rejected": tamper_rejected,
        },
    )


def silent_drop():
    graph = build()
    context = RequestContext(
        request_id=graph.request_id,
        prompt="read a file and write a database",
        parameters=("path", "dsn"),
        semantic_request=graph,
    )
    rejected = False
    error = None
    try:
        DeterministicPythonProjector().project(context)
    except ValueError as exc:
        rejected = "structured semantic request" in str(exc)
        error = str(exc)
    record(
        "legacy_keyword_projector_cannot_silently_drop_graph",
        "DEFENSE_HOLDS" if rejected else "EXPLOIT",
        {"rejected": rejected, "error": error},
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    distinction(
        "relation_direction_preserved",
        lambda: build(reverse_relation=True),
    )
    distinction(
        "dependency_direction_preserved",
        lambda: build(reverse_dependency=True),
    )
    distinction(
        "negation_preserved",
        lambda: build(negated=True),
    )
    distinction(
        "quantity_4_to_5_preserved",
        lambda: build(count=4),
    )
    distinction(
        "quantity_5_to_6_preserved",
        lambda: build(count=6),
    )
    distinction(
        "entity_type_preserved",
        lambda: build(data_type="bytes"),
    )
    distinction(
        "operation_argument_order_preserved",
        lambda: build(input_order=("dsn", "path")),
    )
    declaration_order()
    invalid_graphs()
    silent_drop()

    report = {
        "schema": "elpis.redteam-c2r7a-relational-semantic-ir.v1",
        "base": "06db7c83fcbd24d0e0ec0ac3ca8d552cbb2f2d0b",
        "role": "READ_ONLY_ADVERSARIAL_DIAGNOSTIC",
        "exploit_count": len(EXPLOITS),
        "exploits": EXPLOITS,
        "findings": FINDINGS,
        "claim_boundary": {
            "canonical_relational_representation": True,
            "natural_language_extraction": False,
            "grid81_binding": False,
            "semantic_reconstruction": False,
            "relational_ecs_decomposition": False,
            "learned_compiler": False,
            "runtime_admission": False,
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
