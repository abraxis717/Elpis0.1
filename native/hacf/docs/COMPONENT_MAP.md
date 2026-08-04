# Component map

## Existing implementation

### Memory plane

`src/memory/fms/`

Owns logical HOT/WARM/COLD residency, physical-domain accounting, promotion,
demotion, durable cold replicas and accelerator leases.

### Retrieval preparation

`src/retrieval/chunking/`

Owns deterministic structural chunking and normalized chunk identities.

## Reserved implementation boundaries

### Hash plane

`src/hash/`

Owns SHA-256 and canonical serialization helpers. There must be one canonical
digest implementation used by FMS, retrieval, graph and cascade envelopes.

### Cascade kernel

`src/kernel/`

Will own immutable package envelopes, Merkle-parent references, queue state,
dependency readiness, loop-election records and result handovers.

### Admission plane

`src/admission/`

Will own schema validation, policy-snapshot validation, capability checks,
admission receipts and execution/resource leases.

### Graph plane

`src/graph/`

Will own append-only graph deltas, snapshot identities, session graph state and
gated permanent-memory proposals.

### Retrieval plane

`src/retrieval/corpus/` and `src/retrieval/vector/`

Will own content-addressed corpus storage, SQLite FTS5, vector shards and sealed
RetrievalBundle construction.
