# R2 vector architecture

## Why the CPU path is authoritative

Exact flat search over 384-dimensional float32 vectors is small, total and
checkable. Every candidate is scored; nothing is pruned, sampled, quantized or
approximated, so the output is a function of the inputs alone. That makes it
usable as an oracle: any later backend (quantized, ANN, or accelerator) is
correct exactly insofar as it reproduces this backend's ranking on the same
inputs. An approximate backend admitted before the oracle existed would have
nothing to be wrong against.

The kernel is therefore held to a stricter numerical contract than performance
would suggest:

- stored vectors are float32; every accumulation is `double`
- each product is `(double)a * (double)b`; no float-domain multiply is used
- the dimension loop runs in index order, fixing the summation order
- `-ffp-contract=off` on `elpis_vector`, so no fused multiply-add reassociates
- no `-ffast-math`, no `-Ofast`, no reciprocal approximation

## Why exact search precedes ANN

ANN structures trade recall for latency, and the trade is only measurable
against exact results. Building HNSW or PQ first would mean tuning recall
against an unknown. It would also hide format and residency defects: a graph
index that silently drops a corrupt shard still returns plausible neighbours.
`R2` deliberately ships the slow, complete implementation, with corruption
handling and residency accounting fully exercised, before anything faster is
allowed to exist.

## Component boundaries

```
embedding_provider   profile identity, fixture and external providers
vector_shard         immutable on-disk format, build and verification
cpu_exact            scoring kernel, canonical score key, deterministic order
vector_index         admission, FMS residency, filtering, top-k
vector_manifest      canonical shard and index manifests
```

The vector layer stores no text and owns no chunk identities. Chunk and document
digests come from the corpus; the shard binds the corpus manifest digest so
metadata drift is detectable rather than silent.

## Deterministic ordering

Ranking binds a canonical integer, never a host double:

```
searchable profile = L2 only; metric = cosine or DOT over verified unit vectors
score domain       = [-1,1], with <=2e-4 declared overshoot clamped
score_key          = round(score * 1e12), half away from zero
order              = score_key descending, then chunk digest ascending
```

Digests are unique within an index (duplicates are rejected at admission), so
the order is total. Nothing in the comparison consults a pointer address, an
insertion time, a hash-table iteration order, a locale or sort stability.

`ELPIS_NORM_NONE` remains available only to qualify providers in isolation. It
cannot create a searchable index, because unbounded raw DOT scores cannot be
represented by the fixed canonical key without collisions. The `double score`
field is returned for diagnostics and is explicitly not part of any identity.

## Fixture embedder

The identity-bearing provider name is `fixture-sha256-v2`, matching the v2 seed
and sparse construction below.


The fixture provider derives 16 distinct positions and 16 signs from repeated
SHA-256 material and assigns exactly `+/-0.25f`, leaving every other component
`+0.0f`. Since `16 * 0.25^2 = 1`, the vector is exactly unit-norm with no square
root, no division and no libm call, so the float32 bytes are identical on every
host. The unnormalized profile uses `+/-1.0f`, giving an exact norm of `4.0`.

Consequences worth stating plainly: fixture vectors are sparse and mostly
orthogonal, so most pairs score exactly `0` and ties are common. That is a
feature for qualification, since it exercises tie-breaking heavily, and it is
why the fixture is not a semantic embedding and must never be presented as one.

## Excluded from R2

FAISS, HNSW, product quantization, any approximate search, Vulkan, OpenCL,
Intel GPU execution, transformer inference, model downloads, RRF fusion,
GraphRAG, Projector/TRM/DarwinianMatrix adapters, persistent queue journaling,
and any network listener. `FMS_HOT` is never requested.
