# Grid81 Deterministic Canonical Candidate Constructor

This component constructs a complete, isolated immediate-successor Grid81
canonical candidate.

It does **not** publish the candidate and does **not** mutate live canonical
state.

## Inputs

Construction requires:

- a valid one-use `ATOMIC_GRID81_CANONICAL_PROMOTION` capability;
- the exact inert G5.3B structural-influence artifact bound by that capability;
- a production-reader-valid current Grid81 canonical state; and
- a fresh output path outside the live project root.

## Output

The constructor copies the current canonical tree byte-for-byte, appends exactly
one successor generation, and replaces the current transaction sidecars with
records for the new candidate.

The candidate contains the same seven-file top-level contract used by the
production reader:

- `.authority_audit.json`
- `.consumed_capability.json`
- `.consumption_receipt.json`
- `.source_nonmutation_audit.json`
- `.transaction_manifest.json`
- `HEAD.json`
- `generations/`

All prior generation files remain byte-identical.

## Generation semantic contract

New candidates use `elpis.grid81.canonical-generation.v2`.

The generation semantic digest is a domain-separated SHA-256 over the complete
generation record before the `generation_semantic_digest` field is added.

This avoids inheriting the opaque historical internal
`generation_file_sha256` convention from generation `000001`. The production
reader still authenticates raw generation bytes independently through HEAD.

## Structural artifact boundary

The source structural artifact must remain `UNAPPLIED`.

The constructor validates its G5.3B invariant surface and recomputes both the
artifact semantic digest and full artifact digest before accepting it.

No structural proposal is selected, ranked, activated, or written into ECS.

## Authority boundary

The constructor:

- does not consume the publication ledger;
- does not perform the atomic canonical exchange;
- does not alter live `Canonical/Grid81`;
- does not authorize itself;
- does not manufacture a promotion capability.

Its output becomes canonical only if the separate authority-gated atomic
publisher accepts and publishes it.
