# Elpis2.1.8 — Deterministic Runtime Hardening

## Version: v2.1.8

Elpis2.1.8 is a runtime, correctness, dependency-boundary, and
release-integrity successor to Elpis2.1.7.

Elpis2.1.7 and all earlier published manifests remain immutable.

## Python static-policy hardening

Canonical AST prohibitions are now non-subtractive. A caller may extend the
restricted set but cannot remove the canonical restrictions.

The policy also rejects the reproduced frame, generator, coroutine,
async-generator, traceback, and code-object introspection families used to
recover restricted callables indirectly.

The AST policy remains a static source-policy boundary. It is not a Python
execution sandbox and does not authorize generated-source execution.

## Optional learned runtime

The base package dependency surface is reduced to NumPy and SciPy.

Torch and model-oriented dependencies are supplied through the explicit `trm`
optional dependency group. Deterministic/base imports and the R0 transaction
are qualified with Torch intentionally unavailable.

Capabilities which require learned/model or tensor-backed functionality fail
explicitly when the optional dependency is absent.

Hosted jobs that exercise those surfaces request the `trm` extra explicitly;
the deterministic-base qualification remains a plain base installation.

## C2R6-P0 allocation repair

The production C2R6-P0 allocator replaces incomplete greedy rank/locus
placement with deterministic joint finite-domain allocation for the audited
Furyan subset.

FuryanLocusOracle R0 itself remains byte-for-byte unchanged.

Successor qualification compares production against the independent Furyan
oracle over all 44,005 canonical core cases, retains the historical
counterexamples, checks the admitted SAT/UNSAT boundary, and verifies
fresh-process deterministic output.

Furyan remains independent qualification evidence rather than runtime
authority.

## Deterministic semantic replay identity

Deterministic semantic/replay identity is separated from ephemeral
process-local security and capability identity.

Equal deterministic semantic inputs can therefore retain stable replay
identity across fresh processes while authority-instance, capability,
consumption, and related security identifiers remain ephemeral and enforcing.

This does not establish cross-process bearer authority or external
attestation.

## Functional-evaluation boundary

A machine-readable functional-evaluation contract distinguishes static source
validity from functional correctness.

The contract does not execute candidate source and grants no execution
authority. Isolated generated-source execution remains outside this release.

## Release and CI integrity

Public qualification workflows accept both `v*` and `Elpis*` release-tag
conventions.

Repository regression coverage binds those conventions so a supported release
tag cannot silently escape qualification.

Torch-backed qualification jobs request the learned-runtime dependency
explicitly, while deterministic-base qualification proves that the base
package remains Torch-free.

## Unchanged authority boundaries

Elpis2.1.8 does not:

- grant learned components transition or execution authority;
- execute generated source;
- treat AST validity as functional correctness;
- promote Furyan into runtime authority;
- alter FuryanLocusOracle R0 source or frozen evidence;
- alter Grid81's 81-cell structural geometry;
- alter HACF ABI;
- alter model checkpoint identity;
- create cross-process bearer capability or external attestation;
- make a performance claim.

No performance claim is made.
