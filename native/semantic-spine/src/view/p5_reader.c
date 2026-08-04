/* p5_reader.c — Unified P5 persistence readers. */
#include "elpis_semantic/context_rebind.h"
#include "elpis_semantic/context_iteration_policy.h"
#include "elpis_semantic/context_iteration_state.h"
#include "elpis_semantic/context_reevaluation.h"
#include "elpis_semantic/context_progress.h"
#include "elpis_semantic/bounded_view_policy.h"
#include "elpis_semantic/bounded_view_seed.h"
#include "elpis_semantic/bounded_view_candidate.h"
#include "elpis_semantic/bounded_semantic_view.h"
#include "elpis_semantic/downstream_handoff.h"
#include <stdio.h>
#include <string.h>

int elpis_p5_read_all(const char *dir,
                       elpis_semantic_context_rebind_v1 *rebind,
                       elpis_semantic_context_iteration_policy_v1 *policy,
                       elpis_semantic_context_iteration_state_v1 *state,
                       elpis_semantic_context_reevaluation_v1 *reeval,
                       elpis_semantic_context_progress_v1 *progress,
                       elpis_semantic_bounded_view_policy_v1 *bview_policy,
                       elpis_semantic_bounded_view_seed_set_v1 *seeds,
                       elpis_semantic_bounded_view_candidate_set_v1 *candidates,
                       elpis_semantic_bounded_semantic_view_v1 *bview,
                       elpis_semantic_downstream_handoff_v1 *handoff)
{
    if (!dir) return SEMANTIC_E_INVAL;
    int rc = SEMANTIC_OK;
    if (rebind) rc |= elpis_read_context_rebind(dir, rebind);
    if (policy) rc |= elpis_read_iteration_policy(dir, policy);
    if (state) rc |= elpis_read_iteration_state(dir, state);
    if (reeval) rc |= elpis_read_context_reevaluation(dir, reeval);
    if (progress) rc |= elpis_read_context_progress(dir, progress);
    if (bview_policy) rc |= elpis_read_bounded_view_policy(dir, bview_policy);
    if (seeds) rc |= elpis_read_bounded_view_seed_set(dir, seeds);
    if (candidates) rc |= elpis_read_bounded_view_candidate_set(dir, candidates);
    if (bview) rc |= elpis_read_bounded_semantic_view(dir, bview);
    if (handoff) rc |= elpis_read_downstream_handoff(dir, handoff);
    return rc;
}
