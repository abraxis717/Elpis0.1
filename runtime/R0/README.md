# Elpis Runtime Integration R0 — Deterministic Structural Transaction

## Mission

Create the first deterministic beginning-to-end Elpis runtime transaction
using qualified components from the canonical R1 assembly at:

```
$ELPIS_CANON_ROOT/Elpis_Canon/Elpis
```

## Transaction Pipeline

```
RequestContext → P0 projection → Grid81 read → scope derivation
  → StructuralOracle → adjudication → Darwinian episode
  → decoder → AST validator → receipt
```

## Disposition

```
ELPIS_RUNTIME_INTEGRATION_R0_DETERMINISTIC_TRANSACTION_QUALIFIED
```

## Package Structure

```
R0/
├── pyproject.toml
├── README.md
├── src/elpis_runtime_r0/
│   ├── __init__.py
│   ├── composition.py     # Authority binding and rules
│   ├── contracts.py       # Receipt and intermediate data types
│   ├── adapters.py        # Bridges to canonical component APIs
│   ├── transaction.py     # Full pipeline orchestrator
│   ├── receipt.py         # Receipt serialization and verification
│   ├── replay.py          # Cross-process determinism testing
│   └── errors.py          # Typed fail-closed error hierarchy
└── tests/
    └── test_r0_transaction.py
```

## Running

```bash
export CUDA_VISIBLE_DEVICES=""
export PYTHONPATH="$ELPIS_CANON_ROOT/Elpis_Canon/Elpis/TRMFractalSpine/src:$ELPIS_CANON_ROOT/Elpis_Canon/Elpis/Pipeline/P0ControlProtocol/src:$ELPIS_CANON_ROOT/Elpis_Canon/Elpis/Grid81DeterministicStructuralAdjudicator/src:$ELPIS_CANON_ROOT/Elpis_Canon/Elpis/Grid81StructuralSemantics/src:$ELPIS_CANON_ROOT/Elpis_Canon/Elpis:src:$PYTHONPATH"
cd $ELPIS_CANON_ROOT/Elpis_Canon/Elpis_Runtime_Integration/R0
python -m pytest tests/ -v
```

## Authority Rules

- **P0 projector**: structural description only
- **StructuralOracle**: structural transition authority
- **Grid81 adjudicator**: validation and adjudication only
- **DarwinianMatrix**: lifecycle, fitness, selection, heredity, retirement, episode records
- **P0 decoder**: deterministic offline artifact generation
- **AST validator**: artifact validation
- **R0 integration**: transaction composition and receipt assembly only

Runtime admission: **FALSE**

## Test Results

26 tests, all passing:
- 11 happy-path tests (projection, receipt, determinism, authority)
- 10 negative fail-closed tests (malformed input, missing state, mutation detection)
- 5 authority boundary and determinism tests

## Excluded from R0

HACF retrieval, Semantic Structural Spine, RAG, learned TRM, model inference,
sandbox execution, governance, persistent memory, network serving, Blackwell.
