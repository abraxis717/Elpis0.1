# Native Elpis Components

> **Active-development disclaimer**
>
> The `native/` tree is under active development and should not be treated as a
> stable ABI, production-hardened deployment surface, or fully portable native
> release. Subdirectory layout, build flags, bridge contracts, and linkage may
> change as the public stack is consolidated.
>
> `runtime_admission` remains **false**.

## What this tree contains

The current public tree includes native subprojects such as:

- `hacf/`
- `hacf_bridge/`
- `semantic-spine/`
- `elpis-header/`
- `elpis-nanbeige42-host/`

Their presence in the repository does not imply that each subtree is required
by, or admitted into, the current runnable reference path.

## Current qualification boundary

The current public build/CI evidence supports the HACF native path on macOS and
Linux through CMake-selected platform linkage.

- **macOS:** native HACF/bridge path is supported by the existing Apple CMake
  branch.
- **Linux:** native HACF/bridge path is exercised by public CI.
- **Windows:** the portable Python/reference surface is targeted, but native
  HACF is **not yet qualified**.

Do not infer Windows native support or a stable cross-platform native ABI from
the presence of C/C++ source alone.

## Platform-aware setup

Inspect what the current host can support before building:

```bash
python tools/setup.py --profile full --dry-run
```

The setup layer detects the host and decides whether the native path is
available. A reference-profile install does not require native HACF.

## Build artifacts

Compiled `.so`, `.dylib`, `.dll`, `.a`, `.o`, and generated build directories
are build products, not repository authority, and should not be committed.

## Development policy

Until the native layer receives a stable-release qualification:

- treat public headers/bridges as evolving;
- pin source revisions for reproducible experiments;
- prefer fail-closed capability detection over guessed platform support;
- do not present native subprojects as production-ready merely because they
  compile;
- use qualification evidence and CI, not directory presence, to determine what
  is supported.
