# Elpis Runtime Integration R1

Bounded pre-refinement retrieval layer backed by canonical HACF R3.

## Transaction flow

```
RequestContext -> RetrievalQueryDeriver -> HACFRetrievalProvider
  -> RetrievalBundleValidator -> RetrievalBudgetGuard
  -> EvidenceBoundRequestAdapter -> qualified Runtime R0 transaction
  -> R1 composite receipt
```

## Architecture

R1 inserts a deterministic retrieval stage *before* P0 projection. The
retrieval produces a validated `RetrievalBundle` from HACF R3 that becomes
an evidence envelope consumed by downstream R0.

## Safety

- HACF R3 is used read-only. No corpus or index mutation during retrieval.
- All budgets are versioned contracts recorded in receipts.
- Fail-closed on any budget overflow, epoch drift, or schema mismatch.
- Runtime admission remains FALSE.
- No network access, model serving, or learned models.

## Build

R1 depends on the compiled HACF R3 shared library at:
```
$ELPIS_CANON_ROOT/Elpis_Canon/Elpis/HACF_R3/build_ctypes/libelpis_hacf.so
```

Build HACF R3 first:
```bash
cd $ELPIS_CANON_ROOT/Elpis_Canon/Elpis/HACF_R3
mkdir -p build_ctypes && cd build_ctypes
cmake -DHACF_BUILD_FMS=ON -DCMAKE_BUILD_TYPE=Release ..
cmake --build . -j$(nproc)
# Link shared lib:
gcc -shared -o libelpis_hacf.so \
  libelpis_hash.a libelpis_chunking.a libelpis_corpus.a libelpis_cascade.a \
  libelpis_graph.a libelpis_fms.a libelpis_embedding.a libelpis_vector.a \
  libelpis_hybrid.a -lsqlite3 -lpthread -lm
```

## Tests

```bash
cd $ELPIS_CANON_ROOT/Elpis_Canon/Elpis_Runtime_Integration/R1
PYTHONPATH=src pytest tests/ -v
```
