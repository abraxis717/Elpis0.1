# G5.1B — Deterministic Structural Adjudicator

Consumes sealed G5.0B proposal sets under the sealed G5.1A contract.
Produces deterministic adjudication records and inert capability-review requests.

## What it does

- Verifies upstream seals (G5.0A, G5.0B, G5.1A)
- Joins source inventories by source_row_digest
- Applies deterministic adjudication policy
- Produces canonical output inventories

## What it does NOT do

- Does not authorize influence
- Does not issue or consume capabilities
- Does not select models, adapters, or runtime targets
- Does not activate, dispatch, or execute

## Usage

```bash
cd Grid81DeterministicStructuralAdjudicator
PYTHONPATH=src:../Grid81StructuralAdjudicationContract PYTHONHASHSEED=0 python g51b_execute.py --all
python verify_g51b.py --all
```
