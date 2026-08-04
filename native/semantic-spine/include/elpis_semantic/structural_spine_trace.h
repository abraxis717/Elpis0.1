/* elpis_semantic/structural_spine_trace.h — Spine trace sidecar v1.
 *
 * Preserves recoverable correspondence between structural refinement steps
 * and the guarded P8/P9 boundary. Read-only attachment.
 *
 * Identity domain: "elpis.semantic.structural_spine_trace.v1"
 */
#ifndef ELPIS_SEMANTIC_STRUCTURAL_SPINE_TRACE_H
#define ELPIS_SEMANTIC_STRUCTURAL_SPINE_TRACE_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SPINE_TRACE_MAX_STEPS 32u

typedef enum spine_trace_step_disposition {
    SPINE_TRACE_COMMITTED = 0,
    SPINE_TRACE_REJECTED = 1,
    SPINE_TRACE_NOOP = 2,
} spine_trace_step_disposition;

typedef struct spine_trace_step_v1 {
    uint32_t                          step_index;
    uint32_t                          disposition;     /* spine_trace_step_disposition */
    hacf_digest                       native_proposal_digest;
    hacf_digest                       candidate_frame_digest;
    hacf_digest                       decoded_candidate_digest;
    hacf_digest                       guard_receipt_digest;
    hacf_digest                       committed_state_digest;
    uint32_t                          admitted_changes;
    uint32_t                          candidate_changes;
    uint8_t                           reserved[64];
} spine_trace_step_v1;

typedef struct elpis_semantic_structural_spine_trace_v1 {
    uint32_t                          step_count;
    spine_trace_step_v1               steps[SPINE_TRACE_MAX_STEPS];
    hacf_digest                       initial_state_digest;
    hacf_digest                       final_state_digest;
    hacf_digest                       integration_trace_digest;
    hacf_digest                       complete_trace_digest;
    uint8_t                           reserved[128];
} elpis_semantic_structural_spine_trace_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                           */
/* ──────────────────────────────────────────────────────────────────── */

void elpis_spine_trace_init(elpis_semantic_structural_spine_trace_v1 *trace);
int elpis_spine_trace_add_step(
    elpis_semantic_structural_spine_trace_v1 *trace,
    const spine_trace_step_v1 *step);
int elpis_spine_trace_identity(
    const elpis_semantic_structural_spine_trace_v1 *trace, hacf_digest *out);
int elpis_spine_trace_validate(
    const elpis_semantic_structural_spine_trace_v1 *trace);

#ifdef __cplusplus
}
#endif

#endif /* ELPIS_SEMANTIC_STRUCTURAL_SPINE_TRACE_H */
