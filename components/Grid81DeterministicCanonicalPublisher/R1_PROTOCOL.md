# Grid81DeterministicCanonicalPublisher R1 protocol

R1 serializes canonical publication mechanics and makes crash recovery
monotonic. The canonical directory visibility switch is atomic. The SQLite
reservation and filesystem exchange are **not** one atomic transaction.

## Synchronization and authority

The logical namespace is the Grid81 canonical publication domain of one project.
The physical lock object is the existing `Canonical` **directory inode** in the
resolved project root. `canonical_namespace_lock` opens it with
`O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC`, takes `flock`, and checks that
the named and opened device/inode still agree. It does not create a lock file,
create a parent, change permissions, or delete/recreate a lock object.

Writers take `LOCK_EX`; production readers take `LOCK_SH` for their entire
multi-file read. The publisher calls the same reader implementation through its
private already-locked entry point for live reads, avoiding recursive flock on
a second descriptor. Candidate reads use the public reader on a separate root.

`Canonical/Grid81` is exchanged; `Canonical` is never exchanged. A nonempty
directory cannot be unlinked like a lock file. Creating, deleting or replacing
caller lock files has no effect on this domain. Relative paths, redundant dot
components, valid dotdot paths and symlinked project roots resolve to the same
directory. Bind aliases sharing that directory inode also share flock; separate
physical copies are separate namespaces. Symlinked `Canonical` parents and
symlinked `Grid81` targets are rejected. Separate project parents do not block
one another.

The lock grants no semantic authority. The existing promotion capability class
`GRID81_ATOMIC_CANONICAL_PUBLISHER_R0`, its policy digest, grants, one-use bounds,
and validation remain unchanged. R1 names the mechanics revision; it does not
issue a new permission class. ECS, proposals, structural science and runtime
admission remain outside this boundary.

## API migration

```python
publish_candidate(
    *, project_root, candidate_root, ledger, promotion_capability,
    lock_path=None,
)
publication_lock_path(project_root)  # resolved root / "Canonical"
```

The existing entry point and result type remain. `lock_path` is now optional
and asserts the derived domain. A supplied alternate path fails with
`WRONG_LOCK_DOMAIN`; a symlink used as the lock argument also fails. It is never
silently ignored. All repository call sites were migrated and tested: publisher
fixture, constructor publication test, and three calls in the root writer-chain
test. External callers using arbitrary lock files must omit the argument or use
the helper. This is an intentional fail-closed configuration incompatibility.

R1 requires `DurableApplicationLedger`; the old duck-typed in-memory ledger
cannot promise process recovery and receives `DURABLE_LEDGER_REQUIRED`.
`storage_identity` exposes the durable database's host-local device/inode for
recovery metadata and detects replacement of its named file. No ledger schema,
append algorithm, hash identity or `applied_artifacts` semantics changed.

## Writer-chain census and control flow

```text
G5.3B structural artifact / G5.3C shadow application evidence
        ↓ promotion plan + decision + source chain + operator approval digest
CanonicalPromotionAuthority.issue_promotion_capability
        ↓ exact one-use capability
CanonicalCandidateConstructor.construct_candidate
        ↓ immutable, isolated candidate
publisher: capability validation (pre-lock)
        ↓ publisher-derived exclusive Canonical-parent lock
live reader + candidate reader + capability/candidate/history validation
        ↓ exact receipt identity + ledger/recovery reconciliation
stage copy → tree fsync → exchange support probe
        ↓ fsynced target recovery record (PREPARED)
durable ledger append / recognition of exact existing reservation
        ↓ RESERVED_NOT_VISIBLE
renameat2(RENAME_EXCHANGE) → canonical-parent fsync
        ↓ VISIBLE_UNVERIFIED
production-reader verification under existing writer lock
        ↓ VISIBLE_VERIFIED
old stage cleanup → parent fsync → unlock / CLOSED
```

