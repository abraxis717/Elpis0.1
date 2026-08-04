# Current worktree status

## Present

- FMS ABI v2 public header.
- FMS PAL ABI and POSIX PAL.
- Test-only PAL.
- FMS R0 invariant suite.
- FMS concurrency suite.
- Deterministic chunker implementation.
- R1 corpus test specification.

## Missing before a complete build

- `include/elpis/sha256.h`
- canonical SHA-256 implementation under `src/hash/`
- `include/elpis/chunking.h`
- `include/elpis/corpus.h`
- corpus/SQLite/FTS implementation
- build system files
- cascade-envelope ABI
- queue/admission implementation
- graph-delta implementation

## Known R0 blockers from adversarial review

1. Public lease lifetime after asynchronous reap.
2. Nonfatal demotion pressure must not mark intact objects failed.
3. Cold-read verification staging must be physically accounted or removed.
4. Shutdown with pending device fences needs an explicit safe contract.

## Gate state

- R0 supplied tests: passed previously.
- R0 adversarial qualification: not sealed.
- R1: incomplete; test specification present, corpus implementation absent.
- Intel GPU/Vulkan work: not yet admissible.
