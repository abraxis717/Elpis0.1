"""Deterministic legal-move decoder for the transplanted core (D0).

Authority boundary:
    The model emits per-cell BasisToken logits only. The decoder
    * enumerates structurally legal candidate moves from (grid, mask)
      alone,
    * scores those legal candidates using ONLY the TRM output logits,
    * chooses the highest-scoring legal candidate (deterministic
      first-in-enumeration tie-break).

The decoder NEVER reads:
    structural residual, target/hidden grid, teacher cost, invariants,
    or any semantic identity. The residual remains an INPUT FEATURE to
    the TRM, never a cheat available to the decoder.

Every emitted transition satisfies, by construction, the production
Elpis transition contract (exactly the semantics of
``elpis_p0.structural_residual.validate_transition``):
    * after is 81 entries, tokens 0..9
    * frozen loci (writable mask 0) do not change
    * per-lane operational-token multiset (INPUT/TRANSFORM/OUTPUT) is
      preserved: operational tokens relocate within their lane only;
      none are created or destroyed.

If no legal transition exists the decoder returns KEEP (no-op).
No fallback search solver.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import torch

# Production Grid81 structural geometry (components/TRMFractalSpine /
# elpis_p0.structural_residual).
GRID_SIZE = 81
LANES = 9
RANKS = 9
TERMINAL_CELL = 80

# BasisToken values (elpis_p0.contracts.BasisToken).
VOID = 0
INPUT = 1
TRANSFORM = 2
OUTPUT = 3
MEMORY = 4
CONSTRAINT = 5
EXPANSION = 6
ROUTE = 7
INTERFACE = 8
RESOLUTION = 9

OPERATIONAL_TOKENS = frozenset({INPUT, TRANSFORM, OUTPUT})

# Tokens a refiner may place (production PLACEABLE_TOKENS).
PLACEABLE_TOKENS = (
    VOID,
    MEMORY,
    CONSTRAINT,
    ROUTE,
    INTERFACE,
    RESOLUTION,
)


def cell(rank: int, lane: int) -> int:
    return rank * LANES + lane


class DecoderError(ValueError):
    pass


@dataclass
class CandidateMove:
    op: str  # "set" | "move"
    a: int   # set: index; move: lane
    b: int   # set: token; move: target rank
    score: float = 0.0

    def as_tuple(self) -> Tuple[str, int, int]:
        return (self.op, self.a, self.b)


@dataclass
class DecoderInstrumentation:
    """Counts oracle reads so tests can prove the decoder is clean."""

    residual_reads: int = 0
    target_grid_reads: int = 0
    teacher_cost_reads: int = 0
    invariant_reads: int = 0
    candidate_count: int = 0
    emitted_transition: bool = False

    def read_residual(self) -> None:
        self.residual_reads += 1

    def read_target_grid(self) -> None:
        self.target_grid_reads += 1

    def read_teacher_cost(self) -> None:
        self.teacher_cost_reads += 1

    def read_invariants(self) -> None:
        self.invariant_reads += 1

    @property
    def oracle_reads_total(self) -> int:
        return (
            self.residual_reads
            + self.target_grid_reads
            + self.teacher_cost_reads
            + self.invariant_reads
        )


def apply_move(grid: List[int], move: Tuple[str, int, int]) -> List[int]:
    """Production _apply semantics (probe + elpis_p0)."""
    out = list(grid)
    op, a, b = move
    if op == "set":
        out[a] = b
    elif op == "move":
        lane, rank = a, b
        current = next(
            r for r in range(RANKS)
            if grid[cell(r, lane)] in OPERATIONAL_TOKENS
        )
        token = grid[cell(current, lane)]
        out[cell(current, lane)] = VOID
        out[cell(rank, lane)] = token
    else:
        raise DecoderError(f"unknown move op {op!r}")
    return out


def legal_moves(grid: List[int], mask: List[int]) -> List[Tuple[str, int, int]]:
    """Structurally legal candidate moves from (grid, mask) ONLY.

    Identical enumeration to the production probe ``_legal_moves``:
      * set: writable non-operational cell -> any placeable token
             (different from current)
      * move: relocate the unique operational token of a lane to a
             writable non-operational rank in the same lane
    Deterministic enumeration order (fixed loops), used as tie-break.
    """
    if len(grid) != GRID_SIZE:
        raise DecoderError(f"grid must be 81 entries, got {len(grid)}")
    if len(mask) != GRID_SIZE:
        raise DecoderError(f"mask must be 81 entries, got {len(mask)}")
    for v in grid:
        if not 0 <= v <= 9:
            raise DecoderError(f"grid token out of range: {v}")
    for v in mask:
        if v not in (0, 1):
            raise DecoderError(f"mask entry must be 0/1, got {v}")

    moves: List[Tuple[str, int, int]] = []
    op_lanes: dict = {}
    for lane in range(LANES):
        for rank in range(RANKS):
            if grid[cell(rank, lane)] in OPERATIONAL_TOKENS:
                op_lanes[lane] = rank

    for index in range(GRID_SIZE):
        if not mask[index]:
            continue
        if grid[index] in OPERATIONAL_TOKENS:
            continue
        for token in PLACEABLE_TOKENS:
            if token != grid[index]:
                moves.append(("set", index, token))

    for lane, current in op_lanes.items():
        for rank in range(RANKS):
            target = cell(rank, lane)
            if rank == current or not mask[target]:
                continue
            if grid[target] in OPERATIONAL_TOKENS:
                continue
            moves.append(("move", lane, rank))

    return moves


def validate_transition_d0(
    before: List[int],
    after: List[int],
    mask: List[int],
) -> None:
    """Exhaustive production transition contract (fail-closed).

    Mirrors ``elpis_p0.structural_residual.validate_transition`` exactly
    for the (grid, mask) surface: token range, frozen loci, and
    per-lane operational multiset preservation.
    """
    if len(after) != GRID_SIZE:
        raise DecoderError("proposed grid must be 81 entries")
    for value in after:
        if not 0 <= value <= 9:
            raise DecoderError(f"proposed token out of range: {value}")
    for index in range(GRID_SIZE):
        if mask[index] == 0 and after[index] != before[index]:
            raise DecoderError(f"refiner wrote frozen locus {index}")
    for lane in range(LANES):
        was = sorted(
            before[cell(rank, lane)] for rank in range(RANKS)
            if before[cell(rank, lane)] in OPERATIONAL_TOKENS
        )
        now = sorted(
            after[cell(rank, lane)] for rank in range(RANKS)
            if after[cell(rank, lane)] in OPERATIONAL_TOKENS
        )
        if was != now:
            raise DecoderError(
                f"refiner altered the operational multiset of lane {lane}: "
                f"{was} -> {now}"
            )


def _candidate_score(
    move: Tuple[str, int, int],
    grid: List[int],
    logits: torch.Tensor,
) -> float:
    """Score a legal candidate using ONLY the TRM per-cell logits.

    set(index, token): logits[index, token]
    move(lane, rank):  logits[cell(rank,lane), token] + logits[source, VOID]
    """
    op, a, b = move
    if op == "set":
        return float(logits[a, b])
    lane, rank = a, b
    current = next(
        r for r in range(RANKS)
        if grid[cell(r, lane)] in OPERATIONAL_TOKENS
    )
    token = grid[cell(current, lane)]
    return float(
        logits[cell(rank, lane), token] + logits[cell(current, lane), VOID]
    )


@dataclass
class DecodeResult:
    grid_before: List[int]
    grid_after: List[int]
    move: Optional[Tuple[str, int, int]]
    kept: bool
    candidate_count: int
    score: Optional[float] = None


def deterministic_decode(
    grid: List[int],
    mask: List[int],
    cell_logits: torch.Tensor,
    instrumentation: Optional[DecoderInstrumentation] = None,
) -> DecodeResult:
    """Enumerate legal candidates, score with logits, pick the max.

    cell_logits: [81, 10] per-cell BasisToken logits (single sample).
    Returns KEEP when there is no legal candidate.
    """
    if cell_logits.ndim != 2 or cell_logits.shape != (GRID_SIZE, 10):
        raise DecoderError(
            f"cell_logits must be [81, 10], got {tuple(cell_logits.shape)}"
        )

    inst = instrumentation or DecoderInstrumentation()
    moves = legal_moves(grid, mask)
    inst.candidate_count = len(moves)
    if not moves:
        return DecodeResult(list(grid), list(grid), None, True, 0)

    best_move: Optional[Tuple[str, int, int]] = None
    best_score = float("-inf")
    for move in moves:  # deterministic enumeration order = tie-break
        score = _candidate_score(move, grid, cell_logits)
        if score > best_score:
            best_score = score
            best_move = move

    assert best_move is not None  # moves was non-empty above
    after = apply_move(grid, best_move)
    # Construction guarantee, checked on every emission (fail-closed).
    validate_transition_d0(grid, after, mask)
    inst.emitted_transition = True

    return DecodeResult(
        list(grid), after, best_move, False, len(moves), best_score
    )
