# Platform portability

Elpis public source is developed under a platform-neutral architecture rule.

Platform-neutral code owns semantic and structural behavior. Platform-specific
logic is restricted to bootstrap, native build, and learned-runtime device
selection.

The current public learned reference remains the pinned Samsung MLP-T TRM.
This phase does not introduce a model-backend abstraction and does not claim
model agnosticism.

- Semantic task-residual and reverse-trace contracts: pure Python.
- Reference TRM runtime: PyTorch with automatic CPU/CUDA/MPS selection.
- HACF native code: CMake-selected macOS/Linux build paths.
- Windows: portable Python/reference surface is exercised by CI; native HACF
  remains explicitly unqualified.
- Qualification scripts may be workstation-specific and are not runtime
  architecture.

`tools/setup.py` performs platform discovery and derives the build plan. It
contains no developer-workstation absolute paths.
