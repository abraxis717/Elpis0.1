/* elpis_semantic/bounded_view_seed.h — Bounded-view seed-set construction.
 *
 * Seeds are the mandatory starting points for bounded-view construction.
 *
 * Identity domain: "elpis.semantic.bounded_view_seed_set.v1"
 */
#ifndef ELPIS_SEMANTIC_BOUNDED_VIEW_SEED_H
#define ELPIS_SEMANTIC_BOUNDED_VIEW_SEED_H

#include "elpis_semantic/context_deficit.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BOUNDED_VIEW_SEED_ABI_VERSION 1u
#define BOUNDED_VIEW_MAX_SEEDS        512u

typedef enum bounded_view_seed_reason {
    SEED_REASON_QUERY_ANCHOR      = 0,
    SEED_REASON_REQUIREMENT_TARGET = 1,
    SEED_REASON_REQUIREMENT_WITNESS = 2,
    SEED_REASON_CONFLICT_ANCHOR   = 3,
    SEED_REASON_SCOPE_ANCHOR      = 4,
    SEED_REASON_QUALIFIER_ANCHOR  = 5,
    SEED_REASON_DIAGNOSTIC_ANCHOR = 6
} bounded_view_seed_reason;

typedef enum bounded_view_seed_priority {
    SEED_PRIORITY_MANDATORY  = 0,
    SEED_PRIORITY_PREFERRED  = 1,
    SEED_PRIORITY_DIAGNOSTIC = 2
} bounded_view_seed_priority;

typedef struct bounded_view_seed_record {
    semantic_asserted_object_kind semantic_object_kind;
    hacf_digest                   semantic_object_digest;
    uint32_t                      seed_reason;
    hacf_digest                   originating_requirement_digest;
    uint32_t                      requirement_level;
    uint32_t                      seed_priority_class;
    uint32_t                      mandatory_inclusion;
    uint8_t                       reserved[32];
} bounded_view_seed_record;

/* Forward declarations — full types in other headers */
typedef struct elpis_typed_evidence_view_v1 elpis_typed_evidence_view_v1;
typedef struct elpis_semantic_context_reevaluation_v1 elpis_semantic_context_reevaluation_v1;
typedef struct elpis_semantic_context_requirement_set_v1 elpis_semantic_context_requirement_set_v1;
typedef struct elpis_semantic_context_deficit_report_v1 elpis_semantic_context_deficit_report_v1;

typedef struct elpis_semantic_bounded_view_seed_set_v1 {
    uint32_t                abi_version;
    hacf_digest             typed_evidence_view_digest;
    hacf_digest             reevaluation_report_digest;
    hacf_digest             rebound_requirement_set_digest;
    bounded_view_seed_record ordered_seeds[BOUNDED_VIEW_MAX_SEEDS];
    uint32_t                seed_count;
    hacf_digest             seed_policy_digest;
    hacf_digest             seed_set_digest;
    uint8_t                 reserved[32];
} elpis_semantic_bounded_view_seed_set_v1;

void elpis_bounded_view_seed_set_init(elpis_semantic_bounded_view_seed_set_v1 *set);

int elpis_bounded_view_construct_seeds(
    const elpis_typed_evidence_view_v1                *typed_view,
    const elpis_semantic_context_reevaluation_v1      *reevaluation,
    const elpis_semantic_context_requirement_set_v1   *rebound_set,
    const elpis_semantic_context_deficit_report_v1    *P2_report,
    elpis_semantic_bounded_view_seed_set_v1          *seed_set);

int elpis_bounded_view_seed_set_identity(
    const elpis_semantic_bounded_view_seed_set_v1 *set, hacf_digest *out);

int elpis_bounded_view_seed_set_validate(
    const elpis_semantic_bounded_view_seed_set_v1 *set);

int elpis_write_bounded_view_seed_set(const char *path,
    const elpis_semantic_bounded_view_seed_set_v1 *set);
int elpis_read_bounded_view_seed_set(const char *path,
    elpis_semantic_bounded_view_seed_set_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
