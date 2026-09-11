# Elpis2.1.13

## Version: v2.1.13

Elpis2.1.13 is the engineering-hardening successor to Elpis2.1.12. It makes
the already-published ECS Structural Authority R0 contract executable, adds a
bounded E0R2 Semantic-IR sufficiency diagnostic, and closes repository,
packaging, containment, and CI-integrity gaps identified during independent
post-release review.

## Executable ECS Structural R0

- `MICROSCOPIC_COLUMN_PARTICIPATION_MASK_R0` remains the frozen structural
  ontology.
- Whole-column participation is enforced through explicit ACTIVE, DISABLED,
  and non-writable FROZEN_ZERO states.
- Mutation authority remains limited to `ABSTAIN`, `DISABLE_COLUMN`, and
  `RESTORE_COLUMN`.
- DISABLE materializes six exact binary64 `+0.0` values in the existing slot;
  RESTORE reproduces the retained frozen column bytes exactly.
- Width, primitive law, continuous retained Theta bytes, and scientific
  observation authority remain frozen.
- Operational column slots remain gauge addresses rather than intrinsic
  semantic entities, and simultaneous column permutation remains the published
  equivalence.
- Candidate state cannot be fabricated through a public arbitrary-mask
  constructor; mutation-bound state transitions remain the ordinary writable
  path.
- Installed deployments require an explicit intact ECS authority root when the
  source-tree authority is not colocated.

## E0R2 diagnostic

The release includes a bounded executable diagnostic against the existing
production Semantic IR and Projector. Its qualified terminal result is:

`SEMANTIC_IR_INSUFFICIENT`

with one unresolved executable primitive: a writable binary whole-column
participation referent bound to an external frozen sidecar and operational
gauge slot, with deterministic DISABLE/RESTORE and reverse-binding semantics
while exact-zero slots remain frozen.

The existing Projector can preserve the participation facts descriptively, but
does not confer that writable structural meaning. Generic lane-capacity
controls therefore do not resolve the missing semantic primitive.

E1 and E2 were not executed.

## Repository and distribution hardening

- Reconcile canonical-only Nanbeige42 host metadata with the public shipped
  component registry instead of requiring a path the release boundary forbids.
- Gate canonical assembly verification and repository/tooling completeness.
- Package the intended nested Python package roots so the installed artifact is
  the qualified artifact rather than a source tree repaired by `PYTHONPATH`.
- Validate canonical roots and use path-aware containment so a hostile or bad
  root such as `/` cannot vacuously satisfy dependency containment.
- Remove workstation-private runtime path literals and bind public-scan
  exceptions to the complete containing-file digest as well as literal,
  finding-kind, and occurrence count.
- Preserve mutation-suite reachability after whole-file allowlist binding by
  explicitly rebinding only deliberate throwaway fixture mutations.
- Treat the separately distributed FPRM checkpoint as optional in a public
  source-only checkout while retaining an explicit fail-closed
  checkpoint-required qualification mode.
- Document and gate pristine-tree release verification before in-place build or
  installation artifacts can contaminate the manifest census.

## Release integrity

Elpis2.1.13 advances the VERSION/package/citation declarations, public release
identity table, immutable predecessor belt, predecessor guard coverage, and a
new write-once successor manifest. Every historical release manifest through
Elpis2.1.12 remains byte-for-byte immutable.

The release candidate must pass local pre-seal and post-seal qualification,
then hosted `main` push workflows before the annotated `Elpis2.1.13` tag is
created. Tag-triggered workflows must pass before the public GitHub Release is
registered.

## Explicit nonclaims

This release does not establish the missing E0R2 semantic primitive, authorize
E1 or E2, establish learned-refinement efficacy, execute Darwinian evolution,
perform scientific evaluation, claim evolutionary benefit, autonomous
self-improvement, general RSI safety, AGI, ASI, or full Elpis alignment.
