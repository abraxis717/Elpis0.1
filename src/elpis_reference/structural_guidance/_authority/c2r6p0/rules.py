"""Centralized rule identifiers and the pinned ruleset for C2R6-P0.

Every deterministic decision the projector makes cites one of these rule
identifiers in its trace event. The ruleset digest binds the exact pinned
authority versions so that a change of authority is detectable.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

FROZEN_STRUCTURAL_RESIDUAL_SHA256 = "d517be0041cf61dafe7813bd4b443982723288b43e7ab30f69c8075459c9b5ca"
FROZEN_STRUCTURAL_TRM_FEATURES_SHA256 = "d1dec9488c7eca67008b14b7e9d6fb620c48965f417f8a30c5486b5d5df427b2"
FROZEN_P0_CONTRACTS_SHA256 = "8f0d7e14774d02ea068833bb4fa91eee43c14b1733371edac52a7cba019005a1"
FROZEN_P0_SEMANTIC_IR_SHA256 = "d4c44e586c7869ff1ab8621e0f0ddd638784951f2583b847b75efc07f788f519"


def _sha(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class FrozenAuthorityError(RuntimeError):
    """An imported authority source cannot be verified against its frozen pin."""


def _verify_authority(module: ModuleType, expected: str) -> None:
    path = inspect.getsourcefile(module)
    if path is None:
        raise FrozenAuthorityError(f"frozen authority source unavailable: {module.__name__}")
    try:
        actual = _sha(path)
    except OSError as exc:
        raise FrozenAuthorityError(
            f"frozen authority source unreadable: {module.__name__} ({path})"
        ) from exc
    if actual != expected:
        raise FrozenAuthorityError(
            f"frozen authority SHA-256 mismatch: {module.__name__} ({path}); "
            f"expected={expected}; actual={actual}"
        )


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


DEFAULT_NODE_BUDGET = 84
MAX_NODE_BUDGET = 4096


@dataclass(frozen=True)
class BudgetedRulesetV2(Ruleset):
    """Operational search bound; it is not a completeness theorem."""
    node_budget: int = DEFAULT_NODE_BUDGET

    def __post_init__(self):
        if type(self.node_budget) is not int or not 1 <= self.node_budget <= MAX_NODE_BUDGET:
            raise ValueError(f"node_budget must be an integer in [1, {MAX_NODE_BUDGET}]")

    def digest(self) -> str:
        from dataclasses import asdict
        payload = {**asdict(self), "ruleset_version": "c2r6p0.ruleset.v2"}
        return hashlib.sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()


def load_ruleset() -> BudgetedRulesetV2:
    """Verify imported authority source bytes before building the pinned ruleset."""
    from ..elpis_p0 import structural_residual as SR
    from ..c2r7c import structural_trm_features as F
    from ..elpis_p0 import contracts as C, semantic_ir as IR

    # These are the vendored authorities consumed by the projector/refiner;
    # C supplies BasisToken, not the c2r6p0 projector wrapper contracts.
    for module, expected in (
        (SR, FROZEN_STRUCTURAL_RESIDUAL_SHA256),
        (F, FROZEN_STRUCTURAL_TRM_FEATURES_SHA256),
        (C, FROZEN_P0_CONTRACTS_SHA256),
        (IR, FROZEN_P0_SEMANTIC_IR_SHA256),
    ):
        _verify_authority(module, expected)

    return BudgetedRulesetV2(
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
