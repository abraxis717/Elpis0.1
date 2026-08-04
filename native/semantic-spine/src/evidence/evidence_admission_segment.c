/* evidence_admission_segment.c — Admission segment construction.
 *
 * Creates one immutable semantic segment containing all new P4 objects:
 * new claim nodes, span ref nodes, typer-profile ref nodes,
 * typing-bundle ref nodes, admission-decision ref nodes,
 * new semantic hyperedges, new assertions, new incidences.
 */

#include "elpis_semantic/identity.h"
#include "elpis_semantic/evidence_admission.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"




#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}
/*
 * Segment identity = HACF graph operations applied to prior P3 expanded view.
 * The segment is insertion-order independent: readers recalculate every
 * semantic and HACF identity.
 */

typedef struct elpis_admission_segment_v1 {
    uint32_t                abi_version;
    hacf_digest             prior_snapshot_digest;      /* P3 expanded view */
    hacf_digest             prior_segment_identity;     /* P3 segment chain */
    uint32_t                new_node_count;
    hacf_digest             new_node_digests[256];
    uint32_t                new_hyperedge_count;
    hacf_digest             new_hyperedge_digests[256];
    uint32_t                new_assertion_count;
    hacf_digest             new_assertion_digests[512];
    uint32_t                new_incidence_count;
    hacf_digest             new_incidence_digests[512];
    hacf_digest             graph_delta_digest;
    hacf_digest             resulting_snapshot_digest;
    hacf_digest             segment_payload_digest;
    hacf_digest             HACF_package_digest;
    uint8_t                 reserved[32];
} elpis_admission_segment_v1;

static const char SEGMENT_DOMAIN[] = "elpis.semantic.evidence_admission_segment.v1";

void elpis_admission_segment_init(elpis_admission_segment_v1 *segment) {
    memset(segment, 0, sizeof(*segment));
    segment->abi_version = 1;
}

int elpis_admission_segment_identity(const elpis_admission_segment_v1 *segment,
                                      hacf_digest *out) {
    if (!segment || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    elpis_sha256_update(&ctx, (const uint8_t *)SEGMENT_DOMAIN,
                       strlen(SEGMENT_DOMAIN));

    uint32_t v = __builtin_bswap32(segment->abi_version);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_update(&ctx, segment->prior_snapshot_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, segment->prior_segment_identity.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(segment->new_node_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < segment->new_node_count; i++) {
        elpis_sha256_update(&ctx, segment->new_node_digests[i].bytes, HACF_DIGEST_BYTES);
    }

    v = __builtin_bswap32(segment->new_hyperedge_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < segment->new_hyperedge_count; i++) {
        elpis_sha256_update(&ctx, segment->new_hyperedge_digests[i].bytes, HACF_DIGEST_BYTES);
    }

    v = __builtin_bswap32(segment->new_assertion_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < segment->new_assertion_count; i++) {
        elpis_sha256_update(&ctx, segment->new_assertion_digests[i].bytes, HACF_DIGEST_BYTES);
    }

    v = __builtin_bswap32(segment->new_incidence_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < segment->new_incidence_count; i++) {
        elpis_sha256_update(&ctx, segment->new_incidence_digests[i].bytes, HACF_DIGEST_BYTES);
    }

    elpis_sha256_update(&ctx, segment->graph_delta_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, segment->resulting_snapshot_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, segment->HACF_package_digest.bytes, HACF_DIGEST_BYTES);

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}
