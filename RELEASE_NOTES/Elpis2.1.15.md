# Elpis2.1.15

## Version: v2.1.15

Elpis2.1.15 is the forward repair successor to the failed, untagged
Elpis2.1.14 public-main release candidate. Elpis2.1.14 remains immutable
public history: it is not amended, resealed, force-rewritten, tagged, or
registered as a GitHub Release.

## Distribution identity

The Python distribution project remains `elpisai`.

This remains a distribution-label boundary only:

- installation target: `pip install elpisai`;
- console command remains `elpis`;
- Python import packages remain unchanged, including `elpis`,
  `elpis_reference`, `elpis_runtime_r0`, and `elpis_runtime_r1`;
- cache/runtime namespaces that are intentionally named `elpis` are not
  distribution metadata and remain unchanged.

## Reference-runtime hosted repair

Elpis2.1.14 successfully built and installed `elpisai-2.1.14`, but its hosted
`reference-runtime-smoke` job retained one stale metadata assertion:

`importlib.metadata.version("elpis")`

Because the distribution project is now `elpisai`, that assertion correctly
raised `PackageNotFoundError` after installation.

Elpis2.1.15 repairs only that boundary:

- hosted reference-runtime metadata now uses `version("elpisai")`;
- a repository regression requires the new assertion and forbids the legacy
  `version("elpis")` lookup in that workflow;
- the `elpis` CLI, Python import-package names, FPRM cache namespace,
  package data, and runtime semantics remain unchanged.

## Existing ECS structural result

The executable Structural Authority R0 semantics remain unchanged.
The bounded E0R2 terminal result remains:

`SEMANTIC_IR_INSUFFICIENT`

with one unresolved executable semantic primitive: a writable binary
whole-column participation referent bound to an external frozen sidecar and
operational gauge slot, with deterministic DISABLE/RESTORE and reverse-binding
semantics while exact-zero slots remain frozen.

E1 and E2 were not executed.

## Release-integrity qualification

Elpis2.1.15 treats the public Elpis2.1.14 manifest as immutable predecessor
authority despite the absence of an annotated tag or GitHub Release.

Local qualification must reproduce both hosted failure surfaces before any
release commit or push:

1. repository-completeness ordering in a clean isolated source copy:
   read-only assembly/tooling gates -> `pip install ".[trm]"` ->
   complete `tests/` execution with `PYTHONPATH=""`;
2. the complete hosted `reference-runtime-smoke` sequence:
   public verifier -> install `".[trm]"` -> installed `elpisai` metadata and
   package-data smoke -> model-blind FPRM construction -> Sudoku runtime tests
   -> feedback/Projector regressions.

The release separately proves all 17 intended import surfaces resolve from
`site-packages`, legacy distribution `elpis` is absent, the `elpis` console
entry point is preserved, and installed ECS authority resolution remains
fail-closed unless repository authority is supplied explicitly.

## Explicit nonclaims

This release does not establish the unresolved E0R2 semantic primitive,
authorize E1 or E2, establish learned-refinement efficacy, execute Darwinian
evolution, perform scientific evaluation, claim evolutionary benefit,
autonomous self-improvement, general RSI safety, AGI, ASI, or full Elpis
alignment.
