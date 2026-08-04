"""P0.2 frozen expansion evidence records.

All records are frozen, slotted dataclasses carrying chronological
evidence (frame_index, wall_time_ns, monotonic_ns) plus a deterministic
SHA-256 structural digest that excludes clock values.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Literal, Optional


# ---------------------------------------------------------------------------
# Timing helper
# ---------------------------------------------------------------------------

def _now() -> tuple[int, int, int]:
    """Return (frame_index placeholder, wall_time_ns, monotonic_ns).

    Callers must supply frame_index; this provides clock readings.
    """
    return (0, time.time_ns(), time.monotonic_ns())


def _clock() -> tuple[int, int]:
    """Return (wall_time_ns, monotonic_ns)."""
    return (time.time_ns(), time.monotonic_ns())


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# ExpansionProposalEvidence
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ExpansionProposalEvidence:
    request_id: str
    parent_proposal_digest: str
    semantic_space_digest: str
    proposed_cells: tuple[int, ...]
    valid_cells: tuple[int, ...]
    rejected_cells: tuple[int, ...]
    frame_index: int
    wall_time_ns: int
    monotonic_ns: int
    digest: str

    @classmethod
    def create(
        cls,
        request_id: str,
        parent_proposal_digest: str,
        semantic_space_digest: str,
        proposed_cells: tuple[int, ...],
        valid_cells: tuple[int, ...],
        rejected_cells: tuple[int, ...],
        frame_index: int,
    ) -> "ExpansionProposalEvidence":
        wall, mono = _clock()
        payload = (
            f"{request_id}|{parent_proposal_digest}|{semantic_space_digest}|"
            f"{','.join(str(c) for c in proposed_cells)}|"
            f"{','.join(str(c) for c in valid_cells)}|"
            f"{','.join(str(c) for c in rejected_cells)}"
        )
        return cls(
            request_id=request_id,
            parent_proposal_digest=parent_proposal_digest,
            semantic_space_digest=semantic_space_digest,
            proposed_cells=proposed_cells,
            valid_cells=valid_cells,
            rejected_cells=rejected_cells,
            frame_index=frame_index,
            wall_time_ns=wall,
            monotonic_ns=mono,
            digest=_sha256_hex(payload),
        )


# ---------------------------------------------------------------------------
# ExpansionAdmissionRecord
# ---------------------------------------------------------------------------

AdmissionDecision = Literal[
    "ADMITTED",
    "NONE_PROPOSED",
    "REJECTED_SEMANTIC_SPACE",
    "REJECTED_POLICY",
    "REJECTED_RANKING",
    "REJECTED_BUDGET",
]


@dataclass(frozen=True, slots=True)
class ExpansionAdmissionRecord:
    request_id: str
    proposal_digest: str
    chosen_cell: Optional[int]
    decision: AdmissionDecision
    allocation: Optional[tuple[int, ...]]
    spawn_cost: tuple[int, ...]
    ranking_before: int
    spawn_rank_cost: int
    ranking_after: int
    reason_codes: tuple[str, ...]
    frame_index: int
    wall_time_ns: int
    monotonic_ns: int
    digest: str

    @classmethod
    def create(
        cls,
        request_id: str,
        proposal_digest: str,
        chosen_cell: Optional[int],
        decision: AdmissionDecision,
        allocation: Optional[tuple[int, ...]],
        spawn_cost: tuple[int, ...],
        ranking_before: int,
        spawn_rank_cost: int,
        ranking_after: int,
        reason_codes: tuple[str, ...],
        frame_index: int,
    ) -> "ExpansionAdmissionRecord":
        wall, mono = _clock()
        payload = (
            f"{request_id}|{proposal_digest}|{chosen_cell}|{decision}|"
            f"{','.join(str(a) for a in (allocation or ()))}|"
            f"{','.join(str(s) for s in spawn_cost)}|"
            f"{ranking_before}|{spawn_rank_cost}|{ranking_after}|"
            f"{','.join(rc for rc in reason_codes)}"
        )
        return cls(
            request_id=request_id,
            proposal_digest=proposal_digest,
            chosen_cell=chosen_cell,
            decision=decision,
            allocation=allocation,
            spawn_cost=spawn_cost,
            ranking_before=ranking_before,
            spawn_rank_cost=spawn_rank_cost,
            ranking_after=ranking_after,
            reason_codes=reason_codes,
            frame_index=frame_index,
            wall_time_ns=wall,
            monotonic_ns=mono,
            digest=_sha256_hex(payload),
        )


# ---------------------------------------------------------------------------
# ChildSeedRecord
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ChildSeedRecord:
    request_id: str
    child_request_id: str
    chosen_cell: int
    seed_rule_id: str
    parent_grid_digest: str
    child_seed_grid81: tuple[int, ...]
    child_seed_digest: str
    frame_index: int
    wall_time_ns: int
    monotonic_ns: int
    digest: str

    @classmethod
    def create(
        cls,
        request_id: str,
        child_request_id: str,
        chosen_cell: int,
        seed_rule_id: str,
        parent_grid_digest: str,
        child_seed_grid81: tuple[int, ...],
        child_seed_digest: str,
        frame_index: int,
    ) -> "ChildSeedRecord":
        wall, mono = _clock()
        payload = (
            f"{request_id}|{child_request_id}|{chosen_cell}|{seed_rule_id}|"
            f"{parent_grid_digest}|{','.join(str(c) for c in child_seed_grid81)}|"
            f"{child_seed_digest}"
        )
        return cls(
            request_id=request_id,
            child_request_id=child_request_id,
            chosen_cell=chosen_cell,
            seed_rule_id=seed_rule_id,
            parent_grid_digest=parent_grid_digest,
            child_seed_grid81=child_seed_grid81,
            child_seed_digest=child_seed_digest,
            frame_index=frame_index,
            wall_time_ns=wall,
            monotonic_ns=mono,
            digest=_sha256_hex(payload),
        )


# ---------------------------------------------------------------------------
# FoldRecord
# ---------------------------------------------------------------------------

ChildStatus = Literal["COMPLETED", "ABORTED"]


@dataclass(frozen=True, slots=True)
class FoldRecord:
    request_id: str
    child_request_id: str
    chosen_cell: int
    fold_rule_id: str
    child_status: ChildStatus
    child_token: int
    folded_token: int
    unresolved_expansion: bool
    parent_before_digest: str
    parent_after_digest: str
    frame_index: int
    wall_time_ns: int
    monotonic_ns: int
    digest: str

    @classmethod
    def create(
        cls,
        request_id: str,
        child_request_id: str,
        chosen_cell: int,
        fold_rule_id: str,
        child_status: ChildStatus,
        child_token: int,
        folded_token: int,
        unresolved_expansion: bool,
        parent_before_digest: str,
        parent_after_digest: str,
        frame_index: int,
    ) -> "FoldRecord":
        wall, mono = _clock()
        payload = (
            f"{request_id}|{child_request_id}|{chosen_cell}|{fold_rule_id}|"
            f"{child_status}|{child_token}|{folded_token}|{unresolved_expansion}|"
            f"{parent_before_digest}|{parent_after_digest}"
        )
        return cls(
            request_id=request_id,
            child_request_id=child_request_id,
            chosen_cell=chosen_cell,
            fold_rule_id=fold_rule_id,
            child_status=child_status,
            child_token=child_token,
            folded_token=folded_token,
            unresolved_expansion=unresolved_expansion,
            parent_before_digest=parent_before_digest,
            parent_after_digest=parent_after_digest,
            frame_index=frame_index,
            wall_time_ns=wall,
            monotonic_ns=mono,
            digest=_sha256_hex(payload),
        )


# ---------------------------------------------------------------------------
# NormalizedAuthorityEvent
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class NormalizedAuthorityEvent:
    event_kind: str
    account_role: str
    capability_role: Optional[str]
    lease_role: Optional[str]
    charge_axes: tuple[str, ...]
    budget_before_axes: Optional[tuple[tuple[str, Optional[int]], ...]]
    budget_after_axes: Optional[tuple[tuple[str, Optional[int]], ...]]
    close_reason: Optional[str]
    sequence_role: str


# ---------------------------------------------------------------------------
# P02Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class P02Result:
    request_id: str
    parent_input_digest: str
    parent_proposal_digest: str
    expansion_proposal: ExpansionProposalEvidence
    admission: ExpansionAdmissionRecord
    child_seed: Optional[ChildSeedRecord]
    child_proposal_digest: Optional[str]
    fold_record: Optional[FoldRecord]
    parent_conservation_before: tuple[tuple[str, Optional[int]], ...]
    parent_conservation_after: tuple[tuple[str, Optional[int]], ...]
    child_conservation_before: Optional[tuple[tuple[str, Optional[int]], ...]]
    child_conservation_after: Optional[tuple[tuple[str, Optional[int]], ...]]
    normalized_authority_trace: tuple[NormalizedAuthorityEvent, ...]
    raw_authority_evidence: tuple[str, ...]
    references: tuple[str, ...]
    structural_result_digest: str
    normalized_authority_digest: str
    child_allocated: bool
    child_inference_invoked: bool
    child_closed: bool
    expert_activated: bool = False
    artifact_executed: bool = False
    memory_written: bool = False
    governance_invoked: bool = False
    stop_authorized: bool = False
