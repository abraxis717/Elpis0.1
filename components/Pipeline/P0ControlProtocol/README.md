# P0 — Model-Wide Structural and TRM Control Protocol

P0 establishes the deterministic control bridge:

```text
request/context
→ StructuralProjection
→ TRM refinement proposal
→ expert activation proposal
→ controller-owned DecoderControlPlan
→ offline Python artifact
→ AST ValidatorEvidence
```

## Authority boundary

```text
TRM proposes
controller executes
P0 shadow account records cost intents
validators assess
production governance remains inactive
```

P0 does not:

- spawn recursive children;
- consume admitted L0 affine authority;
- refund authority;
- hot-load experts;
- attach experts to active token decoding;
- execute generated Python;
- make an HRM bridge authoritative;
- invoke governance;
- write memory.

## Learned TRM status

There are two separate integration states that should not be conflated:

1. **Repository-level learned reference runtime — integrated and runnable.**
   The public root runtime under `src/elpis_reference/` can download, SHA-256 verify,
   strictly normalize/load, and execute the pinned 5,028,866-parameter Samsung
   MLP-T TRM checkpoint for the bounded Sudoku reference task.

2. **P0 learned-checkpoint adapter — not yet integrated.**
   P0 still uses `ShadowTRMProposer`, a deterministic stand-in with proposal-only
   authority. `CoreRuntimeBundle` explicitly identifies it as **not the learned
   TRM**. P0 does not currently invoke the pinned checkpoint during its own
   transaction.

This is intentional while the task-residual → semantic/topology → Projector
release → learned re-proposal seam is being consolidated. The existence of a
working learned reference checkpoint does not by itself make that model part of
P0's authority-bearing transaction.

## Current components

| Component | Status |
| --- | --- |
| Typed contracts | Implemented |
| Canonical hashing | Implemented |
| Deterministic Python projector | Implemented |
| Shadow TRM proposer | Implemented |
| Expert proposal layer | Implemented |
| Controller allow-list | Implemented |
| Deterministic Python decoder | Implemented |
| AST validator | Implemented |
| Shadow accounting | Implemented |
| Deterministic replay | Implemented |
| Repository-level learned TRM reference | Runnable outside P0 |
| P0 learned TRM checkpoint adapter | Not integrated |
| L0 RequestAccount adapter | Not integrated |
| Child expansion | Prohibited |
| Expert loading | Prohibited |
| Sandbox execution | Prohibited |
| Governance | Inactive |
| Memory writes | Prohibited |

## Install and test

From this component directory:

```bash
python3 -m pip install -e '.[test]'
pytest
```

## Demonstration

```bash
elpis-p0 \
  examples/python_add.json \
  --replay-check \
  --output runtime/p0_demo.json
```

## Expected artifact

```python
def add(a, b):
    """Create a typed deterministic Python function that adds two values and validate its AST."""
    return a + b
```

The artifact is parsed and statically inspected but never executed.

## Runtime admission

`runtime_admission = false`. P0's qualified structural/control behavior is not
equivalent to production governance or full Elpis runtime admission.
