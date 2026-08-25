# TRMFractalSpine

TRMFractalSpine contains the deterministic **structural contracts and oracle
surfaces** around Elpis refinement. Despite the name, this directory is not the
learned Samsung TRM checkpoint implementation.

The component manifest declares its role as structural proposal, refinement,
and oracle support (S06/S07), with `runtime_admission = false`.

## Canonical public interfaces

The component manifest identifies these public structural interfaces:

- `src/elpis_fractal_spine/structural_semantics.py`
- `src/elpis_fractal_spine/structural_oracle.py`
- `src/elpis_fractal_spine/structural_refinement.py`

`StructuralRefinementInputV1` binds:

```text
explicit Grid81 structural state
+ explicit writable mask
+ canonical digests
→ bounded structural refinement input
```

No writable scope is inferred from missing input. The mask is explicit and
digest-bound so downstream code cannot silently inflate the refinement scope.

## Relationship to the learned TRM

The runnable learned reference model lives in the top-level
`src/elpis_reference/` package. It can fetch and execute the pinned Samsung
MLP-T TRM checkpoint.

TRMFractalSpine does **not** itself mean that a learned checkpoint is wired into
P0 or into the production task-residual/Projector loop. Its job is to preserve
the deterministic structural boundary around whatever learned proposal is
eventually admitted.

## Current integration boundary

Public v1.2.2 includes the R7A task-residual and semantic/topology reverse-trace
foundation. The canonical DarwinianMatrix Projector RELEASE adapter and learned
re-proposal closure remain subsequent qualification gates.

## Development status

The structural contracts are qualified for their declared roles, but the full
end-to-end learned refinement controller is still under active consolidation.
Do not infer production runtime admission from component qualification.

## Tests

```bash
pytest components/TRMFractalSpine/tests -v
```
