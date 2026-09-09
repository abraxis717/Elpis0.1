/* elpis_semantic/context_reevaluation.h — Post-admission context re-evaluation.
 *
 * P5 consumes an immutable P2 deficit report already evaluated against the
 * exact rebound requirement set and typed-evidence-view identity. P5 does not
 * claim to invoke P2. It verifies the report binding and preserves its exact
 * disposition.
 *
 * Identity domain: "elpis.semantic.context_reevaluation.v2"
 */
#ifndef ELPIS_SEMANTIC_CONTEXT_REEVALUATION_H
#define ELPIS_SEMANTIC_CONTEXT_REEVALUATION_H

#include "elpis_semantic/context_rebind.h"
#include "elpis_semantic/embedding_collection.h"
#include "elpis_semantic/context_deficit_report.h"
#include "elpis_semantic/typed_evidence_view.h"
#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CONTEXT_REEVALUATION_ABI_VERSION 2u

/* ──────────────────────────────────────────────────────────────────── */
/* Context re-evaluation receipt                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_context_reevaluation_v1 {
    uint32_t                abi_version;

    hacf_digest             typed_evidence_view_digest;
    hacf_digest             rebind_receipt_digest;
    hacf_digest             rebound_requirement_set_digest;
    hacf_digest             P2_deficit_policy_digest;

    hacf_digest             P2_deficit_report_digest;
    uint32_t                P2_report_disposition; /* overall_disposition from P2 */

    hacf_digest             P2_retrieval_requirement_bundle_digest;

    uint32_t                satisfied_mandatory_count;
    uint32_t                unsatisfied_mandatory_count;
    uint32_t                unsatisfied_preferred_count;
    uint32_t                diagnostic_deficit_count;
    uint32_t                blocked_evaluation_count;

    hacf_digest             reevaluation_receipt_digest;
    hacf_digest             HACF_package_digest;

    uint8_t                 reserved[64];
} elpis_semantic_context_reevaluation_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                            */
/* ──────────────────────────────────────────────────────────────────── */

/* Zero-initialize. Sets abi_version. */
void elpis_context_reevaluation_init(
    elpis_semantic_context_reevaluation_v1 *receipt);

/* Consume a post-admission P2 deficit report:
 *  1. Verify the P4 typed-evidence view and its identity.
 *  2. Verify the requirement rebind receipt and rebound set identity.
 *  3. Verify the P2 policy identity.
 *  4. Verify the supplied P2 report identity and all cross-bindings.
 *  5. Preserve the report's exact P2 disposition in the receipt.
 *
 * P5 does not invoke P2 in this ABI. The caller supplies the P2 report.
 * Returns SEMANTIC_OK on success. P2 disposition is preserved exactly:
 *   DISP_CONTEXT_SUFFICIENT, DISP_RETRIEVAL_REQUIRED,
 *   DISP_REQUIREMENT_SET_INVALID, DISP_EVALUATION_BLOCKED. */
int elpis_context_reevaluate(
    const elpis_typed_evidence_view_v1                    *typed_view,
    const elpis_semantic_context_rebind_v1                *rebind_receipt,
    const elpis_semantic_context_requirement_set_v1       *rebound_set,
    const elpis_semantic_context_deficit_policy_v1        *P2_policy,
    const elpis_semantic_context_deficit_report_v1        *P2_report,
    elpis_semantic_context_reevaluation_v1               *receipt);

/* Compute reevaluation receipt identity. Domain: "elpis.semantic.context_reevaluation.v2" */
int elpis_context_reevaluation_identity(
    const elpis_semantic_context_reevaluation_v1 *receipt, hacf_digest *out);

/* Validate: known ABI, zero reserved, non-zero required digests,
 * valid disposition enum. */
int elpis_context_reevaluation_validate(
    const elpis_semantic_context_reevaluation_v1 *receipt);

/* Persistence */
int elpis_write_context_reevaluation(const char *path,
                                      const elpis_semantic_context_reevaluation_v1 *receipt);
int elpis_read_context_reevaluation(const char *path,
                                     elpis_semantic_context_reevaluation_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
