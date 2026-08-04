# HACF R2 Toolchain Hotfix 001

Status: `HACF_R2_IMPLEMENTED_NOT_SEALED`

## Scope

This hotfix changes only the allocation-failure injection harness in
`tests/vector/test_vector_adversarial.cpp`.

GCC 16 performs interprocedural `-Wmismatched-new-delete` analysis through the
intentional replacement global `operator new` / `operator delete` pair. When
the replacement operators call `malloc` and `free` directly, GCC diagnoses the
matching test-only pair as a mismatch after inlining and `-Werror` stops the
Release build.

The hotfix routes raw allocation and deallocation through non-inlined internal
helpers. It does not suppress the warning, alter project-wide warning policy,
or change the allocation-failure injection semantics.

## Qualification

Construction-environment Release build with `-O3 -Werror`:

```text
15/15 PASS
```

Authoritative functional and sanitizer qualification remains required on
Ouroboros after installation. No R2 seal is created by this hotfix.
