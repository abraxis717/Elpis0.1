# Elpis Header Observer: Grid81 Runtime Integration

This package contains the production observer boundary that converts the sealed Grid81 canonical generation into immutable Elpis runtime state.

## Entry point

```python
from pathlib import Path

from elpis_header.observer.grid81_reducer import load_grid81_runtime_state

state = load_grid81_runtime_state(
    Path("$ELPIS_CANON_ROOT/Elpis_Canon")
)
```

The function returns a frozen `Grid81RuntimeState`.

## Data flow

```text
Canonical/Grid81/HEAD.json
        │
        ▼
Grid81.canonical_reader.load_current_grid81
        │
        ▼
elpis_header.observer.grid81_reducer.load_grid81_runtime_state
        │
        ▼
Grid81RuntimeState
```

## Responsibilities

The observer must:

- use the production canonical reader;
- resolve canonical state through `HEAD.json`;
- preserve generation number and semantic digest;
- preserve transaction and capability identity;
- preserve the Grid81 structural schema;
- produce a deterministic runtime projection digest;
- return immutable runtime state;
- propagate canonical read failures;
- perform no writes;
- create no runtime object when canonical validation fails.

## Prohibited behavior

The observer must not:

- import a `g53i*` phase harness;
- call the promotion writer;
- use `verify_committed_state` as its runtime API;
- read phase reports as runtime input;
- reconstruct the D.2 package;
- hard-code `generations/000001.json` as the default source;
- fall back after a HEAD failure;
- modify `Canonical/Grid81`;
- cache mutable canonical dictionaries.

## Testing

The production reader and runtime boundary are jointly exercised by:

```text
Grid81/test_g53ig1_adversarial_runtime_consumer.py
```

Run:

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

Every adversarial rejection must prove both:

1. the canonical reader rejected the malformed state; and
2. the observer produced no `Grid81RuntimeState`.

## Canonical-directory warning

Do not place a README or any other file inside `Canonical/Grid81`. The production reader rejects unmanifested canonical files by design.
