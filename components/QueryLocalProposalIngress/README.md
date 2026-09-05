# QueryLocalProposalIngress

**Status:** `QUALIFIED_SUCCESSOR_COMPONENT`
**Runtime admission:** `FALSE`

## Role

`QueryLocalProposalIngress` is the successor-side, query-local representation
boundary for provenance-bound proposal envelopes.

It exists downstream of candidate production (for the currently-qualified path:
bounded Regex + native HACF lexical/context proposal) and upstream of any future
semantic truth admission or runtime authority.

Its contract is deliberately weak:

- proposal representation is query-local only;
- nodes are `SEMANTIC_NODE_FLAG_EXTERNAL`;
- assertion authority is zero;
- semantic/admission/execution/runtime authority are all zero;
- no persistent base-graph admission is performed;
- no P4 relation enum is extended;
- no Grid81 semantic meaning is introduced.

## Atomic batch boundary

The component exposes a constructor that validates and materializes an entire
proposal batch in private memory, builds a fresh private query overlay, finalizes
it, and only then publishes the overlay pointer and batch receipt.

Failure publishes neither overlay nor receipt.

Exact duplicate proposal envelopes are rejected. Input ordering is not semantic:
proposal-set identity is based on canonical sorted envelope identities.

## Authority boundary

This component does **not** decide truth and does **not** authorize execution.
It preserves provenance and identity while keeping proposals explicitly
`PROPOSED_UNADMITTED`.

Semantic Structural Spine V1 remains sealed and is not modified by this component.

## Current qualified producer

The initial qualification fixture is the frozen two-candidate bounded
Regex+HACF proposal lineage. The native contract itself is producer-neutral so
long as a caller presents a valid `elpis_query_local_proposal_v1` bound to the
same query/context/registry/policy identities.

## Deferred

Runtime admission remains false. Connecting the live streaming Regex+HACF
producer to this component is a separate qualification boundary.
