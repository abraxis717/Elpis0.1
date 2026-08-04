# HACF implementation status

## Implemented in this bundle

- SHA-256 C11 implementation and tests.
- Chunking ABI and corrected deterministic chunker.
- Content-addressed corpus implementation.
- SQLite FTS5 literal-query lexical retrieval.
- Canonical corpus manifests and corruption verification.
- Hash-addressed package digest ABI.
- Deterministic in-process queue and admission state machine.
- Failure-class to refinement-loop election.
- Immutable graph-delta and snapshot digest functions.
- CMake/Ninja build and eight test targets.

## FMS corrections included

- completed fences no longer free caller-visible lease handles during reap;
- explicit release after reap is safe and single-unpins;
- nonfatal demotion pressure no longer poisons intact resident objects;
- POSIX cold reads verify directly in the unpublished destination allocation,
  avoiding an unaccounted duplicate full-size staging allocation.

## Qualification run in the construction environment

- strict warnings as errors: pass;
- normal CTest: 8/8 pass;
- ASAN + UBSAN + leak detection: 8/8 pass;
- TSAN selected concurrent tests: 3/3 pass.

## Not yet sealed

- destruction/shutdown while a real accelerator fence remains pending needs a
  status-returning production shutdown contract;
- no Vulkan/i915 accelerator PAL;
- no vector embedding/index implementation;
- no persistent cascade queue journal;
- no mutable session/permanent graph database;
- no Projector/TRM/DarwinianMatrix adapters.
