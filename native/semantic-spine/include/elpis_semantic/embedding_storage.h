/* elpis_semantic/embedding_storage.h — Immutable persistence for embedding objects.
 *
 * Publication uses:
 *   1. same-directory temporary file
 *   2. complete write
 *   3. file fsync
 *   4. atomic no-replace rename (O_EXCL on destination)
 *   5. directory fsync
 *
 * Readers recalculate all identities and reject corruption.
 * Pre-existing destinations are never overwritten.
 */
#ifndef ELPIS_SEMANTIC_EMBEDDING_STORAGE_H
#define ELPIS_SEMANTIC_EMBEDDING_STORAGE_H

#include "elpis_semantic/embedding_collection.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ──────────────────────────────────────────────────────────────────── */
/* File format magic bytes (ASCII "ESF1" + version)                       */
/* ──────────────────────────────────────────────────────────────────── */

#define EMBEDDING_FILE_MAGIC   0x45534631u  /* "ESF1" */
#define EMBEDDING_FILE_VERSION 1u

/* File type identifiers. */
typedef enum embedding_file_type {
    EMBEDDING_FILE_PROFILE   = 1u,
    EMBEDDING_FILE_VECTOR    = 2u,
    EMBEDDING_FILE_REFERENCE = 3u,
    EMBEDDING_FILE_COLLECTION = 4u
} embedding_file_type;

/* ──────────────────────────────────────────────────────────────────── */
/* Profile storage                                                       */
/* ──────────────────────────────────────────────────────────────────── */

/* Write profile atomically. Returns SEMANTIC_OK or error.
 * Pre-existing destination is never replaced (returns SEMANTIC_E_DUPLICATE). */
int elpis_embedding_write_profile(const elpis_semantic_embedding_profile_v1 *profile,
                                   const char *path, char hex_out[65]);

/* Read and verify profile. Recalculates identity. */
int elpis_embedding_read_profile(const char *path,
                                  elpis_semantic_embedding_profile_v1 *out);

/* ──────────────────────────────────────────────────────────────────── */
/* Vector storage                                                        */
/* ──────────────────────────────────────────────────────────────────── */

/* Write vector atomically. Requires canonical bytes. */
int elpis_embedding_write_vector(const elpis_semantic_embedding_vector_v1 *vec,
                                  const uint8_t *canonical_bytes, uint32_t byte_count,
                                  const char *path, char hex_out[65]);

/* Read and verify vector. Returns canonical bytes (caller must free). */
int elpis_embedding_read_vector(const char *path,
                                 elpis_semantic_embedding_vector_v1 *out,
                                 uint8_t **canonical_bytes_out,
                                 uint32_t *canonical_bytes_len);

/* ──────────────────────────────────────────────────────────────────── */
/* Collection storage                                                    */
/* ──────────────────────────────────────────────────────────────────── */

/* Write collection atomically. */
int elpis_embedding_write_collection(const elpis_semantic_embedding_collection_v1 *col,
                                      const char *path, char hex_out[65]);

/* Read and verify collection. Recalculates identity. */
int elpis_embedding_read_collection(const char *path,
                                     elpis_semantic_embedding_collection_v1 *out);

/* ──────────────────────────────────────────────────────────────────── */
/* Common storage operations                                             */
/* ──────────────────────────────────────────────────────────────────── */

/* Compute HACF package digest for a file (SHA-256 of file contents). */
int elpis_embedding_file_package_digest(const char *path, hacf_digest *out);

#ifdef __cplusplus
}
#endif
#endif
