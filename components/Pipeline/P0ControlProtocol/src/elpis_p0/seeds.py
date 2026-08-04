"""P0.2 child seed and fold rules.

Seed rule: child_seed.copy_void_cell.v1
Fold rule: fold.replace_cell.v1

Both rules are deterministic and operate on structural grid81 tuples only.
"""
from __future__ import annotations

import hashlib
from typing import Optional, Tuple

from .expansion_contracts import (
    ChildSeedRecord,
    FoldRecord,
    _sha256_hex,
)
from .expansion import EXPANSION_TOKEN, VOID_TOKEN


# ---------------------------------------------------------------------------
# Seed rule: child_seed.copy_void_cell.v1
# ---------------------------------------------------------------------------

SEED_RULE_ID = "child_seed.copy_void_cell.v1"


def derive_child_seed(
    parent_grid81: tuple[int, ...],
    chosen_cell: int,
) -> tuple[int, ...]:
    """Copy parent grid, set chosen expansion cell to VOID (0).

    Algorithm:
      1. Copy complete parent proposed_grid81.
      2. Set selected expansion cell to VOID token 0.
      3. Preserve every other cell.
      4. Preserve structural semantic-space identity.
    """
    if len(parent_grid81) != 81:
        raise ValueError("parent_grid81 must have 81 cells")
    if chosen_cell < 0 or chosen_cell >= 81:
        raise ValueError("chosen_cell must be in [0, 81)")

    seed = list(parent_grid81)
    seed[chosen_cell] = VOID_TOKEN
    return tuple(seed)


def derive_child_request_id(
    parent_request_id: str,
    parent_structural_digest: str,
    chosen_cell: int,
) -> str:
    """Derive deterministic child request ID from parent identity + cell.

    Uses fixed domain separator.
    """
    payload = (
        f"{parent_request_id}|{parent_structural_digest}|"
        f"child:{chosen_cell}|P0.2_DOMAIN_SEPARATOR"
    )
    return _sha256_hex(payload)


def grid_digest(grid81: tuple[int, ...]) -> str:
    """Deterministic digest of a grid81 tuple."""
    payload = ",".join(str(c) for c in grid81)
    return _sha256_hex(payload)


def create_child_seed_record(
    request_id: str,
    parent_request_id: str,
    parent_structural_digest: str,
    chosen_cell: int,
    parent_grid81: tuple[int, ...],
    frame_index: int,
) -> ChildSeedRecord:
    """Create a complete ChildSeedRecord."""
    child_seed_grid81 = derive_child_seed(parent_grid81, chosen_cell)
    child_seed_digest = grid_digest(child_seed_grid81)
    child_request_id = derive_child_request_id(
        parent_request_id, parent_structural_digest, chosen_cell
    )
    return ChildSeedRecord.create(
        request_id=request_id,
        child_request_id=child_request_id,
        chosen_cell=chosen_cell,
        seed_rule_id=SEED_RULE_ID,
        parent_grid_digest=parent_structural_digest,
        child_seed_grid81=child_seed_grid81,
        child_seed_digest=child_seed_digest,
        frame_index=frame_index,
    )


# ---------------------------------------------------------------------------
# Fold rule: fold.replace_cell.v1
# ---------------------------------------------------------------------------

FOLD_RULE_ID = "fold.replace_cell.v1"


def fold_child_result(
    parent_grid81: tuple[int, ...],
    child_proposed_grid81: tuple[int, ...],
    chosen_cell: int,
    child_completed: bool,
) -> Tuple[int, int, bool]:
    """Apply fold.replace_cell.v1.

    Returns (child_token, folded_token, unresolved_expansion).

    On successful child proposal:
      if child_proposed_grid81[chosen_cell] != EXPANSION:
          folded_token = child_proposed_grid81[chosen_cell]
          unresolved = false
      else:
          folded_token = VOID
          unresolved = true

    On child abort:
      folded_token = VOID
      unresolved = true
    """
    child_token = child_proposed_grid81[chosen_cell] if child_completed else VOID_TOKEN

    if not child_completed:
        return (VOID_TOKEN, VOID_TOKEN, True)

    if child_token != EXPANSION_TOKEN:
        return (child_token, child_token, False)
    else:
        return (child_token, VOID_TOKEN, True)


def apply_fold(
    parent_grid81: tuple[int, ...],
    chosen_cell: int,
    folded_token: int,
) -> tuple[int, ...]:
    """Replace only the chosen parent cell with the folded token."""
    if len(parent_grid81) != 81:
        raise ValueError("parent_grid81 must have 81 cells")
    if chosen_cell < 0 or chosen_cell >= 81:
        raise ValueError("chosen_cell must be in [0, 81)")

    folded = list(parent_grid81)
    folded[chosen_cell] = folded_token
    return tuple(folded)


def create_fold_record(
    request_id: str,
    child_request_id: str,
    chosen_cell: int,
    child_status: str,
    child_token: int,
    folded_token: int,
    unresolved_expansion: bool,
    parent_before_digest: str,
    parent_after_digest: str,
    frame_index: int,
) -> FoldRecord:
    """Create a complete FoldRecord."""
    return FoldRecord.create(
        request_id=request_id,
        child_request_id=child_request_id,
        chosen_cell=chosen_cell,
        fold_rule_id=FOLD_RULE_ID,
        child_status=child_status,
        child_token=child_token,
        folded_token=folded_token,
        unresolved_expansion=unresolved_expansion,
        parent_before_digest=parent_before_digest,
        parent_after_digest=parent_after_digest,
        frame_index=frame_index,
    )
