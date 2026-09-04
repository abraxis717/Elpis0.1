"""Structural residual oracle for bounded ECS component refinement.

This is the primitive C2R7-C is missing. Everything else in the gate is
downstream of it:

  * "resolved" is defined as an empty residual, not as a filled grid;
  * the halt score becomes ``1 - |residual| / |invariants|``;
  * a refiner is anything that reduces the residual using only
    ``(grid81, writable_mask, invariants)``;
  * an ablation is falsified by the residual it fails to clear;
  * training pairs for a learned refiner are ``(G_t, G_t+1, delta_residual)``.

Geometry
--------
``index = rank * 9 + lane``. Rows are execution ranks, columns are lanes.
Lanes 0..7 may be bound to one semantic object each. Lane 8 is the control
lane and is never semantically bound. Cell 80 is the terminal control locus.

Token discipline (BasisToken, unchanged)
----------------------------------------
VOID       settled empty. Quiescent. NOT "unresolved".
EXPANSION  unresolved. The only non-quiescent token.
Every other token is a placed structural fact.

The residual is computed from the integer grid and the invariant set alone.
It never reads a semantic identifier. That is the firewall which keeps a
refiner from becoming a semantic reasoner: a refiner given exactly the inputs
of ``residual`` cannot consult meaning even in principle.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .contracts import BasisToken

GRID_SIZE = 81
LANES = 9
RANKS = 9
CONTROL_LANE = 8
TERMINAL_CELL = 80
MAX_SEMANTIC_LANES = 8

STRUCTURAL_RESIDUAL_SCHEMA = "elpis.p0-structural-schema.c2r7c.v1"
STRUCTURAL_RESIDUAL_DOMAIN = "elpis.p0-structural-schema.c2r7c.v1"

OPERATIONAL_TOKENS = frozenset({
    int(BasisToken.INPUT),
    int(BasisToken.TRANSFORM),
    int(BasisToken.OUTPUT),
})

# Tokens a refiner is permitted to place. Every one of these is materialisable
# without a new semantic identity. INPUT/TRANSFORM/OUTPUT are absent by design:
# operational loci are relocated within their own lane, never created.
PLACEABLE_TOKENS = (
    int(BasisToken.VOID),
    int(BasisToken.MEMORY),
    int(BasisToken.CONSTRAINT),
    int(BasisToken.ROUTE),
    int(BasisToken.INTERFACE),
    int(BasisToken.RESOLUTION),
)

INVARIANT_KINDS = frozenset({
    "LANE_SINGLE_OCCUPANCY",
    "PRECEDES",
    "CROSS_LANE_ROUTE",
    "MEMORY_SPAN",
    "MUTATION_HAZARD",
    "CONSTRAINT_AFTER",
    "INTERFACE_TERMINAL",
    "TERMINAL_RESOLUTION",
})


class StructuralSchemaError(ValueError):
    """A structural schema or grid violates its contract."""


class DecompositionRequired(ValueError):
    """The component does not fit one Grid81. Never truncate; split instead."""

    def __init__(self, lanes: int, ranks: int, loci: int) -> None:
        super().__init__(
            f"component requires lanes={lanes} ranks={ranks} loci={loci}; "
            f"capacity is lanes<={MAX_SEMANTIC_LANES} ranks<={RANKS} "
            f"loci<={GRID_SIZE}"
        )
        self.lanes_required = lanes
        self.ranks_required = ranks
        self.loci_required = loci


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _domain_digest(domain: str, payload: object) -> str:
    return hashlib.sha256(
        domain.encode("utf-8") + b"\x00" + _canonical_bytes(payload)
    ).hexdigest()


def cell(rank: int, lane: int) -> int:
    return rank * LANES + lane


def rank_of(index: int) -> int:
    return index // LANES


def lane_of(index: int) -> int:
    return index % LANES


# ---------------------------------------------------------------- contracts


@dataclass(frozen=True, slots=True)
class LaneBindingV1:
    """Binds one lane to one semantic object. Sidecar; never read by residual."""

    lane: int
    semantic_id: str
    role: str                 # "operation" | "entity"
    operational_token: int    # INPUT / TRANSFORM / OUTPUT, or VOID for entity lanes


@dataclass(frozen=True, slots=True)
class StructuralInvariantV1:
    """A predicate over the integer grid. Lanes are integers, not meanings."""

    invariant_id: str
    kind: str
    lanes: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.kind not in INVARIANT_KINDS:
            raise StructuralSchemaError(f"unknown invariant kind {self.kind!r}")
        for lane in self.lanes:
            if not 0 <= lane < LANES:
                raise StructuralSchemaError(f"lane {lane} outside 0..{LANES - 1}")


@dataclass(frozen=True, slots=True)
class StructuralSchemaV1:
    semantic_request_digest: str
    lanes: tuple[LaneBindingV1, ...]
    writable_mask: tuple[int, ...]
    initial_grid: tuple[int, ...]
    invariants: tuple[StructuralInvariantV1, ...]
    schema_digest: str

    def validate(self) -> None:
        if len(self.writable_mask) != GRID_SIZE:
            raise StructuralSchemaError("writable_mask must be 81 entries")
        if len(self.initial_grid) != GRID_SIZE:
            raise StructuralSchemaError("initial_grid must be 81 entries")
        if any(value not in (0, 1) for value in self.writable_mask):
            raise StructuralSchemaError("writable_mask entries must be 0 or 1")
        if any(not 0 <= value <= 9 for value in self.initial_grid):
            raise StructuralSchemaError("grid tokens must be 0..9")
        if self.writable_mask[TERMINAL_CELL] != 0:
            raise StructuralSchemaError("terminal control cell must be frozen")
        bound = [binding.lane for binding in self.lanes]
        if len(set(bound)) != len(bound):
            raise StructuralSchemaError("duplicate lane binding")
        if any(lane >= MAX_SEMANTIC_LANES for lane in bound):
            raise StructuralSchemaError("lane 8 is the control lane")
        expected = _domain_digest(
            STRUCTURAL_RESIDUAL_DOMAIN, structural_schema_payload(self)
        )
        if expected != self.schema_digest:
            raise StructuralSchemaError("structural schema digest mismatch")

    def bound_lanes(self) -> tuple[int, ...]:
        return tuple(sorted(binding.lane for binding in self.lanes))


def structural_schema_payload(schema: StructuralSchemaV1) -> dict[str, object]:
    return {
        "schema": STRUCTURAL_RESIDUAL_SCHEMA,
        "semantic_request_digest": schema.semantic_request_digest,
        "lanes": [
            {
                "lane": binding.lane,
                "operational_token": binding.operational_token,
                "role": binding.role,
                "semantic_id": binding.semantic_id,
            }
            for binding in sorted(schema.lanes, key=lambda b: b.lane)
        ],
        "writable_mask": list(schema.writable_mask),
        "initial_grid": list(schema.initial_grid),
        "invariants": [
            {
                "invariant_id": inv.invariant_id,
                "kind": inv.kind,
                "lanes": list(inv.lanes),
            }
            for inv in sorted(schema.invariants, key=lambda i: i.invariant_id)
        ],
    }


# ------------------------------------------------------------ the primitive


def _operational_rank(grid: tuple[int, ...], lane: int) -> int | None:
    """Rank of the unique operational locus in a lane, or None if not unique."""
    found = [
        rank for rank in range(RANKS)
        if grid[cell(rank, lane)] in OPERATIONAL_TOKENS
    ]
    return found[0] if len(found) == 1 else None


def _has_token(grid: tuple[int, ...], lane: int, token: int,
               low: int, high: int) -> bool:
    """True if `token` occupies lane at any rank r with low <= r < high."""
    return any(
        grid[cell(rank, lane)] == token
        for rank in range(max(0, low), min(RANKS, high))
    )


def residual(
    grid: tuple[int, ...],
    invariants: tuple[StructuralInvariantV1, ...],
) -> tuple[str, ...]:
    """Return the ids of unsatisfied invariants.

    Reads the integer grid and the invariant set. Nothing else. No semantic
    identifier is in scope, by construction.
    """
    if len(grid) != GRID_SIZE:
        raise StructuralSchemaError("grid must be 81 entries")

    unsatisfied: list[str] = []
    for inv in invariants:
        if not _satisfied(grid, inv):
            unsatisfied.append(inv.invariant_id)
    return tuple(sorted(unsatisfied))


def _satisfied(grid: tuple[int, ...], inv: StructuralInvariantV1) -> bool:
    kind = inv.kind

    if kind == "TERMINAL_RESOLUTION":
        return grid[TERMINAL_CELL] == int(BasisToken.RESOLUTION)

    if kind == "LANE_SINGLE_OCCUPANCY":
        lane = inv.lanes[0]
        return _operational_rank(grid, lane) is not None

    if kind == "PRECEDES":
        a, b = inv.lanes
        ra, rb = _operational_rank(grid, a), _operational_rank(grid, b)
        return ra is not None and rb is not None and ra < rb

    if kind == "CROSS_LANE_ROUTE":
        # A value crossing lanes is realised only by a ROUTE locus placed in
        # the consumer lane strictly between producer and consumer ranks.
        a, b = inv.lanes
        ra, rb = _operational_rank(grid, a), _operational_rank(grid, b)
        if ra is None or rb is None or ra >= rb:
            return False
        return _has_token(grid, b, int(BasisToken.ROUTE), ra + 1, rb)

    if kind == "MEMORY_SPAN":
        # A produced value consumed later must be owned by a MEMORY locus in
        # the producer lane covering [producer, consumer).
        a, b = inv.lanes
        ra, rb = _operational_rank(grid, a), _operational_rank(grid, b)
        if ra is None or rb is None or ra >= rb:
            return False
        return _has_token(grid, a, int(BasisToken.MEMORY), ra + 1, rb)

    if kind == "MUTATION_HAZARD":
        # a produces, b consumes, c mutates. c must not fall between a and b
        # unless a MEMORY snapshot in lane a covers [a, c).
        a, b, c = inv.lanes
        ra = _operational_rank(grid, a)
        rb = _operational_rank(grid, b)
        rc = _operational_rank(grid, c)
        if ra is None or rb is None or rc is None:
            return False
        if not (ra < rc < rb):
            return True
        return _has_token(grid, a, int(BasisToken.MEMORY), ra + 1, rc + 1)

    if kind == "CONSTRAINT_AFTER":
        lane = inv.lanes[0]
        ra = _operational_rank(grid, lane)
        if ra is None:
            return False
        return _has_token(grid, lane, int(BasisToken.CONSTRAINT), ra + 1, RANKS)

    if kind == "INTERFACE_TERMINAL":
        lane = inv.lanes[0]
        ra = _operational_rank(grid, lane)
        if ra is None:
            return False
        return _has_token(grid, lane, int(BasisToken.INTERFACE), ra + 1, RANKS)

    raise StructuralSchemaError(f"unknown invariant kind {kind!r}")


def quiescent(grid: tuple[int, ...]) -> bool:
    """No unresolved loci. VOID is settled; EXPANSION is not."""
    return int(BasisToken.EXPANSION) not in grid


def materialisable(grid: tuple[int, ...], schema: StructuralSchemaV1) -> bool:
    """Every bound lane carries exactly one operational locus of its kind, and
    no operational token appears in an unbound lane."""
    bound = {binding.lane: binding for binding in schema.lanes}
    for lane in range(LANES):
        ranks = [
            rank for rank in range(RANKS)
            if grid[cell(rank, lane)] in OPERATIONAL_TOKENS
        ]
        binding = bound.get(lane)
        if binding is None or binding.operational_token == int(BasisToken.VOID):
            if ranks:
                return False
            continue
        if len(ranks) != 1:
            return False
        if grid[cell(ranks[0], lane)] != binding.operational_token:
            return False
    return True


def is_resolved(grid: tuple[int, ...], schema: StructuralSchemaV1) -> bool:
    """All three conditions. 'Filled' is not one of them."""
    return (
        quiescent(grid)
        and not residual(grid, schema.invariants)
        and materialisable(grid, schema)
    )


def halt_score(grid: tuple[int, ...], schema: StructuralSchemaV1) -> float:
    """Residual-based. Never VOID-count-based."""
    total = len(schema.invariants)
    if total == 0:
        return 1.0 if quiescent(grid) else 0.0
    return 1.0 - len(residual(grid, schema.invariants)) / total


def validate_transition(
    before: tuple[int, ...],
    after: tuple[int, ...],
    schema: StructuralSchemaV1,
) -> None:
    """Enforce the refiner's authority boundary. Fails closed."""
    if len(after) != GRID_SIZE:
        raise StructuralSchemaError("proposed grid must be 81 entries")
    if any(not 0 <= value <= 9 for value in after):
        raise StructuralSchemaError("proposed tokens must be 0..9")
    for index in range(GRID_SIZE):
        if schema.writable_mask[index] == 0 and after[index] != before[index]:
            raise StructuralSchemaError(
                f"refiner wrote frozen locus {index} "
                f"(rank {rank_of(index)}, lane {lane_of(index)})"
            )
    # Operational tokens may move within their lane, never across lanes,
    # and none may be created or destroyed.
    for lane in range(LANES):
        was = sorted(
            before[cell(rank, lane)] for rank in range(RANKS)
            if before[cell(rank, lane)] in OPERATIONAL_TOKENS
        )
        now = sorted(
            after[cell(rank, lane)] for rank in range(RANKS)
            if after[cell(rank, lane)] in OPERATIONAL_TOKENS
        )
        if was != now:
            raise StructuralSchemaError(
                f"refiner altered the operational multiset of lane {lane}: "
                f"{was} -> {now}"
            )


