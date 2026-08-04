"""D4PairOrbitV1 — orbit compiler (G4.0B Phase 8).

For pair x:
  orbit(x) = { transform_pair(x, element) for element in D4 }

Canonicalization:
  1. serialize all 8 transformed pairs canonically
  2. sort canonical byte strings lexicographically
  3. choose minimum as canonical representative
  4. deduplicate identical members
  5. compute member digests
  6. compute pair_orbit_digest

Require: orbit_size * stabilizer_size == 8
"""

from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from elpis_grid81_semantics.d4 import D4, D4_ELEMENTS, transform_pair
from elpis_grid81_semantics.canonical import canonical_bytes, canonical_digest


@dataclass(frozen=True)
class D4OrbitMemberV1:
    """A single member of a D4 orbit."""
    d4_element_name: str
    canonical_digest: str
    canonical_bytes_hex: str


@dataclass(frozen=True)
class D4PairOrbitV1:
    """Canonical orbit identity for a pair under D4."""
    canonical_representative: dict
    canonical_representative_bytes_hex: str
    members: list[D4OrbitMemberV1]
    unique_member_digests: list[str]
    orbit_size: int
    stabilizer_size: int
    pair_orbit_digest: str
    schema_id: str
    schema_version: str
    registry_digest: str


def compute_orbit(
    pair_dict: dict[str, Any],
    schema_id: str = "elpis.d4_pair_payload.v1",
    schema_version: str = "1.0",
    registry_digest: str = "grid81.structural.v1:1.0",
) -> D4PairOrbitV1:
    """Compute the full D4 orbit for a pair."""
    # Step 1: generate all 8 transformed pairs
    transformed = []
    for elem in D4_ELEMENTS:
        tp = transform_pair(pair_dict, elem)
        transformed.append((elem, tp))

    # Step 2: serialize all canonically
    canonical_list = []
    for elem, tp in transformed:
        cb = canonical_bytes(tp)
        cd = hashlib.sha256(cb).hexdigest()
        canonical_list.append((elem.name, cd, cb, tp))

    # Step 3: sort by canonical bytes lexicographically, pick minimum
    sorted_by_bytes = sorted(canonical_list, key=lambda x: x[2])
    canonical_rep_bytes = sorted_by_bytes[0][2]
    canonical_rep_dict = sorted_by_bytes[0][3]

    # Step 4: deduplicate
    seen_digests: dict[str, str] = {}  # digest -> element_name
    for elem_name, cd, cb, tp in canonical_list:
        if cd not in seen_digests:
            seen_digests[cd] = elem_name

    unique_digests = sorted(seen_digests.keys())

    # Build members
    members = []
    for elem_name, cd, cb, tp in canonical_list:
        members.append(D4OrbitMemberV1(
            d4_element_name=elem_name,
            canonical_digest=cd,
            canonical_bytes_hex=cb.hex(),
        ))

    # Step 5: orbit and stabilizer sizes
    orbit_size = len(unique_digests)
    stabilizer_size = 8 // orbit_size

    # Step 6: pair_orbit_digest
    combined = f"{schema_id}:{schema_version}:{registry_digest}:".encode("utf-8") + canonical_rep_bytes
    pair_orbit_digest = hashlib.sha256(combined).hexdigest()

    return D4PairOrbitV1(
        canonical_representative=canonical_rep_dict,
        canonical_representative_bytes_hex=canonical_rep_bytes.hex(),
        members=members,
        unique_member_digests=unique_digests,
        orbit_size=orbit_size,
        stabilizer_size=stabilizer_size,
        pair_orbit_digest=pair_orbit_digest,
        schema_id=schema_id,
        schema_version=schema_version,
        registry_digest=registry_digest,
    )
