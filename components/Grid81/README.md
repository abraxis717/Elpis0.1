# Grid81

The local publisher R1 revision coordinates production reads with canonical
publication using a shared lock on the persistent `Canonical` directory inode.
`load_current_grid81` holds this lock across HEAD, generation and sidecar reads;
the writer holds it exclusively through validation, reservation, exchange and
cleanup. This closes the multi-file reader race that directory exchange alone
cannot prevent. The reader remains read-only and requires POSIX directory flock.
See [the R1 protocol](../Grid81DeterministicCanonicalPublisher/R1_PROTOCOL.md)
for the recovery and filesystem trust boundary.

Grid81 contains historical sealed state and a reader used by Elpis to verify, load, and consume a canonical Grid81 generation.

The supplied historical state is **canonical generation `000001`**, committed under `state/Canonical/Grid81`, loaded through a reusable production reader, and consumed by the Elpis Header runtime observer.

## Qualified mutation and replay boundary

The **Elpis2.1.16 released public boundary** is read-only: canonical generation
`000001`, the production reader, and the runtime reducer are shipped there
without an in-repository canonical writer.

The post-2.1.16 successor engineering lineage now contains a qualified,
explicitly authorized writer chain outside the normal runtime read path:

```text
Grid81DeterministicCanonicalPromotionPlanner
        |
        v
Grid81DeterministicCanonicalPromotionAuthority
        |
        v
Grid81DeterministicCanonicalCandidateConstructor
        |
        v
DurableApplicationLedger reservation
        |
        v
Grid81DeterministicCanonicalPublisher
        |
        v
Canonical/Grid81
        |
        v
canonical_reader.py post-verification
```

The boundaries are intentionally strict:

- the promotion planner remains advisory, non-executable, non-self-applying,
  and non-authoritative;
- promotion authority issues a deterministic one-use capability only after an
  explicit external operator-approval digest is supplied;
- that digest binds approval input but is not claimed to authenticate a human,
  prove private-key possession, or constitute a digital signature;
- the candidate constructor works in an isolated output tree and must not
  mutate live canonical state or consume the publication ledger;
- the publisher requires the exact promotion capability rather than bare
  digests;
- the durable SQLite ledger provides cross-process reservation and replay
  history for publication;
- publication preserves all historical generation bytes, performs atomic
  exchange, and verifies committed state through the production reader;
- ECS world mutation remains unauthorized.

The historical `.authority_audit.json` was produced by the original generation
`000001` promotion flow. Its fields remain historical assertions rather than
independent observations of authority, network use, mutation, or publication.

The earlier process-local `ApplicationLedger` still proves consumption only
inside one in-memory instance. It must not be confused with the later
`DurableApplicationLedger`, which is the publication-reservation primitive used
by the successor writer chain.


## Current runtime path

```text
Canonical/Grid81/HEAD.json
        │
        ▼
Grid81/canonical_reader.py
  load_current_grid81(project_root)
        │
        ▼
components/elpis_header/src/elpis_header/observer/grid81_reducer.py
  load_grid81_runtime_state(project_root)
        │
        ▼
Grid81RuntimeState
```

The runtime path is **HEAD-first**. Production code must not hard-code or directly select `generations/000001.json` as its default loading path.

## Canonical state

The canonical directory contains exactly seven files:

```text
Canonical/Grid81/
├── .authority_audit.json
├── .consumed_capability.json
├── .consumption_receipt.json
├── .source_nonmutation_audit.json
├── .transaction_manifest.json
├── HEAD.json
└── generations/
    └── 000001.json
```

### Critical rule: do not add documentation to `Canonical/Grid81`

The canonical reader rejects unexpected files. A `README.md`, editor backup, cache file, temporary file, or other unmanifested artifact placed inside `Canonical/Grid81` invalidates the canonical directory contract.

Documentation belongs in this `Grid81/` source directory or beside the consuming runtime module, never inside the sealed canonical directory.

## Production reader

