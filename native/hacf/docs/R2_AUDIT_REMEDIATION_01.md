# R2 Audit Remediation 01

```
status=HACF_R2_IMPLEMENTED_NOT_SEALED
```

All four confirmed defects are fixed, all hardening items are implemented, and a
fifteenth CTest target `vector_adversarial` regression-tests each finding.

## Proof the new suite actually catches the defects

Three defects were deliberately reintroduced in a scratch copy of the remediated
tree and the suite was rerun:

```
FAIL [2] stale metadata: same address returned 'aaa' after replacement, expected 'bbb'
FAIL [3] empty index, absent digest returned OK
FAIL [3] absent digest
FAIL [4] unknown authority class accepted
FAIL [4] authority class outside the declared four accepted
80 checks, 5 failures
```

The same suite on the remediated tree reports `80 checks, 0 failures`. The tests
fail on the old behaviour, so they are regression tests rather than descriptions
of the new behaviour.

## Defect 1: fixed-field over-read

`elpis_embedding_profile_validate()` no longer calls `strlen` on any fixed-width
ABI array. Two bounded helpers replace it:

- `elpis_embedder_valid_hex64(field)` inspects bytes `[0,64]` only. It never
  touches byte 65 or later, requires exactly 64 lowercase hex characters, and
  requires `field[64] == '\0'`.
- `elpis_embedder_valid_text(field, cap, allow_empty)` requires a terminator
  strictly inside the declared width and rejects control characters.

`reserved != 0` is now a validation failure. `elpis_embedding_profile_digest()`
validates before hashing, so no digest can be computed over an unterminated
field.

Case 1 allocates a profile with `malloc(sizeof(elpis_embedding_profile))` and
fills the trailing `tokenizer_digest` with 65 non-NUL bytes, so any read past
the field is a heap-buffer-overflow that ASan reports. The suite passes clean
under ASan.

## Defect 2: stale metadata cache

The cache key is now content identity, not an address:

```
addr + metadata_map_digest[32] + vector_count + payload_bytes + metadata_bytes
```

On a mismatch the tables are re-parsed and the key is rewritten; a parse failure
clears `addr` so a half-valid key can never be reused. Case 2 writes shard A
(namespace `aaa`) into a buffer, queries it, overwrites the same buffer with
equally sized shard B (namespace `bbb`), queries again and requires `bbb`, then
restores A and requires `aaa`.

## Defect 3: missing verify target

`elpis_vector_index_verify()` semantics are now explicit:

| input | result |
|---|---|
| `NULL` | verify every admitted shard; empty index is OK |
| present, valid | `ELPIS_VEC_OK` |
| absent | `ELPIS_VEC_E_NOTFOUND` |
| malformed | `ELPIS_VEC_E_INVAL`, checked before any lookup |

`elpis_vector_index_inspect()` and `elpis_vector_index_shard_object()` follow the
same rules. Uppercase digests are malformed, not merely absent.

## Defect 4: filter validation

`elpis_corpus_list_chunks()` validates with exactly the policy the sealed
`elpis_corpus_search_lexical()` uses: `valid_token(ns, 95)` and `valid_authority`
over `canonical | reference | advisory | provisional`. Validation happens before
any statement is prepared or executed. Empty-string filters are rejected, as in
R1, rather than silently meaning "no filter".

`elpis_vector_index_search()` applies the same policy to `ns_filter` and
`authority_filter` and returns `ELPIS_VEC_E_INVAL`; an unknown authority class
never produces an empty result set.

## Immutable shard-write correction

`stat()` then `rename()` is replaced by atomic no-replace publication:

```
mkstemp in the destination directory
write all bytes
fsync file
close  (failure checked)
link(temp, destination)     -> EEXIST is the guarantee doing its job
unlink(temp)
open + fsync destination directory  -> failure returned, not ignored
```

Every failure path unlinks the temporary. Case 5 runs two threads writing
different shards to one destination and requires exactly one success, a
verifiable complete file belonging to the winner, a later write failing, and no
`.vshard-` temporaries left behind.

## Canonical identity

