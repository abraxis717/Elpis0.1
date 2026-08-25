# Elpis Runtime Integration R1

> **Historical qualification layer.** R1 preserves the bounded HACF retrieval
> integration that was qualified before the current platform-aware setup path.
> The architecture remains valid, but the original manual build commands were
> environment-specific. Use `runtime/README.md`, `tools/setup.py`, and current
> CI as the public setup authority.

Bounded pre-refinement retrieval layer backed by canonical HACF.

## Transaction flow

```text
RequestContext -> RetrievalQueryDeriver -> HACFRetrievalProvider
  -> RetrievalBundleValidator -> RetrievalBudgetGuard
  -> EvidenceBoundRequestAdapter -> qualified Runtime R0 transaction
  -> R1 composite receipt
```

## Architecture

R1 inserts a deterministic retrieval stage *before* P0 projection. The
retrieval produces a validated `RetrievalBundle` that becomes an evidence
envelope consumed by downstream R0.

## Safety

- HACF retrieval is read-only during the transaction.
- All budgets are versioned contracts recorded in receipts.
- Fail-closed on budget overflow, epoch drift, or schema mismatch.
- Runtime admission remains FALSE.
- No network model serving or learned-model authority is introduced by R1.

## Current build guidance

The repository now owns a platform-aware setup boundary. Inspect the detected
plan with:

```bash
python tools/setup.py --profile full --dry-run
```

On currently qualified native platforms, the setup layer derives CMake build
commands for `native/hacf` and `native/hacf_bridge`. Native Windows HACF remains
unqualified.

The repository CI is the executable reference for the currently supported Linux
native build path.

## Tests

```bash
pytest runtime/R1/tests/ -v
```

R1 itself remains an offline retrieval + structural transaction layer. The
separate top-level learned TRM reference runtime does not retroactively make R1
a learned-model-serving runtime.
