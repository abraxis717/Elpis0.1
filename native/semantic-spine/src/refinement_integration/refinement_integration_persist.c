/* refinement_integration_persist.c — Persistence helpers for P12 integration types. */
#include "elpis_semantic/refinement_backend.h"
#include "elpis_semantic/refinement_backend_registry.h"
#include "elpis_semantic/refinement_integration_policy.h"
#include "elpis_semantic/refinement_integration_request.h"
#include "elpis_semantic/refinement_integration_result.h"
#include "elpis_semantic/refinement_integration_handoff.h"
#include "elpis_semantic/refinement_integration_receipt.h"
#include <stdio.h>

/* Aggregate write function — writes all P12 types to a given directory. */
int elpis_persist_integration_artifacts(const char *dir,
    const elpis_semantic_refinement_backend_registry_v1 *registry,
    const elpis_semantic_refinement_integration_policy_v1 *policy,
    const elpis_semantic_refinement_integration_request_v1 *request,
    const elpis_semantic_refinement_integration_result_v1 *result,
    const elpis_semantic_refinement_integration_handoff_v1 *handoff,
    const elpis_semantic_refinement_integration_receipt_v1 *receipt) {
    char buf[512];

    snprintf(buf, sizeof(buf), "%s/backend_registry.bin", dir);
    if (elpis_write_refinement_backend_registry(buf, registry) != SEMANTIC_OK)
        return SEMANTIC_E_IO;

    snprintf(buf, sizeof(buf), "%s/integration_policy.bin", dir);
    if (elpis_write_refinement_integration_policy(buf, policy) != SEMANTIC_OK)
        return SEMANTIC_E_IO;

    snprintf(buf, sizeof(buf), "%s/integration_request.bin", dir);
    if (elpis_write_refinement_integration_request(buf, request) != SEMANTIC_OK)
        return SEMANTIC_E_IO;

    snprintf(buf, sizeof(buf), "%s/integration_result.bin", dir);
    if (elpis_write_refinement_integration_result(buf, result) != SEMANTIC_OK)
        return SEMANTIC_E_IO;

    snprintf(buf, sizeof(buf), "%s/integration_handoff.bin", dir);
    if (elpis_write_refinement_integration_handoff(buf, handoff) != SEMANTIC_OK)
        return SEMANTIC_E_IO;

    snprintf(buf, sizeof(buf), "%s/integration_receipt.bin", dir);
    if (elpis_write_refinement_integration_receipt(buf, receipt) != SEMANTIC_OK)
        return SEMANTIC_E_IO;

    return SEMANTIC_OK;
}
