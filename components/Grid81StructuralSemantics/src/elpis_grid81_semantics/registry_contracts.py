"""StructuralSymbolRegistryV1 — passive data contract (G4.0B Phase 13).

Binds:
  registry_id, registry_version, structural_regime_id
  symbols: 0=VOID, 1-9=opaque structural terminals/expansion
  primitive group definitions
  symbol-to-group memberships
  orientation behavior
  registry digest, provenance root

0 = unresolved/void
1..9 = registry-relative opaque structural symbols (no universal meanings)
"""

from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class StructuralSymbolRegistryV1:
    registry_id: str
    registry_version: str
    structural_regime_id: str
    symbols: dict[str, dict]
    reserved_symbols: set[int]
    primitive_groups: dict[str, set[int]]
    symbol_to_group: dict[int, list[str]]
    orientation_behavior: str
    registry_digest: str
    provenance_root: str

    def __post_init__(self):
        # Validate symbol 0 is void
        if 0 not in self.primitive_groups.get("void_group", set()):
            raise ValueError("Symbol 0 must be in void_group")
        # Validate symbols 1-9 are present
        for s in range(1, 10):
            if s not in self.primitive_groups.get("all_opcodes", set()):
                raise ValueError(f"Symbol {s} must be in all_opcodes")

    def to_dict(self) -> dict:
        return {
            "registry_id": self.registry_id,
            "registry_version": self.registry_version,
            "structural_regime_id": self.structural_regime_id,
            "symbols": self.symbols,
            "primitive_groups": {k: sorted(v) for k, v in self.primitive_groups.items()},
            "symbol_to_group": self.symbol_to_group,
            "orientation_behavior": self.orientation_behavior,
            "registry_digest": self.registry_digest,
            "provenance_root": self.provenance_root,
        }


def default_structural_symbol_registry() -> StructuralSymbolRegistryV1:
    """Create the default G4.0A structural symbol registry."""
    symbols = {
        "0": {"canonical_name": "VOID", "role": "unresolved_placeholder", "reserved": True, "is_void": True},
        "1": {"canonical_name": "TERMINAL_A", "role": "opaque_structural_terminal", "reserved": True, "is_terminal": True},
        "2": {"canonical_name": "TERMINAL_B", "role": "opaque_structural_terminal", "reserved": True, "is_terminal": True},
        "3": {"canonical_name": "TERMINAL_C", "role": "opaque_structural_terminal", "reserved": True, "is_terminal": True},
        "4": {"canonical_name": "TERMINAL_D", "role": "opaque_structural_terminal", "reserved": True, "is_terminal": True},
        "5": {"canonical_name": "TERMINAL_E", "role": "opaque_structural_terminal", "reserved": True, "is_terminal": True},
        "6": {"canonical_name": "EXPANSION", "role": "expansion_bearing", "reserved": True, "is_expansion_bearing": True},
        "7": {"canonical_name": "TERMINAL_F", "role": "opaque_structural_terminal", "reserved": True, "is_terminal": True},
        "8": {"canonical_name": "TERMINAL_G", "role": "opaque_structural_terminal", "reserved": True, "is_terminal": True},
        "9": {"canonical_name": "TERMINAL_H", "role": "opaque_structural_terminal", "reserved": True, "is_terminal": True},
    }
    primitive_groups = {
        "terminal_group": {1, 2, 3, 4, 5, 7, 8, 9},
        "void_group": {0},
        "expansion_group": {6},
        "all_opcodes": {0, 1, 2, 3, 4, 5, 6, 7, 8, 9},
    }
    symbol_to_group = {
        0: ["void_group", "all_opcodes"],
        1: ["terminal_group", "all_opcodes"],
        2: ["terminal_group", "all_opcodes"],
        3: ["terminal_group", "all_opcodes"],
        4: ["terminal_group", "all_opcodes"],
        5: ["terminal_group", "all_opcodes"],
        6: ["expansion_group", "all_opcodes"],
        7: ["terminal_group", "all_opcodes"],
        8: ["terminal_group", "all_opcodes"],
        9: ["terminal_group", "all_opcodes"],
    }
    registry_content = {
        "registry_id": "grid81.structural.v1",
        "symbols": symbols,
        "primitive_groups": {k: sorted(v) for k, v in primitive_groups.items()},
    }
    registry_digest = hashlib.sha256(
        json.dumps(registry_content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return StructuralSymbolRegistryV1(
        registry_id="grid81.structural.v1",
        registry_version="1.0",
        structural_regime_id="grid81.structural.v1",
        symbols=symbols,
        reserved_symbols={0, 1, 2, 3, 4, 5, 6, 7, 8, 9},
        primitive_groups=primitive_groups,
        symbol_to_group=symbol_to_group,
        orientation_behavior="D4 acts on positions, not symbol identities",
        registry_digest=registry_digest,
        provenance_root="g4.0a.spec.v1",
    )
