/* elpis_semantic/refiner_execution.h — Execution transaction v1.
 *
 * Identity domain: "elpis.semantic.refiner_execution.v1"
 */
#ifndef ELPIS_SEMANTIC_REFINER_EXECUTION_H
#define ELPIS_SEMANTIC_REFINER_EXECUTION_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REFINER_EXECUTION_VERSION 1u

typedef enum refiner_execution_disposition {
    REFINER_EXECUTION_COMPLETE = 0u,
    REFINER_EXECUTION_NO_CHANGE = 1u,
    REFINER_EXECUTION_BLOCKED_BY_ADAPTER = 2u,
    REFINER_EXECUTION_BLOCKED_BY_CANDIDATE = 3u,
    REFINER_EXECUTION_BLOCKED_BY_TIMEOUT = 4u,
    REFINER_EXECUTION_BLOCKED_BY_FRAME = 5u,
    REFINER_EXECUTION_REJECTED_BY_GUARD = 6u,
    REFINER_EXECUTION_BLOCKED_INTERNAL = 7u,
} refiner_execution_disposition;

typedef struct elpis_semantic_refiner_execution_v1 {
    uint32_t                          abi_version;
    hacf_digest                       candidate_manifest_digest;
    hacf_digest                       input_state_digest;
    hacf_digest                       output_state_digest;
    uint32_t                          execution_steps;
    uint32_t                          disposition;  /* refiner_execution_disposition */
    uint32_t                          fixed_violation_count;
    uint32_t                          guard_rejection_count;
    hacf_digest                       execution_digest;
    uint8_t                           reserved[64];
} elpis_semantic_refiner_execution_v1;

void elpis_refiner_execution_init(elpis_semantic_refiner_execution_v1 *exec);
int elpis_refiner_execution_identity(const elpis_semantic_refiner_execution_v1 *exec,
    hacf_digest *out);
int elpis_refiner_execution_validate(const elpis_semantic_refiner_execution_v1 *exec);

int elpis_write_refiner_execution(const char *path,
    const elpis_semantic_refiner_execution_v1 *exec);
int elpis_read_refiner_execution(const char *path,
    elpis_semantic_refiner_execution_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
