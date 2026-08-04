/* elpis_semantic/trm_persist.h — TRM adapter persistence utilities v1.
 *
 * Helper functions for P8 persistence: digest computation, serialization,
 * and file I/O shared across all TRM adapter modules.
 *
 * Identity domain: "elpis.semantic.trm_persist.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_PERSIST_H
#define ELPIS_SEMANTIC_TRM_PERSIST_H

#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Compute SHA-256 digest of raw bytes. Uses hacf_digest from cascade. */
int elpis_trm_digest_bytes(const uint8_t *data, size_t len, hacf_digest *out);

/* Compute digest from domain tag + payload bytes. */
int elpis_trm_digest_domain(const char *domain, uint32_t abi_version,
    const uint8_t *payload, size_t payload_len, hacf_digest *out);

/* Write binary blob with length header and fsync. */
int elpis_trm_write_binary(const char *path,
    const uint8_t *data, uint32_t data_len);

/* Read binary blob, verify no trailing bytes. */
int elpis_trm_read_binary(const char *path,
    uint8_t *data, uint32_t expected_len, uint32_t *actual_len);

#ifdef __cplusplus
}
#endif
#endif
