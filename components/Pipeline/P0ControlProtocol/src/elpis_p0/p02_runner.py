"""P0.2 runner - one-child affine expansion shadow protocol.

Orchestrates the full expansion sequence:
  parent proposal -> admission -> allocate child -> derive seed ->
  charge child refinement -> child TRM proposal -> seal -> close -> fold
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional

from elpis.contracts.budget import BudgetVector, Charge
from elpis.logic.account import ChildCloseReason

from .contracts import (
    TRMRefinementProposal,
    StructuralProjection,
    BasisToken,
)
from .expansion_contracts import (
    ExpansionProposalEvidence,
    ExpansionAdmissionRecord,
    ChildSeedRecord,
    FoldRecord,
    NormalizedAuthorityEvent,
    P02Result,
    _sha256_hex,
)
from .expansion import (
    SEMANTIC_SPACE,
    ABI_VERSION,
    SHAPE,
    DTYPE,
    VOCABULARY_SIZE,
    EXPANSION_TOKEN,
    VOID_TOKEN,
    make_semantic_space_digest,
    admit_expansion,
    validate_expansion_cells,
)
from .seeds import (
    create_child_seed_record,
    derive_child_seed,
    derive_child_request_id,
    grid_digest,
    fold_child_result,
    apply_fold,
    create_fold_record,
)
from .authority_bridge import L0ExpansionAuthorityBridge


# ---------------------------------------------------------------------------
# Canonical axes helper
# ---------------------------------------------------------------------------

def _canonical_axes(bv: BudgetVector) -> tuple[tuple[str, Optional[int]], ...]:
    """Produce canonical (axis, value) tuples for conservation recording."""
    axes = ("steps", "depth", "backend", "tokens", "energy", "wall_ms", "writes")
    return tuple((a, getattr(bv, a)) for a in axes)


def _structural_digest(grid81: tuple[int, ...]) -> str:
    """Deterministic digest of a grid81 structural result."""
    payload = ",".join(str(c) for c in grid81)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# TRM proposal test double
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DeterministicProposalTRM:
    """A deterministic TRM test double that emits a fixed proposal.

    Implements the TRM proposal port without inference.
    """
    proposed_grid81: tuple[int, ...]
    expansion_cells: tuple[int, ...] = ()
    residual81: tuple[float, ...] = field(default_factory=lambda: (0.0,) * 81)
    halt_score: float = 0.5

    def propose(
        self,
        seed_grid81: tuple[int, ...],
    ) -> TRMRefinementProposal:
        """Return the fixed proposal. Does NOT authorize anything."""
        digest = _sha256_hex(
            f"TRM|{'|'.join(str(c) for c in self.proposed_grid81)}|"
            f"{'|'.join(str(c) for c in self.expansion_cells)}"
        )
        return TRMRefinementProposal(
            input_digest=grid_digest(seed_grid81),
            proposed_grid81=self.proposed_grid81,
            residual81=self.residual81,
            halt_score=self.halt_score,
            expansion_cells=self.expansion_cells,
            rationale=(),
            digest=digest,
        )

    def propose_from_seed(
        self,
        seed_grid81: tuple[int, ...],
    ) -> TRMRefinementProposal:
        """Alias for the TRMProposalPort interface."""
        return self.propose(seed_grid81)


class FailingTRM:
    """A TRM test double that fails on propose with a typed error."""

    def __init__(self, error_type: str = "nan"):
        self._error_type = error_type

    def propose(self, seed_grid81: tuple[int, ...]) -> TRMRefinementProposal:
        if self._error_type == "nan":
            raise ValueError("TRM produced NaN residual")
        elif self._error_type == "shape":
            raise ValueError("TRM produced invalid shape")
        else:
            raise RuntimeError(f"TRM typed ABI failure: {self._error_type}")


# ---------------------------------------------------------------------------
# P0.2 Runner
# ---------------------------------------------------------------------------

def run_p02_expansion(
    request_id: str,
    parent_seed_grid81: tuple[int, ...],
    parent_trm: DeterministicProposalTRM,
    child_trm: DeterministicProposalTRM,
    initial_budget: BudgetVector,
    spawn_cost: Charge,
    child_allocation: Charge,
    child_refinement_charge: Charge,
    current_depth: int = 0,
) -> P02Result:
    """Execute the full P0.2 one-child affine expansion protocol.

    Sequence:
      1. Parent structural input -> parent TRM proposal
      2. Expansion proposal evidence
      3. Deterministic admission
      4. Child seed derivation
      5. Authority: allocate child
      6. Authority: charge child refinement
      7. Child TRM proposal
      8. Authority: seal child
      9. Authority: close parent lease (COMPLETED or ABORTED)
      10. Deterministic structural fold
      11. Parent conservation assertion
    """
    frame = 0
    raw_evidence: list[str] = []
    normalized_trace: list[NormalizedAuthorityEvent] = []

    # ---- Step 0: Parent input digest ----
    parent_input_digest = _structural_digest(parent_seed_grid81)

    # ---- Step 1: Parent TRM proposal ----
    parent_proposal = parent_trm.propose(parent_seed_grid81)
    parent_proposal_digest = parent_proposal.digest
    proposed_grid81 = parent_proposal.proposed_grid81

    frame += 1

    # ---- Step 2: Expansion proposal evidence ----
    semantic_space_digest = make_semantic_space_digest()
    valid_cells, rejected_cells = validate_expansion_cells(
        parent_proposal.expansion_cells,
        proposed_grid81,
    )

    expansion_proposal = ExpansionProposalEvidence.create(
        request_id=request_id,
        parent_proposal_digest=parent_proposal_digest,
        semantic_space_digest=semantic_space_digest,
        proposed_cells=parent_proposal.expansion_cells,
        valid_cells=valid_cells,
        rejected_cells=rejected_cells,
        frame_index=frame,
    )
    frame += 1

    # ---- Step 3: Admission ----
    admission = admit_expansion(
        request_id=request_id,
        proposal_digest=parent_proposal_digest,
        proposed_cells=parent_proposal.expansion_cells,
        proposed_grid81=proposed_grid81,
        semantic_space=SEMANTIC_SPACE,
        abi_version=ABI_VERSION,
        shape=SHAPE,
        dtype=DTYPE,
        vocabulary_size=VOCABULARY_SIZE,
        budget=initial_budget,
        spawn_cost=spawn_cost,
        allocation=child_allocation,
        current_depth=current_depth,
        frame_index=frame,
    )
    frame += 1

    # Record authority event for admission
    normalized_trace.append(NormalizedAuthorityEvent(
        event_kind="ADMISSION",
        account_role="parent",
        capability_role=None,
        lease_role=None,
        charge_axes=tuple(),
        budget_before_axes=None,
        budget_after_axes=None,
        close_reason=None,
        sequence_role="admission",
    ))

    # ---- Admission rejection -> early return ----
    if admission.decision != "ADMITTED":
        return P02Result(
            request_id=request_id,
            parent_input_digest=parent_input_digest,
            parent_proposal_digest=parent_proposal_digest,
            expansion_proposal=expansion_proposal,
            admission=admission,
            child_seed=None,
            child_proposal_digest=None,
            fold_record=None,
            parent_conservation_before=_canonical_axes(initial_budget),
            parent_conservation_after=_canonical_axes(initial_budget),
            child_conservation_before=None,
            child_conservation_after=None,
            normalized_authority_trace=tuple(normalized_trace),
            raw_authority_evidence=tuple(raw_evidence),
            references=(),
            structural_result_digest=_structural_digest(parent_seed_grid81),
            normalized_authority_digest=_sha256_hex(
                ",".join(e.event_kind for e in normalized_trace)
            ),
            child_allocated=False,
            child_inference_invoked=False,
            child_closed=False,
            expert_activated=False,
            artifact_executed=False,
            memory_written=False,
            governance_invoked=False,
            stop_authorized=False,
        )

    # ---- Step 4: Open parent account ----
    bridge, root_cap = L0ExpansionAuthorityBridge.open_parent(
        request_id=request_id,
        initial_budget=initial_budget,
    )
    raw_evidence.append(f"parent-opened: {bridge.snapshot().account_id}")

    # Conservation after open
    bridge.assert_conservation()
    parent_conservation_before = _canonical_axes(bridge.snapshot().initial_budget)

    normalized_trace.append(NormalizedAuthorityEvent(
        event_kind="ACCOUNT_OPEN",
        account_role="parent",
        capability_role="parent-root-capability",
        lease_role=None,
        charge_axes=tuple(),
        budget_before_axes=None,
        budget_after_axes=_canonical_axes(initial_budget),
        close_reason=None,
        sequence_role="open",
    ))
    frame += 1

    # ---- Step 5: Child seed derivation ----
    chosen_cell = admission.chosen_cell  # type: ignore[union-attr]
    child_seed_record = create_child_seed_record(
        request_id=request_id,
        parent_request_id=request_id,
        parent_structural_digest=parent_input_digest,
        chosen_cell=chosen_cell,
        parent_grid81=proposed_grid81,
        frame_index=frame,
    )
    child_request_id = child_seed_record.child_request_id
    frame += 1

    # ---- Step 6: Allocate child ----
    child_alloc = bridge.allocate_child(
        child_request_id=child_request_id,
        allocation=child_allocation,
        spawn_cost=spawn_cost,
    )
    raw_evidence.append(
        f"child-allocated: {child_alloc.child_account._state.account_id}"
    )

    # Conservation after allocation
    bridge.assert_conservation()
    bridge.child_assert_conservation(child_alloc.child_account)

    normalized_trace.append(NormalizedAuthorityEvent(
        event_kind="CHILD_ALLOCATE",
        account_role="parent",
        capability_role="parent-successor-capability",
        lease_role="child-lease-0",
        charge_axes=("steps", "depth"),
        budget_before_axes=_canonical_axes(child_alloc.parent_receipt.budget_before),
        budget_after_axes=_canonical_axes(child_alloc.parent_receipt.budget_after),
        close_reason=None,
        sequence_role="allocate",
    ))
    frame += 1

    # ---- Step 7: Charge child refinement ----
    _, child_successor_cap = bridge.charge_child_refinement(
        child_alloc.child_account,
        child_alloc.child_root,
        child_refinement_charge,
    )
    raw_evidence.append("child-refinement-charged")

    # Child conservation after charge
    bridge.child_assert_conservation(child_alloc.child_account)
    child_conservation_after_charge = _canonical_axes(
        child_alloc.child_account._state.remaining_budget
    )

    normalized_trace.append(NormalizedAuthorityEvent(
        event_kind="CHILD_REFINEMENT_CHARGE",
        account_role="child",
        capability_role="child-successor-capability-0",
        lease_role=None,
        charge_axes=("steps", "depth"),
        budget_before_axes=None,
        budget_after_axes=child_conservation_after_charge,
        close_reason=None,
        sequence_role="refine",
    ))
    frame += 1

    # ---- Step 8: Child TRM proposal ----
    child_completed = False
    child_proposal_digest: Optional[str] = None
    child_proposed_grid81: tuple[int, ...] = (VOID_TOKEN,) * 81

    try:
        child_proposal = child_trm.propose(child_seed_record.child_seed_grid81)
        child_proposal_digest = child_proposal.digest
        child_proposed_grid81 = child_proposal.proposed_grid81
        child_completed = True
        raw_evidence.append(f"child-proposal: {child_proposal_digest}")
    except Exception as e:
        raw_evidence.append(f"child-proposal-failed: {type(e).__name__}: {e}")

    normalized_trace.append(NormalizedAuthorityEvent(
        event_kind="CHILD_INFERENCE" if child_completed else "CHILD_INFERENCE_FAILED",
        account_role="child",
        capability_role=None,
        lease_role=None,
        charge_axes=tuple(),
        budget_before_axes=None,
        budget_after_axes=None,
        close_reason=None,
        sequence_role="inference",
    ))
    frame += 1

    # ---- Step 9: Seal child ----
    bridge.seal_child(child_alloc.child_account)
    raw_evidence.append("child-sealed")

    # Assert child conservation
    bridge.child_assert_conservation(child_alloc.child_account)
    child_conservation_after = _canonical_axes(
        child_alloc.child_account._state.remaining_budget
    )

    normalized_trace.append(NormalizedAuthorityEvent(
        event_kind="CHILD_SEAL",
        account_role="child",
        capability_role=None,
        lease_role=None,
        charge_axes=tuple(),
        budget_before_axes=None,
        budget_after_axes=child_conservation_after,
        close_reason=None,
        sequence_role="seal",
    ))
    frame += 1

    # ---- Step 10: Close parent lease ----
    close_reason = ChildCloseReason.COMPLETED if child_completed else ChildCloseReason.ABORTED
    close_receipt = bridge.close_child(
        child_alloc.lease,
        reason=close_reason,
    )
    raw_evidence.append(f"child-closed: {close_receipt.reason.value}")

    normalized_trace.append(NormalizedAuthorityEvent(
        event_kind="CHILD_LEASE_CLOSE",
        account_role="parent",
        capability_role=None,
        lease_role="child-lease-0",
        charge_axes=tuple(),
        budget_before_axes=None,
        budget_after_axes=None,
        close_reason=close_receipt.reason.value,
        sequence_role="close",
    ))
    frame += 1

    # ---- Step 11: Fold ----
    child_token, folded_token, unresolved = fold_child_result(
        proposed_grid81,
        child_proposed_grid81,
        chosen_cell,
        child_completed,
    )

    folded_grid81 = apply_fold(proposed_grid81, chosen_cell, folded_token)
    parent_before_digest = _structural_digest(proposed_grid81)
    parent_after_digest = _structural_digest(folded_grid81)

    fold_record = create_fold_record(
        request_id=request_id,
        child_request_id=child_request_id,
        chosen_cell=chosen_cell,
        child_status="COMPLETED" if child_completed else "ABORTED",
        child_token=child_token,
        folded_token=folded_token,
        unresolved_expansion=unresolved,
        parent_before_digest=parent_before_digest,
        parent_after_digest=parent_after_digest,
        frame_index=frame,
    )
    frame += 1

    # ---- Step 12: Final parent conservation ----
    bridge.assert_conservation()
    parent_conservation_after = _canonical_axes(
        bridge.snapshot().remaining_budget
    )

    normalized_trace.append(NormalizedAuthorityEvent(
        event_kind="PARENT_CONSERVATION",
        account_role="parent",
        capability_role=None,
        lease_role=None,
        charge_axes=tuple(),
        budget_before_axes=parent_conservation_after,
        budget_after_axes=parent_conservation_after,
        close_reason=None,
        sequence_role="final",
    ))

    # ---- Build result ----
    structural_result_digest = _structural_digest(folded_grid81)
    normalized_authority_digest = _sha256_hex(
        "|".join(
            f"{e.event_kind}:{e.account_role}:{e.sequence_role}"
            for e in normalized_trace
        )
    )

    child_conservation_before = _canonical_axes(
        child_alloc.child_account._state.initial_budget
    )

    return P02Result(
        request_id=request_id,
        parent_input_digest=parent_input_digest,
        parent_proposal_digest=parent_proposal_digest,
        expansion_proposal=expansion_proposal,
        admission=admission,
        child_seed=child_seed_record,
        child_proposal_digest=child_proposal_digest,
        fold_record=fold_record,
        parent_conservation_before=parent_conservation_before,
        parent_conservation_after=parent_conservation_after,
        child_conservation_before=child_conservation_before,
        child_conservation_after=child_conservation_after,
        normalized_authority_trace=tuple(normalized_trace),
        raw_authority_evidence=tuple(raw_evidence),
        references=(),
        structural_result_digest=structural_result_digest,
        normalized_authority_digest=normalized_authority_digest,
        child_allocated=True,
        child_inference_invoked=True,
        child_closed=True,
        expert_activated=False,
        artifact_executed=False,
        memory_written=False,
        governance_invoked=False,
        stop_authorized=False,
    )
