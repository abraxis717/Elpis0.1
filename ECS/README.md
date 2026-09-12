# ECS

Elpis ECS is the repository surface for the Entity-Component/System workstream: frozen structural authority, closed scientific evidence, and the executable same-process ECS kernel.

This directory deliberately keeps **one current prose authority surface**: this README. Historical design drafts, generated audit reports, qualification narratives, and machine-local evidence are not part of the public ECS source tree. Executable implementation and test code live beside the frozen authority/science material; descriptive integration status is consolidated here.

## Repository layout

- `ECS_AUTHORITY/STRUCTURAL_R0/` — frozen executable Structural R0 authority payload.
- `ECS_AUTHORITY_HEADER.md` — frozen public structural-authority header.
- `science/` — closed Branch35–40 scientific evidence and adjudication lineage.
- `runtime/elpis_ecs/` — executable same-process ECS kernel.
- `tests/` — source-level qualification and adversarial regression tests for the ECS kernel.
- `qualification/` — executable qualification programs only. Generated evidence belongs outside the source tree.

The authority/header were relocated here byte-for-byte. Scientific evidence was imported byte-for-byte from its closed handoff. Historical evidence is not rewritten for repository aesthetics.

## Status and scope

The current executable ECS milestone is **M1A: deterministic same-process kernel mechanics**.

M1A provides:

- deterministic entity identity and lifecycle;
- entity-bound local invocation through `EntityPort`;
- bounded local mailboxes;
- kernel-owned sender attribution;
- monotonic per-sender message sequencing;
- deterministic scheduling;
- one authoritative append-only event history;
- deterministic canonical state roots;
- replay from committed event history;
- recoverable framed-log persistence;
- serialized local mutation and introspection;
- crash/restart recovery;
- nonauthoritative checkpoint markers;
- fail-closed corruption handling.

M1A does **not** establish cross-process transport, federation, semantic truth, topology authority, Structural R0 mutation admission, Grid81/Semantic-IR integration, Projector/TRM/DarwinianMatrix efficacy, or autonomous semantic authority.

Runtime admission remains outside this milestone. This code is a qualified mechanical substrate, not a grant of broader Elpis execution authority.

## Architectural boundary

The central M1A rule is:

> semantic authority does not arise from entity existence, messaging, scheduling, hashing, replay, or persistence.

Entities may act through the local ECS API, but the kernel is mechanical infrastructure. It does not infer semantic truth, authorize Structural R0 edits, interpret Branch35–40 scientific results as runtime permission, or turn proposals into higher-level authority.

The current kernel is intentionally same-process. Cross-process authority remains **UNRESOLVED / DEFERRED** because a digest is not authentication and a deterministic identifier is not a credential.

## Entity model

An entity is founded from a canonical founding record. Its stable `entity_id` is domain-separated content identity derived from that record.

The entity ID is an identifier, not authentication.

The lifecycle is:

```text
FOUNDED -> ACTIVE
ACTIVE -> DORMANT
DORMANT -> ACTIVE
ACTIVE -> TERMINATED
DORMANT -> TERMINATED
```

`TERMINATED` is terminal. Terminated identities are not silently recycled.

Lifecycle transitions are committed events and are reproduced by replay.

Each entity also carries canonical logical state with monotonic versioning and digest linkage. State changes are mechanical delivery/version transitions in M1A; no claim is made that this state is cognition, semantic truth, memory sufficiency, or scientific state.

## Entity-facing API and sender attribution

Entity-facing messaging uses an entity-bound local `EntityPort`.

A port is bound by the kernel to one entity and one live kernel epoch. The entity-facing send operation does not accept a sender ID. Sender identity, sender sequence, and commit clock are assigned by the kernel.

This prevents the supported entity-facing API from selecting another active entity as sender.

Ports are process-local mechanical handles. They are invalid across kernel instances/epochs and become unusable when their bound entity cannot legally send.

This is an API-level same-process guarantee. It is **not** cryptographic isolation against hostile Python code that already controls or can arbitrarily introspect the trusted kernel object.

## Messaging contract

A canonical message envelope binds:

- schema/version;
- message ID;
- sender entity ID;
- receiver entity ID;
- monotonic per-sender sequence;
- canonical payload;
- payload digest;
- logical commit context.

Message IDs and digests provide deterministic content/context identity. They are not authentication tokens.

