# Elpis2.1.6 — AST Policy and Release-Integrity Hardening

## Version: v2.1.6

Elpis2.1.6 is a narrow security/integrity successor to Elpis2.1.5.

It carries two independently qualified repairs. It does not change the
C2R6-P0 allocator, Grid81 semantics, learned-model authority, runtime execution
authority, model checkpoints, HACF behavior, or the qualified Furyan scientific
object introduced in Elpis2.1.5.

## Python AST policy hardening

The canonical Python AST policy previously rejected direct calls to configured
dangerous names, but several equivalent reference forms were accepted as
`AST_VALID`.

The qualified R0 repair closes five reproduced bypass classes, including:

- dynamically retrieving `eval` through `getattr`;
- retrieving `exec` through `__builtins__` subscription;
- dunder-attribute introspection through the Python object hierarchy;
- aliasing a banned callable before invoking it;
- retrieving `open` through `vars(__builtins__)`.

The repair preserves the existing externally visible decision code
`BANNED_CALL`; no semantic-space or P0/Grid81 protocol migration is introduced.

The negative controls were demonstrated against the unpatched Elpis2.1.5
policy before implementation, where all five were accepted as `AST_VALID`.
After repair, all five fail closed as `BANNED_CALL`.

This remains a static source-policy boundary. It is not claimed to be a Python
execution sandbox or a proof that arbitrary generated code is safe.

## Declared release-text integrity

Elpis2.1.5 contained a stale canonical `RELEASE_NOTES.md` inherited from the
older R1.1.1 release line even though `VERSION`, package metadata, README, and
the 2.1.5 release-specific notes identified Elpis2.1.5.

The public verifier accepted that inconsistency.

Elpis2.1.6 adds a VERSION-bound declared-text guard for the canonical
declarations in:

- `README.md`;
- `RELEASE_NOTES.md`.

The guard fails closed when a canonical declaration is absent, duplicated, or
does not equal repository `VERSION`. Arbitrary occurrence of the current
version elsewhere in a document does not satisfy the guard.

Two resealed negative mutations independently demonstrate that the old
verifier accepted stale README and stale RELEASE_NOTES declarations. Both
mutations are rejected by the repaired verifier for the intended declared-text
reason.

The release mutation suite therefore expands from 20 to 22 guarded cases.

## Release integrity

The immutable Elpis2.1.5 manifest is not rewritten.

Elpis2.1.6 receives its own successor version identity and release manifest only
after pre-seal qualification. The sealer's historical published-release belt is
advanced through Elpis2.1.5.

The post-seal real-tree verifier control is intentionally run only after the
Elpis2.1.6 manifest exists.

## Unchanged scientific/runtime boundaries

Elpis2.1.6 does not:

- repair the known C2R6-P0 allocator completeness limitation documented by
  Elpis2.1.5;
- alter FuryanLocusOracle R0;
- grant generated-source execution authority;
- change TRM or Projector authority;
- change Grid81 allocation semantics;
- change receipt-verification semantics;
- change model checkpoints;
- make a new performance claim.

No performance claim is made.
