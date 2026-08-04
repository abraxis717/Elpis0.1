"""P0 sidecar envelope binding oracle evidence to a legacy TRM proposal.

Patch 2 of P3 topology dynamics and corpus binding.

This module is additive. It does not alter ``TRMRefinementProposal`` and does
not reinterpret ``residual81``. The current oracle adapter's residual vector is
classified explicitly as a legacy VOID-mask recode and is bound beside the
qualified ``StructuralTransitionFieldsV1`` evidence record.

The existing ``evaluate_one_step`` API remains untouched. Callers that need
complete state/transition identities use ``evaluate_one_step_with_evidence``.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from typing import Optional

from elpis_fractal_spine.structural_identity import (
    oracle_next_state_identity,
    oracle_transition_identity,
    structural_state_identity,
)
from elpis_fractal_spine.structural_oracle import OracleTransition, StructuralOracle
from elpis_fractal_spine.structural_refinement import (
    StructuralRefinementError,
    StructuralRefinementInputV1,
)
from elpis_fractal_spine.structural_semantics import StructuralState
from elpis_fractal_spine.structural_transition_fields import (
    StructuralTransitionFieldsV1,
    compute_transition_fields,
    validate_transition_fields,
)

from .canonical import digest
from .contracts import TRMRefinementProposal
from .structural_oracle_adapter import (
    oracle_transition_to_trm_proposal,
    refinement_input_to_structural_state,
)

__all__ = [
    "SCHEMA",
    "LegacyResidual81Provenance",
    "StructuralProposalEnvelopeError",
    "StructuralProposalEnvelopeV1",
    "build_structural_proposal_envelope",
    "evaluate_one_step_with_evidence",
    "validate_structural_proposal_envelope",
]

SCHEMA = "elpis.p0.structural_proposal_envelope.v1"
_DOMAIN = SCHEMA.encode("utf-8")
_HEX_64 = re.compile(r"\A[0-9a-f]{64}\Z")
_U64_MAX = 0xFFFFFFFFFFFFFFFF


class LegacyResidual81Provenance(str, Enum):
    """Exact provenance of the legacy residual carried by this envelope."""

    VOID_MASK_RECODE_V1 = "legacy.residual81.void_mask_recode.v1"


class StructuralProposalEnvelopeError(ValueError):
    """Raised when a proposal/evidence envelope is incomplete or inconsistent."""


def _lp(payload: bytes) -> bytes:
    if not isinstance(payload, (bytes, bytearray)):
        raise StructuralProposalEnvelopeError("length-prefix payload must be bytes")
    raw = bytes(payload)
    if len(raw) > _U64_MAX:
        raise StructuralProposalEnvelopeError("payload exceeds uint64 length")
    return len(raw).to_bytes(8, "big") + raw


def _field(name: str, value: bytes) -> bytes:
    return _lp(name.encode("utf-8")) + _lp(value)


def _boolean(value: bool, *, name: str) -> bytes:
    if not isinstance(value, bool):
        raise StructuralProposalEnvelopeError(f"{name} must be bool")
    return b"\x01" if value else b"\x00"


def _u64(value: int, *, name: str) -> bytes:
    if not isinstance(value, int) or isinstance(value, bool):
        raise StructuralProposalEnvelopeError(f"{name} must be an integer")
    if value < 0 or value > _U64_MAX:
        raise StructuralProposalEnvelopeError(f"{name} outside uint64 range")
    return value.to_bytes(8, "big")


def _identity(value: str, *, name: str) -> bytes:
    if not isinstance(value, str) or _HEX_64.fullmatch(value) is None:
        raise StructuralProposalEnvelopeError(
            f"{name} must be lowercase 64-character hexadecimal"
        )
    return value.encode("ascii")


def _code_tuple(codes: tuple[str, ...], *, name: str) -> bytes:
    if not isinstance(codes, tuple):
        raise StructuralProposalEnvelopeError(f"{name} must be a tuple")
    encoded = []
    for index, code in enumerate(codes):
        if not isinstance(code, str):
            raise StructuralProposalEnvelopeError(f"{name}[{index}] must be str")
        encoded.append(_lp(code.encode("utf-8")))
    return b"".join(encoded)


def _expected_legacy_residual(proposed_grid81: tuple[int, ...]) -> tuple[float, ...]:
    return tuple(1.0 if token == 0 else 0.125 for token in proposed_grid81)


def _proposal_digest(proposal: TRMRefinementProposal) -> str:
    return digest(
        {
            "input_digest": proposal.input_digest,
            "proposed_grid81": proposal.proposed_grid81,
            "residual81": proposal.residual81,
            "halt_score": proposal.halt_score,
            "expansion_cells": proposal.expansion_cells,
            "rationale": proposal.rationale,
        }
    )


@dataclass(frozen=True, slots=True)
class StructuralProposalEnvelopeV1:
    """P0 proposal plus complete deterministic transition sidecar evidence."""

    schema: str
    input_digest: str
    proposal: TRMRefinementProposal
    transition_fields: StructuralTransitionFieldsV1
    legacy_residual81_provenance: LegacyResidual81Provenance
    quiescence: bool
    violation_codes: tuple[str, ...]
    candidate_count: int
    rationale_codes: tuple[str, ...]
    envelope_digest: str

    def __post_init__(self) -> None:
        validate_structural_proposal_envelope(self)


def _encode_without_digest(envelope: StructuralProposalEnvelopeV1) -> bytes:
    return b"".join(
        (
            _lp(_DOMAIN),
            _field("input_digest", _identity(envelope.input_digest, name="input_digest")),
            _field(
                "proposal_digest",
                _identity(envelope.proposal.digest, name="proposal.digest"),
            ),
            _field(
                "transition_fields_digest",
                _identity(
                    envelope.transition_fields.fields_digest,
                    name="transition_fields.fields_digest",
                ),
            ),
            _field(
                "source_state_identity",
                _identity(
                    envelope.transition_fields.source_state_identity,
                    name="transition_fields.source_state_identity",
                ),
            ),
            _field(
                "oracle_transition_identity",
                _identity(
                    envelope.transition_fields.oracle_transition_identity,
                    name="transition_fields.oracle_transition_identity",
                ),
            ),
            _field(
                "canonical_target_identity",
                _identity(
                    envelope.transition_fields.canonical_target_identity,
                    name="transition_fields.canonical_target_identity",
                ),
            ),
            _field(
                "legacy_residual81_provenance",
                envelope.legacy_residual81_provenance.value.encode("utf-8"),
            ),
            _field("quiescence", _boolean(envelope.quiescence, name="quiescence")),
            _field(
                "violation_codes",
                _code_tuple(envelope.violation_codes, name="violation_codes"),
            ),
            _field(
                "candidate_count",
                _u64(envelope.candidate_count, name="candidate_count"),
            ),
            _field(
                "rationale_codes",
                _code_tuple(envelope.rationale_codes, name="rationale_codes"),
            ),
        )
    )


def _expected_envelope_digest(envelope: StructuralProposalEnvelopeV1) -> str:
    return hashlib.sha256(_encode_without_digest(envelope)).hexdigest()


def validate_structural_proposal_envelope(
    envelope: StructuralProposalEnvelopeV1,
) -> None:
    if not isinstance(envelope, StructuralProposalEnvelopeV1):
        raise StructuralProposalEnvelopeError(
            f"expected StructuralProposalEnvelopeV1, got {type(envelope)!r}"
        )
    if envelope.schema != SCHEMA:
        raise StructuralProposalEnvelopeError(
            f"schema {envelope.schema!r} != {SCHEMA!r}"
        )

    _identity(envelope.input_digest, name="input_digest")
    _identity(envelope.envelope_digest, name="envelope_digest")

    if not isinstance(envelope.proposal, TRMRefinementProposal):
        raise StructuralProposalEnvelopeError("proposal has wrong type")
    envelope.proposal.validate()
    if envelope.proposal.input_digest != envelope.input_digest:
        raise StructuralProposalEnvelopeError(
            "proposal.input_digest does not match envelope input_digest"
        )
    if envelope.proposal.digest != _proposal_digest(envelope.proposal):
        raise StructuralProposalEnvelopeError("proposal digest mismatch")

    validate_transition_fields(envelope.transition_fields)

    if envelope.legacy_residual81_provenance is not (
        LegacyResidual81Provenance.VOID_MASK_RECODE_V1
    ):
        raise StructuralProposalEnvelopeError(
            "only the current oracle adapter VOID-mask recode is admitted in V1"
        )
    expected_residual = _expected_legacy_residual(envelope.proposal.proposed_grid81)
    if envelope.proposal.residual81 != expected_residual:
        raise StructuralProposalEnvelopeError(
            "proposal residual81 does not match declared legacy VOID-mask recode"
        )

    if not isinstance(envelope.quiescence, bool):
        raise StructuralProposalEnvelopeError("quiescence must be bool")
    if not isinstance(envelope.candidate_count, int) or isinstance(
        envelope.candidate_count, bool
    ):
        raise StructuralProposalEnvelopeError("candidate_count must be integer")
    if envelope.candidate_count < 0:
        raise StructuralProposalEnvelopeError("candidate_count must be nonnegative")
    if envelope.candidate_count != envelope.transition_fields.valid_next_state_count:
        raise StructuralProposalEnvelopeError(
            "candidate_count does not match transition evidence denominator"
        )

    _code_tuple(envelope.violation_codes, name="violation_codes")
    _code_tuple(envelope.rationale_codes, name="rationale_codes")
    if envelope.proposal.rationale != envelope.rationale_codes:
        raise StructuralProposalEnvelopeError(
            "proposal rationale does not match envelope rationale_codes"
        )

    expected_halt = (
        1.0
        if envelope.quiescence
        else sum(token != 0 for token in envelope.proposal.proposed_grid81) / 81.0
    )
    if envelope.proposal.halt_score != expected_halt:
        raise StructuralProposalEnvelopeError(
            "proposal halt_score is inconsistent with current oracle adapter law"
        )

    if envelope.envelope_digest != _expected_envelope_digest(envelope):
        raise StructuralProposalEnvelopeError("envelope digest mismatch")


def build_structural_proposal_envelope(
    *,
    state: StructuralState,
    transition: OracleTransition,
    proposal: TRMRefinementProposal,
    input_digest: str,
) -> StructuralProposalEnvelopeV1:
    """Bind a real state, transition, and legacy proposal into one sidecar envelope."""
    if proposal.input_digest != input_digest:
        raise StructuralProposalEnvelopeError(
            "proposal input digest does not match supplied input digest"
        )
    if proposal.proposed_grid81 != transition.canonical_next_state.grid.tokens:
        raise StructuralProposalEnvelopeError(
            "proposal grid does not match oracle canonical target"
        )
    if proposal.expansion_cells != tuple(
        target.cell for target in transition.expansion_targets
    ):
        raise StructuralProposalEnvelopeError(
            "proposal expansion cells do not match oracle transition"
        )
    if proposal.rationale != transition.rationale_codes:
        raise StructuralProposalEnvelopeError(
            "proposal rationale does not match oracle transition"
        )

    fields = compute_transition_fields(state, transition)
    if fields.source_state_identity != structural_state_identity(state):
        raise StructuralProposalEnvelopeError("source state identity mismatch")
    if fields.oracle_transition_identity != oracle_transition_identity(transition):
        raise StructuralProposalEnvelopeError("oracle transition identity mismatch")
    if fields.canonical_target_identity != oracle_next_state_identity(
        transition.canonical_next_state
    ):
        raise StructuralProposalEnvelopeError("canonical target identity mismatch")

    provisional = object.__new__(StructuralProposalEnvelopeV1)
    object.__setattr__(provisional, "schema", SCHEMA)
    object.__setattr__(provisional, "input_digest", input_digest)
    object.__setattr__(provisional, "proposal", proposal)
    object.__setattr__(provisional, "transition_fields", fields)
    object.__setattr__(
        provisional,
        "legacy_residual81_provenance",
        LegacyResidual81Provenance.VOID_MASK_RECODE_V1,
    )
    object.__setattr__(provisional, "quiescence", transition.quiescence)
    object.__setattr__(provisional, "violation_codes", transition.violation_codes)
    object.__setattr__(provisional, "candidate_count", len(transition.valid_next_states))
    object.__setattr__(provisional, "rationale_codes", transition.rationale_codes)
    object.__setattr__(provisional, "envelope_digest", "0" * 64)
    envelope_digest = _expected_envelope_digest(provisional)

    return StructuralProposalEnvelopeV1(
        schema=SCHEMA,
        input_digest=input_digest,
        proposal=proposal,
        transition_fields=fields,
        legacy_residual81_provenance=(
            LegacyResidual81Provenance.VOID_MASK_RECODE_V1
        ),
        quiescence=transition.quiescence,
        violation_codes=transition.violation_codes,
        candidate_count=len(transition.valid_next_states),
        rationale_codes=transition.rationale_codes,
        envelope_digest=envelope_digest,
    )


def evaluate_one_step_with_evidence(
    input_v1: StructuralRefinementInputV1,
    *,
    oracle: Optional[StructuralOracle] = None,
    depth: int = 0,
) -> StructuralProposalEnvelopeV1:
    """Evaluate one P0 oracle step and return proposal plus complete sidecar evidence."""
    if not isinstance(input_v1, StructuralRefinementInputV1):
        raise StructuralRefinementError(
            "input_v1 must be StructuralRefinementInputV1"
        )
    state = refinement_input_to_structural_state(input_v1, depth=depth)
    active_oracle = oracle if oracle is not None else StructuralOracle()
    transition = active_oracle.evaluate(state)
    proposal = oracle_transition_to_trm_proposal(
        transition,
        input_digest=input_v1.combined_digest,
    )
    return build_structural_proposal_envelope(
        state=state,
        transition=transition,
        proposal=proposal,
        input_digest=input_v1.combined_digest,
    )
