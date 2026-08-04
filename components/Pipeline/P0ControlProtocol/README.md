# P0 — Model-Wide Structural and TRM Control Protocol

P0 establishes the deterministic bridge:

```text
request/context
→ StructuralProjection
→ TRM refinement proposal
→ expert activation proposal
→ controller-owned DecoderControlPlan
→ offline Python artifact
→ AST ValidatorEvidence
````

## Authority boundary

```text
TRM proposes
controller executes
P0 shadow account records cost intents
validators assess
production governance remains inactive
```

P0 does not:

* spawn recursive children;
* consume admitted L0 affine authority;
* refund authority;
* hot-load experts;
* attach experts to active token decoding;
* execute generated Python;
* make an HRM bridge authoritative;
* invoke governance;
* write memory.

## Current components

| Component                      | Status         |
| ------------------------------ | -------------- |
| Typed contracts                | Implemented    |
| Canonical hashing              | Implemented    |
| Deterministic Python projector | Implemented    |
| Shadow TRM proposer            | Implemented    |
| Expert proposal layer          | Implemented    |
| Controller allow-list          | Implemented    |
| Deterministic Python decoder   | Implemented    |
| AST validator                  | Implemented    |
| Shadow accounting              | Implemented    |
| Deterministic replay           | Implemented    |
| Real TRM checkpoint            | Not integrated |
| L0 RequestAccount adapter      | Not integrated |
| Child expansion                | Prohibited     |
| Expert loading                 | Prohibited     |
| Sandbox execution              | Prohibited     |
| Governance                     | Inactive       |
| Memory writes                  | Prohibited     |

## Install and test

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
