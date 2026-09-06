# Elpis2.1.3 — Fail-closed runtime and authority guards

## Breaking change

**BREAKING:** `CapabilityRegistry.issue(scope=...)` now requires a non-empty
explicit scope. The prior empty default produced effectively unbounded authority;
callers depending on it were depending on unsafe semantics. Missing metadata,
missing bound scope, and scope mismatches raise `CapabilityForgery` without
consuming the capability. Receipts sign the issue-time bound scope.

## Receipt verification and retention

Verification is process-local only, under a private per-instance symmetric key.
The registry retains exact signing payloads and recomputes HMAC under the current
key using `hmac.compare_digest`. No third-party, cross-process, or asymmetric
receipt verification is claimed.

`retention_limit` defaults to **4096**. A full window raises
`ReceiptRetentionExhausted` before sequence advancement, nonce generation,
signing, or capability lifecycle mutation. Failed retention and scope consumes
are transactionally inert; pending capabilities remain live. `end_episode()`
explicitly closes the retained verification window, so old receipts cease to
verify there. It does not reset capability lifecycle or widen bound scopes.

`state_digest()` includes registry data, counters, metadata values, retained
payloads, and key identity. Synchronization machinery is excluded.

## Runtime and release guards

R0 and R1 require every audited dependency to import, expose a module file, and
resolve inside the normalized real canonical root. Their common secondary legacy
denylist accepts `ELPIS_FORBIDDEN_ROOTS` extensions. Findings veto transactions.
R1 requires a real qualified R0 report with explicit false canonical nonmutation
evidence. Its build directory now resolves lazily. R0's NumPy minimum is
compatible with the root project's NumPy 1.26 dependency range.

The VERSION-driven public verifier rejects unknown or unsealed identities,
undeclared files, and dirty/ephemeral release trees, including bytecode and empty
cache directories. Only `.git` is entirely ignored. Verify a pristine clone or
export before installing, fetching models, or building inside the tree.
Declared text must be strict UTF-8; non-UTF-8 declared text is rejected.
Scanner exceptions bind exact path, finding kind, matched-literal SHA256, and
occurrence count. Removed occurrences reject as stale allowlist entries.
Sealing itself makes no correctness claim.

## Pre-seal qualification

- Release mutations: **20/20**, including exact diagnostic assertions.
- Authority focused: **21/21**; runtime guards and mechanical parity: **22/22**.
- Sealer/identity guards: **10/10**; full Python suite: **313/313**.
- Grid81StructuralSemantics: **122/122**; installed R0: **26/26**.
- Native HACF: **21/21**; genuine native R1 transaction completed.
- R1 negatives: `R0_AUDIT_REPORT_MISSING`, `CANONICAL_FIELD_ABSENT`, and
  `OUTSIDE_CANONICAL` each vetoed the transaction; no R1 receipt completed.
- Canonical R0 component census remained unchanged; historical-manifest
  comparison and `git diff --check` passed.

Qualification used real project/CUDA-environment dependencies and the pinned
FPRM checkpoint, without stubs or collection waivers. Only the 2080 SUPER was
visible for CUDA qualification, with allocation caps and monitoring below 5 GB.
These Python tests do not establish GPU inference performance. Historical-code
replays and disabled-control probes establish negative-test sensitivity.

## Provenance and open scope

The immediate predecessor is immutable `Elpis2.1.2`, commit
`8adfdd80f004611a1af77a2105d845bba4464d9b`; its tag, release, and manifest are
unchanged. `primitive_closure_commit` retains
`482d4064321392108b87124cd47343d9c748f5bc`. `base_release_commit` retains the
existing distribution identity's original Elpis2.0.0 baseline,
`c911af22e01ee35c441d65e8dbcad18694bdcb2a`; it does not mean immediate predecessor.

The independently installable R0/R1 packages intentionally duplicate their
audits, with mechanical parity tests. Torch remains an import dependency of the
logic package. Cross-process authority and asymmetric verification remain open.
No performance claim is made. Publication requires separate approval and green
workflows on the exact release commit; this seal alone does not establish it.
