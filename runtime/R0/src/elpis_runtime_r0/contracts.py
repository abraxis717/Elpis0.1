"""R0 transaction contracts — canonical receipt and intermediate states."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Canonical JSON helpers (matches P0 convention)
# ---------------------------------------------------------------------------


def _canonical_bytes(obj: Any) -> bytes:
    """Minimal canonical JSON: sorted keys, compact separators, no NaN."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    """Lowercase SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def _digest(obj: Any) -> str:
    """Canonical digest of any JSON-serializable object."""
    return _sha256_hex(_canonical_bytes(obj))


# ---------------------------------------------------------------------------
# R0 Transaction state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class R0ProjectionState:
    """Result of P0 deterministic projection phase."""
    projection_digest: str
    grid81: tuple[int, ...]
    semantic_rows: tuple[str, ...]
    features_digest: str


@dataclass(frozen=True)
class R0Grid81State:
    """Canonical Grid81 state read result."""
    generation_number: int
    generation_raw_sha256: str
    generation_semantic_digest: str
    canonical_digest: str
    transaction_id: str


@dataclass(frozen=True)
class R0ScopeDerivation:
    """Scope derivation result."""
    mask_digest: str
    writable_mask81: tuple[int, ...]
    scope_decision_digest: str


@dataclass(frozen=True)
class R0OracleResult:
    """StructuralOracle transition result."""
    input_digest: str
    output_digest: str
    quiescence: bool
    violation_codes: tuple[str, ...]
    rationale_codes: tuple[str, ...]
    candidate_count: int


@dataclass(frozen=True)
class R0AdjudicationResult:
    """Adjudication result with verdict."""
    adjudication_digest: str
    verdict: str  # "ACCEPTED" | "REJECTED"
    outcome: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class R0DarwinianResult:
    """Darwinian episode result."""
    episode_digest: str
    verdict: str  # "ACCEPTED" | "REJECTED"
    lifecycle_authorities_exercised: tuple[str, ...]
    lifecycle_authorities_inactive: tuple[str, ...]


@dataclass(frozen=True)
class R0DecoderResult:
    """Decoder control plan result."""
    control_plan_digest: str
    plan_backend: str


@dataclass(frozen=True)
class R0ArtifactResult:
    """Decoded artifact result."""
    artifact_digest: str
    source_length: int
    language: str


@dataclass(frozen=True)
class R0ASTValidationResult:
    """AST validator result."""
    passed: bool
    code: str
    message: str
    validator_id: str


# ---------------------------------------------------------------------------
# R0 Transaction receipt
# ---------------------------------------------------------------------------

RECEIPT_SCHEMA = "elpis.runtime.r0.receipt.v1"


@dataclass(frozen=True)
class R0TransactionReceipt:
    """Canonical sorted-JSON transaction receipt.

    Self-hash convention:
        1. All fields except receipt_self_hash are serialized to canonical JSON
        2. SHA-256 of that JSON is the self-hash
        3. Self-hash is recorded but not included in the digest computation
        (self-referential hash excluded from its own computation)
    """

    schema: str = RECEIPT_SCHEMA
    transaction_id: str = ""
    request_digest: str = ""
    logical_tick: int = -1

    # P0 projection
    p0_projection_digest: str = ""

    # Grid81 canonical state
    grid81_generation_number: int = 0
    grid81_canonical_state_digest: str = ""

    # Scope derivation
    scope_decision_digest: str = ""

    # StructuralOracle
    structural_oracle_input_digest: str = ""
    structural_oracle_output_digest: str = ""

    # Adjudication
    adjudication_digest: str = ""
    adjudication_verdict: str = ""

    # Darwinian
    darwinian_episode_digest: str = ""
    darwinian_verdict: str = ""

    # Decoder
    decoder_control_plan_digest: str = ""

    # Artifact
    decoded_artifact_digest: str = ""

    # AST validation
    ast_validation_result: str = ""

    # Component manifests
    component_manifest_digests: str = ""

    # Dependency audit
    dependency_resolution_audit: str = ""

    # Termination
    termination_disposition: str = ""

    # Runtime admission
    runtime_admission: bool = False

    # Receipt self-hash
    receipt_self_hash: str = ""

    def __post_init__(self) -> None:
        # Validate runtime admission is always False for R0
        if self.runtime_admission is not False:
            object.__setattr__(self, "runtime_admission", False)

        # Compute self-hash from all fields except self_hash
        payload = {
            "schema": self.schema,
            "transaction_id": self.transaction_id,
            "request_digest": self.request_digest,
            "logical_tick": self.logical_tick,
            "p0_projection_digest": self.p0_projection_digest,
            "grid81_generation_number": self.grid81_generation_number,
            "grid81_canonical_state_digest": self.grid81_canonical_state_digest,
            "scope_decision_digest": self.scope_decision_digest,
            "structural_oracle_input_digest": self.structural_oracle_input_digest,
            "structural_oracle_output_digest": self.structural_oracle_output_digest,
            "adjudication_digest": self.adjudication_digest,
            "adjudication_verdict": self.adjudication_verdict,
            "darwinian_episode_digest": self.darwinian_episode_digest,
            "darwinian_verdict": self.darwinian_verdict,
            "decoder_control_plan_digest": self.decoder_control_plan_digest,
            "decoded_artifact_digest": self.decoded_artifact_digest,
            "ast_validation_result": self.ast_validation_result,
            "component_manifest_digests": self.component_manifest_digests,
            "dependency_resolution_audit": self.dependency_resolution_audit,
            "termination_disposition": self.termination_disposition,
            "runtime_admission": self.runtime_admission,
        }
        self_hash = _sha256_hex(_canonical_bytes(payload))
        object.__setattr__(self, "receipt_self_hash", self_hash)

    def to_canonical_json(self) -> str:
        """Serialize to canonical JSON string (deterministic bytes)."""
        payload = {
            "schema": self.schema,
            "transaction_id": self.transaction_id,
            "request_digest": self.request_digest,
            "logical_tick": self.logical_tick,
            "p0_projection_digest": self.p0_projection_digest,
            "grid81_generation_number": self.grid81_generation_number,
            "grid81_canonical_state_digest": self.grid81_canonical_state_digest,
            "scope_decision_digest": self.scope_decision_digest,
            "structural_oracle_input_digest": self.structural_oracle_input_digest,
            "structural_oracle_output_digest": self.structural_oracle_output_digest,
            "adjudication_digest": self.adjudication_digest,
            "adjudication_verdict": self.adjudication_verdict,
            "darwinian_episode_digest": self.darwinian_episode_digest,
            "darwinian_verdict": self.darwinian_verdict,
            "decoder_control_plan_digest": self.decoder_control_plan_digest,
            "decoded_artifact_digest": self.decoded_artifact_digest,
            "ast_validation_result": self.ast_validation_result,
            "component_manifest_digests": self.component_manifest_digests,
            "dependency_resolution_audit": self.dependency_resolution_audit,
            "termination_disposition": self.termination_disposition,
            "runtime_admission": self.runtime_admission,
            "receipt_self_hash": self.receipt_self_hash,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)

    def receipt_bytes(self) -> bytes:
        """Canonical receipt as UTF-8 bytes (what gets hashed for determinism)."""
        return self.to_canonical_json().encode("utf-8")
