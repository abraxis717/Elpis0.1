# HACF R2 implementation manifest — Remediation 02

```text
status=HACF_R2_IMPLEMENTED_NOT_SEALED
```

This is a provisional implementation record. It is not a seal. The authoritative
Ouroboros sanitizer gate, `elpis-mba72` qualification, source parity, result
parity and formal sealing remain operator gates.

## Sealed baseline

```text
baseline_status=HACF_R0_R1_CROSS_HOST_FUNCTIONAL_SEALED
formal_seal_sha256=cf492f6345a8a9e89e2c7e2b68ee831d36e51aec48eeba18bfcfcada1632ed74
sealed_source_manifest_sha256=d15d49245063643a57a4e70190f61d34efb7728092af340360e5ac57c34e5d01
sealed_entries_verified=26/26
baseline_tests=8/8_PASS
```

The historical R0/R1 seal is not modified by this overlay.

## Implemented scope

- additive embedding-provider ABI;
- deterministic 384-dimensional fixture provider;
- validated external-vector provider;
- immutable float32 vector-shard format;
- SHA-256-bound profile, shard, index and result identities;
- exact CPU search with double accumulation;
- deterministic `score_key = round(score * 10^12)` ranking;
- L2-only searchable indexes with cosine or normalized-dot scoring;
- namespace and authority filtering through the sealed corpus;
- FMS WARM-only shard residency and structured failure propagation;
- deterministic cross-host fixture;
- 10k and 100k exact-search benchmark harness.

Excluded: ANN, FAISS, HNSW, quantization, GPU execution, Vulkan, RRF,
GraphRAG, persistent queue journal, Projector/TRM/DarwinianMatrix adapters.

## Remediation 02 corrections

1. Searchable indexes now require `ELPIS_NORM_L2`. Unbounded raw-DOT profiles
   are rejected with `ELPIS_VEC_E_PROFILE`.
2. Canonical indexed scores are finite and bounded to `[-1,1]`; only a small
   documented floating overshoot is clamped before score-key conversion.
3. Public vector-shard, vector-index and embedder C ABI error paths contain
   `std::bad_alloc`, standard and unknown C++ exceptions.
4. Embedder diagnostics use a fixed-size nonallocating error buffer.
5. `verify`, `inspect`, `shard_object` and `close_shard` apply the same
   canonical lowercase digest policy.
6. Fixture identity corrected from `fixture-sha256-v1` to
   `fixture-sha256-v2`, matching the already implemented v2 seed and sparse
   exactly normalized construction.
7. The adversarial suite now covers score-domain saturation, non-L2 rejection,
   allocation-failure containment, digest-policy consistency and fixture
   identity.

Full details: `docs/R2_AUDIT_REMEDIATION_02.md`.

## Construction-environment qualification

```text
functional=15/15_PASS total_seconds=7.98
asan_ubsan=15/15_PASS total_seconds=22.38
asan_runtime=libasan.so.8
ubsan_runtime=libubsan.so.1
tsan=15/15_PASS total_seconds=27.89
tsan_runtime=libtsan.so.2
vector_adversarial=143_checks_0_failures
vector_concurrency_tsan_seconds=13.64
```

These results were obtained in the construction container with GCC 14.2.0.
They do not substitute for the authoritative host gates.

## Cross-host fixture identities

The fixture vectors remain byte-identical; profile-bound identities changed
because the profile name was corrected from v1 to v2.

```text
embedding_profile_digest=68db7e3136ca715df91cf3bb059a51a921627419af7046f88b9d50525cafd1d5
corpus_manifest_digest=0236ee2156c0c3d0b02924bcfe2a78aafac71c9a48b2229f4bab058534b1ed40
shard_digest=db3f287093db35e1de525ba3f359a9d7bc597e65c07374b89101dfc1d2ae3332
index_manifest_digest=e90263312cffd531dd6e7662b34a4c74b21d552d2e2baeafa15a7905cc084113
query_digest=8075ab006b2dcb9bc3ec27ffb481703a94e3c23aadd53e1b8435e3dca762a42d
result_digest=440a91c23c3b3177a228576dd6f560dfcab972fd66311032355ae158269fbd69
```

Parity is not claimed until the committed fixture passes on both Ouroboros and
`elpis-mba72`.

## Benchmark snapshot

Construction container: AMD EPYC 9V74, GCC 14.2.0. Re-measure on the actual
hosts before capacity decisions.

```text
10000x384  p50_ms=8.0244   p95_ms=8.4560   qps=124.26
100000x384 p50_ms=126.1460 p95_ms=130.6851 qps=7.86
```

Complete machine-readable and Markdown records are under
`benchmarks/vector/results/`.

## Known limitations

1. Search materializes all candidates before sorting; the bounded top-k heap is
   deliberately deferred until correctness sealing.
2. Shard verification recomputes every stored vector norm, increasing admission
   cost but catching policy violations before search.
3. Cross-shard duplicate detection leases admitted shards and scales linearly
   with shard count per admission.
4. The fixture provider is a deterministic qualification instrument, not a
   semantic embedding model.
5. The index admits at most 64 shards.
6. Construction-container timings are not target capacity evidence.

## Next admissible action

Install the replacement overlay on the authoritative tree, run functional,
ASan+UBSan and TSan qualification on Ouroboros, deploy the byte-identical source
to `elpis-mba72`, run the functional suite and cross-host fixture, compare source
and fixture identities, then create an R2 seal only if every gate passes.
