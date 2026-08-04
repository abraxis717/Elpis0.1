# R2 vector shard format

Little-endian throughout. Every integer is assembled byte by byte, so the image
does not depend on host endianness, struct padding or compiler layout.

## Layout

```
[0,   256)                         header          ELPIS_VSHARD_HEADER_BYTES
[256, 256+payload_bytes)           records         vector_count * 1600
[...,  +metadata_bytes)            metadata table
```

Total file length must equal `256 + payload_bytes + metadata_bytes` exactly.
Anything shorter is `truncated_payload`; anything longer is
`extra_undeclared_payload`. There is no alignment padding and no trailing slack.

## Header fields

| offset | size | field |
|---|---|---|
| 0 | 8 | magic `ELPVSHD1` |
| 8 | 4 | abi_version (1) |
| 12 | 4 | header_bytes (256) |
| 16 | 8 | vector_count |
| 24 | 4 | dimensions (384) |
| 28 | 4 | element_type (1 = float32) |
| 32 | 4 | metric (1 = dot, 2 = cosine) |
| 36 | 4 | normalization (0 = none, 1 = L2) |
| 40 | 4 | record_bytes (1600) |
| 44 | 4 | flags (0) |
| 48 | 8 | payload_bytes |
| 56 | 8 | metadata_bytes |
| 64 | 32 | embedding_profile_digest |
| 96 | 32 | corpus_manifest_digest |
| 128 | 32 | metadata_map_digest |
| 160 | 32 | payload_digest |
| 192 | 32 | header_digest |
| 224 | 32 | reserved, zero |

## Record

```
chunk_digest[32] || doc_digest[32] || float32 vector[384]      = 1600 bytes
```

Records are sorted by raw chunk digest ascending. Sorting is what makes the
image a function of logical content rather than of insertion order, and it makes
duplicate detection a single adjacent comparison.

No text of any kind appears in a record.

## Digest definitions

Three digests are stored, and a fourth is derived:

- `payload_digest` = SHA-256 over the record region only.
- `metadata_map_digest` = SHA-256 over the metadata region only.
- `header_digest` = SHA-256 over bytes `[0, 256)` with the 32 bytes at offset
  192 set to zero. It therefore covers the magic, every scalar field and the
  other three digest fields.
- **complete shard digest** = SHA-256 over the entire file as stored, all
  `256 + payload_bytes + metadata_bytes` bytes, with nothing zeroed. It is
  **not** stored inside the header; it is computed by the reader after
  verification succeeds and is reported in `elpis_vshard_header.shard_digest`.
  Keeping it out of the header avoids the self-reference entirely: there is no
  field to zero, and no ambiguity about which bytes are covered.

Because `header_digest` covers `payload_digest` and `metadata_map_digest`, and
those cover their regions, a single header check plus two region checks
authenticate the whole image.

## Verification order

The reader admits nothing partially. In order: length for a header, magic, ABI,
header size, header digest, then every scalar field (dimensions, element type,
metric, normalization, record size, vector count, overflow of
`count * record_bytes`, declared sizes against actual length), then payload
digest, then metadata digest, then metadata structure, then per-record ordering
and finiteness. Only after all of that may a caller touch a record.

## Rejection codes

`bad_magic`, `unsupported_abi`, `bad_header_bytes`, `header_digest_mismatch`,
`bad_dimensions`, `unknown_element_type`, `unknown_metric`,
`unknown_normalization`, `bad_record_bytes`, `bad_vector_count`,
`integer_overflow`, `payload_size_mismatch`, `truncated_header`,
`truncated_payload`, `extra_undeclared_payload`, `payload_digest_mismatch`,
`metadata_map_digest_mismatch`, `bad_metadata_map`, `duplicate_chunk_digest`,
`unsorted_records`, `non_finite_vector`.

## Metadata side table

```
u32 ns_count,   ns_count   * (u16 len + bytes)     sorted, unique
u32 auth_count, auth_count * (u16 len + bytes)     sorted, unique
vector_count * (u32 ns_index, u32 auth_index)      record order
```

Namespace and authority originate in the corpus and are captured here at build
time. The shard also binds `corpus_manifest_digest`, and the index refuses a
shard whose binding does not match the corpus it was created against, so the
side table cannot drift away from corpus metadata unnoticed.

## Immutability

`elpis_vshard_write` refuses to overwrite an existing path and commits through a
temporary file, `fsync`, `rename`, `fsync(dir)`. A shard is never edited in
place; a changed corpus means a new shard with a new digest.