# ------------------------------------------------------------- the compiler


def capacity_requirements(
    lane_count: int,
    longest_chain: int,
    cross_lane_edges: int,
    memory_spans: int,
) -> tuple[int, int, int]:
    """Lower bounds. Counts only; never places."""
    lanes_required = lane_count
    ranks_required = longest_chain + max(cross_lane_edges, memory_spans)
    loci_required = lane_count * max(1, ranks_required)
    return lanes_required, ranks_required, loci_required


def decomposition_measure(
    lanes_required: int, ranks_required: int, loci_required: int
) -> int:
    """Well-founded measure. Must strictly decrease on every re-decomposition."""
    return max(lanes_required, ranks_required, -(-loci_required // LANES))


def build_structural_schema(
    *,
    semantic_request_digest: str,
    lane_bindings: tuple[LaneBindingV1, ...],
    invariants: tuple[StructuralInvariantV1, ...],
) -> StructuralSchemaV1:
    """Compile lanes + invariants into the initial bounded refinement problem.

    The compiler places only what is uniquely determined: lane identity, the
    operational token of each bound lane, the frozen control locus, and frozen
    VOID in unbound lanes. Rank placement, routing, memory ownership,
    constraint discharge and interface placement are left unresolved on
    purpose -- that is the refiner's entire job.
    """
    bound = {binding.lane for binding in lane_bindings}
    if len(bound) > MAX_SEMANTIC_LANES:
        raise DecompositionRequired(len(bound), 0, 0)

    grid = [int(BasisToken.VOID)] * GRID_SIZE
    mask = [0] * GRID_SIZE

    for lane in range(LANES):
        writable = lane in bound or lane == CONTROL_LANE
        for rank in range(RANKS):
            mask[cell(rank, lane)] = 1 if writable else 0

    for binding in lane_bindings:
        if binding.operational_token != int(BasisToken.VOID):
            # Deliberately degenerate: every operation starts at rank 0, which
            # violates every PRECEDES invariant. The refiner must schedule.
            grid[cell(0, binding.lane)] = binding.operational_token
        # One unresolved locus per bound lane. The compiler does not say what
        # belongs there.
        grid[cell(1, binding.lane)] = int(BasisToken.EXPANSION)

    # Determined fact: the terminal control locus. Projector writes and
    # freezes it, discharging TERMINAL_RESOLUTION before refinement begins.
    grid[TERMINAL_CELL] = int(BasisToken.RESOLUTION)
    mask[TERMINAL_CELL] = 0

    unsigned = StructuralSchemaV1(
        semantic_request_digest=semantic_request_digest,
        lanes=tuple(sorted(lane_bindings, key=lambda b: b.lane)),
        writable_mask=tuple(mask),
        initial_grid=tuple(grid),
        invariants=tuple(sorted(invariants, key=lambda i: i.invariant_id)),
        schema_digest="",
    )
    return StructuralSchemaV1(
        semantic_request_digest=unsigned.semantic_request_digest,
        lanes=unsigned.lanes,
        writable_mask=unsigned.writable_mask,
        initial_grid=unsigned.initial_grid,
        invariants=unsigned.invariants,
        schema_digest=_domain_digest(
            STRUCTURAL_RESIDUAL_DOMAIN, structural_schema_payload(unsigned)
        ),
    )
