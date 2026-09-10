# Elpis2.1.14

## Version: v2.1.14

Elpis2.1.14 is the forward repair successor to the failed, untagged
Elpis2.1.13 public-main release candidate. Elpis2.1.13 remains immutable
history: it is not amended, resealed, tagged, or registered as a GitHub
Release.

## Distribution identity

The Python distribution project is now `elpisai`.

This is a distribution-label migration only:
- installation target: `pip install elpisai`;
- console command remains `elpis`;
- Python import packages remain unchanged (`elpis`, `elpis_reference`,
  `elpis_runtime_r0`, `elpis_runtime_r1`, and the other qualified surfaces);
- release verification and sealing bind the current package identity as
  `elpisai`.

## Hosted completeness repair

The Elpis2.1.13 hosted completeness job established that the wheel contained
all 17 intended import surfaces and aggregate collection succeeded, but
repository-owned ECS tests failed in an installed environment because they
implicitly assumed frozen ECS authority was colocated with the imported
module.

Elpis2.1.14 repairs the ownership boundary rather than weakening runtime
authority resolution:
- installed `elpis_reference.ecs_r0` still fails closed with
  `AUTHORITY_ROOT_REQUIRED` when no root is supplied;
- repository tests explicitly bind repository ECS authority;
- repository E0R2 tooling explicitly supplies its containing repository root;
- hosted installed-artifact qualification verifies `elpisai` metadata, absence
  of a legacy installed `elpis` distribution, the unchanged `elpis` console
  command, all 17 installed import surfaces, and ECS authority relocation.

The qualified E0R2 terminal remains `SEMANTIC_IR_INSUFFICIENT` with one
unresolved executable semantic primitive. E1 and E2 were not executed.

## Release integrity

The public Elpis2.1.13 manifest is treated as immutable predecessor history
despite the absence of a tag or GitHub Release. Elpis2.1.14 advances the
VERSION/package/citation declarations, release identity table, predecessor
guard belt, and a new write-once successor manifest with
`package_name=elpisai`.

Qualification reproduces the hosted repository-completeness operator order in
an isolated environment: install `".[trm]"`, then run the complete top-level
test suite with `PYTHONPATH=""`, and separately qualify the installed package
surfaces.

No tag, GitHub Release, PyPI upload, E1/E2, learned execution, Darwinian
execution, or scientific execution is authorized by this local qualification.
