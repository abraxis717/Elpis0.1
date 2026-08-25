# DarwinianMatrix

DarwinianMatrix is the first-party evolutionary/lifecycle substrate used by
Elpis for bounded episode state, constraint projection, fitness/selection,
heredity, retirement, and related structural bookkeeping.

The component manifest currently classifies it as **ACTIVE** and **QUALIFIED**
for its declared component role, while explicitly retaining
`runtime_admission = false`.

## Current role

The canonical component tree contains, among other areas:

- `projector/` — constraint and gap projection machinery;
- `controller/` — lifecycle/control surfaces;
- `ecology/`, `climate/`, `life/` — evolutionary state machinery;
- `evaluation/` — evaluation/fitness surfaces;
- `ledger/` — lifecycle/evidence bookkeeping;
- `trm/` — TRM-facing reference/integration material;
- `geometry.py` — structural geometry utilities.

The exact public authority boundary is narrower than the amount of code present
in this directory. A component being present or historically qualified does
not mean every path is active in the public runtime.

## Refinement integration status

Public v1.2.3 promotes the qualified R7A RELEASE-planning mechanism against the
existing canonical Projector transaction types:

```text
task/validator failure
→ typed task residual
→ semantic/topology reverse trace
→ canonical DarwinianMatrix Projector RELEASE
→ revised structural support
```

The adapter releases only currently active support already selected by reverse
trace, derives each owner from the current ClampState, and binds the transaction
to the current state digest. Generic task failure cannot ASSERT or REPLACE a
structural claim.

The adapter does not prove that a task diagnostic matches the historical
evidence digest that originally created a clamp because ClampState does not
retain that per-cell history.

The **learned re-proposal loop is not yet promoted**. Therefore this does not
establish arbitrary-task improvement, generalized semantic resolution, or
runtime admission.

## Safety / authority invariants

- Task errors do not directly select Grid81 cells or values.
- Structural rejection is not automatically a task residual.
- Existing clamps remain evidence-owned.
- Generic conflict may release implicated existing support.
- ASSERT/REPLACE require newly established evidence.
- Learned TRM output is proposal-only.
- Runtime admission remains false.

## Development status

This component is under active integration. Interfaces that are not identified
as canonical public contracts may change while the refinement seam is
consolidated. Use the component manifest, public qualification evidence, and
top-level release status as the authority for what is actually admitted.

## Tests

```bash
pytest components/DarwinianMatrix/tests -v
```
