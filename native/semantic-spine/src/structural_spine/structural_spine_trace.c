/* structural_spine_trace.c — Spine trace sidecar v1. */
#include "elpis_semantic/structural_spine_trace.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdint.h>

void elpis_spine_trace_init(elpis_semantic_structural_spine_trace_v1 *trace) {
    if (!trace) return;
    memset(trace, 0, sizeof(*trace));
}

int elpis_spine_trace_add_step(
    elpis_semantic_structural_spine_trace_v1 *trace,
    const spine_trace_step_v1 *step) {
    if (!trace || !step) return SEMANTIC_E_INVAL;
    if (trace->step_count >= SPINE_TRACE_MAX_STEPS) return SEMANTIC_E_REGISTRY_FULL;
    memcpy(&trace->steps[trace->step_count], step, sizeof(spine_trace_step_v1));
    trace->steps[trace->step_count].step_index = trace->step_count;
    trace->step_count++;
    return SEMANTIC_OK;
}

int elpis_spine_trace_identity(
    const elpis_semantic_structural_spine_trace_v1 *trace, hacf_digest *out) {
    if (!trace || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char domain[] = "elpis.semantic.structural_spine_trace.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    uint32_t f;
    f = trace->step_count;                  elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    for (uint32_t i = 0; i < trace->step_count; i++) {
        const spine_trace_step_v1 *s = &trace->steps[i];
        f = s->step_index;                  elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
        f = s->disposition;                 elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
        elpis_sha256_update(&ctx, s->native_proposal_digest.bytes, HACF_DIGEST_BYTES);
        elpis_sha256_update(&ctx, s->candidate_frame_digest.bytes, HACF_DIGEST_BYTES);
        elpis_sha256_update(&ctx, s->decoded_candidate_digest.bytes, HACF_DIGEST_BYTES);
        elpis_sha256_update(&ctx, s->guard_receipt_digest.bytes, HACF_DIGEST_BYTES);
        elpis_sha256_update(&ctx, s->committed_state_digest.bytes, HACF_DIGEST_BYTES);
        f = s->admitted_changes;            elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
        f = s->candidate_changes;           elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    }
    elpis_sha256_update(&ctx, trace->initial_state_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, trace->final_state_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, trace->integration_trace_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_spine_trace_validate(const elpis_semantic_structural_spine_trace_v1 *trace) {
    if (!trace) return SEMANTIC_E_INVAL;
    if (trace->step_count > SPINE_TRACE_MAX_STEPS) return SEMANTIC_E_INVAL;
    for (uint32_t i = 0; i < trace->step_count; i++) {
        if (trace->steps[i].step_index != i) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}
