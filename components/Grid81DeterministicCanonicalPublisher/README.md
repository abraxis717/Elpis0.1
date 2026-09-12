# Grid81 Deterministic Canonical Publisher R1

R1 serializes one canonical Grid81 publication namespace, reserves an exact
publication in the durable ledger, and recovers monotonically across the
ledger/filesystem crash window. Only the canonical directory visibility change
is atomic; SQLite reservation and filesystem exchange are separate operations.

```python
from elpis_grid81_canonical_publisher import publish_candidate

receipt = publish_candidate(
    project_root=project_root,
    candidate_root=candidate_root,
    ledger=durable_publication_ledger,
    promotion_capability=promotion_capability,
)
```

The publisher derives its lock from the resolved project root: it exclusively
locks the persistent `Canonical` directory inode. Production readers share-lock
that inode across all HEAD/generation/sidecar reads. The lock survives exchange
of `Canonical/Grid81` and cannot be redirected by a caller-provided lock file.
The optional legacy `lock_path` argument now asserts this derived path; an
alternate path fails with `WRONG_LOCK_DOMAIN`. All repository callers are
migrated. External callers using arbitrary lock paths must update configuration.

The existing capability policy, candidate/history validation, publication receipt
v1 identity, durable ledger CAS/uniqueness, fsync and Linux atomic-exchange
preflight remain. Lock access grants no promotion capability or semantic
permission. Runtime consumers remain read-only. ECS and structural proposal
selection remain outside publication authority.

A fsynced `.Grid81.publisher-r1.json` recovery record beside the target binds the
exact publication payload, complete candidate tree and host-local ledger inode.
It excludes a conflicting successor even when the ledger is ahead and canonical
still shows the old generation. It is recovery metadata, not a portable semantic
receipt. Exact old-visible retries resume without another append; exact
new-visible retries verify and clean up without another exchange. Verification
failure never exchanges backward. A different publication cannot reuse or clear
the pending reservation.

R1 requires Linux/POSIX directory flock, directory fsync, working SQLite durable
locking and `renameat2(RENAME_EXCHANGE)`. There is no gap-producing rename
fallback. Readers may wait for a writer. Cooperating processes must preserve the
Canonical parent inode, recovery record and database; hostile filesystem
replacement and mixed old/new publisher processes are outside the guarantee.

See [R1_PROTOCOL.md](R1_PROTOCOL.md) for the writer-chain census, immutable
identity bindings, API migration, state machine, conflict codes, D4 adjudication,
W1–W10 invariants and trust boundary.

Local qualification evidence is intentionally external to the source tree and is
not publication authority. `COMPONENT_MANIFEST.json` and repository release
registries retain their existing provenance until a later explicit integration/
release phase reconciles successor source inventory. No release or runtime
admission is implied by this DEV worktree.
