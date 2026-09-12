#ifndef ELPIS_STREAMING_REGEX_INGRESS_V2_H
#define ELPIS_STREAMING_REGEX_INGRESS_V2_H
#include "streaming_regex_ingress.h"
#ifdef __cplusplus
extern "C" {
#endif
#define ELPIS_STREAMING_REGEX_ABI_VERSION_V2 2u
#define ELPIS_STREAMING_REGEX_E_STATE (-5)
#define ELPIS_STREAMING_REGEX_INLINE_TEXT_BYTES_V2 4096u
#define ELPIS_STREAMING_REGEX_DEFAULT_MAX_EVIDENCE_V2 4096u
/* SHA-256's 64-bit bit-count bound, not a carry/input-buffer bound. */
#define ELPIS_STREAMING_REGEX_MAX_SOURCE_BYTES_V2 (UINT64_MAX / 8u)

typedef struct elpis_streaming_regex_stream_v2 elpis_streaming_regex_stream_v2;
typedef struct elpis_streaming_regex_options_v2 {
    uint32_t abi_version;
    uint32_t struct_size;
    uint32_t max_evidence;
    uint32_t reserved;
    uint64_t max_source_bytes;
} elpis_streaming_regex_options_v2;
typedef struct elpis_streaming_regex_stats_v2 {
    uint32_t abi_version;
    uint32_t struct_size;
    uint64_t source_bytes;
    uint64_t peak_candidates;
    uint64_t peak_threads;
    uint64_t peak_inline_bytes;
    uint64_t peak_capture_bytes;
    uint64_t program_instructions;
    uint64_t evidence_count;
} elpis_streaming_regex_stats_v2;

/* NULL options selects defaults. Nonzero limits required otherwise. Each live
 * handle requires external synchronization. Independent handles may be used
 * concurrently. Error text is thread-local, valid until the next V2 operation.
 * No source pointer is retained. NULL+0 is a no-op while open; NULL+n is fatal.
 * Failed streams are terminal. Neither failure nor feed publishes a result.
 * Finalize transfers a separately owned immutable result, read/destroy using
 * the V1 result accessors. A second finalize or feed after finalize returns
 * E_STATE without modifying that result. A NULL output slot is rejected but
 * leaves the stream open. destroy(NULL) is safe; stale/forged handles, double
 * destruction, invalid readable buffers and concurrent use are caller UB.
 *
 * Matches <=4096 bytes retain exact V1 JSON. Longer matches carry the exact
 * hash and offsets but omit matched_text, use lexical evidence schema v2 and
 * matched_text_omitted=true. See V2_DESIGN.md for the necessary identity change.
 */
ELPIS_STREAMING_REGEX_API int elpis_streaming_regex_stream_create_v2(
    const elpis_streaming_regex_options_v2*, elpis_streaming_regex_stream_v2** out);
ELPIS_STREAMING_REGEX_API int elpis_streaming_regex_stream_feed_v2(
    elpis_streaming_regex_stream_v2*, const uint8_t*, size_t);
ELPIS_STREAMING_REGEX_API int elpis_streaming_regex_stream_finalize_v2(
    elpis_streaming_regex_stream_v2*, elpis_streaming_regex_result_v1** out);
ELPIS_STREAMING_REGEX_API void elpis_streaming_regex_stream_destroy_v2(
    elpis_streaming_regex_stream_v2*);
ELPIS_STREAMING_REGEX_API int elpis_streaming_regex_stream_stats_v2(
    const elpis_streaming_regex_stream_v2*, elpis_streaming_regex_stats_v2* out);
ELPIS_STREAMING_REGEX_API const char* elpis_streaming_regex_last_error_v2(void);
#ifdef __cplusplus
}
#endif
#endif