`canonical_hex64()` parses digest text to 32 raw bytes only when it is exactly
64 lowercase hex characters followed by NUL. Shard records are now **sorted and
deduplicated on the raw 32-byte values**, never on the source strings, so no
unnormalized text participates in an identity comparison. Uppercase, mixed case,
non-hex, short and unterminated digests are rejected at shard build, at index
creation (corpus binding) and at verify/inspect.

## Shard semantic validation

Added at build and at verify: `unknown_flags`, `nonzero_reserved`,
`zero_norm_vector`, `l2_policy_violation`, control characters in a namespace,
and authority classes outside the declared four. When the profile declares
`ELPIS_NORM_L2`, every stored vector must have a finite non-zero norm within
`1e-4` of 1.0, accumulated in double.

## Read-side locking

`profile_digest`, `shard_count`, `list_shards` and `shard_object` now take the
index shared lock; the mutex is `mutable` so const accessors can. Recursive
locking is avoided by internal `list_shards_locked` / `inspect_locked` helpers
and a single `elpis_vector_index_manifest_locked()` entry that the manifest
writer uses, because `std::shared_mutex` is not recursive. Case 10 hammers all
four accessors plus `manifest_json` from three threads while a writer admits and
closes six shards repeatedly; it passes under TSan.

## Exception containment

Every `extern "C"` entry point that allocates a container or string now runs
inside a guard that converts `std::bad_alloc` and any other exception into a
named failure: `ELPIS_VEC_E_INTERNAL` for the index, `-1` for the shard, manifest
and corpus entry points. Integrity errors are returned as status codes and are
never thrown, so nothing here can swallow one.

## TSan `vector_concurrency` runtime

Measured directly on the implementation host, scaling the iteration count with
`ELPIS_R2_CONC_ITERS` (default 60):

| iters | functional | TSan | ratio | bytes moved |
|---|---|---|---|---|
| 20 | 1.5 s | 8.7 s | 5.8x | ~108 MB |
| 60 | 3.5 s | 21.2 s | 6.1x | ~234 MB |
| 120 | 8.2 s | 44.6 s | 5.4x | ~605 MB |

Diagnosis: **expected instrumentation overhead on top of real cold I/O under
deliberate shard thrashing.** The evidence:

1. Runtime is linear in iteration count in both builds. A fixed stall would
   show up as a constant offset or as quantized jumps.
2. The TSan/functional ratio is flat at 5.4-6.1x, which is ordinary
   ThreadSanitizer overhead, not a lock-contention blowup.
3. No residency deadline is ever reached. A five-second deadline expiry returns
   `ELPIS_VEC_E_RESIDENCY` and fails the test; the test passes, so every
   acquisition completed well inside the bound.
4. The dominant cost is genuine I/O: four ~800 KiB shards against a 2 MiB WARM
   ceiling means most queries promote from COLD, and the run moves hundreds of
   megabytes through the cold store.

It is therefore not pathological thrashing in the sense of a defect, and not a
liveness defect. The thrashing is the point of the test.

The audit host measured over 240 s, roughly 11x this host at the same settings,
which is consistent with slower storage and/or more contending cores. The test
remains adversarial and unweakened; runtime is now bounded and reproducible:

- `set_tests_properties(vector_concurrency PROPERTIES TIMEOUT 600)` so a genuine
  hang fails instead of running forever
- `ELPIS_R2_CONC_ITERS` documented for attribution, default unchanged at 60

If 600 s is too close on the audit host, lower the iteration count via the
environment variable rather than raising the timeout; the pressure ratio, and
therefore the adversarial value, is per iteration and unchanged.

## Identity stability

Remediation changed no identity. The committed fixture expectations were
regenerated and compared byte-for-byte:

```
FIXTURE IDENTITIES UNCHANGED by remediation
```

The benchmark's shard digests and top-k result digests are also unchanged
(`2f1542ea...`, `962aa7ca...`, `ef473e86...`, `68b9c81c...`). This is expected:
every canonicalization added is a *rejection* rule, and all pre-existing fixture
inputs were already canonical lowercase hex with declared authority classes.
