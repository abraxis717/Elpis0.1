/* trm_execution_handoff.c — Future TRM execution handoff v1. */

#include "elpis_semantic/trm_execution_handoff.h"
#include "elpis_semantic/trm_persist.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdint.h>

void elpis_trm_execution_handoff_init(elpis_semantic_trm_execution_handoff_v1 *handoff) {
    if (!handoff) return;
    memset(handoff, 0, sizeof(*handoff));
    handoff->abi_version = TRM_EXECUTION_HANDOFF_VERSION;
    handoff->handoff_kind = TRM_HANDOFF_GRID81_TO_FROZEN_TRM_EXECUTION_INPUT;

    /* P9 explicit declarations: all must be 1 */
    handoff->P9_may_bind_model = 1;
    handoff->P9_may_execute_model = 1;
    handoff->P9_must_emit_candidate = 1;
    handoff->P9_must_pass_guard = 1;
    handoff->P9_may_not_mutate_P7 = 1;
    handoff->P9_may_not_mutate_fixed = 1;
    handoff->P9_may_not_feed_sidecar = 1;
    handoff->P9_may_not_define_residual = 1;
    handoff->P9_may_not_invoke_projector = 1;
    handoff->P9_may_not_grant_admission = 1;
}

int elpis_trm_execution_handoff_identity(
    const elpis_semantic_trm_execution_handoff_v1 *handoff, hacf_digest *out)
{
    if (!handoff || !out) return SEMANTIC_E_INVAL;
    return elpis_trm_digest_domain("elpis.semantic.trm_execution_handoff.v1",
        handoff->abi_version, (const uint8_t *)handoff, sizeof(*handoff), out);
}

int elpis_trm_execution_handoff_validate(
    const elpis_semantic_trm_execution_handoff_v1 *handoff)
{
    if (!handoff) return SEMANTIC_E_INVAL;
    if (handoff->abi_version != TRM_EXECUTION_HANDOFF_VERSION) return SEMANTIC_E_INVAL;
    if (handoff->handoff_kind != TRM_HANDOFF_GRID81_TO_FROZEN_TRM_EXECUTION_INPUT) {
        return SEMANTIC_E_INVAL;
    }

    /* P9 declarations must all be 1 */
    if (handoff->P9_may_bind_model != 1) return SEMANTIC_E_INVAL;
    if (handoff->P9_may_execute_model != 1) return SEMANTIC_E_INVAL;
    if (handoff->P9_must_emit_candidate != 1) return SEMANTIC_E_INVAL;
    if (handoff->P9_must_pass_guard != 1) return SEMANTIC_E_INVAL;
    if (handoff->P9_may_not_mutate_P7 != 1) return SEMANTIC_E_INVAL;
    if (handoff->P9_may_not_mutate_fixed != 1) return SEMANTIC_E_INVAL;
    if (handoff->P9_may_not_feed_sidecar != 1) return SEMANTIC_E_INVAL;
    if (handoff->P9_may_not_define_residual != 1) return SEMANTIC_E_INVAL;
    if (handoff->P9_may_not_invoke_projector != 1) return SEMANTIC_E_INVAL;
    if (handoff->P9_may_not_grant_admission != 1) return SEMANTIC_E_INVAL;

    for (size_t i = 0; i < sizeof(handoff->reserved); i++) {
        if (handoff->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_write_trm_execution_handoff(const char *path,
    const elpis_semantic_trm_execution_handoff_v1 *handoff)
{
    if (!path || !handoff) return SEMANTIC_E_INVAL;
    return elpis_trm_write_binary(path, (const uint8_t *)handoff, (uint32_t)sizeof(*handoff));
}

int elpis_read_trm_execution_handoff(const char *path,
    elpis_semantic_trm_execution_handoff_v1 *out)
{
    if (!path || !out) return SEMANTIC_E_INVAL;
    memset(out, 0, sizeof(*out));
    uint32_t actual = 0;
    int ret = elpis_trm_read_binary(path, (uint8_t *)out, (uint32_t)sizeof(*out), &actual);
    if (ret < 0) return SEMANTIC_E_IO;
    if (actual != (uint32_t)sizeof(*out)) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}