`Grid81/canonical_reader.py` exposes the production API:

```python
from pathlib import Path

from Grid81.canonical_reader import (
    CanonicalReadError,
    Grid81CanonicalState,
    load_current_grid81,
)

state: Grid81CanonicalState = load_current_grid81(
    Path("$ELPIS_CANON_ROOT/Elpis_Canon")
)
```

`Grid81CanonicalState` is an immutable runtime-facing representation. The reader:

- resolves `Canonical/Grid81/HEAD.json` first;
- rejects symlinks and path traversal;
- validates the generation number and generation path;
- verifies the raw generation file hash;
- verifies the generation semantic digest;
- preserves transaction and capability identity;
- checks that stored capability fields declare one consumption; this does not prove one-time consumption;
- rejects replay-permitted capability state;
- verifies the six ordinary transaction-manifest hashes;
- applies the `INTENTIONALLY_UNHASHED_SELF_ENTRY` policy to the manifest self-entry;
- rejects unexpected canonical files;
- returns immutable data;
- performs no writes;
- fails closed with `CanonicalReadError` and typed rejection codes.

## Runtime consumer

The production runtime boundary is:

```text
components/elpis_header/src/elpis_header/observer/grid81_reducer.py
```

Its public entry point is:

```python
from pathlib import Path

from elpis_header.observer.grid81_reducer import load_grid81_runtime_state

runtime_state = load_grid81_runtime_state(
    Path("$ELPIS_CANON_ROOT/Elpis_Canon")
)
```

The reducer converts `Grid81CanonicalState` into the frozen `Grid81RuntimeState` consumed by Elpis runtime components. It preserves:

- canonical generation number;
- generation semantic digest;
- transaction ID;
- capability ID;
- structural schema identity;
- deterministic runtime projection digest.

It must not consult phase reports, reconstruct the D.2 package, fall back to a direct generation path, or write into canonical state.

## Failure model

Canonical loading is fail-closed. Representative rejection classes include:

```text
HEAD_NOT_FOUND
HEAD_MISSING_GENERATION
HEAD_MISSING_GENERATION_PATH
GENERATION_NOT_FOUND
GENERATION_RAW_HASH_MISMATCH
SEMANTIC_DIGEST_MISMATCH
TRANSACTION_ID_MISMATCH
CAPABILITY_ID_MISMATCH
MANIFEST_TRANSACTION_ID_MISMATCH
MANIFEST_CAPABILITY_ID_MISMATCH
CAPABILITY_NOT_CONSUMED
RECEIPT_NOT_COMMITTED
MANIFEST_FILE_MISSING_*
MANIFEST_HASH_MISMATCH_*
UNEXPECTED_CANONICAL_FILES
SYMLINK_REJECTED
PATH_TRAVERSAL_REJECTED
INVALID_JSON_*
```

Callers should catch `CanonicalReadError`; they must not silently fall back to precommit evidence or a hard-coded generation file.

## Verification

### Postcommit runtime-consumer suite

Run against the committed live root:

```bash
cd $ELPIS_CANON_ROOT/Elpis_Canon

$ELPIS_CANON_ROOT/Elpis/venv_cuda/bin/python3 -m pytest -q \
  -p no:asyncio \
  Grid81/test_g53ig1_adversarial_runtime_consumer.py
```

Qualified result:

```text
28 passed
0 failed
```

The suite covers malformed or missing HEAD state, generation tampering, transaction and capability mismatches, symlinks, manifest tampering, lifecycle corruption, missing canonical records, unexpected files, and cross-field inconsistency.

### Legacy promotion regression

The original 314-test C-through-E qualification suite contains precommit invariants that require `Canonical/Grid81` to be absent. It must not be evaluated against the committed live root and its live-root failures must not be reclassified as passes.

Run it unchanged in an isolated precommit replica that:

- contains the unchanged source and test files;
- has `Canonical/` present;
- has `Canonical/Grid81` absent;
- appears inside the test namespace at `$ELPIS_CANON_ROOT/Elpis_Canon`;
- uses no `conftest.py` monkeypatches;
- uses no modified expected hashes, paths, tests, or executor code.

