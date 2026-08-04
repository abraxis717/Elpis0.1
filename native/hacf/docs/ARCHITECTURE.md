# Architecture boundary

## Data plane

1. source bytes are SHA-256 addressed;
2. deterministic chunking emits stable chunk identities;
3. SQLite stores document/chunk metadata and FTS5 lexical indexes;
4. a package digest binds type, schema, policy, lineage, dependencies and payload;
5. the queue advances packages through explicit states;
6. only dependency-ready, policy-matching, resource-admissible work is admitted;
7. failures elect the narrowest permitted refinement loop;
8. graph updates are immutable deltas chained into snapshot digests.

## Memory plane

FMS owns residency only. Queue presence does not imply active residency.
Accelerator and CPU logical tiers can charge the same physical RAM domain.

## Authority plane

Retrieved content and graph deltas are advisory until separately admitted.
A valid digest proves identity and integrity, not truth or permission.
