# R2 Audit Remediation 02

```text
status=HACF_R2_IMPLEMENTED_NOT_SEALED
```

This remediation closes the four remaining blockers found by the independent
Remediation 01 audit. It does not claim Ouroboros installation, MacBook
qualification, cross-host parity, or an R2 seal.

## 1. Bounded canonical score domain

The embedding-provider ABI still permits `ELPIS_NORM_NONE` for isolated
provider tests. `elpis_vector_index_create()` now rejects every non-L2 profile
with `ELPIS_VEC_E_PROFILE` and clears the output pointer.

An index accepts cosine or DOT only over L2-declared, admission-verified stored
vectors. Every query is normalized on a private copy. Indexed scores must be
finite and lie in `[-1,1]`; the declared shard norm tolerance can create at most
a small DOT overshoot, so values within `2e-4` are clamped and larger values are
rejected as integrity failures before score-key conversion.

`elpis_vector_score_key()` is now contained for direct callers as well: finite
overshoot clamps to `[-1,1]`, and non-finite input maps to `INT64_MIN`. Raw,
unbounded DOT is not an R2 searchable identity domain.

The adversarial suite proves that:

- `NORM_NONE + DOT` cannot create an index;
- a huge finite external vector cannot enter an L2 profile;
- two valid normalized DOT scores retain their true order even when the lower
  score owns the lexicographically smaller chunk digest;
- direct overshoot cannot overflow or saturate the canonical key.

## 2. C ABI exception containment

The embedder's internal `std::string` error slot was replaced with a fixed
`char[192]` buffer and a nonallocating `snprintf` setter. Provider error paths
therefore cannot throw while reporting an error.

`elpis_vshard_verify()` now delegates to an internal implementation and catches
`std::bad_alloc`, `std::exception`, and unknown exceptions. Allocation failure
returns `-1`, reports `allocation_failure`, and leaves the output header fully
zeroed.

Vector-index error formatting is fixed-buffer. `close_shard`, `inspect`,
`shard_object`, profile access, list, verify, search, and admission paths are
contained by guards where their C++ operations can throw. Guard catch handlers
do not allocate.

The test executable overrides global `operator new` under a controlled switch.
It proves allocation failure cannot cross shard verification, external-provider
creation, fixture error handling, or shard close.

## 3. Canonical digest policy completed

`verify`, `inspect`, `shard_object`, and `close_shard` now use one policy:

| input | result |
|---|---|
| canonical present digest | `ELPIS_VEC_OK` |
| canonical absent digest | `ELPIS_VEC_E_NOTFOUND` |
| short, nonhex, uppercase, or mixed-case digest | `ELPIS_VEC_E_INVAL` |

Validation occurs before lock acquisition or lookup. The adversarial test is
table-driven across all four operations.

## 4. Fixture identity corrected

The seed and sparse construction were already version 2:

```text
elpis-fixture-embed-v2
```

The identity-bearing provider name is now:

```text
fixture-sha256-v2
```

Fixture vector bytes are unchanged. Profile-bound identities changed by design:

```text
embedding_profile_digest=68db7e3136ca715df91cf3bb059a51a921627419af7046f88b9d50525cafd1d5
shard_digest=db3f287093db35e1de525ba3f359a9d7bc597e65c07374b89101dfc1d2ae3332
index_manifest_digest=e90263312cffd531dd6e7662b34a4c74b21d552d2e2baeafa15a7905cc084113
result_digest=440a91c23c3b3177a228576dd6f560dfcab972fd66311032355ae158269fbd69
```

The corpus manifest, query digest, chunk digests, score keys, and ranking remain
unchanged because the embedding algorithm itself did not change.

## Independent reconstruction results

Environment: GCC 14.2.0, CMake/Ninja, SQLite 3.46.1, x86-64 Linux container.

```text
functional       15/15 PASS   6.88 s
ASan + UBSan     15/15 PASS  23.45 s
TSan             15/15 PASS  28.35 s
vector_adversarial 143 checks, 0 failures
```

Runtime linkage was confirmed with `ldd`:

```text
libasan.so.8
libubsan.so.1
libtsan.so.2
```

The first aggregate TSAN invocation encountered the previously observed
container-specific concurrency slowdown and was terminated by the external tool
timeout without a race report. Direct attribution runs then passed at 5, 20,
and 60 iterations; a fresh complete CTest run passed 15/15, with the default
60-iteration concurrency test completing in 13.70 seconds.

## Benchmark identity change

The benchmark was rerun in Release mode with 50 queries per scale. Because the
profile name is identity-bearing, shard and top-k result digests changed. The
new values are recorded in `benchmarks/vector/results/`.

## Gate state

```text
R2.0 baseline verification      PASS
R2.1 ABI and format             PASS
R2.2 provider and shard         PASS
R2.3 exact CPU search           PASS
R2.4 FMS integration            PASS
local functional/sanitizers     PASS
R2.5 Ouroboros qualification    NOT RUN
R2.6 MacBook qualification      NOT RUN
R2.7 cross-host parity          NOT RUN
R2.8 formal seal                NOT CREATED
```
