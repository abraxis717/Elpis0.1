# Hash-Addressed Cascade Fabric

This repository is the isolated native C/C++ substrate for the Elpis work
created in the current session. It does not modify Projector, TRM,
DarwinianMatrix, Grid81, model checkpoints, or unrelated Elpis packages.

Implemented components:

- canonical SHA-256 with incremental and one-shot APIs;
- FMS v2 HOT/WARM/COLD residency and durable POSIX cold storage;
- deterministic structural chunking;
- content-addressed corpus storage with SQLite FTS5 lexical retrieval;
- immutable package digests bound to schema, policy, parents and dependencies;
- deterministic queue election, admission and loop-election primitives;
- append-only graph-delta and snapshot hashing;
- strict, sanitizer-compatible tests.

The SHA-256 digest is an object identity and integrity binding. It is not a
semantic encoding of the payload.

## Build

```bash
cmake -S . -B build -G Ninja -DHACF_WARNINGS_AS_ERRORS=ON
cmake --build build -j2
ctest --test-dir build --output-on-failure
```

## Current boundary

The cascade kernel is a deterministic in-process library, not yet a daemon or
persistent queue. The graph module hashes immutable deltas but does not yet
store/query a full contextual graph. Dense vectors and Intel Vulkan compute are
not included in this gate.

## Hypergraph folder structure

The **qualified graph core currently inside `Elpis_Canon`** is here:

```text
$ELPIS_CANON_ROOT/Elpis_Canon/HashAdressedCascadeFabric
```

The principal graph directories and files are:

```text
$ELPIS_CANON_ROOT/Elpis_Canon/HashAdressedCascadeFabric/src/graph
```

```text
$ELPIS_CANON_ROOT/Elpis_Canon/HashAdressedCascadeFabric/src/graph/graph.c
```

```text
$ELPIS_CANON_ROOT/Elpis_Canon/HashAdressedCascadeFabric/include/elpis/graph.h
```

The R3 contextual graph and hybrid-retrieval graph files are here:

```text
$ELPIS_CANON_ROOT/Elpis_Canon/HashAdressedCascadeFabric/src/retrieval/hybrid
```

```text
$ELPIS_CANON_ROOT/Elpis_Canon/HashAdressedCascadeFabric/src/retrieval/hybrid/context_graph.cpp
```

```text
$ELPIS_CANON_ROOT/Elpis_Canon/HashAdressedCascadeFabric/include/elpis/context_graph.h
```

```text
$ELPIS_CANON_ROOT/Elpis_Canon/HashAdressedCascadeFabric/src/retrieval/hybrid/hybrid_retrieval.cpp
```

```text
$ELPIS_CANON_ROOT/Elpis_Canon/HashAdressedCascadeFabric/src/retrieval/hybrid/retrieval_bundle.cpp
```

The associated graph tests are here:

```text
$ELPIS_CANON_ROOT/Elpis_Canon/HashAdressedCascadeFabric/tests/graph
```

```text
$ELPIS_CANON_ROOT/Elpis_Canon/HashAdressedCascadeFabric/tests/hybrid
```

The relevant architecture documentation is here:

```text
$ELPIS_CANON_ROOT/Elpis_Canon/HashAdressedCascadeFabric/docs/R3_FUSION_AND_GRAPH.md
```

```text
$ELPIS_CANON_ROOT/Elpis_Canon/HashAdressedCascadeFabric/docs/R3_ARCHITECTURE.md
```

```text
$ELPIS_CANON_ROOT/Elpis_Canon/HashAdressedCascadeFabric/docs/R3_RETRIEVAL_BUNDLE.md
```

These paths are confirmed by the transferred Canon inventory.  

## Important distinction: the semantic hypergraph fabric was not placed inside `Elpis_Canon`

We intentionally assigned the proposed higher-level semantic hypergraph implementation to the companion root:

```text
$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric
```

Its planned graph directories are:

```text
$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric/include/elpis_semantic
```

```text
$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric/src/graph
```

With the planned core files:

```text
$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric/include/elpis_semantic/hypergraph.h
```

```text
$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric/include/elpis_semantic/segment.h
```

```text
$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric/include/elpis_semantic/snapshot.h
```

```text
$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric/src/graph/hypergraph_builder.c
```

```text
$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric/src/graph/incidence_validate.c
```

```text
$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric/src/graph/segment_writer.c
```

```text
$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric/src/graph/segment_reader.c
```

```text
$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric/src/graph/snapshot_manifest.c
```

```text
$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric/src/graph/snapshot_view.c
```

```text
$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric/src/graph/query_overlay.c
```

That companion placement was deliberate so the semantic-hypergraph layer could consume sealed HACF artifacts without introducing a reverse dependency into the canonical kernel.  

So, in practical terms:

```text
HACF native graph primitives:
  $ELPIS_CANON_ROOT/Elpis_Canon/HashAdressedCascadeFabric

Semantic hypergraph/constellation companion:
  $ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric

Microsoft GraphRAG source:
  $ELPIS_CANON_ROOT/Elpis_Canon/RAG/external/microsoft-graphrag
```