| Boundary and implementation | Authority input / validation | Mutable state and crash-visible output | Retry / concurrency |
|---|---|---|---|
| Application executor `application.py`, `artifact.py`, `ledger.py`, `durable_ledger.py` | 17 guards bind structural artifact, shadow state, contract, capability, lifecycle, scope, expected head; receipt digest binds application output | Inert shadow state and application ledger, never canonical files | In-memory ledger is process-local; durable append is CAS. This upstream ledger is distinct from publication ledger |
| Promotion authority `authority.py`: `_source_record`, `_transaction_id`, `issue_promotion_capability`, `require_promotion_capability` | READY plan/decision/source-chain continuity, explicit approval digest, actual canonical reader, source artifact and structural capability, application receipt/state/ledger evidence, separate publication head | Produces deterministic capability data only | Issuance may become stale immediately; publisher must revalidate. Approval digest is a binding, not operator authentication |
| Constructor `constructor.py`: `_validate_structural_artifact`, `_validate_authority_against_current`, `_generation_record`, `construct_candidate` | Full/semantic artifact digests, authorized structural-capability relation, UNAPPLIED state, exact source generation/digests; target transaction/capability | Isolated temporary build, copied history, v2 generation, HEAD, consumed projection, receipt, audits and manifest; no live or ledger writes | Existing/inside-live output rejected; source inventory before/after checked; interrupted build confers no authority |
| Publisher pre-lock | Capability schema, class, policy, grants, deterministic ID/digest; canonicalized root and optional lock assertion; durable ledger type | No publication mutation; target existence is only an early layout check | Live source observations from issuance/construction are never trusted without under-lock reads |
| Namespace lock | No capability derived from lock access; stable directory descriptor and inode check | Advisory kernel lock only | Process death closes descriptor; other writers then re-read all live state. Readers hold shared locks |
| Under-lock publisher validation | Live and candidate readers; hex IDs; promotion target/source binding; generation n+1; prior semantic binding; exact historical bytes; consumed-capability projection; receipt/manifest hashes | Reads current digest/generation/semantic digest, exact receipt, artifact association and current ledger head, target recovery record, complete candidate tree digest | Stale/future writers fail. Conflicting pending identity fails before stage cleanup or append |
| Stage / probe | Exact validated candidate tree inventory; copied tree and source rehashed after copy; Linux exchange support proven | Full-digest sibling stage, fsynced files/directories; two probe directories exchanged twice and removed | Unreserved stages have no authority. Exact retry rebuilds its own stage. Probe failure reserves nothing |
| Recovery record | Full v1 publication payload digest, complete tree digest, host-local ledger identity | `.Grid81.publisher-r1.json`, written via fsynced temporary file, atomic replace and parent fsync | PREPARED excludes conflicts even if append never happened. Partial `.tmp` is ignored; exact retry can rewrite it |
| Durable reservation | Exact expected head + receipt digest + source artifact digest | One committed SQLite entry plus artifact association; filesystem may still be old | `BEGIN IMMEDIATE`, full verification and expected-head check inside write transaction, unique receipt and nonempty artifact, FK association; exact retry does not append |
| Exchange | Only validated/reserved exact stage | One atomic directory exchange; a crash can leave either old or new visible around persistence | No two-rename fallback. New-visible retry never invokes exchange. Unsupported primitive fails closed |
| Verification | Same production loader while exclusive lock is held; resulting digest and generation | New canonical already visible to a reader after writer death; otherwise readers wait for lock | Verification error retains new state and exact recovery material; no rollback to old canonical |
| Cleanup | Exact publication already visible and verified | Stage now contains old tree; may be partially deleted on crash; parent fsynced | Exact retry verifies visible tree, fsyncs visibility, then removes remaining old stage. Conflict cannot delete another publication's stage |

## Immutable identity and mutable revalidation

The portable publication receipt remains
`elpis.grid81.atomic-publication-receipt.v1`, byte-for-byte the same schema.
Its digest binds artifact digest, promotion capability digest, source canonical
digest, resulting canonical digest, generation number, raw generation SHA-256,
generation semantic digest, transaction ID, capability ID and expected previous
publication-ledger head. These fields were already sufficient semantic identity;
no machine path or cosmetic lock-domain field was added.

Transaction ID is domain-hashed by promotion authority from plan, decision,
source chain, approval, source canonical/semantic identities, target generation
and expected publication head. Capability ID and digest are recomputed by the
authority validator. Constructor generation, HEAD, consumed projection,
consumption receipt and transaction manifest bind the same IDs and hashes.
Publisher `_validate_candidate_promotion_bindings`,
`_validate_live_source_promotion_bindings`, `_validate_successor` and
`_validate_candidate_sidecars` enforce those relations at publication.

The recovery record has its own new schema,
`elpis.grid81.publication-recovery.v1`. It retains the complete receipt payload,
receipt digest, full candidate tree digest and local database inode identity.
The latter two are recovery constraints, not new semantic capability grants or
portable receipt fields. Candidate pathname and staging pathname are not
authority. A byte-identical candidate moved to another root resumes normally.

