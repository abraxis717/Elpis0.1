"""Experimental C2R7-C structural constraint features.

This is an experimental neural-input sidecar, not a production ABI.

It encodes only declared structural invariants and their current residual
membership. Semantic identifiers and hidden/final solution grids are absent.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Protocol


LANES = 8

BINARY_KINDS = (
    "PRECEDES",
    "CROSS_LANE_ROUTE",
    "MEMORY_SPAN",
)

UNARY_LANE_KINDS = (
    "LANE_SINGLE_OCCUPANCY",
    "CONSTRAINT_AFTER",
    "INTERFACE_TERMINAL",
)


class StructuralFeatureError(ValueError):
    pass


class InvariantLike(Protocol):
    invariant_id: str
    kind: str
    lanes: tuple[int, ...]


def _build_signature_vocabulary() -> tuple[tuple[str, tuple[int, ...]], ...]:
    out: list[tuple[str, tuple[int, ...]]] = [
        ("TERMINAL_RESOLUTION", ())
    ]

    for lane in range(LANES):
        out.append(("LANE_SINGLE_OCCUPANCY", (lane,)))

    for kind in BINARY_KINDS:
        for a in range(LANES):
            for b in range(LANES):
                if a != b:
                    out.append((kind, (a, b)))

    for a in range(LANES):
        for b in range(LANES):
            if b == a:
                continue
            for c in range(LANES):
                if c != a and c != b:
                    out.append(("MUTATION_HAZARD", (a, b, c)))

    for kind in ("CONSTRAINT_AFTER", "INTERFACE_TERMINAL"):
        for lane in range(LANES):
            out.append((kind, (lane,)))

    return tuple(out)


SIGNATURES = _build_signature_vocabulary()
SIGNATURE_TO_INDEX = {
    signature: index
    for index, signature in enumerate(SIGNATURES)
}

FEATURE_WIDTH = len(SIGNATURES)

VOCABULARY_DIGEST = hashlib.sha256(
    json.dumps(
        [[kind, list(lanes)] for kind, lanes in SIGNATURES],
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
).hexdigest()


def signature_index(kind: str, lanes: Iterable[int]) -> int:
    signature = (str(kind), tuple(int(v) for v in lanes))
    try:
        return SIGNATURE_TO_INDEX[signature]
    except KeyError as exc:
        raise StructuralFeatureError(
            f"unsupported structural invariant signature: {signature!r}"
        ) from exc


def encode_constraint_state(
    invariants: Iterable[InvariantLike],
    unsatisfied_ids: Iterable[str],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return (declared529, residual529).

    declared529 identifies the structural constraint graph.
    residual529 identifies which declared constraints are currently violated.

    invariant_id is used only to join residual membership to its declaration;
    it has no position in the neural feature vocabulary.
    """
    declared = [0] * FEATURE_WIDTH
    active = [0] * FEATURE_WIDTH
    invariant_index_by_id: dict[str, int] = {}

    for inv in invariants:
        invariant_id = str(inv.invariant_id)
        if invariant_id in invariant_index_by_id:
            raise StructuralFeatureError(
                f"duplicate invariant id: {invariant_id!r}"
            )

        index = signature_index(inv.kind, inv.lanes)
        invariant_index_by_id[invariant_id] = index
        declared[index] = 1

    for invariant_id in unsatisfied_ids:
        key = str(invariant_id)
        try:
            index = invariant_index_by_id[key]
        except KeyError as exc:
            raise StructuralFeatureError(
                f"residual references undeclared invariant: {key!r}"
            ) from exc
        active[index] = 1

    return tuple(declared), tuple(active)


def _self_test() -> None:
    @dataclass(frozen=True)
    class Inv:
        invariant_id: str
        kind: str
        lanes: tuple[int, ...]

    assert FEATURE_WIDTH == 529

    assert signature_index("PRECEDES", (1, 2)) != \
        signature_index("PRECEDES", (2, 1))

    assert signature_index("CROSS_LANE_ROUTE", (1, 2)) != \
        signature_index("MEMORY_SPAN", (1, 2))

    assert signature_index("MUTATION_HAZARD", (1, 2, 3)) != \
        signature_index("MUTATION_HAZARD", (1, 3, 2))

    a = (
        Inv("semantic.name.A", "TERMINAL_RESOLUTION", ()),
        Inv("semantic.name.B", "PRECEDES", (1, 2)),
        Inv("semantic.name.C", "MEMORY_SPAN", (1, 2)),
    )
    b = (
        Inv("completely.different.1", "TERMINAL_RESOLUTION", ()),
        Inv("completely.different.2", "PRECEDES", (1, 2)),
        Inv("completely.different.3", "MEMORY_SPAN", (1, 2)),
    )

    declared_a, residual_a = encode_constraint_state(
        a, ("semantic.name.B", "semantic.name.C")
    )
    declared_b, residual_b = encode_constraint_state(
        b, ("completely.different.2", "completely.different.3")
    )

    assert declared_a == declared_b
    assert residual_a == residual_b
    assert sum(declared_a) == 3
    assert sum(residual_a) == 2

    _, terminal_only = encode_constraint_state(
        a, ("semantic.name.A",)
    )
    assert terminal_only != residual_a

    try:
        signature_index("UNKNOWN_KIND", ())
    except StructuralFeatureError:
        pass
    else:
        raise AssertionError("unknown invariant kind did not fail closed")

    try:
        encode_constraint_state(a, ("not.declared",))
    except StructuralFeatureError:
        pass
    else:
        raise AssertionError("undeclared residual id did not fail closed")

    print(
        "TRM_FEATURES_SELFTEST=PASS "
        f"width={FEATURE_WIDTH} "
        f"vocabulary_sha256={VOCABULARY_DIGEST}"
    )


if __name__ == "__main__":
    _self_test()
