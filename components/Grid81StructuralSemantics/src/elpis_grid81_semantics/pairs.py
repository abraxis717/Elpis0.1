"""D4PairPayloadV1 — canonical pair representation (G4.0B Phase 7).

Per G4.0A spec, the pair binds exactly:
  grid81: tuple[int, 81], domain 0..9
  writable_mask81: tuple[int, 81], domain {0,1}
  action: {'kind': 'noop'|'edit', 'target_cell': int|None, 'target_value': int|None}
  schema_id, schema_version

Validation:
  grid81 length = 81, tokens valid (0..9)
  mask length = 81, tokens in {0,1}
  action canonical (see actions.py)
  EDIT target within writable scope
  NOOP invariant under all transforms
  target_value unchanged by D4, target_cell transformed by D4
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from elpis_grid81_semantics.canonical import SCHEMA_ID, SCHEMA_VERSION
from elpis_grid81_semantics.actions import Grid81ActionV1, ActionKindV1


@dataclass(frozen=True)
class D4PairPayloadV1:
    grid81: tuple[int, ...]
    writable_mask81: tuple[int, ...]
    action: Grid81ActionV1
    schema_id: str
    schema_version: str

    def __post_init__(self):
        # Validate grid81
        if len(self.grid81) != 81:
            raise ValueError(f"grid81 length={len(self.grid81)}, expected 81")
        for i, v in enumerate(self.grid81):
            if not (0 <= v <= 9):
                raise ValueError(f"grid81[{i}]={v} out of [0,9]")

        # Validate mask
        if len(self.writable_mask81) != 81:
            raise ValueError(f"writable_mask81 length={len(self.writable_mask81)}, expected 81")
        for i, v in enumerate(self.writable_mask81):
            if v not in (0, 1):
                raise ValueError(f"writable_mask81[{i}]={v} not in {{0,1}}")

        # Validate action canonical consistency
        if self.action.kind == ActionKindV1.EDIT:
            cell = self.action.target_cell
            if cell is not None and self.writable_mask81[cell] == 0:
                raise ValueError(f"EDIT targets non-writable cell {cell}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "grid81": list(self.grid81),
            "writable_mask81": list(self.writable_mask81),
            "action": self.action.to_dict(),
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> D4PairPayloadV1:
        return cls(
            grid81=tuple(d["grid81"]),
            writable_mask81=tuple(d["writable_mask81"]),
            action=Grid81ActionV1.from_dict(d["action"]),
            schema_id=d.get("schema_id", SCHEMA_ID),
            schema_version=d.get("schema_version", SCHEMA_VERSION),
        )

    @classmethod
    def from_corpus_row(cls, row: dict[str, Any]) -> D4PairPayloadV1:
        """Construct from a T00 corpus row.

        Corpus row has:
          input_grid: list[int] (81)
          input_mask: list[int] (81)
          expansion_targets: list[{'cell': int, ...}]
          rationale_codes: list[str]

        We derive the action from expansion_targets.
        """
        grid81 = tuple(row["input_grid"])
        writable_mask81 = tuple(row["input_mask"])

        expansion = row.get("expansion_targets", [])
        if expansion:
            # EDIT action: first expansion target
            exp = expansion[0]
            cell = exp["cell"]
            # The target value for expansion: we use the grid81 structural token
            # The rationale determines what value gets written
            # For VOID_RESOLUTION -> target_value=0
            # For ACTIVE_EXPANSION -> target_value=6 (EXPANSION token per registry)
            # We need to infer the target value from the rationale
            rationale = row.get("rationale_codes", [])
            target_value = _rationale_to_target_value(rationale, grid81[cell])
            action = Grid81ActionV1(
                kind=ActionKindV1.EDIT,
                target_cell=cell,
                target_value=target_value,
            )
        else:
            # No expansion targets -> NOOP
            action = Grid81ActionV1(
                kind=ActionKindV1.NOOP,
                target_cell=None,
                target_value=None,
            )

        return cls(
            grid81=grid81,
            writable_mask81=writable_mask81,
            action=action,
            schema_id=SCHEMA_ID,
            schema_version=SCHEMA_VERSION,
        )


def _rationale_to_target_value(rationale_codes: list[str], current_value: int) -> int:
    """Determine target_value from rationale codes.

    Per corpus semantics:
      VOID_RESOLUTION -> write 0 (resolve void)
      ACTIVE_EXPANSION -> write 6 (EXPANSION token)
      If current value already matches desired, the edit is no-op in effect
      but the action is still EDIT per corpus encoding.
    """
    for code in rationale_codes:
        if code == "VOID_RESOLUTION":
            return 0
        if code == "ACTIVE_EXPANSION":
            return 6
    # Default: the expansion target resolves to void (0)
    return 0