Every mutable decision is made under the exclusive lock: live canonical digest,
generation, semantic digest, promotion source bindings, successor and history,
ledger verification/snapshot/head, reserved receipt, artifact association and
target recovery record. Candidate validation currently stays under lock too.
SQLite append independently rechecks its head under its own write transaction;
unrelated ledger appenders can cause a fail-closed stale-head result, never a
publication using the stale observation. Publication is best served by a
dedicated ledger; another component advancing it after a pending reservation
blocks old-visible recovery with `LEDGER_ADVANCED_AFTER_RESERVATION`.

## Exact state machine

| State | Inference | Fresh / exact retry | Conflicting caller | Visibility and cleanup |
|---|---|---|---|---|
| NO_RESERVATION | No pending target record for source; no exact ledger entry; live source | Fully validate, stage and probe; then prepare record | May compete, only one lock holder proceeds | Old canonical; orphan stage is inert |
| PREPARED | Target record binds exact object/ledger/tree; exact ledger entry absent; live source; expected head still current | Only exact object may append | `PUBLICATION_RESERVATION_CONFLICT`, even if caller binds advanced head | Old canonical; record remains durable; exact candidate needed to rebuild stage |
| RESERVED_NOT_VISIBLE | Exact receipt/previous-head entry plus artifact association; live source; reserved entry is ledger head | Revalidate source/history, rebuild stage, probe, exchange; `resumed=True`; no append | Reservation conflict; different database is ledger mismatch | Old canonical; conflicting caller cannot clean recovery material |
| VISIBLE_UNVERIFIED | Exact reservation; live result; writer died/failed before verification | Re-read/verify exact live tree and original capability, fsync parent before deleting old stage; never exchange | Same-source other object conflicts | New canonical is available after kernel releases dead writer's lock; stage is old tree |
| VISIBLE_VERIFIED | Same identities; successful production verification | Safe cleanup/finalization | Same-source conflict; valid next-source writer may proceed after verifying predecessor record/receipt/tree | New canonical; no backward exchange |
| CLOSED | Visible verified result and cleanup complete | `ALREADY_COMMITTED`, `resumed=True`; no second receipt or exchange | Same-source conflict; immediate next generation may publish | New canonical; record retained to protect source reservation and bind ledger |

VISIBLE_UNVERIFIED/VERIFIED are knowledge states, not stored flags. Recovery
always verifies again. A new successor replaces the last record only when its
source is the verified previous result and the previous exact ledger receipt
still exists. Historical generations remain in the live chain. A delayed retry
of an older generation after further progress fails closed; it never restores
an earlier generation.

If a process dies before PREPARED, a different valid publication may win; an
unreserved stage cannot exclude it. If it dies after PREPARED, only the exact
object can finish, even before SQLite append. There is no automatic timeout or
reservation cancellation. This sacrifices availability when the caller loses
its immutable candidate/capability, rather than inventing replacement authority.

## Conflict taxonomy and recovery errors

| Case | R1 behavior |
|---|---|
| A: exact duplicate | One reservation, one successor; one fresh `COMMITTED/False`, subsequent `ALREADY_COMMITTED/True`; ledger-ahead exact recovery `COMMITTED/True` |
| B: same source, different candidate/object | Pending or closed same-source record gives `PUBLICATION_RESERVATION_CONFLICT` |
| C: same candidate, different capability | Invalid under existing authority semantics: transaction/capability IDs or exact consumed projection mismatch; issuing another capability does not authorize reusing candidate bytes |
| D: source became stale while waiting | Under-lock revalidation; known same-source record gives reservation conflict, otherwise `STALE_CANONICAL_HEAD`; no second n+1 |
| E: future successor | `STALE_CANONICAL_HEAD` (or specific source/successor binding error); no leapfrogging |
| F: ledger-ahead crash | Exact pending identity resumes; a newly issued capability for the same still-visible source and advanced ledger head is excluded by target record |
| Incorrect caller lock | `WRONG_LOCK_DOMAIN` before publication mutation |
| Unavailable or replaced lock parent | `PUBLICATION_LOCK_UNAVAILABLE` / `PUBLICATION_LOCK_INVALID` |
| Different durable DB for existing namespace | `PUBLICATION_LEDGER_MISMATCH` |
| Malformed recovery record / visible tree mismatch | `INVALID_RECOVERY_STATE` |
| Stage symlink/non-directory or copy changed | `CORRUPTED_STAGING_STATE`; a damaged ordinary old-visible stage can be rebuilt from exact original input |
| Incompatible ledger head | `STALE_LEDGER_HEAD` or `LEDGER_ADVANCED_AFTER_RESERVATION` |
| Incompatible artifact reservation | Existing `ARTIFACT_LEDGER_CONFLICT` and exact-receipt checks retained |