Mailboxes are bounded FIFO structures. Capacity is immutable for a durable history and is authority-bound into canonical state/genesis configuration.

Senders must satisfy the current lifecycle rule for sending. Receivers may be admitted according to the current local lifecycle contract. Dormant receivers retain queued work without processing; terminated mailboxes remain inert and rooted.

The local delivery claim is deliberately limited:

- a committed enqueue is represented by durable event history;
- sender sequence is monotonic and replay-checked;
- committed processing is reproduced by replay;
- duplicate/regressed sequence is rejected;
- no transport-level at-least-once or exactly-once claim is made.

## Deterministic scheduler

The scheduler is mechanical only.

Ready work is derived from rooted entity/mailbox state using an explicit total ordering. It does not use wall-clock time, process IDs, object addresses, set iteration order, or unspecified dictionary iteration as authority.

Scheduler readiness is derived rather than a hidden mutable semantic controller.

If two host threads race to invoke independent kernel operations, thread arrival order is external input. Once an operation enters the serialized kernel transition boundary, event ordering and replay are deterministic.

## Canonical state authority

The current root schema is `ecs.state_root.v3`.

The root binds all behavior-affecting logical/configuration state required by M1A, including:

- schema/revision;
- genesis digest;
- history digest;
- logical clock;
- next founding index;
- mailbox capacity;
- mailbox default capacity;
- full entity registry/lifecycle/state identity;
- mailbox lookup identity, capacities, and ordered envelopes;
- sender sequence watermarks;
- deterministic scheduler state/derivation inputs.

The design rule is:

> if changing a value can change a future accepted transition or deterministic output, that value must be directly root-bound or transitively bound through immutable root-bound configuration.

The history commitment prevents two otherwise similar live projections with different committed histories from silently sharing authority while producing different future event bytes.

Runtime-local descriptors, filesystem paths, locks, file offsets, object identities, scratch values, and port object references are not canonical logical state.

## Event history

The event log is the single authoritative mutable history.

Materialized entity/mailbox/watermark state is a projection of committed events. A projection is not a second independent source of truth.

Each event contains the canonical transition record:

- schema;
- event index;
- logical clock;
- transaction ID;
- event kind;
- entity ID where applicable;
- event payload;
- payload digest;
- before-state root;
- after-state root;
- previous-event digest;
- event self digest.

Event kinds are restricted to the kernel contract. Unknown event kinds or unexpected fields fail closed.

Replay validates exact field sets and types, bounded values, digest format, event index, clock progression, payload digest, self digest, previous-event linkage, before-root continuity, transition preconditions, and resulting after-root.

Python booleans are not accepted as integers where integer semantics are required.

## Commit model

A mutation is linearized under the kernel transition lock.

The intended transition is:

```text
read current projection
-> clone post-state
-> validate and apply transition to clone
-> advance logical clock
-> construct canonical event
-> compute after-state root/history commitment
-> append complete framed event
-> reach the configured durability boundary
-> install the post-state projection
-> return success
```

A successful call means the live projection corresponds to the committed event under the documented same-process POSIX model.

A rejected transition does not become partially visible.

Failures whose durable outcome cannot be proven are treated as indeterminate: the live kernel is invalidated and must be reopened/recovered before further mutation. The API does not guess whether an uncertain write committed.

## Concurrency and lock hierarchy

M1A serializes mutation and coherent introspection.

The lock hierarchy is:

```text
Kernel RLock
    -> EventLog RLock
```

or:

```text
Kernel RLock
    -> CheckpointStore RLock
```

Lower persistence layers do not call upward into the kernel while holding their locks.

Public mutation, observation, checkpoint, open/close, and recovery boundaries are serialized so that an observer does not see a durable event without its corresponding installed projection and cannot mistake a live writer's partial frame for crash residue.

The event log also owns a process-local reentrant lock. Live log reads never perform recovery truncation.

The durable storage path uses an exclusive inode lock to reject another cooperative live owner, including supported path aliases. This is not a defense against a hostile privileged process replacing files underneath the kernel.

## Persistence format and recovery

The event log is length-framed:

```text
8-byte big-endian payload length
canonical UTF-8 JSON event bytes
```

The maximum event-frame payload is bounded. Current M1A limits include:

- event-frame payload up to 262,144 bytes;
- message payload up to 65,536 bytes;
- bounded UTF-8 labels/strings;
- bounded integer domain.

