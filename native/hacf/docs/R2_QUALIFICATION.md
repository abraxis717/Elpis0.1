# R2 qualification procedure

## What this overlay establishes, and what it does not

Established here, on one workstation:

- the sealed R0/R1 baseline builds and passes 8/8 with only the approved
  additive SQLite shim
- the R2 layer passes 15/15 in three configurations (functional,
  ASan+UBSan, TSan), warnings-as-errors throughout
- the committed cross-host fixture produces a fixed set of seven identities

Explicitly **not** established, and not claimed anywhere in this overlay:

- Ouroboros sanitizer qualification
- MacBook deployment or native execution
- source manifest parity between hosts
- cross-host result parity
- any R2 seal

The fixture test is the instrument for parity, not the evidence of it. Parity
exists only once the same identities are produced on both hosts and compared.

## Commands

```sh
cmake -G Ninja -S . -B build && ninja -C build
ctest --test-dir build --output-on-failure

cmake -G Ninja -S . -B build-asan -DELPIS_ENABLE_ASAN=ON -DELPIS_ENABLE_UBSAN=ON
ninja -C build-asan && ctest --test-dir build-asan --output-on-failure
ldd build-asan/test_vector_fms | grep -E 'asan|ubsan'

cmake -G Ninja -S . -B build-tsan -DELPIS_ENABLE_TSAN=ON
ninja -C build-tsan && ctest --test-dir build-tsan --output-on-failure
ldd build-tsan/test_vector_concurrency | grep tsan

./build/benchmark_vector_exact <output-dir> <work-dir>
```

A build directory name is not evidence a sanitizer is active. `ldd` is.

## Cross-host parity, when the operator runs it

On each host:

```sh
ctest --test-dir build -R vector_crosshost_fixture --output-on-failure
```

The test compares the identity-bearing pipeline outputs against `tests/vector/fixture/expected.txt`:
embedding profile digest, corpus manifest digest, shard digest, index manifest
digest, query digest, chunk count, hit count, the ordered top-k
`chunk_digest:score_key` pairs, and the result digest. Any difference fails the test and names the field.

`ELPIS_R2_FIXTURE_REGENERATE=1` rewrites the expectations. That is legitimate
only when a profile, chunking policy or ABI has deliberately changed, and it
invalidates every previously built shard. It must never be used to make a
failing parity run pass.

## What would invalidate the fixture

- a change to the fixture embedder construction, algorithm version, or profile fields
- a change to the chunking profile, which changes chunk digests
- a change to the shard header layout, record layout or digest definitions
- a change to `score_key` scaling or the tie-break rule
- a change to the corpus manifest serialization

Each of those changes an identity by design. The correct response is a
deliberate regeneration with a note, never a tolerance.

## Gate state

```
R2.0  baseline verification        PASS   26/26 sealed digests, 8/8 tests
R2.1  ABI and format               PASS   headers, format document
R2.2  provider and shard           PASS   embedding_provider, vector_shard
R2.3  exact CPU search             PASS   vector_search
R2.4  FMS integration              PASS   vector_fms, vector_concurrency
R2.5  Ouroboros sanitizers         NOT RUN HERE - operator gate
R2.6  MacBook qualification        NOT RUN HERE - operator gate
R2.7  cross-host parity            NOT RUN HERE - operator gate
R2.8  formal seal                  NOT CREATED
```
