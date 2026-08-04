"""P0.2 expansion admission and ranking.

Deterministic expansion admission:
  1. Validate each proposed cell.
  2. Select min(admissible_cells).
  3. Compute spawn ranking cost.
  4. Admit or reject with typed evidence.

Uses admitted BudgetVector axes (steps, depth) for ranking.
"""
from __future__ import annotations

import hashlib
from typing import Optional, Tuple

from elpis.contracts.budget import BudgetVector, Charge

from .expansion_contracts import (
    ExpansionProposalEvidence,
    ExpansionAdmissionRecord,
    AdmissionDecision,
    _clock,
    _sha256_hex,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEMANTIC_SPACE = "grid81.structural.v1"
ABI_VERSION = "elpis.p0.trm-proposal.v1"
SHAPE = (1, 81)
DTYPE = "int64"
VOCABULARY_SIZE = 10

# Ranked axes and weights (admitted, positive integers)
W_STEPS = 1
W_DEPTH = 1
RANKED_AXES = ("steps", "depth")

# EXPANSION token value (from BasisToken)
EXPANSION_TOKEN = 6
VOID_TOKEN = 0

# Policy depth limit for P0.2
MAX_DEPTH = 1


# ---------------------------------------------------------------------------
# Semantic space identity
# ---------------------------------------------------------------------------

def make_semantic_space_digest() -> str:
    """Produce a deterministic digest for the P0.2 semantic space identity."""
    payload = (
        f"{SEMANTIC_SPACE}|{ABI_VERSION}|"
        f"{','.join(str(s) for s in SHAPE)}|{DTYPE}|{VOCABULARY_SIZE}"
    )
    return _sha256_hex(payload)


def validate_semantic_space(
    semantic_space: str,
    abi_version: str,
    shape: tuple[int, ...],
    dtype: str,
    vocabulary_size: int,
) -> bool:
    """Check whether a packet's declared identity matches P0.2 requirements."""
    return (
        semantic_space == SEMANTIC_SPACE
        and abi_version == ABI_VERSION
        and shape == SHAPE
        and dtype == DTYPE
        and vocabulary_size == VOCABULARY_SIZE
    )


# ---------------------------------------------------------------------------
# Cell validation
# ---------------------------------------------------------------------------

def validate_expansion_cells(
    proposed_cells: tuple[int, ...],
    proposed_grid81: tuple[int, ...],
    admitted_children: Optional[set[int]] = None,
) -> Tuple[tuple[int, ...], tuple[int, ...]]:
    """Validate proposed expansion cells.

    Returns (valid_cells, rejected_cells) with rejection reasons embedded
    in the caller's evidence.
    """
    if admitted_children is None:
        admitted_children = set()

    valid: list[int] = []
    rejected: list[int] = []

    for cell in proposed_cells:
        if cell < 0 or cell >= 81:
            rejected.append(cell)
            continue
        if proposed_grid81[cell] != EXPANSION_TOKEN:
            rejected.append(cell)
            continue
        if cell in admitted_children:
            rejected.append(cell)
            continue
        valid.append(cell)

    return tuple(valid), tuple(rejected)


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def compute_ranking(budget: BudgetVector) -> int:
    """Compute the ranking value from a BudgetVector's granted ranked axes.

    ranking = Σ w_a * B.a  for granted ranked axes a.
    NOT_GRANTED axes contribute 0.
    """
    ranking = 0
    for ax in RANKED_AXES:
        val = getattr(budget, ax)
        if val is not None:
            w = W_STEPS if ax == "steps" else W_DEPTH
            ranking += w * val
    return ranking


def has_granted_ranked_axes(budget: BudgetVector) -> bool:
    """Check whether at least one ranked axis is granted."""
    return any(getattr(budget, ax) is not None for ax in RANKED_AXES)


def compute_spawn_rank_cost(spawn_cost: Charge) -> int:
    """Compute spawn ranking cost using only granted ranked axes.

    spawn_rank_cost = Σ w_a * spawn_cost.a  for ranked axes a.
    """
    cost = 0
    for ax in RANKED_AXES:
        val = getattr(spawn_cost, ax)
        if val > 0:
            w = W_STEPS if ax == "steps" else W_DEPTH
            cost += w * val
    return cost


# ---------------------------------------------------------------------------
# Admission
# ---------------------------------------------------------------------------

def admit_expansion(
    request_id: str,
    proposal_digest: str,
    proposed_cells: tuple[int, ...],
    proposed_grid81: tuple[int, ...],
    semantic_space: str,
    abi_version: str,
    shape: tuple[int, ...],
    dtype: str,
    vocabulary_size: int,
    budget: BudgetVector,
    spawn_cost: Charge,
    allocation: Charge,
    admitted_children: Optional[set[int]] = None,
    current_depth: int = 0,
    frame_index: int = 0,
) -> ExpansionAdmissionRecord:
    """Deterministic expansion admission.

    Returns an ExpansionAdmissionRecord with the admission decision and
    all evidence fields populated.
    """
    if admitted_children is None:
        admitted_children = set()

    semantic_space_digest = make_semantic_space_digest()

    # Check semantic space identity first
    if not validate_semantic_space(
        semantic_space, abi_version, shape, dtype, vocabulary_size
    ):
        wall, mono = _clock()
        spawn_tuple = tuple(getattr(spawn_cost, ax) for ax in RANKED_AXES)
        return ExpansionAdmissionRecord(
            request_id=request_id,
            proposal_digest=proposal_digest,
            chosen_cell=None,
            decision="REJECTED_SEMANTIC_SPACE",
            allocation=None,
            spawn_cost=spawn_tuple,
            ranking_before=0,
            spawn_rank_cost=0,
            ranking_after=0,
            reason_codes=("SEMANTIC_SPACE_MISMATCH",),
            frame_index=frame_index,
            wall_time_ns=wall,
            monotonic_ns=mono,
            digest=_sha256_hex(
                f"{request_id}|{proposal_digest}|None|REJECTED_SEMANTIC_SPACE|"
                f"{'|'.join(str(s) for s in spawn_tuple)}"
            ),
        )

    # Check policy depth
    if current_depth >= MAX_DEPTH:
        wall, mono = _clock()
        return ExpansionAdmissionRecord(
            request_id=request_id,
            proposal_digest=proposal_digest,
            chosen_cell=None,
            decision="REJECTED_POLICY",
            allocation=None,
            spawn_cost=tuple(getattr(spawn_cost, ax) for ax in RANKED_AXES),
            ranking_before=0,
            spawn_rank_cost=0,
            ranking_after=0,
            reason_codes=("DEPTH_LIMIT_EXCEEDED",),
            frame_index=frame_index,
            wall_time_ns=wall,
            monotonic_ns=mono,
            digest=_sha256_hex(
                f"{request_id}|{proposal_digest}|None|REJECTED_POLICY|depth={current_depth}"
            ),
        )

    # No proposed cells
    if not proposed_cells:
        wall, mono = _clock()
        return ExpansionAdmissionRecord(
            request_id=request_id,
            proposal_digest=proposal_digest,
            chosen_cell=None,
            decision="NONE_PROPOSED",
            allocation=None,
            spawn_cost=tuple(getattr(spawn_cost, ax) for ax in RANKED_AXES),
            ranking_before=0,
            spawn_rank_cost=0,
            ranking_after=0,
            reason_codes=(),
            frame_index=frame_index,
            wall_time_ns=wall,
            monotonic_ns=mono,
            digest=_sha256_hex(
                f"{request_id}|{proposal_digest}|None|NONE_PROPOSED"
            ),
        )

    # Validate cells
    valid_cells, rejected_cells = validate_expansion_cells(
        proposed_cells, proposed_grid81, admitted_children
    )

    if not valid_cells:
        wall, mono = _clock()
        return ExpansionAdmissionRecord(
            request_id=request_id,
            proposal_digest=proposal_digest,
            chosen_cell=None,
            decision="REJECTED_POLICY",
            allocation=None,
            spawn_cost=tuple(getattr(spawn_cost, ax) for ax in RANKED_AXES),
            ranking_before=0,
            spawn_rank_cost=0,
            ranking_after=0,
            reason_codes=("NO_VALID_CELLS",),
            frame_index=frame_index,
            wall_time_ns=wall,
            monotonic_ns=mono,
            digest=_sha256_hex(
                f"{request_id}|{proposal_digest}|None|REJECTED_POLICY|no_valid_cells"
            ),
        )

    # Check ranked axes are granted
    if not has_granted_ranked_axes(budget):
        wall, mono = _clock()
        return ExpansionAdmissionRecord(
            request_id=request_id,
            proposal_digest=proposal_digest,
            chosen_cell=None,
            decision="REJECTED_RANKING",
            allocation=None,
            spawn_cost=tuple(getattr(spawn_cost, ax) for ax in RANKED_AXES),
            ranking_before=0,
            spawn_rank_cost=0,
            ranking_after=0,
            reason_codes=("RANKED_AXES_NOT_GRANTED",),
            frame_index=frame_index,
            wall_time_ns=wall,
            monotonic_ns=mono,
            digest=_sha256_hex(
                f"{request_id}|{proposal_digest}|None|REJECTED_RANKING|no_granted_axes"
            ),
        )

    # Compute spawn ranking cost
    spawn_rank_cost = compute_spawn_rank_cost(spawn_cost)

    # Spawn cost must charge at least one granted ranked axis
    if spawn_rank_cost < 1:
        wall, mono = _clock()
        return ExpansionAdmissionRecord(
            request_id=request_id,
            proposal_digest=proposal_digest,
            chosen_cell=None,
            decision="REJECTED_RANKING",
            allocation=None,
            spawn_cost=tuple(getattr(spawn_cost, ax) for ax in RANKED_AXES),
            ranking_before=0,
            spawn_rank_cost=0,
            ranking_after=0,
            reason_codes=("ZERO_RANKED_SPAWN_CHARGE",),
            frame_index=frame_index,
            wall_time_ns=wall,
            monotonic_ns=mono,
            digest=_sha256_hex(
                f"{request_id}|{proposal_digest}|None|REJECTED_RANKING|zero_spawn_charge"
            ),
        )

    # Compute ranking
    ranking_before = compute_ranking(budget)
    ranking_after = ranking_before - spawn_rank_cost

    # Select min valid cell
    chosen_cell = min(valid_cells)

    # Produce admission record
    alloc_tuple = tuple(getattr(allocation, ax) for ax in RANKED_AXES)
    spawn_tuple = tuple(getattr(spawn_cost, ax) for ax in RANKED_AXES)
    wall, mono = _clock()
    digest_payload = (
        f"{request_id}|{proposal_digest}|{chosen_cell}|ADMITTED|"
        f"{'|'.join(str(a) for a in alloc_tuple)}|"
        f"{'|'.join(str(s) for s in spawn_tuple)}|"
        f"{ranking_before}|{spawn_rank_cost}|{ranking_after}"
    )
    return ExpansionAdmissionRecord(
        request_id=request_id,
        proposal_digest=proposal_digest,
        chosen_cell=chosen_cell,
        decision="ADMITTED",
        allocation=alloc_tuple,
        spawn_cost=spawn_tuple,
        ranking_before=ranking_before,
        spawn_rank_cost=spawn_rank_cost,
        ranking_after=ranking_after,
        reason_codes=(),
        frame_index=frame_index,
        wall_time_ns=wall,
        monotonic_ns=mono,
        digest=_sha256_hex(digest_payload),
    )