An exact R0 receipt is recognizable without changing its bytes and can bootstrap
the R1 record, both old-visible and new-visible. Fresh bootstrap accepts an empty
ledger. A nonempty opaque legacy ledger without an exact known reservation or
R1 record cannot establish fresh R1 authority: `UNBOUND_PUBLICATION_LEDGER`.

An already-visible exact retry returns the original reserved entry digest as
`resulting_ledger_head`, even if unrelated entries were subsequently appended;
the returned receipt does not drift with the current ledger head.
R0 stored receipt hashes, not queryable source-generation payloads, so inferring
that no hidden pending reservation exists would be unsound. Mixed R0/R1 writers
are unsupported; stop old writers before migration. Legacy truncated-name stages
can remain inert. R1 does not silently destroy or adopt them.

## D4 adjacency

`applied_artifacts` is the durable receipt/artifact association and replay
exclusion index. In the canonical publisher, existence means **reservation**,
including the legitimate old-visible crash window; it does not attest successful
filesystem visibility. The application executor has its own shadow-application
semantics. The name is imprecise across these uses, but the behavior is correct.
R1 infers visibility from the reader and exact recovery evidence, so no D4 schema
or naming rewrite is needed. The only ledger addition is local storage identity.

## Invariants and qualification mapping

| Invariant | Enforcement / tests |
|---|---|
| W1 single lock domain | Derived directory lock; controlled lock ordering, all root aliases, unrelated roots, alternate lock rejection, unlink/replacement tests |
| W2 no stale publication | Under-lock reader/source/successor checks; controlled loser, future writer, stress races |
| W3 one reserved successor | Persistent PREPARED/reserved target identity plus ledger CAS; ledger-ahead newly issued capability regression and all crash schedules |
| W4 exact retry idempotence | Exact receipt lookup; visible branch skips exchange; duplicate stress and old/new-visible crash retries |
| W5 conflicting retry exclusion | Record equality includes semantic receipt and tree; conflicting process restart and untouched corrupted stage tests |
| W6 reader atomicity | Shared reader lock for entire read; paused HEAD-to-sidecars schedule and three-reader successive-generation runs |
| W7 history immutability | Byte comparison before first publication; history assertions in every stress trial and every sequential reader-test publication |
| W8 capability binding | Original authority tests, cross-capability/candidate tests, original consumed projection checks and tree-bound recovery |
| W9 monotonic recovery | No post-verification rollback; new-visible retry cannot call exchange; all crash points and bounded model |
| W10 lock grants no authority | Original tampered/cross-capability tests remain required; exclusive lock never replaces capability validation |

The bounded dependency-free model explores acquire/validate/prepare/reserve/
expose/verify/close interleavings for two writers, with at most one crash/restart
each. It checks reservation uniqueness and monotonic visibility, and compares
allowed abstract crash-state triples to the implementation's separately checked
fault boundaries. It is a bounded model and boundary correspondence, not a proof
that every Python instruction refines the model.

## Filesystem and operational trust boundary

Linux/POSIX flock and Linux `renameat2(RENAME_EXCHANGE)` on a local filesystem
with working directory fsync are required. SQLite requires working locks and
FULL synchronization. There is no two-rename fallback or cross-host/distributed
lock claim. Filesystem durability ultimately depends on the filesystem and
storage honoring sync. Process-death tests are not physical power-cut tests.

The existing project parent, database and candidate inputs are trusted against
hostile out-of-protocol mutation. Cooperating writers never rename/replace the
Canonical parent, remove recovery records, replace the database or mutate a
candidate during validation/copy. A same-user attacker with directory write
permission can rename the whole parent or rewrite the database; flock cannot
protect against that or a privileged filesystem administrator. Parent replacement
between open and acquisition is detected; arbitrary replacement after the inode
check is outside this trust boundary. Existing ownership/mode policy is not
changed; directory read access lets production readers lock without write access.

Readers may block for the whole writer transaction. No starvation/fairness bound
is promised by flock. Historical/noncooperating readers or writers bypassing this
protocol are not covered by W1/W6. Candidate mutation during construction may
make construction fail; publisher under-lock validation still prevents stale
output from being published. Orphan pre-reservation stages and old stages from
a superseded closed publication may remain after crashes; they are never
reservation authority and are never selected by scanning directories.
