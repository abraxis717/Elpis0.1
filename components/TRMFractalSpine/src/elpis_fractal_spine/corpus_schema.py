"""
GATE 10 — Corpus schema for T0.0 structural TRM training data.

Defines CorpusCase, CorpusManifest, SplitManifest with deterministic
serialization. No PyTorch, no model loading, no wall clocks.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .structural_semantics import (
    ABI_VERSION,
    GRID_SIZE,
    SEMANTIC_SPACE,
)

# ---------------------------------------------------------------------------
# Corpus case (GATE 10)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorpusCase:
    """
    A single training/evaluation case.

    Fields:
    - case_id: unique identifier
    - generator_version: version string of generator that produced this
    - generator_seed: deterministic seed used
    - template_family: structural template family for split isolation
    - stratum: stratum label
    - input_grid: list of 81 integers (structural tokens)
    - input_mask: list of 81 integers (0 or 1)
    - input_depth: recursion depth
    - semantic_space: semantic-space ID
    - abi_version: ABI version
    - valid_target_digests: list of SHA-256 digests of all valid targets
    - canonical_target_digest: SHA-256 digest of canonical target
    - expansion_targets: list of (cell, rationale_code) tuples
    - quiescence_target: boolean
    - violation_codes: list of strings
    - rationale_codes: list of strings
    - symmetry_family: symmetry family label
    - provenance_digest: SHA-256 digest of parent provenance
    - case_digest: SHA-256 digest of the entire case
    """

    case_id: str
    generator_version: str
    generator_seed: int
    template_family: str
    stratum: str
    input_grid: Tuple[int, ...]
    input_mask: Tuple[int, ...]
    input_depth: int
    semantic_space: str
    abi_version: str
    valid_target_digests: Tuple[str, ...]
    canonical_target_digest: str
    expansion_targets: Tuple[Tuple[int, str], ...]
    quiescence_target: bool
    violation_codes: Tuple[str, ...]
    rationale_codes: Tuple[str, ...]
    symmetry_family: str
    provenance_digest: str
    case_digest: str

    def __post_init__(self):
        if len(self.input_grid) != GRID_SIZE:
            raise ValueError(
                f"input_grid length {len(self.input_grid)} != {GRID_SIZE}"
            )
        if len(self.input_mask) != GRID_SIZE:
            raise ValueError(
                f"input_mask length {len(self.input_mask)} != {GRID_SIZE}"
            )
        if self.semantic_space != SEMANTIC_SPACE:
            raise ValueError(
                f"semantic_space '{self.semantic_space}' != '{SEMANTIC_SPACE}'"
            )

    def to_dict(self) -> dict:
        """Serialize to dict for JSON output."""
        return {
            "abi_version": self.abi_version,
            "canonical_target_digest": self.canonical_target_digest,
            "case_digest": self.case_digest,
            "case_id": self.case_id,
            "expansion_targets": [
                {"cell": c, "rationale_code": r}
                for c, r in self.expansion_targets
            ],
            "generator_seed": self.generator_seed,
            "generator_version": self.generator_version,
            "input_depth": self.input_depth,
            "input_grid": list(self.input_grid),
            "input_mask": list(self.input_mask),
            "provenance_digest": self.provenance_digest,
            "quiescence_target": self.quiescence_target,
            "rationale_codes": list(self.rationale_codes),
            "semantic_space": self.semantic_space,
            "stratum": self.stratum,
            "symmetry_family": self.symmetry_family,
            "template_family": self.template_family,
            "valid_target_digests": sorted(list(self.valid_target_digests)),
            "violation_codes": list(self.violation_codes),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CorpusCase":
        """Deserialize from dict."""
        expansion_targets = tuple(
            (et["cell"], et["rationale_code"])
            for et in d["expansion_targets"]
        )
        return cls(
            case_id=d["case_id"],
            generator_version=d["generator_version"],
            generator_seed=d["generator_seed"],
            template_family=d["template_family"],
            stratum=d["stratum"],
            input_grid=tuple(d["input_grid"]),
            input_mask=tuple(d["input_mask"]),
            input_depth=d["input_depth"],
            semantic_space=d["semantic_space"],
            abi_version=d["abi_version"],
            valid_target_digests=tuple(sorted(d["valid_target_digests"])),
            canonical_target_digest=d["canonical_target_digest"],
            expansion_targets=expansion_targets,
            quiescence_target=d["quiescence_target"],
            violation_codes=tuple(d["violation_codes"]),
            rationale_codes=tuple(d["rationale_codes"]),
            symmetry_family=d["symmetry_family"],
            provenance_digest=d["provenance_digest"],
            case_digest=d["case_digest"],
        )


@dataclass(frozen=True)
class CorpusManifest:
    """
    Manifest describing the full corpus.
    """

    corpus_id: str
    generator_version: str
    total_cases: int
    strata: Dict[str, int]
    splits: Dict[str, int]
    checksum: str

    def to_dict(self) -> dict:
        return {
            "checksum": self.checksum,
            "corpus_id": self.corpus_id,
            "generator_version": self.generator_version,
            "splits": dict(sorted(self.splits.items())),
            "strata": dict(sorted(self.strata.items())),
            "total_cases": self.total_cases,
        }


@dataclass(frozen=True)
class SplitManifest:
    """
    Manifest for a single split (train/validation/test).
    """

    split_name: str
    case_ids: Tuple[str, ...]
    template_families: Tuple[str, ...]
    strata: Dict[str, int]
    checksum: str

    def to_dict(self) -> dict:
        return {
            "case_ids": sorted(list(self.case_ids)),
            "checksum": self.checksum,
            "split_name": self.split_name,
            "strata": dict(sorted(self.strata.items())),
            "template_families": sorted(list(self.template_families)),
        }


# ---------------------------------------------------------------------------
# Corpus serialization (GATE 12)
# ---------------------------------------------------------------------------


class CorpusSerializer:
    """
    Deterministic corpus serializer.

    Produces canonical JSON with sorted keys, no timestamps, no NaN/Inf.
    """

    @staticmethod
    def serialize_case(case: CorpusCase) -> str:
        """Serialize a single case to a JSON line."""
        d = case.to_dict()
        return json.dumps(d, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def deserialize_case(line: str) -> CorpusCase:
        """Deserialize a JSON line to a CorpusCase."""
        d = json.loads(line)
        return CorpusCase.from_dict(d)

    @staticmethod
    def serialize_manifest(manifest: CorpusManifest) -> str:
        """Serialize manifest to JSON."""
        return json.dumps(manifest.to_dict(), sort_keys=True, indent=2)

    @staticmethod
    def serialize_split_manifest(manifest: SplitManifest) -> str:
        """Serialize split manifest to JSON."""
        return json.dumps(manifest.to_dict(), sort_keys=True, indent=2)

    @staticmethod
    def compute_checksum(data: str) -> str:
        """Compute SHA-256 checksum of data."""
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def canonicalize_negative_zero(obj):
        """Recursively canonicalize -0.0 to 0.0 in nested structures."""
        if isinstance(obj, float):
            return 0.0 if obj == 0.0 else obj
        if isinstance(obj, dict):
            return {k: CorpusSerializer.canonicalize_negative_zero(v)
                    for k, v in obj.items()}
        if isinstance(obj, list):
            return [CorpusSerializer.canonicalize_negative_zero(v)
                    for v in obj]
        return obj
