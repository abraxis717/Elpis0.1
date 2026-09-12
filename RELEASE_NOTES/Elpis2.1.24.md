# Elpis2.1.24

## Version: v2.1.24

Elpis2.1.24 is the post-Elpis2.1.23 engineering successor that integrates three independently qualified lines under one release boundary: Grid81 Canonical Publisher R1, StreamingRegexIngress/RegexHACF V2, and the code-only ECS M1A same-process kernel.

## Grid81 Canonical Publisher R1

The canonical publisher closes the D3 lock-domain defect by deriving one persistent canonical publication lock domain and requiring cooperating readers and writers to serialize against it.

R1 also adds deterministic publication recovery state bound to the exact publication, candidate tree, and durable application-ledger identity. Exact retries can resume or verify already-visible publication without reversing a completed exchange. Conflicting or unbound recovery fails closed.

The contract remains bounded to cooperating R1 readers/writers on the documented local filesystem model. It does not claim protection against legacy R0 writers, hostile parent/database replacement, or universal physical-power-loss behavior.

## StreamingRegexIngress V2

StreamingRegexIngress V2 adds a true incremental streaming state machine for the frozen V1 grammar and composes it through RegexHACFQueryIngress.

For matches up to 4096 bytes, V2 preserves the qualified V1 evidence identity. Longer matches use an explicit V2 representation that retains the required hashes, offsets, and payload identity without pretending to be byte-transparent V1 output.

Qualification includes a frozen-Elpis2.1.23 V1 differential oracle, deterministic property testing, long-span families, bounded-allocation checks, and downstream QueryLocalProposalIngress atomic-batch regression.

The historical 196-valid/21-malformed fixture matrix was not recovered and is not claimed as rerun. V2 is an additive successor contract, not a claim that every long-match evidence byte is V1-identical.

## ECS M1A

The public ECS surface now includes the deterministic same-process `elpis_ecs` kernel under `ECS/runtime`, its executable tests/qualification programs, and one consolidated `ECS/README.md`.

M1A provides deterministic entity identity/lifecycle, entity-bound local invocation, bounded mailboxes, kernel-owned sender attribution, deterministic scheduling, a canonical event history, state-root v3 authority, serialized mutation/introspection, recoverable framed-log persistence, replay, crash/restart recovery, and fail-closed corruption handling.

The public tree intentionally does not include the Hermes/Astra design-note archive, generated qualification prose/JSON evidence, `.astra_tmp`, or cache debris.

M1A is qualified only for the documented same-process, single-owner POSIX model. Checkpoints currently provide no authoritative replay acceleration. Cross-process authentication/authority remains `UNRESOLVED / DEFERRED`. M1A does not grant Structural R0 mutation authority or broaden semantic/runtime admission.

## Combined qualification

Before release sealing, the three lines were materialized together from their exact independently qualified bytes with zero cross-line path collisions.

The combined candidate passed:

- 426 ECS M1A tests
- 301 combined Grid81 Publisher tests
- 404 existing ECS/repository regressions
- 9 focused Regex native tests
- 97 root native tests after the documented eight baseline path-incompatible exclusions
- 3,024 frozen-V1 differential runs
- 963 deterministic V2 property runs across 14 long-span families
- QueryLocalProposalIngress atomic-batch regression
- secret/private-path scanning
- wheel build/install/import including `elpis_ecs`
- final exact byte revalidation for all three qualified source lines

Frozen ECS Structural R0 authority and closed Branch35–40 science remain unchanged.

## Release-authority continuity

Elpis2.1.23 remains immutable. Elpis2.1.24 receives a new release manifest and tag over the qualified successor tree.

`PUBLISHED_RELEASES.json` is intentionally not modified in the pre-tag release commit. Publication-registry admission remains a post-tag operation derived from immutable tag authority.
