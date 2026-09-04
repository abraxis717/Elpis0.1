from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


SCHEMA = "elpis.structural-guidance.runtime-receipt.v1"

_ALLOWED_OUTCOMES = frozenset(
    {
        "BYPASSED",
        "ADMITTED",
        "FALLBACK_REQUIRED",
    }
)


def _digest(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class StructuralGuidanceReceiptV1:
    schema: str
    outcome: str
    enabled: bool

    projection_digest: str
    envelope_digest: str

    input_refinement_fingerprint: str
    output_refinement_fingerprint: str

    checkpoint_sha256: str

    seed: int
    budget: int
    restarts: int
    plateau: int

    iterations: int
    best_cost: int
    applied_moves: int

    authority_granted: int

    error_code: str = ""
    receipt_digest: str = ""

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise ValueError(
                "unsupported structural-guidance receipt schema"
            )

        if self.outcome not in _ALLOWED_OUTCOMES:
            raise ValueError(
                "unsupported structural-guidance receipt outcome"
            )

        if self.authority_granted != 0:
            raise ValueError(
                "structural guidance may never receive authority"
            )

        expected = _digest(self.payload())

        if self.receipt_digest:
            if self.receipt_digest != expected:
                raise ValueError(
                    "structural-guidance receipt digest mismatch"
                )
        else:
            object.__setattr__(
                self,
                "receipt_digest",
                expected,
            )

    def payload(self) -> dict:
        return {
            "schema": self.schema,
            "outcome": self.outcome,
            "enabled": self.enabled,
            "projection_digest": self.projection_digest,
            "envelope_digest": self.envelope_digest,
            "input_refinement_fingerprint": (
                self.input_refinement_fingerprint
            ),
            "output_refinement_fingerprint": (
                self.output_refinement_fingerprint
            ),
            "checkpoint_sha256": self.checkpoint_sha256,
            "seed": self.seed,
            "budget": self.budget,
            "restarts": self.restarts,
            "plateau": self.plateau,
            "iterations": self.iterations,
            "best_cost": self.best_cost,
            "applied_moves": self.applied_moves,
            "authority_granted": self.authority_granted,
            "error_code": self.error_code,
        }

    def validate_digest(self) -> bool:
        return (
            self.receipt_digest
            == _digest(self.payload())
        )
