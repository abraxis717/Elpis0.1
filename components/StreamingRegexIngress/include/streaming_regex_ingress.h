#ifndef ELPIS_STREAMING_REGEX_INGRESS_H
#define ELPIS_STREAMING_REGEX_INGRESS_H

#include <stddef.h>
#include <stdint.h>

#if defined(__GNUC__) || defined(__clang__)
#define ELPIS_STREAMING_REGEX_API __attribute__((visibility("default")))
#else
#define ELPIS_STREAMING_REGEX_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define ELPIS_STREAMING_REGEX_ABI_VERSION_V1 1u
#define ELPIS_STREAMING_REGEX_DEFAULT_CARRY_BYTES_V1 1024u

#define ELPIS_STREAMING_REGEX_OK 0
#define ELPIS_STREAMING_REGEX_E_INVAL (-1)
#define ELPIS_STREAMING_REGEX_E_PARSE (-2)
#define ELPIS_STREAMING_REGEX_E_NOMEM (-3)
#define ELPIS_STREAMING_REGEX_E_RANGE (-4)

typedef struct elpis_streaming_regex_result_v1 elpis_streaming_regex_result_v1;

typedef struct elpis_streaming_regex_evidence_view_v1 {
    uint32_t abi_version;
    char evidence_id[65];
    char pattern_id[96];
    char lexical_anchor[128];
    uint8_t reserved[32];
} elpis_streaming_regex_evidence_view_v1;

typedef struct elpis_streaming_regex_candidate_view_v1 {
    uint32_t abi_version;
    char candidate_id[65];
    uint8_t reserved[32];
} elpis_streaming_regex_candidate_view_v1;

ELPIS_STREAMING_REGEX_API uint32_t elpis_streaming_regex_abi_version_v1(void);

ELPIS_STREAMING_REGEX_API int elpis_streaming_regex_parse_bytes_v1(
    const uint8_t *data,
    size_t data_len,
    size_t chunk_size,
    size_t carry_bytes,
    elpis_streaming_regex_result_v1 **out);

ELPIS_STREAMING_REGEX_API void elpis_streaming_regex_result_destroy_v1(
    elpis_streaming_regex_result_v1 *result);

ELPIS_STREAMING_REGEX_API const char *elpis_streaming_regex_result_json_v1(
    const elpis_streaming_regex_result_v1 *result);

ELPIS_STREAMING_REGEX_API const char *elpis_streaming_regex_result_ingress_json_v1(
    const elpis_streaming_regex_result_v1 *result);

ELPIS_STREAMING_REGEX_API const char *elpis_streaming_regex_result_composition_json_v1(
    const elpis_streaming_regex_result_v1 *result);

ELPIS_STREAMING_REGEX_API const char *elpis_streaming_regex_result_source_sha256_v1(
    const elpis_streaming_regex_result_v1 *result);

ELPIS_STREAMING_REGEX_API uint64_t elpis_streaming_regex_result_source_bytes_v1(
    const elpis_streaming_regex_result_v1 *result);

ELPIS_STREAMING_REGEX_API uint32_t elpis_streaming_regex_result_evidence_count_v1(
    const elpis_streaming_regex_result_v1 *result);

ELPIS_STREAMING_REGEX_API uint32_t elpis_streaming_regex_result_candidate_count_v1(
    const elpis_streaming_regex_result_v1 *result);

ELPIS_STREAMING_REGEX_API uint32_t elpis_streaming_regex_result_ambiguity_count_v1(
    const elpis_streaming_regex_result_v1 *result);

ELPIS_STREAMING_REGEX_API int elpis_streaming_regex_result_fail_closed_v1(
    const elpis_streaming_regex_result_v1 *result);

ELPIS_STREAMING_REGEX_API int elpis_streaming_regex_result_evidence_at_v1(
    const elpis_streaming_regex_result_v1 *result,
    uint32_t index,
    elpis_streaming_regex_evidence_view_v1 *out);

ELPIS_STREAMING_REGEX_API int elpis_streaming_regex_result_candidate_at_v1(
    const elpis_streaming_regex_result_v1 *result,
    uint32_t index,
    elpis_streaming_regex_candidate_view_v1 *out);

ELPIS_STREAMING_REGEX_API const char *elpis_streaming_regex_last_error_v1(void);

#ifdef __cplusplus
}
#endif

#endif
