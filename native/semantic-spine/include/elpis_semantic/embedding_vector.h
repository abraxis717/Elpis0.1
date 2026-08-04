/* elpis_semantic/embedding_vector.h — Canonical embedding vector object.
 *
 * A vector object is an immutable content-addressed sequence of canonical
 * float32 values interpreted under one exact embedding profile.
 *
 * Canonical float encoding:
 *   - IEEE-754 binary32, little-endian byte order
 *   - Negative zero canonicalized to positive zero
 *   - NaN rejected, ±infinity rejected
 *   - Host-native float memory is NOT hashed directly
 */
#ifndef ELPIS_SEMANTIC_EMBEDDING_VECTOR_H
#define ELPIS_SEMANTIC_EMBEDDING_VECTOR_H

#include "elpis_semantic/embedding_profile.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EMBEDDING_VECTOR_ABI_VERSION 1u

/* Vector flags. */
#define EMBEDDING_VECTOR_FLAG_NONE   0u
#define EMBEDDING_VECTOR_FLAG_MASK   0xFFu

/* Normalization tolerance for unit-L2 validation (relative). */
#define EMBEDDING_NORMALIZATION_TOLERANCE 1e-4f

/* ──────────────────────────────────────────────────────────────────── */
/* Vector object identity                                                */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_embedding_vector_v1 {
    uint32_t                              abi_version;
    hacf_digest                           profile_digest;
    uint32_t                              dimensions;
    embedding_vector_dtype                vector_dtype;
    hacf_digest                           vector_bytes_digest; /* SHA-256 of canonical bytes */
    uint32_t                              vector_flags;
    hacf_digest                           vector_identity;     /* computed digest */
    uint8_t                               reserved[32];        /* must be zero */
} elpis_semantic_embedding_vector_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Vector operations                                                     */
/* ──────────────────────────────────────────────────────────────────── */

/* Create an embedding vector from raw float32 data. Canonicalizes floats,
 * computes digests, validates against profile. Caller retains ownership
 * of the input buffer; it is copied internally.
 * Returns SEMANTIC_OK or specific error.
 *
 * profile: the embedding profile this vector belongs to
 * data:    array of 'dimensions' float32 values (host native endianness OK)
 * dimensions: must match profile->dimensions
 * out:     on success, filled with the vector identity record; the caller
 *          must embed the canonical bytes separately (see below).
 *          The canonical_bytes buffer is allocated here and the caller
 *          owns it (free with elpis_embedding_vector_free_bytes).
 * canonical_bytes_out: receives pointer to canonical byte array
 * canonical_bytes_len: receives length (= dimensions * sizeof(float32)) */
int elpis_embedding_vector_from_float32(
    const elpis_semantic_embedding_profile_v1 *profile,
    const float *data, uint32_t dimensions,
    elpis_semantic_embedding_vector_v1 *out,
    uint8_t **canonical_bytes_out, uint32_t *canonical_bytes_len);

/* Compute vector identity. Domain: "elpis.semantic.embedding_vector.v1"
 * Byte stream: domain_tag || abi_version(4 BE) || profile_digest(32)
 *             || dimensions(4 BE) || vector_dtype(4 BE)
 *             || vector_bytes_digest(32) || vector_flags(4 BE). */
int elpis_embedding_vector_identity(const elpis_semantic_embedding_vector_v1 *vec,
                                     hacf_digest *out);

/* Validate vector record: known ABI, zero reserved, dimensions > 0,
 * known dtype, non-zero profile digest. */
int elpis_embedding_vector_validate(const elpis_semantic_embedding_vector_v1 *vec);

/* Compute vector_bytes_digest from canonical byte array. */
int elpis_embedding_vector_bytes_digest(const uint8_t *bytes, uint32_t byte_count,
                                         hacf_digest *out);

/* Free canonical bytes allocated by from_float32. */
void elpis_embedding_vector_free_bytes(uint8_t *bytes);

/* Compare two vectors by identity digest. */
int elpis_embedding_vector_cmp(const elpis_semantic_embedding_vector_v1 *a,
                                const elpis_semantic_embedding_vector_v1 *b);

/* Check if two vectors are identical (same identity digest). */
int elpis_embedding_vector_is_same(const elpis_semantic_embedding_vector_v1 *a,
                                    const elpis_semantic_embedding_vector_v1 *b);

/* Compute L2 norm of canonical float32 bytes. Returns norm as float64. */
double elpis_embedding_vector_l2_norm(const uint8_t *bytes, uint32_t dimensions);

/* Validate normalization against profile. Returns 0 if valid, error if not.
 * Does NOT modify the vector — rejects if outside tolerance. */
int elpis_embedding_vector_validate_normalization(
    const elpis_semantic_embedding_profile_v1 *profile,
    const uint8_t *bytes, uint32_t dimensions);

#ifdef __cplusplus
}
#endif
#endif
