# elpis/contracts/routing.py — §VII route law.
# Unknown routes NEVER silently become DEFAULT: they become RouteFamily.UNKNOWN
# with the raw string and provenance preserved, and governance sees the reason.
# Route is control state: NOT identity-bearing; may change only at PROPOSAL or
# GOVERNANCE phases (enforced by phases.validate_route_change).
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class RouteFamily(str, Enum):
    STRUCTURAL = "structural"; CODE = "code"; SQL = "sql"
    VALIDATION = "validation"; MEMORY = "memory"; EXTERNAL = "external"
    DEFAULT = "default"; UNKNOWN = "unknown"


class RouteProvenance(str, Enum):
    DECLARED = "declared"; INFERRED = "inferred"
    LEGACY_MAPPED = "legacy_mapped"; UNKNOWN_INPUT = "unknown_input"


@dataclass(frozen=True, slots=True)
class Route:
    family: RouteFamily
    raw: str
    provenance: RouteProvenance
    forced: bool = False


# Census-filled LEGACY_ROUTE_MAP (A0 E2 + live source verification).
# Bridge_Route (elpis.bridge.packet.Route): GENERAL=0, LOGIC=1, SQL=2, CODE=3, GRAPH=4
# Spine_RoutingHint (elpis.spine.latent_packet.RoutingHint): PASS_THROUGH=0,
#   ORTHOGONALIZE=1, DECOMPOSE=2, DECODE_DIRECT=3
# ABI_Routing (elpis.abi.latent_packet.Routing): GENERAL, LOGIC, SQL, CODE, GRAPH, SELF
# HTR_RoutingClass (elpis.htr.contracts.RoutingClass): DEFAULT, CODE, SQL, STRUCTURAL,
#   VALIDATION, MEMORY, EXTERNAL
LEGACY_ROUTE_MAP: dict[str, RouteFamily] = {
    # --- HTR RoutingClass values (elpis.htr.contracts) ---
    "default": RouteFamily.DEFAULT,
    "code": RouteFamily.CODE,
    "sql": RouteFamily.SQL,
    "structural": RouteFamily.STRUCTURAL,
    "validation": RouteFamily.VALIDATION,
    "memory": RouteFamily.MEMORY,
    "external": RouteFamily.EXTERNAL,
    # --- Bridge Route values (elpis.bridge.packet) ---
    "general": RouteFamily.DEFAULT,
    "logic": RouteFamily.STRUCTURAL,
    "graph": RouteFamily.STRUCTURAL,
    # --- ABI Routing values (elpis.abi.latent_packet) ---
    "self": RouteFamily.MEMORY,
    # --- Spine RoutingHint names (elpis.spine.latent_packet.RoutingHint) ---
    "pass_through": RouteFamily.DEFAULT,
    "orthogonalize": RouteFamily.STRUCTURAL,
    "decompose": RouteFamily.STRUCTURAL,
    "decode_direct": RouteFamily.STRUCTURAL,
    # --- Topology/grid domain strings ---
    "grid": RouteFamily.STRUCTURAL,
    "python": RouteFamily.CODE,
}


def parse_route(raw: str, *, forced: bool = False) -> Route:
    key = (raw or "").strip().lower()
    if key in LEGACY_ROUTE_MAP:
        fam = LEGACY_ROUTE_MAP[key]
        prov = (RouteProvenance.DECLARED if key == fam.value
                else RouteProvenance.LEGACY_MAPPED)
        return Route(fam, raw, prov, forced)
    return Route(RouteFamily.UNKNOWN, raw, RouteProvenance.UNKNOWN_INPUT, forced)
