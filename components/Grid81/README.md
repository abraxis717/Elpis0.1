# Grid81

Grid81 is the sealed structural substrate used by Elpis to promote, verify, load, and consume a canonical Grid81 generation.

The current qualified state is **canonical generation `000001`**, committed under `Canonical/Grid81`, loaded through a reusable production reader, and consumed by the Elpis Header runtime observer.

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
    Path("/mnt/primesauce/Elpis_Canon")
)
```

`Grid81CanonicalState` is an immutable runtime-facing representation. The reader:

- resolves `Canonical/Grid81/HEAD.json` first;
- rejects symlinks and path traversal;
- validates the generation number and generation path;
- verifies the raw generation file hash;
- verifies the generation semantic digest;
- preserves transaction and capability identity;
- verifies that the canonical capability is consumed exactly once;
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
    Path("/mnt/primesauce/Elpis_Canon")
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
cd /mnt/primesauce/Elpis_Canon

/mnt/primesauce/Elpis/venv_cuda/bin/python3 -m pytest -q \
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
- appears inside the test namespace at `/mnt/primesauce/Elpis_Canon`;
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
2. **Never call the promotion writer from runtime code.**
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
Grid81/g53ie_production_atomic_grid81_canonical_promotion_executor.py
components/elpis_header/src/elpis_header/observer/grid81_reducer.py
components/elpis_header/src/elpis_header/observer/__init__.py
```

The phase-named `g53i*` modules are promotion, qualification, forensic, or evidence machinery. They are not the normal runtime API.

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

Grid81 now has three distinct layers:

| Layer | Responsibility | Mutability |
|---|---|---|
| Canonical state | Sealed generation, authority, receipt, manifest and HEAD | Immutable after commit |
| Production reader | Validate and normalize canonical state | Read-only |
| Runtime reducer | Convert canonical state into Elpis runtime state | Read-only |

Promotion and evidence generators remain outside this runtime path.
