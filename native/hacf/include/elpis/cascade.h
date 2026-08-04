#ifndef ELPIS_CASCADE_H
#define ELPIS_CASCADE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define HACF_DIGEST_BYTES 32u
#define HACF_MAX_LINKS 8u

typedef struct hacf_digest { uint8_t bytes[HACF_DIGEST_BYTES]; } hacf_digest;

typedef enum hacf_object_type {
    HACF_OBJ_QUERY=1, HACF_OBJ_RETRIEVAL_INTENT=2, HACF_OBJ_RETRIEVAL_BUNDLE=3,
    HACF_OBJ_PROJECTION=4, HACF_OBJ_TRM_STATE=5, HACF_OBJ_DARWINIAN_DECISION=6,
    HACF_OBJ_GRAPH_DELTA=7, HACF_OBJ_ACTION=8, HACF_OBJ_ADMISSION=9,
    HACF_OBJ_RESULT=10, HACF_OBJ_FAILURE=11, HACF_OBJ_LOOP_ELECTION=12
} hacf_object_type;

typedef enum hacf_authority {
    HACF_AUTH_ADVISORY=0, HACF_AUTH_REFERENCE=1, HACF_AUTH_CANONICAL=2, HACF_AUTH_SYSTEM=3
} hacf_authority;

typedef enum hacf_state {
    HACF_PROPOSED=0, HACF_SCHEMA_VALID=1, HACF_DEPENDENCIES_READY=2,
    HACF_ADMITTED=3, HACF_RESOURCE_LEASED=4, HACF_RUNNING=5,
    HACF_COMMITTED=6, HACF_DEFERRED=7, HACF_REJECTED=8,
    HACF_ABORTED=9, HACF_EXPIRED=10, HACF_QUARANTINED=11
} hacf_state;

typedef struct hacf_package_spec {
    uint32_t abi_version;
    uint32_t object_type;
    uint32_t schema_version;
    uint32_t authority;
    hacf_digest schema_digest;
    hacf_digest policy_digest;
    const hacf_digest *parents;
    uint32_t parent_count;
    const hacf_digest *dependencies;
    uint32_t dependency_count;
    const void *payload;
    uint64_t payload_bytes;
} hacf_package_spec;

typedef struct hacf_work_spec {
    hacf_package_spec package;
    uint32_t priority;
    uint32_t safety_class;
    uint64_t required_capabilities;
    uint64_t required_memory_bytes;
    uint64_t not_before_epoch;
    uint64_t deadline_epoch;
} hacf_work_spec;

typedef struct hacf_entry_info {
    hacf_digest digest;
    uint32_t object_type;
    uint32_t authority;
    uint32_t priority;
    uint32_t safety_class;
    uint32_t state;
    uint32_t dependency_count;
    uint64_t required_capabilities;
    uint64_t required_memory_bytes;
    uint64_t insertion_sequence;
} hacf_entry_info;

typedef struct hacf_queue hacf_queue;

int  hacf_digest_package(const hacf_package_spec *spec, hacf_digest *out);
void hacf_digest_hex(const hacf_digest *d, char out[65]);
int  hacf_digest_from_hex(const char hex[64], hacf_digest *out);
int  hacf_digest_cmp(const hacf_digest *a, const hacf_digest *b);

hacf_queue *hacf_queue_create(uint32_t capacity);
void        hacf_queue_destroy(hacf_queue *q);
int hacf_queue_submit(hacf_queue *q, const hacf_work_spec *spec, hacf_digest *out);
int hacf_queue_transition(hacf_queue *q, const hacf_digest *id,
                          hacf_state expected, hacf_state next);
int hacf_queue_elect(hacf_queue *q, uint64_t epoch, hacf_digest *out);
int hacf_queue_admit(hacf_queue *q, const hacf_digest *id, uint64_t epoch,
                     uint64_t available_capabilities, uint64_t available_memory_bytes,
                     const hacf_digest *current_policy);
int hacf_queue_get(hacf_queue *q, const hacf_digest *id, hacf_entry_info *out);
uint32_t hacf_queue_count(hacf_queue *q);

typedef enum hacf_failure_class {
    HACF_FAIL_MISSING_EVIDENCE=1, HACF_FAIL_AMBIGUOUS_STRUCTURE=2,
    HACF_FAIL_LOCAL_INCONSISTENCY=3, HACF_FAIL_COMPETING_CLAIMS=4,
    HACF_FAIL_INVALID_ACTION=5, HACF_FAIL_RUNTIME=6,
    HACF_FAIL_MEMORY_PRESSURE=7, HACF_FAIL_POLICY=8
} hacf_failure_class;

typedef enum hacf_loop_type {
    HACF_LOOP_NONE=0, HACF_LOOP_RAG=1, HACF_LOOP_PROJECTOR=2,
    HACF_LOOP_TRM=3, HACF_LOOP_DARWINIAN=4, HACF_LOOP_ACTION=5,
    HACF_LOOP_DIAGNOSTIC=6, HACF_LOOP_FMS=7, HACF_LOOP_REJECT=8
} hacf_loop_type;

typedef struct hacf_loop_request {
    uint32_t failure_class;
    uint32_t prior_attempts;
    uint32_t max_attempts;
    uint32_t policy_allows_retry;
} hacf_loop_request;

hacf_loop_type hacf_elect_loop(const hacf_loop_request *request);

#ifdef __cplusplus
}
#endif
#endif
