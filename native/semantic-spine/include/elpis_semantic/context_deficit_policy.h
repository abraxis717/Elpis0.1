/* elpis_semantic/context_deficit_policy.h — Deficit policy for context evaluation.
 *
 * The deficit policy defines how individual requirement failures map to the
 * overall disposition (CONTEXT_SUFFICIENT, RETRIEVAL_REQUIRED, etc.).
 * It is sealed before evaluation — no runtime mutation.
 *
 * Identity domain: "elpis.semantic.context_deficit_policy.v1"
 */
#ifndef ELPIS_SEMANTIC_CONTEXT_DEFICIT_POLICY_H
#define ELPIS_SEMANTIC_CONTEXT_DEFICIT_POLICY_H

#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CONTEXT_DEFICIT_POLICY_ABI_VERSION      1u
#define CONTEXT_MAX_RETRIEVAL_REQUIREMENTS      128u
#define CONTEXT_MAX_DEFICITS                    256u

/* ──────────────────────────────────────────────────────────────────── */
/* Mandatory-failure behavior                                            */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum mandatory_failure_behavior {
    MAND_BEHAVIOR_RETRIEVAL_REQUIRED = 1
} mandatory_failure_behavior;

/* ──────────────────────────────────────────────────────────────────── */
/* Preferred-failure behavior                                            */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum preferred_failure_behavior {
    PREFERRED_BEHAVIOR_REPORT_ONLY         = 1,
    PREFERRED_BEHAVIOR_RETRIEVAL_REQUIRED  = 2
} preferred_failure_behavior;

/* ──────────────────────────────────────────────────────────────────── */
/* Diagnostic-failure behavior                                           */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum diagnostic_failure_behavior {
    DIAG_BEHAVIOR_REPORT_ONLY = 1
} diagnostic_failure_behavior;

/* ──────────────────────────────────────────────────────────────────── */
/* Unsupported-requirement behavior                                      */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum unsupported_requirement_behavior {
    UNSUPPORTED_BEHAVIOR_FAIL_CLOSED = 1
} unsupported_requirement_behavior;

/* ──────────────────────────────────────────────────────────────────── */
/* Deficit-priority policy                                               */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum deficit_priority_policy {
    PRIORITY_LEVEL_THEN_TYPE = 1
} deficit_priority_policy;

/* ──────────────────────────────────────────────────────────────────── */
/* Deduplication policy                                                  */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum deduplication_policy {
    DEDUP_EXACT_COLLAPSE = 1
} deduplication_policy;

/* ──────────────────────────────────────────────────────────────────── */
/* Context deficit policy record                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_context_deficit_policy_v1 {
    uint32_t                            abi_version;
    uint32_t                            mandatory_failure_behavior;
    uint32_t                            preferred_failure_behavior;
    uint32_t                            diagnostic_failure_behavior;
    uint32_t                            max_retrieval_requirements;
    uint32_t                            max_deficits;
    uint32_t                            deficit_priority_policy;
    uint32_t                            retrieval_dedup_policy;
    uint32_t                            unsupported_requirement_behavior;
    uint32_t                            policy_flags;
    hacf_digest                         policy_identity;
    uint8_t                             reserved[32];
} elpis_semantic_context_deficit_policy_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Policy operations                                                     */
/* ──────────────────────────────────────────────────────────────────── */

/* Zero-initialize a deficit policy. Sets abi_version. */
void elpis_context_deficit_policy_init(
    elpis_semantic_context_deficit_policy_v1 *policy);

/* Compute policy identity. Domain: "elpis.semantic.context_deficit_policy.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || mandatory_failure_behavior(4 BE)
 *             || preferred_failure_behavior(4 BE)
 *             || diagnostic_failure_behavior(4 BE)
 *             || max_retrieval_requirements(4 BE)
 *             || max_deficits(4 BE)
 *             || deficit_priority_policy(4 BE)
 *             || retrieval_dedup_policy(4 BE)
 *             || unsupported_requirement_behavior(4 BE)
 *             || policy_flags(4 BE). */
int elpis_context_deficit_policy_identity(
    const elpis_semantic_context_deficit_policy_v1 *policy, hacf_digest *out);

/* Validate policy: known ABI, valid enum values, zero reserved,
 * max_retrieval_requirements > 0, max_deficits > 0.
 * Mandatory failure MUST be RETRIEVAL_REQUIRED.
 * Diagnostic failure MUST be REPORT_ONLY.
 * Returns SEMANTIC_OK or SEMANTIC_E_INVAL. */
int elpis_context_deficit_policy_validate(
    const elpis_semantic_context_deficit_policy_v1 *policy);

int elpis_write_deficit_policy(const char *path,
                                const elpis_semantic_context_deficit_policy_v1 *policy);
int elpis_read_deficit_policy(const char *path,
                               elpis_semantic_context_deficit_policy_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
