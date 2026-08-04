"""Typed orbit identities for D4 symmetry classes.

Each view type has its own orbit identity with domain-separated digest.
No generic overloaded pair_orbit_digest is exposed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from elpis_grid81_typed.canonical import canonicalize, domain_digest
from elpis_grid81_typed.d4 import (
    transform_grid81,
    transform_index,
    transform_transition_view,
    transform_expansion_view,
    transform_quiescence_view,
    transform_rationale_view,
    D4_TRANSFORMS,
)
from elpis_grid81_typed.errors import OrbitError


# ---------------------------------------------------------------------------
# Semantic payload extractors
# ---------------------------------------------------------------------------
# These functions strip provenance-bound fields from view dicts and return
# only the semantic content that defines orbit identity.

def _transition_semantic_payload(view):
    return {
        "schema_version": "transition_view.semantic.v1",
        "input_grid": list(view["input_grid"]),
        "input_mask": list(view["input_mask"]),
        "canonical_target_grid": list(
            view["canonical_target_grid"]
        ),
        "delta_kind": view["delta_kind"],
        "target_cell": view["target_cell"],
        "target_value": view["target_value"],
    }


def _expansion_semantic_payload(view):
    return {
        "schema_version": "expansion_view.semantic.v1",
        "input_grid": list(view["input_grid"]),
        "expansion_locus_mask81": list(
            view["expansion_locus_mask81"]
        ),
        "expansion_cells": sorted(
            int(cell) for cell in view["expansion_cells"]
        ),
    }


def _quiescence_semantic_payload(view):
    return {
        "schema_version": "quiescence_view.semantic.v1",
        "input_grid": list(view["input_grid"]),
        "derived_quiescence": bool(
            view["derived_quiescence"]
        ),
    }


def _rationale_semantic_payload(view):
    transition_delta = view["transition_delta"]
    return {
        "schema_version": "rationale_view.semantic.v1",
        "input_grid": list(view["input_grid"]),
        "canonical_target_grid": list(
            view["canonical_target_grid"]
        ),
        "transition_delta": {
            "delta_cells": sorted(
                int(cell) for cell in transition_delta["delta_cells"]
            ),
            "delta_size": int(
                transition_delta["delta_size"]
            ),
        },
        "rationale_codes": list(
            view["rationale_codes"]
        ),
    }


@dataclass(frozen=True)
class TransitionOrbitV1:
    """D4 orbit identity for transition views.

    Fields:
        orbit_digest: Domain-separated SHA-256 of canonical representative.
        orbit_size: Number of unique members after D4 transform + dedup.
        stabilizer_size: Number of D4 elements that fix the canonical form.
        canonical_representative: Lexicographically minimum canonical bytes.
    """
    orbit_digest: str
    orbit_size: int
    stabilizer_size: int
    canonical_representative: str

    @classmethod
    def compute(cls, transition_view: Dict[str, Any]) -> "TransitionOrbitV1":
        """Compute transition orbit from a compiled transition view.

        Algorithm:
            1. Generate 8 D4-transformed members
            2. Canonicalize each member to bytes
            3. Deduplicate symmetric members
            4. Select lexicographic minimum as canonical representative
            5. Compute domain-separated orbit digest
            6. Record orbit_size and stabilizer_size
            7. Require orbit_size * stabilizer_size = 8
        """
        orbit_members: List[bytes] = []

        for t_idx in range(8):
            transformed = transform_transition_view(t_idx, transition_view)
            member_bytes = canonicalize(
                _transition_semantic_payload(transformed)
            )
            orbit_members.append(member_bytes)

        # Deduplicate
        unique_members = sorted(set(orbit_members))
        canonical_rep = unique_members[0]  # lexicographic minimum
        orbit_size = len(unique_members)
        stabilizer_size = 8 // orbit_size

        if orbit_size * stabilizer_size != 8:
            raise OrbitError(
                f"Orbit law violated: orbit_size={orbit_size} * stabilizer_size={stabilizer_size} != 8"
            )

        # Compute domain-separated orbit digest
        registry_digest = domain_digest("d4_registry", canonicalize(D4_TRANSFORMS))
        orbit_payload = canonicalize({
            "schema_version": "transition_orbit.v1",
            "canonical_representative": canonical_rep.hex(),
            "orbit_size": orbit_size,
            "stabilizer_size": stabilizer_size,
        })
        orbit_digest = domain_digest("transition_orbit", orbit_payload)

        return cls(
            orbit_digest=orbit_digest,
            orbit_size=orbit_size,
            stabilizer_size=stabilizer_size,
            canonical_representative=canonical_rep.hex(),
        )


@dataclass(frozen=True)
class ExpansionOrbitV1:
    """D4 orbit identity for expansion views."""
    orbit_digest: str
    orbit_size: int
    stabilizer_size: int
    canonical_representative: str

    @classmethod
    def compute(cls, expansion_view: Dict[str, Any]) -> "ExpansionOrbitV1":
        """Compute expansion orbit from a compiled expansion view."""
        orbit_members: List[bytes] = []

        for t_idx in range(8):
            transformed = transform_expansion_view(t_idx, expansion_view)
            member_bytes = canonicalize(
                _expansion_semantic_payload(transformed)
            )
            orbit_members.append(member_bytes)

        unique_members = sorted(set(orbit_members))
        canonical_rep = unique_members[0]
        orbit_size = len(unique_members)
        stabilizer_size = 8 // orbit_size

        if orbit_size * stabilizer_size != 8:
            raise OrbitError(
                f"Expansion orbit law violated: {orbit_size} * {stabilizer_size} != 8"
            )

        orbit_payload = canonicalize({
            "schema_version": "expansion_orbit.v1",
            "canonical_representative": canonical_rep.hex(),
            "orbit_size": orbit_size,
            "stabilizer_size": stabilizer_size,
        })
        orbit_digest = domain_digest("expansion_orbit", orbit_payload)

        return cls(
            orbit_digest=orbit_digest,
            orbit_size=orbit_size,
            stabilizer_size=stabilizer_size,
            canonical_representative=canonical_rep.hex(),
        )


@dataclass(frozen=True)
class QuiescenceOrbitV1:
    """D4 orbit identity for quiescence views."""
    orbit_digest: str
    orbit_size: int
    stabilizer_size: int
    canonical_representative: str

    @classmethod
    def compute(cls, quiescence_view: Dict[str, Any]) -> "QuiescenceOrbitV1":
        """Compute quiescence orbit from a compiled quiescence view."""
        orbit_members: List[bytes] = []

        for t_idx in range(8):
            transformed = transform_quiescence_view(t_idx, quiescence_view)
            member_bytes = canonicalize(
                _quiescence_semantic_payload(transformed)
            )
            orbit_members.append(member_bytes)

        unique_members = sorted(set(orbit_members))
        canonical_rep = unique_members[0]
        orbit_size = len(unique_members)
        stabilizer_size = 8 // orbit_size

        if orbit_size * stabilizer_size != 8:
            raise OrbitError(
                f"Quiescence orbit law violated: {orbit_size} * {stabilizer_size} != 8"
            )

        orbit_payload = canonicalize({
            "schema_version": "quiescence_orbit.v1",
            "canonical_representative": canonical_rep.hex(),
            "orbit_size": orbit_size,
            "stabilizer_size": stabilizer_size,
        })
        orbit_digest = domain_digest("quiescence_orbit", orbit_payload)

        return cls(
            orbit_digest=orbit_digest,
            orbit_size=orbit_size,
            stabilizer_size=stabilizer_size,
            canonical_representative=canonical_rep.hex(),
        )


@dataclass(frozen=True)
class RationaleOrbitV1:
    """D4 orbit identity for rationale views.

    Inherits transition orbit spatial identity per G4.0A.3 Typed Orbit Contracts.
    Rationale codes are D4-invariant symbolic metadata.
    """
    orbit_digest: str
    orbit_size: int
    stabilizer_size: int
    canonical_representative: str

    @classmethod
    def compute(cls, rationale_view: Dict[str, Any]) -> "RationaleOrbitV1":
        """Compute rationale orbit from a compiled rationale view.

        Inherits transition spatial identity: rationale orbit groups by
        the transition orbit's canonical representative, with rationale
        codes as invariant metadata appended to the domain digest.
        """
        orbit_members: List[bytes] = []

        for t_idx in range(8):
            transformed = transform_rationale_view(t_idx, rationale_view)
            member_bytes = canonicalize(
                _rationale_semantic_payload(transformed)
            )
            orbit_members.append(member_bytes)

        unique_members = sorted(set(orbit_members))
        canonical_rep = unique_members[0]
        orbit_size = len(unique_members)
        stabilizer_size = 8 // orbit_size

        if orbit_size * stabilizer_size != 8:
            raise OrbitError(
                f"Rationale orbit law violated: {orbit_size} * {stabilizer_size} != 8"
            )

        orbit_payload = canonicalize({
            "schema_version": "rationale_orbit.v1",
            "canonical_representative": canonical_rep.hex(),
            "orbit_size": orbit_size,
            "stabilizer_size": stabilizer_size,
        })
        orbit_digest = domain_digest("rationale_orbit", orbit_payload)

        return cls(
            orbit_digest=orbit_digest,
            orbit_size=orbit_size,
            stabilizer_size=stabilizer_size,
            canonical_representative=canonical_rep.hex(),
        )
