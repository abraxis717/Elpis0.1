"""Supported-subset taxonomy for the C2R6-P0 projector.

The projector supports the structural subset of the authoritative Semantic
IR. The taxonomy is explicit and small; anything outside it is rejected as
UNSUPPORTED_SEMANTIC_SHAPE (never silently interpreted).
"""
from __future__ import annotations

# Entity kinds with structural meaning in the supported subset.
SUPPORTED_ENTITY_KINDS = frozenset(
    {"input", "output", "state", "memory", "interface"}
)

# Dependency kinds. "precedes" is strict ordering (PRECEDES invariant).
# "state_feeds" is legitimate state/memory recurrence (MEMORY_SPAN); the
# authority's dependency DAG stays acyclic, so recurrence cycles are
# expressed through relations, not raw dependencies.
SUPPORTED_DEPENDENCY_KINDS = frozenset({"precedes", "state_feeds"})

# Relation predicates carrying structural meaning.
ROUTE_PREDICATE = "route"
INTERFACE_PREDICATE = "interface"
MUTATES_PREDICATE = "mutates"
STATE_FEEDS_PREDICATE = "state_feeds"
STRUCTURAL_RELATION_PREDICATES = frozenset(
    {ROUTE_PREDICATE, INTERFACE_PREDICATE, MUTATES_PREDICATE,
     STATE_FEEDS_PREDICATE}
)
# Other relation predicates are preserved in the binding sidecar without
# structural interpretation (no hidden inference).

# Quantity predicates checked against explicit declared arities.
QUANTITY_ARITY_PREDICATES = frozenset({"input_arity", "output_arity"})
