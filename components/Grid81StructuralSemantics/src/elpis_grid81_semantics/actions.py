"""Canonical action representation for Grid81 (G4.0B Phase 4).

Per G4.0A spec:
  action: 'edit' | 'noop'
  target_cell: int|None (0..80) for edit, None for noop
  target_value: int|None (0..9) for edit, None for noop

Canonical invariants:
  NOOP: target_cell is None, target_value is None
  EDIT: target_cell in [0,80], target_value in [0,9]
  Reject NOOP with target fields, EDIT with null targets, sentinel values.
"""

from __future__ import annotations
import json
from dataclasses import dataclass
from enum import Enum


class ActionKindV1(Enum):
    NOOP = "noop"
    EDIT = "edit"


@dataclass(frozen=True)
class Grid81ActionV1:
    kind: ActionKindV1
    target_cell: int | None
    target_value: int | None

    def __post_init__(self):
        # Validate canonical invariants
        if self.kind == ActionKindV1.NOOP:
            if self.target_cell is not None:
                raise ValueError("NOOP must have target_cell=None")
            if self.target_value is not None:
                raise ValueError("NOOP must have target_value=None")
        elif self.kind == ActionKindV1.EDIT:
            if self.target_cell is None:
                raise ValueError("EDIT must have target_cell set")
            if self.target_value is None:
                raise ValueError("EDIT must have target_value set")
            if not (0 <= self.target_cell <= 80):
                raise ValueError(f"EDIT target_cell={self.target_cell} out of [0,80]")
            if not (0 <= self.target_value <= 9):
                raise ValueError(f"EDIT target_value={self.target_value} out of [0,9]")
        else:
            raise ValueError(f"Unknown action kind: {self.kind}")

    def to_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "target_cell": self.target_cell,
            "target_value": self.target_value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Grid81ActionV1:
        kind_str = d.get("kind", d.get("action"))
        if kind_str not in ("noop", "edit"):
            raise ValueError(f"Invalid action kind: {kind_str}")
        kind = ActionKindV1(kind_str)
        target_cell = d.get("target_cell")
        target_value = d.get("target_value")
        return cls(kind=kind, target_cell=target_cell, target_value=target_value)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), sort_keys=True)


def make_noop() -> Grid81ActionV1:
    return Grid81ActionV1(kind=ActionKindV1.NOOP, target_cell=None, target_value=None)


def make_edit(target_cell: int, target_value: int) -> Grid81ActionV1:
    return Grid81ActionV1(kind=ActionKindV1.EDIT, target_cell=target_cell, target_value=target_value)
