# Third Party Notices

This project includes or depends on third-party software.

## Public TRM reference runtime

- **Samsung SAIL Montreal TinyRecursiveModels** — MIT License. The inference-only modules under `src/elpis_reference/vendor/` are namespace adaptations of the pinned upstream source at commit `c01103738605ba39d1430519b1ee0c62f4c707f8d`. See `LICENSES/Samsung-TinyRecursiveModels-MIT.txt` and `docs/REFERENCE_RUNTIME_PROVENANCE.md`.
- **Pinned Sudoku checkpoint** — fetched at runtime from `Sanjin2024/TinyRecursiveModels-Sudoku-Extreme-mlp`, revision `256f32fcbe7123e8bf8c449410773a5ad311dbc5`, raw SHA-256 `20e9dc7ebf83b9b41a8b3f58f5fd94ee3a7eb0b0d245bdeeb14e2f1488d1daaf`. Model weights are not committed into this repository.

## Python dependencies

- **NumPy**
- **PyTorch**
- **einops**
- **huggingface-hub**
- **pydantic**
- **safetensors**
- **pytest** — test dependency
- **setuptools** — build dependency

Refer to each dependency's distribution metadata for its applicable license.

## Native dependencies

All native code (HACF R3, Semantic Structural Spine V1, elpis-header) is first-party Elpis code.

## Component licenses

See `manifests/FILE_LICENSE_MAP.json` for historical component-level mapping. First-party Elpis code remains MIT unless otherwise noted. Third-party adapted reference-runtime files retain their upstream MIT notice.

## SciPy

SciPy is a runtime dependency of the vendored FPRM implementation for statistical distributions. SciPy is distributed under the BSD 3-Clause license.
