# Elpis2.1.9 — Structural Correctness and Runtime Boundary Hardening

## Version: v2.1.9

Elpis2.1.9 is a structural-correctness, native-qualification,
authority-integrity, and airgap-policy successor to Elpis2.1.8.

Elpis2.1.8 and all earlier published manifests remain immutable.

## Structural semantic reconciliation

Structural relations with negative polarity are now rejected as unsupported
semantic shapes rather than being silently interpreted as positive structural
obligations.

Dependency-form `state_feeds` is no longer admitted. `state_feeds` remains a
relation-form memory-span semantic; dependency scheduling remains reserved for
`precedes`.

Structural invariants enforce exact constructor arity by invariant kind.

`residual_clearance_score` names the residual-clearance metric explicitly.
`halt_score` remains a compatibility alias and is not a proof of terminal
resolution.

`capacity_requirements()` is documented as a conservative diagnostic estimate,
not a mathematical lower bound, infeasibility proof, or decomposition
certificate.

The complete joint rank/locus allocator introduced in Elpis2.1.8 remains the
production feasibility authority for the bounded audited domain.

## Frozen Furyan boundary

FuryanLocusOracle R0 remains byte-for-byte unchanged.

The release does not broaden Furyan's claim surface. It remains frozen
independent evidence for the previously audited finite placement subset rather
than runtime authority or a general Grid81 completeness theorem.

## Native sanitizer qualification

Hosted CI now builds HACF under AddressSanitizer and
UndefinedBehaviorSanitizer and executes the native HACF suite with leak
detection enabled.

The real Python/ctypes wrapper boundary is then exercised under ASAN+UBSAN.
LeakSanitizer is disabled only for CPython-hosted processes because isolated
qualification reproduced interpreter-owned shutdown allocations; native HACF
retains leak detection.

The sanitized wrapper load, real HACF retrieval path, and complete Runtime R1
suite are CI-gated.

## Runtime authority integrity

`verify_authority_integrity()` is no longer a vacuous success path. It checks
the exact bounded R0 authority declarations, rejects forbidden or unapproved
authority drift, and requires runtime admission to remain disabled.

Negative regressions cover a forbidden authority claim, an unapproved
authority value, and runtime-admission escalation.

The stale generic `manifests/PUBLIC_RELEASE_MANIFEST.json` artifact is retired
from the successor tree. Versioned historical release manifests remain
immutable.

## Airgap pre-resolution enforcement

`socket.create_connection()` is now guarded before hostname resolution.

Hostnames are rejected before `getaddrinfo`; numeric non-loopback destinations
are rejected before the original helper is invoked; numeric loopback
destinations remain admitted.

The repair is permanently exercised by a dedicated CNumPyCortex airgap CI job.

A differential audit of the pre-existing broad asyncio exception handlers
showed that they do not create a network fail-open, so those handlers are
unchanged.

## Unchanged authority boundaries

Elpis2.1.9 does not:

- grant learned components transition or execution authority;
- execute generated source;
- treat AST validity as functional correctness;
- promote Furyan into runtime authority;
- alter FuryanLocusOracle R0 source or frozen evidence;
- claim general Grid81 satisfiability or allocator completeness;
- alter Grid81's 81-cell structural geometry;
- alter HACF ABI;
- alter model checkpoint identity;
- create cross-process bearer capability or external attestation;
- make a performance claim.

No performance claim is made.
