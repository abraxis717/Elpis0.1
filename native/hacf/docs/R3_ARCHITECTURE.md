# R3 Architecture: Deterministic Hybrid Retrieval

R3 composes the sealed R1 lexical corpus and sealed R2 exact dense index without
changing either ranking engine. The pipeline is:

```
query text ──> FTS5 lexical ranks ─┐
                                   ├─> integer RRF ─> primary evidence
query vector ─> R2 exact ranks ────┘                        │
                                                            └─> bounded one-hop context
                                                                  │
                                                                  ▼
                                                       frozen RetrievalBundle
```

## Epoch discipline

`elpis_hybrid_retriever_create()` captures the corpus manifest and vector-index
manifest. Every retrieval checks both identities before and after the operation.
Any ingest or shard admission during the epoch returns `ELPIS_HYBRID_E_DRIFT`;
R3 never mixes evidence from two snapshots.

## Fusion

Only source ranks enter fusion. SQLite BM25 doubles and raw dense doubles do not
enter bundle identity. One-based ranks use integer reciprocal-rank fusion:

```
weight * 1,000,000,000 / (rrf_k + rank)
```

Integer division is deliberate. Final primary ordering is higher fused key,
then lexicographically smaller canonical chunk digest.

## Context graph

The R3 context graph is an immutable directed adjacency snapshot, not a mutable
knowledge graph. Exact duplicate edges collapse; input order does not affect the
snapshot digest. Expansion occurs only after primary selection, is limited per
seed and globally, and never traverses beyond one hop.

## Frozen evidence

Each selected item is resolved back through the corpus. The bundle carries exact
chunk bytes, metadata, ranks, source mask, graph provenance and dependency
identities. The canonical JSON stores arbitrary namespace, query and evidence
bytes as lowercase hexadecimal, avoiding locale and invalid-UTF-8 ambiguity.

## Excluded

R3 does not implement learned fusion, reranking models, graph traversal beyond
one hop, persistent graph storage, queue journaling, Projector/TRM adapters or
accelerator execution.
