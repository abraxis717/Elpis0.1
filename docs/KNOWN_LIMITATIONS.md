# Known Limitations

## Not included in this release

- **Runtime Integration R2** — Post-selection retrieval not implemented
- **Learned TRM execution** — No model weights or inference engine
- **Expert loading** — No multi-expert routing or factorization
- **Online serving** — No HTTP/gRPC endpoint or production runtime
- **Persistent memory** — No durable state storage
- **Governance** — No policy enforcement or Constitution activation
- **Sandbox execution** — No isolated code execution environment

## Runtime admission

Runtime admission is **FALSE**. The system is qualified for offline structural operations but not authorized for production deployment.

## Platform requirements

- HACF native build requires C11 and C++17 toolchains
- Python >= 3.11 required for all Python components
- Tested on Linux; Windows/macOS compatibility not verified for native components

## Performance

- Grid81 operations are O(81) — trivial scale
- HACF exact retrieval is O(N*K) — suitable for small-to-medium corpora
- No GPU acceleration; all operations run on CPU
