# Elpis Runtime Integrations

`runtime/` contains the historical qualified offline integration layers that
compose canonical Elpis components into deterministic transactions.

These directories are **not equivalent to the current top-level learned
reference runtime** under `src/elpis_reference/`, and none of them imply full
runtime admission.

## Runtime generations

### R0 — deterministic structural transaction

R0 composes the structural transaction:

```text
RequestContext
→ P0 projection
→ Grid81 / scope
→ StructuralOracle
→ adjudication
→ Darwinian episode
→ deterministic decoder
→ AST validator
→ receipt
```

R0 deliberately excluded learned model inference when it was qualified. That
historical exclusion remains true for R0 itself even though the repository now
also contains a separately runnable learned Samsung TRM reference path.

See [`R0/README.md`](R0/README.md).

### R1 — bounded HACF retrieval + R0

R1 prepends a deterministic, read-only HACF retrieval/evidence stage and then
delegates the structural transaction to R0.

See [`R1/README.md`](R1/README.md).

## Current public status

The top-level public release now additionally provides:

- a runnable pinned learned TRM reference path;
- platform-aware setup/build discovery;
- qualified R7A task-residual contracts;
- semantic/topology reverse-trace foundation.

The production task-residual → DarwinianMatrix Projector RELEASE → learned
re-proposal loop is still being consolidated.

`runtime_admission = false`.

## Portability note

The R0/R1 child READMEs preserve commands from their original qualification
environment. Some of those commands and paths are historical and
platform-specific. They should not be treated as the current universal setup
interface.

For current setup discovery use:

```bash
python tools/setup.py --profile reference --dry-run
python tools/setup.py --profile reference
```

Native builds are selected separately by platform capability.

## Development status

Runtime integration remains active development. Qualified historical
transactions are retained for reproducibility while newer integration seams are
promoted incrementally and fail-closed.
