/* elpis_semantic/evidence_span.h — Exact evidence-span anchors.
 *
 * An evidence span is an exact byte range inside one verified evidence chunk.
 * Offsets are byte offsets, not Unicode code-point offsets. Source bytes are
 * never normalized, trimmed, or re-encoded before validation.
 *
 * Identity domain: "elpis.semantic.evidence_span.v1"
 */
#ifndef ELPIS_SEMANTIC_EVIDENCE_SPAN_H
#define ELPIS_SEMANTIC_EVIDENCE_SPAN_H

#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EVIDENCE_SPAN_ABI_VERSION 1u

/* Span flags */
#define EVIDENCE_SPAN_FLAG_NONE   0u
#define EVIDENCE_SPAN_FLAG_PRIMARY 0x01u
#define EVIDENCE_SPAN_FLAG_MASK   0x01u

typedef struct elpis_evidence_span_v1 {
    uint32_t        abi_version;
    hacf_digest     retrieval_expansion_digest;
    hacf_digest     retrieval_bundle_digest;
    hacf_digest     retrieval_bundle_package_digest;
    hacf_digest     retrieval_item_attachment_digest;
    hacf_digest     evidence_node_digest;
    hacf_digest     chunk_digest;
    hacf_digest     item_text_digest;
    uint32_t        byte_start;
    uint32_t        byte_end_exclusive;
    hacf_digest     span_bytes_digest;
    uint32_t        span_flags;
    hacf_digest     span_identity;
    uint8_t         reserved[32];
} elpis_evidence_span_v1;

/* Zero-initialize and set abi_version */
void elpis_evidence_span_init(elpis_evidence_span_v1 *span);

/* Compute span identity.
 * Domain: "elpis.semantic.evidence_span.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || retrieval_expansion_digest(32) || retrieval_bundle_digest(32)
 *             || retrieval_bundle_package_digest(32)
 *             || retrieval_item_attachment_digest(32)
 *             || evidence_node_digest(32) || chunk_digest(32)
 *             || item_text_digest(32) || byte_start(4 BE) || byte_end_exclusive(4 BE)
 *             || span_bytes_digest(32) || span_flags(4 BE). */
int elpis_evidence_span_identity(const elpis_evidence_span_v1 *span, hacf_digest *out);

/* Validate span:
 *  1. Retrieval expansion exists (digest nonzero).
 *  2. RetrievalBundle exists in that expansion (digest nonzero).
 *  3. Retrieval item attachment exists (digest nonzero).
 *  4. Evidence node exists (digest nonzero).
 *  5. byte_start < byte_end_exclusive.
 *  6. End offset does not exceed item_text_byte_count.
 *  7. Extracted bytes hash to span_bytes_digest.
 *  8. Reserved fields are zero. */
int elpis_evidence_span_validate(const elpis_evidence_span_v1 *span,
                                 const uint8_t *item_text, uint32_t item_text_bytes);

/* Compare spans by identity */
int elpis_evidence_span_cmp(const elpis_evidence_span_v1 *a,
                            const elpis_evidence_span_v1 *b);

/* Compare spans for canonical ordering: attachment digest, byte_start, byte_end, span digest */
int elpis_evidence_span_canonical_cmp(const elpis_evidence_span_v1 *a,
                                      const elpis_evidence_span_v1 *b);

#ifdef __cplusplus
}
#endif
#endif