Qualified result:

```text
314 passed
0 failed
0 skipped
0 errors
```

## Development rules

1. **Never modify `Canonical/Grid81` during reader, consumer, or integration development.**
2. **Runtime consumers remain read-only; canonical publication must use the separately authorized successor writer chain.**
3. **Never create generation `000002` without a separately authorized promotion phase.**
4. **Never add files to the canonical directory.**
5. **Never treat a phase verifier as a runtime consumer.**
6. **Never convert expected failures or skipped tests into passing gates.**
7. **Keep production reader code outside `g53i*` phase harnesses.**
8. **Keep runtime consumers in normal production packages.**
9. **Preserve HEAD-first resolution.**
10. **Return immutable runtime state and fail closed.**

## Relevant source files

```text
Grid81/canonical_reader.py
Grid81/test_g53ig1_adversarial_runtime_consumer.py
components/elpis_header/src/elpis_header/observer/grid81_reducer.py
components/elpis_header/src/elpis_header/observer/__init__.py
components/Grid81DeterministicCanonicalPromotionAuthority/src/elpis_grid81_promotion_authority/authority.py
components/Grid81DeterministicCanonicalCandidateConstructor/src/elpis_grid81_candidate_constructor/constructor.py
components/Grid81DeterministicCanonicalPublisher/src/elpis_grid81_canonical_publisher/publisher.py
components/Grid81DeterministicCapabilityApplicationExecutor/src/elpis_grid81_application_executor/durable_ledger.py
tests/test_grid81_canonical_writer_chain_r0.py
```

The earlier documentation referenced `g53ie_production_atomic_grid81_canonical_promotion_executor.py`. That historical phase executor remains absent and is not the successor writer API. The post-2.1.16 writer chain is implemented instead by the normal production components listed above. Available phase-named `g53i*` modules remain qualification, forensic, or evidence machinery rather than the runtime/publication API.

## Evidence and reports

The completed Grid81 promotion and integration chain is recorded under:

```text
reports/G5_3I_F_OperatorAuthorizedGrid81CanonicalCommit/
reports/G5_3I_F_1_PostCommitCanonicalVerificationEvidenceCorrection/
reports/G5_3I_F_1_1_PostCommitEvidenceClosure/
reports/G5_3I_F_1_1_1_TransactionManifestContractSemanticsClosure/
reports/G5_3I_G_PostCommitCanonicalIntegrationVerification.before_G1/
reports/G5_3I_G_1_ProductionRuntimeIntegrationAndRegressionReconciliation/
```

The authoritative terminal disposition is:

```text
G53IG1_PRODUCTION_RUNTIME_INTEGRATION_AND_REGRESSION_RECONCILED
```

The pipeline state is:

```text
GRID81_CANONICAL_GENERATION_000001_PRODUCTION_RUNTIME_INTEGRATION_VERIFIED
G5.3I_COMPLETE
```

## Architectural boundary

Grid81 now has distinct read and promotion layers:

| Layer | Responsibility | Mutability |
|---|---|---|
| Canonical state | Generation history, authority, receipt, manifest and HEAD | Append-only through authorized publication |
| Production reader | Validate and normalize canonical state | Read-only |
| Runtime reducer | Convert canonical state into Elpis runtime state | Read-only |
| Promotion planner | Advisory readiness and bounded intentions | Read-only / non-executable |
| Promotion authority | Issue one-use publication capability from explicit bound authority | No canonical writes |
| Candidate constructor | Build isolated immediate-successor candidate | Candidate tree only |
| Durable publication ledger | Cross-process reservation and replay history | Durable ledger only |
| Atomic publisher | Commit an authority-bound candidate and verify it | Canonical write boundary |

Normal runtime consumers remain read-only. Promotion and publication require a
separate explicit authority path and are not implicit runtime behavior.
