# Grid81 Deterministic Canonical Publisher

This component is the authority-gated atomic publication boundary for canonical
Grid81 state.

It accepts a complete isolated candidate produced outside the live canonical
tree and publishes that candidate only when it is bound to the exact validated
one-use `ATOMIC_GRID81_CANONICAL_PROMOTION` capability.

## Boundary

The publisher does **not** create promotion authority and does **not** construct
semantic candidate content.

Its responsibilities are narrower:

- validate the promotion capability before publication;
- bind the capability to the candidate transaction, generation, and capability
  identity;
- bind the capability's source-canonical state to the live Grid81 source before
  first publication;
- require the capability's expected publication-ledger head to match the
  durable publication ledger;
- preserve all historical generation files byte-for-byte;
- reserve publication exactly once in the durable ledger;
- perform the canonical directory exchange atomically;
- verify the committed result through the production Grid81 reader;
- support exact idempotent replay of an already committed transaction; and
- fail closed on stale, mismatched, malformed, or unauthorized publication.

## Public API

The production entry point is:

```python
publish_candidate(
    *,
    project_root,
    candidate_root,
    ledger,
    promotion_capability,
    lock_path,
)
```

Bare artifact digests, bare canonical-head digests, and bare ledger-head values
are not an authorization surface. Publication requires the validated promotion
capability itself.

## Authority relation

The publisher requires the capability class intended for this boundary and
checks its bindings against both the candidate and the live source state.

The publication path distinguishes two histories:

1. the upstream G5.3C application ledger represented in source evidence; and
2. the durable canonical publication ledger used for publication reservation
   and replay exclusion.

Those ledger heads are distinct authority channels and must not be silently
collapsed.

## Atomicity and recovery

Publication uses an external lock and an atomic directory exchange. The durable
publication reservation is written before the canonical exchange.

This ordering permits deterministic recovery:

- if the durable reservation exists but the live canonical tree has not yet
  advanced, an exact retry can resume the same publication;
- if the candidate is already the committed canonical state and the exact
  reservation exists, replay returns an idempotent already-committed result;
- a different promotion capability cannot reuse that committed candidate;
- post-publication verification failure triggers bounded rollback behavior.

The publisher does not weaken generation-before-HEAD verification, fsync,
exchange preflight, post-commit reader verification, or rollback semantics.

## Candidate contract

The candidate must be a production-reader-valid immediate successor.

Among other relations, the publisher verifies:

- target generation is exactly the capability-authorized generation;
- candidate transaction ID is the capability-reserved transaction ID;
- candidate capability ID is the issued promotion capability ID;
- the candidate consumed-capability sidecar is the exact consumed projection of
  the issued capability;
- the generation and consumption receipt bind the promotion capability digest;
- historical generation bytes are unchanged; and
- the live source canonical identity matches the capability source binding on
  first publication.

Candidate construction is handled by the separate
`Grid81DeterministicCanonicalCandidateConstructor` component.

## Runtime boundary

Normal Grid81 runtime consumers remain read-only. This publisher is an explicit
promotion transaction boundary, not background runtime behavior.

It does not authorize ECS world mutation, model execution, structural proposal
selection, or autonomous promotion.

## Qualification

The component-level publisher tests cover:

- authorized publication and exact replay;
- tampered promotion capability rejection;
- cross-capability candidate rejection;
- stale publication-ledger rejection;
- consumed-capability projection tamper rejection;
- historical-generation mutation rejection;
- crash/resume after durable reservation; and
- atomic-exchange preflight failure.

The repository-level regression
`tests/test_grid81_canonical_writer_chain_r0.py` composes promotion authority,
candidate construction, durable publication reservation, atomic publication,
and production-reader verification in one bounded writer-chain transaction.
