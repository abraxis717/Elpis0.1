# R3 RetrievalBundle Schema

Schema identifier: `elpis.retrieval_bundle.v1`.

A bundle binds:

- canonical query digest, including text bytes, filters, profile identity and
  exact float32 query-vector bytes;
- corpus manifest digest;
- vector-index manifest digest;
- optional immutable graph snapshot digest;
- fusion-policy digest;
- ordered evidence items;
- canonical bundle digest;
- HACF package digest with object type `HACF_OBJ_RETRIEVAL_BUNDLE`.

Each item contains chunk and document digests, namespace, authority, exact text,
text digest, lexical/dense ranks, dense score key, fused score key, source mask,
primary/context type, graph parent, edge type and edge authority.

Canonical JSON uses stable key order and integers only for ranking identity.
Arbitrary query, namespace and evidence bytes are encoded as lowercase hex in
`query_text_hex`, `namespace_hex`, `namespace_filter_hex` and `text_hex`.
Raw host doubles never enter the payload identity.

`elpis_retrieval_bundle_write()` publishes through a same-directory temporary
file and atomic no-replace link. A pre-existing destination is never overwritten.
