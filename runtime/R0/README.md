# Elpis Runtime Integration R0 — Deterministic Structural Transaction

> **Historical qualification layer.** R0 remains a qualified deterministic
> structural transaction, but it predates the repository-level learned TRM
> reference runtime. Commands below document the original qualification shape
> and are not the current platform-neutral setup interface. See `runtime/README.md`
> and `tools/setup.py` from the repository root for current setup guidance.

## Mission

Create the first deterministic beginning-to-end Elpis runtime transaction using
qualified structural components.

## Transaction Pipeline

```text
RequestContext → P0 projection → Grid81 read → scope derivation
  → StructuralOracle → adjudication → Darwinian episode
  → decoder → AST validator → receipt
```

## Disposition

```text
ELPIS_RUNTIME_INTEGRATION_R0_DETERMINISTIC_TRANSACTION_QUALIFIED
```

## Package Structure

```text
R0/
├── pyproject.toml
├── README.md
├── src/elpis_runtime_r0/
│   ├── __init__.py
│   ├── composition.py
│   ├── contracts.py
│   ├── adapters.py
│   ├── transaction.py
│   ├── receipt.py
│   ├── replay.py
│   └── errors.py
└── tests/
    └── test_r0_transaction.py
```

## Running from the public repository

The canonical CI composes `PYTHONPATH` from the public component directories and
runs:

```bash
pytest runtime/R0/tests/ -v
```

See `.github/workflows/ci.yml` for the exact current public CI environment.

## Authority Rules

- **P0 projector**: structural description only
- **StructuralOracle**: structural transition authority
- **Grid81 adjudicator**: validation and adjudication only
- **DarwinianMatrix**: lifecycle, fitness, selection, heredity, retirement, episode records
- **P0 decoder**: deterministic offline artifact generation
- **AST validator**: artifact validation
- **R0 integration**: transaction composition and receipt assembly only

Runtime admission: **FALSE**

## Historical exclusion boundary

R0 itself excludes HACF retrieval, learned TRM inference, sandbox execution,
governance, persistent memory, and network serving.

That statement is scoped to **R0**. The repository now contains separate later
layers: R1 adds HACF retrieval, and the top-level `src/elpis_reference/` package
provides a runnable learned Samsung TRM reference path.
