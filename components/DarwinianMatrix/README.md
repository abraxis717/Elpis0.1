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

Public v1.2.2 has promoted the qualified R7A task diagnostic/residual contract
and the semantic/topology reverse-trace foundation. The remaining production
seam is still being consolidated:

```text
task/validator failure
→ typed task residual
→ semantic/topology reverse trace
→ DarwinianMatrix Projector RELEASE
→ revised structural support
→ learned TRM re-proposal
→ validation
```

The **canonical Projector RELEASE adapter is not yet promoted into the public
end-to-end controller**. Until that gate is qualified, do not interpret the
presence of `projector/` as proof that arbitrary task failure is already
driving live clamp mutation.

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