These limits are part of behavior-affecting configuration and are bound through the genesis/state authority.

Persistence is described as a **recoverable framed append**, not as a universal atomic regular-file transaction.

The implementation handles short writes and retries interruption where appropriate. Zero-progress writes fail rather than spin forever. `fsync` and directory durability are used at the documented boundaries.

Recovery distinguishes:

- a valid complete event;
- a demonstrably incomplete trailing crash frame;
- complete but invalid/corrupt historical data.

Only a genuinely incomplete trailing frame may be treated as crash residue. Complete invalid history fails closed and is not silently discarded.

Live reads do not truncate incomplete frames. Recovery/truncation is restricted to serialized recovery/open semantics.

Physical device behavior outside the claimed POSIX/filesystem contract is not treated as proven.

## Replay

The core deterministic invariant is:

```text
genesis/configuration authority
+ ordered committed event bytes
= exactly one reconstructed kernel state
```

Fresh replay validates the complete event chain and independently re-applies transition preconditions/effects.

The expected closure relation is:

```text
live committed state root
==
fresh-process replay state root
```

Replay reconstructs:

- entity identities and lifecycle;
- entity logical state/version;
- mailboxes and message ordering;
- sender watermarks;
- logical clock;
- next founding index;
- scheduler-visible state;
- final history/state root.

Replay does not trust a stored after-root merely because its hash syntax is valid; transition effects are reproduced and checked.

## Checkpoints

Current checkpoints are nonauthoritative history markers.

They do not currently provide a claimed replay-performance acceleration because they do not contain a complete authoritative projection snapshot.

A checkpoint may assist validation/restart bookkeeping, but full event history remains authoritative.

Checkpoint corruption or mismatch cannot weaken event-chain verification. The full history is verified with the same strength whether a checkpoint exists or not. Invalid checkpoint data falls back to authoritative full replay where the contract permits.

Future snapshot acceleration must preserve this same verification strength before it can replace full replay work.

## Canonical serialization

Canonical objects use deterministic JSON serialization with explicit domain separation for hashes.

Canonical bytes are designed to remain independent of:

- filesystem path;
- process ID;
- Python object identity;
- hash seed;
- dictionary construction order;
- restart boundary.

Digests provide integrity/content identity relative to trusted starting authority. They are not signatures and do not prove an issuer.

## Failure behavior

The implementation fails closed on malformed or inconsistent persistent state.

Qualified failure classes include:

- malformed/corrupt event frames;
- oversized frames;
- invalid canonical JSON;
- duplicate/unknown fields;
- invalid types/ranges;
- bad event/payload/previous digests;
- wrong before/after roots;
- invalid clock/index progression;
- lifecycle-precondition violations;
- malformed message envelopes;
- sequence replay/regression;
- invalid receiver/sender state;
- mailbox overflow;
- corrupt checkpoints;
- wrong genesis/configuration;
- uncertain append/install outcomes.

An incomplete crash tail may recover to the last complete valid event prefix. A complete corrupt historical event is not silently truncated into apparent validity.

## Resource model

M1A is bounded at individual parsing/message/frame boundaries, but legitimate durable history and in-memory registry/projection cost grow with work.

No constant-memory-over-lifetime or throughput claim is made.

Replay cost currently grows with history because checkpoints are not yet authoritative snapshots.

## Structural R0 relationship

`ECS_AUTHORITY/STRUCTURAL_R0/` remains the frozen structural authority.

Its ontology and permitted operations are not replaced by M1A.

M1A does not currently grant entities permission to execute Structural R0 mutations. The Structural R0 bridge/admission layer remains a later milestone.

The existing executable Structural R0 implementation and its tests remain separate authority. No second informal mutation path is created by the ECS kernel.

## Scientific boundary

`science/` contains the closed Branch35–40 scientific lineage.

The closed Branch40 result remains bounded to its frozen regime:

- terminal result: `PASS_BRANCH40_WEAK_S3_DYNAMICAL_RELEVANCE`;
- ECS-facing position: `Outcome_A_RETAIN_FULL_ACTIVE_S3`.

That evidence supports retaining the full active S3 representation under the tested regime. It does not establish global Markov sufficiency, minimal state dimension, universal width independence, semantic memory, reasoning, learning optimality, runtime admission, or autonomous self-improvement.

