# Elpis2.1.11

## Version: v2.1.11

Elpis2.1.11 is the qualified successor to Elpis2.1.10. It adds the
Authority-Preserving Improvement Witness R0 while preserving the existing
production authority contracts.

## Qualified APW R0 observation

- Three deterministic proposal cycles improve quality exactly
  `27 -> 54 -> 81/81`.
- Proposer authority, feedback authority, and accumulated authority remain zero.
- Proposal quality does not grant execution authority.
- The positive terminal fixture is constructed through public Semantic IR,
  deterministic P0 projection, and P1 transition authority. It begins with one
  `MUTATION_HAZARD` residual and frozen structural cost 1.
- Exactly one P1-legal strict improvement is certified and applied: enum 10,
  move `("set", 9, 4)`, cost `1 -> 0`.
- The same final improved proposal packet is exercised against an already
  optimal canonical fixture and produces explicit `ABSTAIN_ALREADY_OPTIMAL`.
- Eight typed negative cases reject authority-contract tamper, forged
  authorizing evidence, adjudicator selection, candidate injection, nonzero
  authority claims, execution claims, application-capability injection, and
  stale-cycle replay.

## Authority boundary

The proposer supplies proposal content and ordering only. Candidate legality,
transition validation, strict-improvement adjudication, application, and replay
remain outside proposer authority in deterministic shipped machinery.

## Release integrity

Elpis2.1.11 advances only the release/package declarations, public release
identity table, immutable predecessor belt and predecessor regression coverage
needed to seal this successor, plus the qualified APW witness/regression and
this release documentation. Historical release manifests and tags are not
rewritten.

The canonical release guard, mutation suite, write-once sealer, public verifier,
and sealed-tree controls qualify the local release candidate. Hosted push
workflows remain external publication evidence and must pass before annotated
tagging and public release.

## Explicit nonclaims

This witness does not establish hostile same-process reflection isolation,
process-external attestation, general RSI safety, arbitrary learned-model
safety, autonomous self-improvement, full Elpis alignment, or universal
semantic or security correctness.

The existing Elpis2.1.10 technical limitations remain in force unless
explicitly qualified above.
