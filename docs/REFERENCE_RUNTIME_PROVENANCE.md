# Reference runtime third-party provenance

The public TRM Sudoku reference runtime uses an inference-only namespace adaptation of code from Samsung SAIL Montreal's `TinyRecursiveModels`, pinned to commit `c01103738605ba39d1430519b1ee0c62f4c707f8d`.

The upstream TinyRecursiveModels source is distributed under the MIT License. The pinned upstream license identifies Samsung Electronics Co., Ltd. as the 2025 copyright holder. The public Elpis distribution preserves that notice in `LICENSES/Samsung-TinyRecursiveModels-MIT.txt` and in the adapted vendor modules.

The default model checkpoint is fetched from `Sanjin2024/TinyRecursiveModels-Sudoku-Extreme-mlp`, revision `256f32fcbe7123e8bf8c449410773a5ad311dbc5`, file `step_16275`, expected SHA-256 `20e9dc7ebf83b9b41a8b3f58f5fd94ee3a7eb0b0d245bdeeb14e2f1488d1daaf`.

The upstream checkpoint is a PyTorch state dictionary. `elpis model fetch` downloads the exact revision, verifies the raw checkpoint SHA-256 before deserialization, loads tensor weights only, normalizes the training-wrapper key prefix, and writes a local `model.safetensors`. The raw checkpoint and converted weights stay in the user's cache and are not repository authority.

The pinned public model identity is:

- architecture commit: `c01103738605ba39d1430519b1ee0c62f4c707f8d`
- checkpoint revision: `256f32fcbe7123e8bf8c449410773a5ad311dbc5`
- checkpoint SHA-256: `20e9dc7ebf83b9b41a8b3f58f5fd94ee3a7eb0b0d245bdeeb14e2f1488d1daaf`
- parameters: `5,028,866`
- sequence length: `81`
- vocabulary size: `11`
- maximum recursive steps: `16`

Elpis adds checkpoint verification/conversion, the public runtime wrapper, Sudoku codec, immutable-given projection, bounded proposal/validation loop, CLI, and tests. The TRM remains a numeric proposal engine and receives no task-semantic authority.