M1A does not reinterpret or extend those claims.

## Topology

Interaction-derived topology is intentionally deferred.

A future topology layer should derive canonical connectivity only from kernel-verifiable committed interaction facts. An entity's self-reported topology observation must not by itself manufacture an authoritative graph edge.

No current M1A API grants topology authority.

## Projector, TRM, DarwinianMatrix and Grid81

These systems remain outside M1A execution authority.

The intended long-term architecture keeps proposal/refinement separate from deterministic admission:

```text
entity / proposer
-> bounded proposal
-> evaluation/refinement surfaces
-> deterministic Elpis admission boundary
-> explicitly authorized execution
```

DarwinianMatrix does not acquire direct Grid81 or Structural R0 mutation authority merely by being connected to ECS.

The current Semantic IR/Grid81 surface is not assumed to represent Structural R0. Existing E0R2 evidence remains `SEMANTIC_IR_INSUFFICIENT` for that representation question.

## Cross-process transport and federation

Cross-process authority remains unresolved.

A deterministic digest over public fields is not a capability credential.

Future federation/transport requires an authenticated principal/issuer model before remote messages can inherit any authority beyond untrusted proposal transport.

SAM, if used later, remains transport/identity/discovery infrastructure rather than semantic authority.

## Security and trust boundary

Qualified M1A guarantees are for a cooperative same-process kernel using supported POSIX primitives and one live owner of a durable history.

Not claimed:

- protection against arbitrary malicious Python code with trusted-kernel introspection/mutation capability;
- hostile privileged filesystem replacement;
- cryptographic remote identity;
- universal physical-power-loss guarantees across all storage hardware;
- Windows/non-POSIX persistence equivalence;
- safe sharing of a live kernel across `fork`;
- detection of a wholly rewritten valid history without an external trusted head.

The log hash chain provides tamper evidence relative to a trusted starting/head authority; it is not a signature scheme.

## Qualification

The source test suite exercises:

- entity lifecycle;
- sender attribution and port lifetime;
- messaging and sequencing;
- scheduler determinism;
- state-root completeness;
- replay clock/index validation;
- checkpoint corruption;
- persistence framing;
- short/zero writes;
- crash/fault boundaries;
- concurrent read/write serialization;
- durable restart;
- hash-seed determinism;
- malformed/corrupt persistent input;
- bounded resource validation.

Qualification programs are executable code only. Generated reports and machine-local evidence are intentionally kept outside the repository source surface.

The finalized M1A audit demonstrated, among other checks:

- deterministic concurrent reader/writer closure with live/reopened root equality;
- fail-closed checkpoint-tail corruption;
- abrupt-process crash recovery across mutation boundaries;
- independent history/replay equality across multiple Python versions, hash seeds, and restart schedules;
- unchanged frozen ECS authority/science bytes.

Those qualification results are evidence for this engineering state, not scientific authority and not runtime admission.

## Packaging

The Python package is `elpis_ecs` and is sourced from `ECS/runtime`.

`pyproject.toml` contains the package-discovery integration required for local wheel installation.

Packaging does not widen runtime authority; it only makes the qualified M1A mechanical API importable as a normal Python package.

## Deferred milestones

The next ECS milestones remain separate admission decisions:

1. interaction-derived topology projection;
2. bounded Structural R0 proposal/admission bridge;
3. observability/health/resource accounting where they affect runtime operation;
4. transport and authenticated cross-process authority;
5. federation;
6. Projector/TRM/DarwinianMatrix integration;
7. future Semantic IR/Grid81 successor work where supported by new evidence.

Each later milestone must preserve the M1A invariants: deterministic authority boundaries, replayability, provenance, local sovereignty, capability-scoped mutation, and no silent semantic-authority escalation.

## Nonclaims

M1A does not claim:

- semantic truth;
- global Markov sufficiency;
- minimal sufficient state;
- exact gauge/null equivalence;
- universal width independence;
- human-like memory/reasoning;
- learned-refinement efficacy;
- Darwinian/evolutionary efficacy;
- autonomous semantic control;
- remote authentication;
- federation trust;
- topology truth;
- Structural R0 mutation admission;
- Grid81 mutation authority;
- runtime admission;
- autonomous self-improvement.

It is a deterministic, same-process, replayable ECS mechanics layer on which later explicitly-authorized Elpis components can be built.
