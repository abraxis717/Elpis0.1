"""Immutable admitted structural-topology boundary.

This module does not execute, decode, select, mutate, solve, route, or
materialize domain-specific runtime state.

It converts one successfully ADMITTED structural-guidance result into a
canonical immutable structural snapshot whose identity is bound to:

* the deterministic C2R6 projection,
* the P1 final refinement state,
* the out-of-band semantic binding envelope,
* the structural-guidance admission receipt.

Only a fully resolved frozen-objective result (best_cost == 0) may cross
this boundary. Guidance authority remains exactly zero.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import hashlib
import json
from typing import Any

from .admission import StructuralGuidanceAdmissionResult
from .hook import ProjectAndAdmitResultV1
from .receipt import StructuralGuidanceReceiptV1
from ._authority.c2r6p0.contracts import (
    ProjectionResultV1,
)
from ._authority.c2r6p1_bridge.contracts import (
    RefinerEnvelopeV1,
    RefinerInputV1,
)


RESOLVED_STRUCTURAL_TOPOLOGY_SCHEMA = (
    "elpis.structural-guidance.resolved-topology.v1"
)

GRID81_CELLS = 81
STRUCTURAL_FEATURE_WIDTH = 529
AUTHORITY_ZERO = 0


class ResolvedStructuralTopologyError(ValueError):
    """Fail-closed resolved-topology boundary rejection."""


def _canonical_json_bytes(
    payload: object,
) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(
    payload: object,
) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(payload)
    ).hexdigest()


def _is_hex_digest(
    value: object,
) -> bool:
    if not isinstance(value, str):
        return False

    if len(value) != 64:
        return False

    try:
        int(value, 16)
    except ValueError:
        return False

    return True


def _normalize(
    value: Any,
) -> Any:
    """Canonical JSON-safe representation without semantic interpretation."""

    if value is None:
        return None

    if isinstance(
        value,
        (str, int, bool),
    ):
        return value

    if isinstance(value, float):
        if value != value:
            raise ResolvedStructuralTopologyError(
                "NaN is forbidden in structural topology"
            )
        return value

    if isinstance(value, Enum):
        return _normalize(value.value)

    if is_dataclass(value):
        return {
            field.name: _normalize(
                getattr(value, field.name)
            )
            for field in fields(value)
        }

    if isinstance(
        value,
        (tuple, list),
    ):
        return [
            _normalize(item)
            for item in value
        ]

    if isinstance(
        value,
        (set, frozenset),
    ):
        normalized = [
            _normalize(item)
            for item in value
        ]
        return sorted(
            normalized,
            key=lambda item: _canonical_json_bytes(
                item
            ),
        )

    if isinstance(value, dict):
        result = {}

        for key in sorted(
            value,
            key=lambda item: str(item),
        ):
            if not isinstance(
                key,
                (str, int),
            ):
                raise ResolvedStructuralTopologyError(
                    "structural topology dictionaries "
                    "must use string/integer keys"
                )

            result[str(key)] = _normalize(
                value[key]
            )

        return result

    raise ResolvedStructuralTopologyError(
        "unsupported structural topology value type: "
        f"{type(value).__name__}"
    )


@dataclass(frozen=True)
class ResolvedStructuralTopologyV1:
    """Immutable authority-zero snapshot of one resolved structural state."""

    schema: str

    grid81: tuple[int, ...]
    frozen_mask: tuple[int, ...]
    writable_mask: tuple[int, ...]

    invariants: tuple[object, ...]
    lane_bindings: tuple[object, ...]
    structural_schema: object

    declared_features: tuple[int, ...]
    active_residual: tuple[int, ...]
    residual_ids: tuple[str, ...]

    structural_bindings_json: str
    structural_bindings_digest: str

    semantic_input_digest: str
    rule_set_digest: str

    projection_structural_schema_digest: str
    refiner_structural_schema_digest: str

    projection_digest: str
    projection_trace_digest: str
    projection_fingerprint: str

    refinement_state_fingerprint: str
    refiner_input_digest: str

    envelope_digest: str
    receipt_digest: str
    checkpoint_sha256: str

    best_cost: int
    iterations: int
    applied_moves: int

    authority_granted: int

    topology_digest: str = ""

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "grid81": list(self.grid81),
            "frozen_mask": list(
                self.frozen_mask
            ),
            "writable_mask": list(
                self.writable_mask
            ),
            "invariants": _normalize(
                self.invariants
            ),
            "lane_bindings": _normalize(
                self.lane_bindings
            ),
            "structural_schema": _normalize(
                self.structural_schema
            ),
            "declared_features": list(
                self.declared_features
            ),
            "active_residual": list(
                self.active_residual
            ),
            "residual_ids": list(
                self.residual_ids
            ),
            "structural_bindings_json": (
                self.structural_bindings_json
            ),
            "structural_bindings_digest": (
                self.structural_bindings_digest
            ),
            "semantic_input_digest": (
                self.semantic_input_digest
            ),
            "rule_set_digest": (
                self.rule_set_digest
            ),
            "projection_structural_schema_digest": (
                self.projection_structural_schema_digest
            ),
            "refiner_structural_schema_digest": (
                self.refiner_structural_schema_digest
            ),
            "projection_digest": (
                self.projection_digest
            ),
            "projection_trace_digest": (
                self.projection_trace_digest
            ),
            "projection_fingerprint": (
                self.projection_fingerprint
            ),
            "refinement_state_fingerprint": (
                self.refinement_state_fingerprint
            ),
            "refiner_input_digest": (
                self.refiner_input_digest
            ),
            "envelope_digest": (
                self.envelope_digest
            ),
            "receipt_digest": (
                self.receipt_digest
            ),
            "checkpoint_sha256": (
                self.checkpoint_sha256
            ),
            "best_cost": self.best_cost,
            "iterations": self.iterations,
            "applied_moves": (
                self.applied_moves
            ),
            "authority_granted": (
                self.authority_granted
            ),
        }

    def topology_digest_computed(
        self,
    ) -> str:
        return _sha256(
            self.canonical_payload()
        )

    def validate(
        self,
    ) -> None:
        if (
            self.schema
            != RESOLVED_STRUCTURAL_TOPOLOGY_SCHEMA
        ):
            raise ResolvedStructuralTopologyError(
                "unsupported resolved topology schema"
            )

        if len(self.grid81) != GRID81_CELLS:
            raise ResolvedStructuralTopologyError(
                "resolved Grid81 must contain 81 cells"
            )

        if any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= 9
            for value in self.grid81
        ):
            raise ResolvedStructuralTopologyError(
                "resolved Grid81 values must be integers in [0, 9]"
            )

        for name, mask in (
            ("frozen_mask", self.frozen_mask),
            ("writable_mask", self.writable_mask),
        ):
            if len(mask) != GRID81_CELLS:
                raise ResolvedStructuralTopologyError(
                    f"{name} must contain 81 cells"
                )

            if any(
                value not in (0, 1)
                for value in mask
            ):
                raise ResolvedStructuralTopologyError(
                    f"{name} must be binary"
                )

        if any(
            frozen + writable != 1
            for frozen, writable in zip(
                self.frozen_mask,
                self.writable_mask,
            )
        ):
            raise ResolvedStructuralTopologyError(
                "frozen/writable masks must be "
                "disjoint and exhaustive"
            )

        if (
            len(self.declared_features)
            != STRUCTURAL_FEATURE_WIDTH
        ):
            raise ResolvedStructuralTopologyError(
                "declared feature width must remain 529"
            )

        if (
            len(self.active_residual)
            != STRUCTURAL_FEATURE_WIDTH
        ):
            raise ResolvedStructuralTopologyError(
                "active residual width must remain 529"
            )

        if self.structural_schema is None:
            raise ResolvedStructuralTopologyError(
                "resolved topology requires structural schema"
            )

        if self.authority_granted != AUTHORITY_ZERO:
            raise ResolvedStructuralTopologyError(
                "resolved topology may not grant authority"
            )

        if self.best_cost != 0:
            raise ResolvedStructuralTopologyError(
                "only frozen-objective cost-zero topology "
                "may cross the resolved boundary"
            )

        if self.iterations < 0:
            raise ResolvedStructuralTopologyError(
                "iterations cannot be negative"
            )

        if self.applied_moves < 0:
            raise ResolvedStructuralTopologyError(
                "applied_moves cannot be negative"
            )

        try:
            bindings_payload = json.loads(
                self.structural_bindings_json
            )
        except Exception as exc:
            raise ResolvedStructuralTopologyError(
                "structural binding snapshot is not "
                "canonical JSON"
            ) from exc

        canonical_bindings_json = (
            _canonical_json_bytes(
                bindings_payload
            ).decode("ascii")
        )

        if (
            canonical_bindings_json
            != self.structural_bindings_json
        ):
            raise ResolvedStructuralTopologyError(
                "structural binding snapshot is not canonical"
            )

        if (
            _sha256(bindings_payload)
            != self.structural_bindings_digest
        ):
            raise ResolvedStructuralTopologyError(
                "structural binding digest mismatch"
            )

        digest_fields = (
            "structural_bindings_digest",
            "semantic_input_digest",
            "rule_set_digest",
            "projection_structural_schema_digest",
            "refiner_structural_schema_digest",
            "projection_digest",
            "projection_trace_digest",
            "projection_fingerprint",
            "refinement_state_fingerprint",
            "refiner_input_digest",
            "envelope_digest",
            "receipt_digest",
            "checkpoint_sha256",
        )

        for name in digest_fields:
            if not _is_hex_digest(
                getattr(self, name)
            ):
                raise ResolvedStructuralTopologyError(
                    f"{name} must be a 64-character "
                    "hexadecimal digest"
                )

        if self.topology_digest:
            if not _is_hex_digest(
                self.topology_digest
            ):
                raise ResolvedStructuralTopologyError(
                    "topology_digest must be hexadecimal"
                )

            if (
                self.topology_digest
                != self.topology_digest_computed()
            ):
                raise ResolvedStructuralTopologyError(
                    "resolved topology digest mismatch"
                )

    def validate_digest(
        self,
    ) -> bool:
        try:
            self.validate()
        except ResolvedStructuralTopologyError:
            return False

        return bool(
            self.topology_digest
            and self.topology_digest
            == self.topology_digest_computed()
        )


def _require_projection_identity(
    projection: ProjectionResultV1,
    final_input: RefinerInputV1,
) -> None:
    """Verify the frozen P0 -> P1 authority-narrowing ABI.

    P1 intentionally derives a narrower transition schema. Therefore the
    two StructuralSchemaV1 objects are not required to be equal.

    Required identity:
    * operational masks carried by RefinerInputV1 remain projector-owned;
    * semantic request, lanes, initial grid, and invariants are preserved;
    * P1 schema writable authority equals the operational writable mask;
    * P1 schema writable authority is a subset of P0 schema authority.
    """
    authority_schema = projection.structural_schema
    refiner_schema = final_input.structural_schema

    if authority_schema is None:
        raise ResolvedStructuralTopologyError(
            "PROJECTED result requires structural schema"
        )

    authority_schema.validate()
    refiner_schema.validate()

    if (
        final_input.frozen_mask
        != projection.frozen_mask
    ):
        raise ResolvedStructuralTopologyError(
            "guidance widened or changed frozen mask"
        )

    if (
        final_input.writable_mask
        != projection.writable_mask
    ):
        raise ResolvedStructuralTopologyError(
            "guidance widened or changed writable mask"
        )

    if (
        final_input.invariants
        != projection.invariants
    ):
        raise ResolvedStructuralTopologyError(
            "guidance changed structural invariants"
        )

    if (
        final_input.lane_bindings
        != projection.lane_bindings
    ):
        raise ResolvedStructuralTopologyError(
            "guidance changed lane bindings"
        )

    if (
        refiner_schema.semantic_request_digest
        != authority_schema.semantic_request_digest
    ):
        raise ResolvedStructuralTopologyError(
            "refiner schema changed semantic request identity"
        )

    if (
        refiner_schema.lanes
        != authority_schema.lanes
    ):
        raise ResolvedStructuralTopologyError(
            "refiner schema changed lane identity"
        )

    if (
        refiner_schema.initial_grid
        != authority_schema.initial_grid
    ):
        raise ResolvedStructuralTopologyError(
            "refiner schema changed initial grid authority"
        )

    if (
        refiner_schema.invariants
        != authority_schema.invariants
    ):
        raise ResolvedStructuralTopologyError(
            "refiner schema changed invariant authority"
        )

    if (
        refiner_schema.writable_mask
        != final_input.writable_mask
    ):
        raise ResolvedStructuralTopologyError(
            "refiner schema writable mask does not match "
            "projector-authorized operational writable mask"
        )

    for index, writable in enumerate(
        refiner_schema.writable_mask
    ):
        if (
            writable
            and not authority_schema.writable_mask[index]
        ):
            raise ResolvedStructuralTopologyError(
                "refiner schema widened projector schema authority "
                f"at cell {index}"
            )

    if (
        final_input.projection_fingerprint
        != projection.structural_input_fingerprint
    ):
        raise ResolvedStructuralTopologyError(
            "final state lost projection identity"
        )


def build_resolved_structural_topology(
    result: ProjectAndAdmitResultV1,
) -> ResolvedStructuralTopologyV1:
    """Build a descriptive topology artifact from one ADMITTED result."""

    if not isinstance(
        result,
        ProjectAndAdmitResultV1,
    ):
        raise TypeError(
            "result must be production ProjectAndAdmitResultV1"
        )

    projection = result.projection
    admission = result.admission

    if not isinstance(
        projection,
        ProjectionResultV1,
    ):
        raise ResolvedStructuralTopologyError(
            "wrong production projection type"
        )

    status = getattr(
        projection.status,
        "value",
        projection.status,
    )

    if status != "PROJECTED":
        raise ResolvedStructuralTopologyError(
            "only PROJECTED structural state may materialize"
        )

    if not isinstance(
        admission,
        StructuralGuidanceAdmissionResult,
    ):
        raise ResolvedStructuralTopologyError(
            "wrong admission result type"
        )

    if not admission.admitted:
        raise ResolvedStructuralTopologyError(
            "only ADMITTED guidance result may materialize"
        )

    if admission.fallback_required:
        raise ResolvedStructuralTopologyError(
            "FALLBACK_REQUIRED result may not materialize"
        )

    final_input = admission.final_input
    envelope = admission.envelope
    receipt = admission.receipt

    if not isinstance(
        receipt,
        StructuralGuidanceReceiptV1,
    ):
        raise ResolvedStructuralTopologyError(
            "ADMITTED result requires "
            "StructuralGuidanceReceiptV1"
        )

    if not isinstance(
        final_input,
        RefinerInputV1,
    ):
        raise ResolvedStructuralTopologyError(
            "ADMITTED result requires final RefinerInputV1"
        )

    if not isinstance(
        envelope,
        RefinerEnvelopeV1,
    ):
        raise ResolvedStructuralTopologyError(
            "ADMITTED result requires RefinerEnvelopeV1"
        )

    if receipt.outcome != "ADMITTED":
        raise ResolvedStructuralTopologyError(
            "receipt outcome must be ADMITTED"
        )

    if receipt.enabled is not True:
        raise ResolvedStructuralTopologyError(
            "resolved learned-guidance artifact "
            "requires enabled admission"
        )

    if receipt.authority_granted != AUTHORITY_ZERO:
        raise ResolvedStructuralTopologyError(
            "receipt widened guidance authority"
        )

    if receipt.error_code:
        raise ResolvedStructuralTopologyError(
            "ADMITTED receipt may not carry an error"
        )

    if not receipt.validate_digest():
        raise ResolvedStructuralTopologyError(
            "invalid structural-guidance receipt digest"
        )

    if receipt.best_cost != 0:
        raise ResolvedStructuralTopologyError(
            "admitted state is not resolved under "
            "the frozen objective"
        )

    if (
        receipt.projection_digest
        != projection.projection_digest
    ):
        raise ResolvedStructuralTopologyError(
            "receipt/projection identity mismatch"
        )

    if (
        receipt.envelope_digest
        != envelope.envelope_digest
    ):
        raise ResolvedStructuralTopologyError(
            "receipt/envelope identity mismatch"
        )

    if (
        receipt.output_refinement_fingerprint
        != final_input.refinement_state_fingerprint
    ):
        raise ResolvedStructuralTopologyError(
            "receipt/final-state identity mismatch"
        )

    if (
        receipt.input_refinement_fingerprint
        != envelope.refiner_input.refinement_state_fingerprint
    ):
        raise ResolvedStructuralTopologyError(
            "receipt/input-state identity mismatch"
        )

    if (
        envelope.projection_digest
        != projection.projection_digest
    ):
        raise ResolvedStructuralTopologyError(
            "envelope/projection identity mismatch"
        )

    if (
        envelope.semantic_input_digest
        != projection.semantic_input_digest
    ):
        raise ResolvedStructuralTopologyError(
            "envelope/semantic identity mismatch"
        )

    if (
        envelope.structural_bindings
        != projection.bindings
    ):
        raise ResolvedStructuralTopologyError(
            "semantic binding sidecar identity mismatch"
        )

    computed_envelope_digest = getattr(
        envelope,
        "envelope_digest_computed",
        None,
    )

    if callable(computed_envelope_digest):
        if (
            envelope.envelope_digest
            != computed_envelope_digest()
        ):
            raise ResolvedStructuralTopologyError(
                "invalid envelope digest"
            )

    _require_projection_identity(
        projection,
        final_input,
    )

    projection_dict = projection.to_dict()

    bindings_payload = projection_dict[
        "bindings"
    ]

    bindings_json = (
        _canonical_json_bytes(
            bindings_payload
        ).decode("ascii")
    )

    unsigned = ResolvedStructuralTopologyV1(
        schema=RESOLVED_STRUCTURAL_TOPOLOGY_SCHEMA,
        grid81=tuple(
            final_input.grid81
        ),
        frozen_mask=tuple(
            final_input.frozen_mask
        ),
        writable_mask=tuple(
            final_input.writable_mask
        ),
        invariants=tuple(
            final_input.invariants
        ),
        lane_bindings=tuple(
            final_input.lane_bindings
        ),
        structural_schema=(
            final_input.structural_schema
        ),
        declared_features=tuple(
            final_input.declared_features
        ),
        active_residual=tuple(
            final_input.active_residual
        ),
        residual_ids=tuple(
            final_input.residual_ids
        ),
        structural_bindings_json=bindings_json,
        structural_bindings_digest=_sha256(
            bindings_payload
        ),
        semantic_input_digest=(
            projection.semantic_input_digest
        ),
        rule_set_digest=(
            projection.rule_set_digest
        ),
        projection_structural_schema_digest=(
            projection.structural_schema.schema_digest
        ),
        refiner_structural_schema_digest=(
            final_input.structural_schema.schema_digest
        ),
        projection_digest=(
            projection.projection_digest
        ),
        projection_trace_digest=(
            projection.trace.trace_digest
        ),
        projection_fingerprint=(
            projection.structural_input_fingerprint
        ),
        refinement_state_fingerprint=(
            final_input.refinement_state_fingerprint
        ),
        refiner_input_digest=(
            final_input.refiner_input_digest
        ),
        envelope_digest=(
            envelope.envelope_digest
        ),
        receipt_digest=(
            receipt.receipt_digest
        ),
        checkpoint_sha256=(
            receipt.checkpoint_sha256
        ),
        best_cost=receipt.best_cost,
        iterations=receipt.iterations,
        applied_moves=receipt.applied_moves,
        authority_granted=(
            receipt.authority_granted
        ),
        topology_digest="",
    )

    unsigned.validate()

    signed = ResolvedStructuralTopologyV1(
        **{
            **unsigned.__dict__,
            "topology_digest": (
                unsigned.topology_digest_computed()
            ),
        }
    )

    signed.validate()

    return signed
