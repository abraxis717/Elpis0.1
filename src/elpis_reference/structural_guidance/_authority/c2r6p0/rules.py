"""Centralized rule identifiers and the pinned ruleset for C2R6-P0.

Every deterministic decision the projector makes cites one of these rule
identifiers in its trace event. The ruleset digest binds the exact pinned
authority versions so that a change of authority is detectable.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

FROZEN_STRUCTURAL_RESIDUAL_SHA256 = "de6fa20b2cdfd2f80419b943c0245094d5975c8d835acf413b46e51284f1fec8"
FROZEN_STRUCTURAL_TRM_FEATURES_SHA256 = "d1dec9488c7eca67008b14b7e9d6fb620c48965f417f8a30c5486b5d5df427b2"
FROZEN_P0_CONTRACTS_SHA256 = "face8a09f0ad76a0e34cd4544a805302502ebb70ff8b7517934521d85ed8266a"
FROZEN_P0_SEMANTIC_IR_SHA256 = "d4c44e586c7869ff1ab8621e0f0ddd638784951f2583b847b75efc07f788f519"


def _sha(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


@dataclass(frozen=True)
class Ruleset:
    """Pinned structural rules (authoritative constants + rule ids).

    The constants are re-exposed from the frozen C2R7-C structural_residual
    module; the projector must not redefine them.
    """

    grid_size: int
    lanes: int
    ranks: int
    control_lane: int
    terminal_cell: int
    max_semantic_lanes: int
    # structural authority version pins (SHA-256 of pinned files)
    structural_residual_sha: str
    features_sha: str
    contracts_sha: str
    semantic_ir_sha: str
    vocabulary_digest: str
    feature_width: int

    def digest(self) -> str:
        payload = {
            "grid_size": self.grid_size,
            "lanes": self.lanes,
            "ranks": self.ranks,
            "control_lane": self.control_lane,
            "terminal_cell": self.terminal_cell,
            "max_semantic_lanes": self.max_semantic_lanes,
            "structural_residual_sha": self.structural_residual_sha,
            "features_sha": self.features_sha,
            "contracts_sha": self.contracts_sha,
            "semantic_ir_sha": self.semantic_ir_sha,
            "vocabulary_digest": self.vocabulary_digest,
            "feature_width": self.feature_width,
            "ruleset_version": "c2r6p0.ruleset.v1",
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


def load_ruleset() -> Ruleset:
    """Build the pinned ruleset from the frozen authority sources."""
    from ..elpis_p0 import structural_residual as SR
    from ..c2r7c import structural_trm_features as F

    return Ruleset(
        grid_size=SR.GRID_SIZE,
        lanes=SR.LANES,
        ranks=SR.RANKS,
        control_lane=SR.CONTROL_LANE,
        terminal_cell=SR.TERMINAL_CELL,
        max_semantic_lanes=SR.MAX_SEMANTIC_LANES,
        structural_residual_sha=FROZEN_STRUCTURAL_RESIDUAL_SHA256,
        features_sha=FROZEN_STRUCTURAL_TRM_FEATURES_SHA256,
        contracts_sha=FROZEN_P0_CONTRACTS_SHA256,
        semantic_ir_sha=FROZEN_P0_SEMANTIC_IR_SHA256,
        vocabulary_digest=F.VOCABULARY_DIGEST,
        feature_width=F.FEATURE_WIDTH,
    )


# ---------------------------------------------------------------------------
# Rule identifiers (centralized; cited by trace events)
# ---------------------------------------------------------------------------

R_INPUT_ACCEPT = "R1.INPUT_ACCEPT"
R_ENTITY_ACCEPT = "R2.ENTITY_ACCEPT"
R_CONTRACT_ACCEPT = "R3.CONTRACT_ACCEPT"
R_DANGLING_REF = "R3.DANGLING_REFERENCE"
R_DUPLICATE_ID = "R3.DUPLICATE_IDENTITY"
R_UNSUPPORTED_KIND = "R4.UNSUPPORTED_KIND"
R_CONTRADICTORY_TYPES = "R4.CONTRADICTORY_TYPES"
R_AMBIGUOUS_INTERFACE = "R4.AMBIGUOUS_INTERFACE"
R_ARITY_VIOLATION = "R4.ARITY_VIOLATION"
R_DAG_TOPO = "R5.TOPOLOGICAL_ORDER"
R_CYCLE_REJECT = "R5.ILLEGAL_CYCLE"
R_COMPONENTS = "R5.COMPONENTS"
R_MULTI_ROOT_INFO = "R5.MULTIPLE_ROOTS"
R_MULTI_OUTPUT_INFO = "R5.MULTIPLE_OUTPUTS"
R_LANE_ALLOC = "R6.LANE_ALLOCATION"
R_LANE_ORDER = "R6.LANE_TOPOTOMIC_KEY"
R_LANE_COLLISION = "R6.LANE_COLLISION"
R_LANE_OVERFLOW = "R6.LANE_OVERFLOW"
R_RANK_ASSIGN = "R7.RANK_ASSIGNMENT"
R_RANK_OVERFLOW = "R7.RANK_OVERFLOW"
R_ROLE_TOKEN = "R8.ROLE_TOKEN"
R_ROUTE_PLACE = "R9.ROUTE_PLACEMENT"
R_ROUTE_DANGLING = "R9.ROUTE_DANGLING_ENDPOINT"
R_ROUTE_RANK = "R9.ROUTE_RANK"
R_MEMORY_PLACE = "R10.MEMORY_SPAN"
R_MEMORY_RANK = "R10.MEMORY_RANK"
R_CONSTRAINT_PLACE = "R11.CONSTRAINT_AFTER"
R_CONSTRAINT_RANK = "R11.CONSTRAINT_RANK"
R_CONSTRAINT_CONTRA = "R11.CONTRADICTORY_CONSTRAINTS"
R_INTERFACE_PLACE = "R12.INTERFACE_TERMINAL"
R_INTERFACE_RANK = "R12.INTERFACE_RANK"
R_TERMINAL_PLACE = "R13.TERMINAL_RESOLUTION"
R_FROZEN = "R14.FROZEN_FACT"
R_WRITABLE = "R14.WRITABLE_UNRESOLVED"
R_UNRESOLVED = "R14.UNRESOLVED_LOCUS"
R_MASK_DISJOINT = "R14.MASK_DISJOINT"
R_CAP_LANES = "R15.CAPACITY_LANES"
R_CAP_RANKS = "R15.CAPACITY_RANKS"
R_CAP_LOCI = "R15.CAPACITY_LOCI"
R_RESIDUAL_DERIVE = "R16.RESIDUAL_DERIVATION"
R_FEATURE_DERIVE = "R16.FEATURE_DERIVATION"
R_FINGERPRINT = "R17.STRUCTURAL_FINGERPRINT"
R_CANONICAL = "R0.CANONICALIZATION"
R_SIDEcar = "R18.SEMANTIC_SIDECAR"
R_SKELON = "R19.SKELETON_EXTRACTION"
R_DECOMPOSITION_REQUIRED_TRACE = "R15.DECOMPOSITION_TRACE"

RULE_IDS = frozenset(
    {
        R_INPUT_ACCEPT, R_ENTITY_ACCEPT, R_CONTRACT_ACCEPT, R_DANGLING_REF,
        R_DUPLICATE_ID, R_UNSUPPORTED_KIND, R_CONTRADICTORY_TYPES,
        R_AMBIGUOUS_INTERFACE, R_ARITY_VIOLATION, R_DAG_TOPO, R_CYCLE_REJECT,
        R_COMPONENTS, R_MULTI_ROOT_INFO, R_MULTI_OUTPUT_INFO, R_LANE_ALLOC,
        R_LANE_ORDER, R_LANE_COLLISION, R_LANE_OVERFLOW, R_RANK_ASSIGN,
        R_RANK_OVERFLOW, R_ROLE_TOKEN, R_ROUTE_PLACE, R_ROUTE_DANGLING,
        R_ROUTE_RANK, R_MEMORY_PLACE, R_MEMORY_RANK, R_CONSTRAINT_PLACE,
        R_CONSTRAINT_RANK, R_CONSTRAINT_CONTRA, R_INTERFACE_PLACE,
        R_INTERFACE_RANK, R_TERMINAL_PLACE, R_FROZEN, R_WRITABLE,
        R_UNRESOLVED, R_MASK_DISJOINT, R_CAP_LANES, R_CAP_RANKS, R_CAP_LOCI,
        R_RESIDUAL_DERIVE, R_FEATURE_DERIVE, R_FINGERPRINT, R_CANONICAL,
        R_SIDEcar, R_SKELON, R_DECOMPOSITION_REQUIRED_TRACE,
    }
)
