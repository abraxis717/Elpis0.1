#include "elpis/cascade.h"
#include "elpis/sha256.h"

#include <pthread.h>
#include <stdlib.h>
#include <string.h>

typedef struct entry {
    hacf_entry_info info;
    hacf_digest policy;
    hacf_digest deps[HACF_MAX_LINKS];
    uint64_t not_before;
    uint64_t deadline;
} entry;

struct hacf_queue {
    entry *entries;
    uint32_t capacity;
    uint32_t count;
    uint64_t sequence;
    pthread_mutex_t mu;
};

static void put_u32(elpis_sha256_ctx *h, uint32_t v) {
    uint8_t b[4] = {(uint8_t)(v >> 24), (uint8_t)(v >> 16),
                    (uint8_t)(v >> 8), (uint8_t)v};
    elpis_sha256_update(h, b, sizeof b);
}

static void put_u64(elpis_sha256_ctx *h, uint64_t v) {
    uint8_t b[8];
    for (int i = 7; i >= 0; --i) {
        b[i] = (uint8_t)v;
        v >>= 8;
    }
    elpis_sha256_update(h, b, sizeof b);
}

static void put_digest(elpis_sha256_ctx *h, const hacf_digest *d) {
    elpis_sha256_update(h, d->bytes, HACF_DIGEST_BYTES);
}

int hacf_digest_package(const hacf_package_spec *s, hacf_digest *out) {
    if (!s || !out || (!s->payload && s->payload_bytes) ||
        s->parent_count > HACF_MAX_LINKS ||
        s->dependency_count > HACF_MAX_LINKS) {
        return -1;
    }
    if ((s->parent_count && !s->parents) ||
        (s->dependency_count && !s->dependencies) ||
        !s->abi_version || !s->object_type || !s->schema_version) {
        return -1;
    }

    elpis_sha256_ctx h;
    static const uint8_t tag[] = "ELPIS-HACF-PACKAGE-V1";
    elpis_sha256_init(&h);
    elpis_sha256_update(&h, tag, sizeof tag - 1);
    put_u32(&h, s->abi_version);
    put_u32(&h, s->object_type);
    put_u32(&h, s->schema_version);
    put_u32(&h, s->authority);
    put_digest(&h, &s->schema_digest);
    put_digest(&h, &s->policy_digest);
    put_u32(&h, s->parent_count);
    for (uint32_t i = 0; i < s->parent_count; ++i) put_digest(&h, &s->parents[i]);
    put_u32(&h, s->dependency_count);
    for (uint32_t i = 0; i < s->dependency_count; ++i) put_digest(&h, &s->dependencies[i]);
    put_u64(&h, s->payload_bytes);
    elpis_sha256_update(&h, s->payload, (size_t)s->payload_bytes);
    elpis_sha256_final(&h, out->bytes);
    return 0;
}

void hacf_digest_hex(const hacf_digest *d, char out[65]) {
    if (d && out) elpis_hex32(d->bytes, out);
}

int hacf_digest_from_hex(const char hex[64], hacf_digest *out) {
    return (!hex || !out) ? -1 : elpis_unhex32(hex, out->bytes);
}

int hacf_digest_cmp(const hacf_digest *a, const hacf_digest *b) {
    return (!a || !b) ? 1 : memcmp(a->bytes, b->bytes, HACF_DIGEST_BYTES);
}

static int find_idx(hacf_queue *q, const hacf_digest *id) {
    for (uint32_t i = 0; i < q->count; ++i) {
        if (!hacf_digest_cmp(&q->entries[i].info.digest, id)) return (int)i;
    }
    return -1;
}

static int allowed_transition(uint32_t a, uint32_t b) {
    if (a == HACF_PROPOSED && b == HACF_SCHEMA_VALID) return 1;
    if (a == HACF_SCHEMA_VALID &&
        (b == HACF_DEPENDENCIES_READY || b == HACF_REJECTED || b == HACF_DEFERRED)) return 1;
    if (a == HACF_DEPENDENCIES_READY &&
        (b == HACF_ADMITTED || b == HACF_DEFERRED || b == HACF_REJECTED)) return 1;
    if (a == HACF_ADMITTED && b == HACF_RESOURCE_LEASED) return 1;
    if (a == HACF_RESOURCE_LEASED && (b == HACF_RUNNING || b == HACF_ABORTED)) return 1;
    if (a == HACF_RUNNING &&
        (b == HACF_COMMITTED || b == HACF_ABORTED || b == HACF_QUARANTINED)) return 1;
    if (a == HACF_DEFERRED &&
        (b == HACF_SCHEMA_VALID || b == HACF_DEPENDENCIES_READY || b == HACF_EXPIRED)) return 1;
    return 0;
}

hacf_queue *hacf_queue_create(uint32_t capacity) {
    if (!capacity) return NULL;
    hacf_queue *q = (hacf_queue *)calloc(1, sizeof *q);
    if (!q) return NULL;
    q->entries = (entry *)calloc(capacity, sizeof *q->entries);
    if (!q->entries) {
        free(q);
        return NULL;
    }
    if (pthread_mutex_init(&q->mu, NULL) != 0) {
        free(q->entries);
        free(q);
        return NULL;
    }
    q->capacity = capacity;
    return q;
}

void hacf_queue_destroy(hacf_queue *q) {
    if (!q) return;
    pthread_mutex_destroy(&q->mu);
    free(q->entries);
    free(q);
}

int hacf_queue_submit(hacf_queue *q, const hacf_work_spec *s, hacf_digest *out) {
    if (!q || !s || !out || s->package.dependency_count > HACF_MAX_LINKS) return -1;
    hacf_digest d;
    if (hacf_digest_package(&s->package, &d) != 0) return -1;

    pthread_mutex_lock(&q->mu);
    int old = find_idx(q, &d);
    if (old >= 0) {
        *out = d;
        pthread_mutex_unlock(&q->mu);
        return 1;
    }
    if (q->count == q->capacity) {
        pthread_mutex_unlock(&q->mu);
        return -2;
    }

    entry *e = &q->entries[q->count++];
    memset(e, 0, sizeof *e);
    e->info.digest = d;
    e->info.object_type = s->package.object_type;
    e->info.authority = s->package.authority;
    e->info.priority = s->priority;
    e->info.safety_class = s->safety_class;
    e->info.state = HACF_PROPOSED;
    e->info.dependency_count = s->package.dependency_count;
    e->info.required_capabilities = s->required_capabilities;
    e->info.required_memory_bytes = s->required_memory_bytes;
    e->info.insertion_sequence = ++q->sequence;
    e->policy = s->package.policy_digest;
    e->not_before = s->not_before_epoch;
    e->deadline = s->deadline_epoch;
    for (uint32_t i = 0; i < s->package.dependency_count; ++i) {
        e->deps[i] = s->package.dependencies[i];
    }
    *out = d;
    pthread_mutex_unlock(&q->mu);
    return 0;
}

int hacf_queue_transition(hacf_queue *q, const hacf_digest *id,
                          hacf_state expected, hacf_state next) {
    if (!q || !id) return -1;
    pthread_mutex_lock(&q->mu);
    int i = find_idx(q, id);
    if (i < 0) {
        pthread_mutex_unlock(&q->mu);
        return -2;
    }
    entry *e = &q->entries[i];
    if (e->info.state != (uint32_t)expected || !allowed_transition(expected, next)) {
        pthread_mutex_unlock(&q->mu);
        return -3;
    }
    e->info.state = next;
    pthread_mutex_unlock(&q->mu);
    return 0;
}

static int deps_ready(hacf_queue *q, const entry *e) {
    for (uint32_t d = 0; d < e->info.dependency_count; ++d) {
        int j = find_idx(q, &e->deps[d]);
        if (j < 0 || q->entries[j].info.state != HACF_COMMITTED) return 0;
    }
    return 1;
}

static int better(const entry *a, const entry *b) {
    if (a->info.authority != b->info.authority) return a->info.authority > b->info.authority;
    if (a->info.safety_class != b->info.safety_class) return a->info.safety_class < b->info.safety_class;
    if (a->info.priority != b->info.priority) return a->info.priority > b->info.priority;
    return a->info.insertion_sequence < b->info.insertion_sequence;
}

int hacf_queue_elect(hacf_queue *q, uint64_t epoch, hacf_digest *out) {
    if (!q || !out) return -1;
    pthread_mutex_lock(&q->mu);
    entry *best = NULL;
    for (uint32_t i = 0; i < q->count; ++i) {
        entry *e = &q->entries[i];
        if (e->deadline && epoch > e->deadline) {
            if (e->info.state == HACF_SCHEMA_VALID ||
                e->info.state == HACF_DEPENDENCIES_READY ||
                e->info.state == HACF_DEFERRED) {
                e->info.state = HACF_EXPIRED;
            }
            continue;
        }
        if (epoch < e->not_before) continue;
        if (e->info.state == HACF_SCHEMA_VALID && deps_ready(q, e)) {
            e->info.state = HACF_DEPENDENCIES_READY;
        }
        if (e->info.state != HACF_DEPENDENCIES_READY) continue;
        if (!best || better(e, best)) best = e;
    }
    if (!best) {
        pthread_mutex_unlock(&q->mu);
        return 1;
    }
    *out = best->info.digest;
    pthread_mutex_unlock(&q->mu);
    return 0;
}

int hacf_queue_admit(hacf_queue *q, const hacf_digest *id, uint64_t epoch,
                     uint64_t caps, uint64_t memory,
                     const hacf_digest *policy) {
    if (!q || !id || !policy) return -1;
    pthread_mutex_lock(&q->mu);
    int i = find_idx(q, id);
    if (i < 0) {
        pthread_mutex_unlock(&q->mu);
        return -2;
    }
    entry *e = &q->entries[i];
    if (e->info.state != HACF_DEPENDENCIES_READY) {
        pthread_mutex_unlock(&q->mu);
        return -3;
    }
    if ((e->deadline && epoch > e->deadline) || epoch < e->not_before) {
        e->info.state = HACF_EXPIRED;
        pthread_mutex_unlock(&q->mu);
        return -4;
    }
    if (hacf_digest_cmp(&e->policy, policy) != 0) {
        e->info.state = HACF_REJECTED;
        pthread_mutex_unlock(&q->mu);
        return -5;
    }
    if ((e->info.required_capabilities & caps) != e->info.required_capabilities ||
        e->info.required_memory_bytes > memory) {
        e->info.state = HACF_DEFERRED;
        pthread_mutex_unlock(&q->mu);
        return 1;
    }
    e->info.state = HACF_ADMITTED;
    pthread_mutex_unlock(&q->mu);
    return 0;
}

int hacf_queue_get(hacf_queue *q, const hacf_digest *id, hacf_entry_info *out) {
    if (!q || !id || !out) return -1;
    pthread_mutex_lock(&q->mu);
    int i = find_idx(q, id);
    if (i < 0) {
        pthread_mutex_unlock(&q->mu);
        return -2;
    }
    *out = q->entries[i].info;
    pthread_mutex_unlock(&q->mu);
    return 0;
}

uint32_t hacf_queue_count(hacf_queue *q) {
    if (!q) return 0;
    pthread_mutex_lock(&q->mu);
    uint32_t n = q->count;
    pthread_mutex_unlock(&q->mu);
    return n;
}

hacf_loop_type hacf_elect_loop(const hacf_loop_request *r) {
    if (!r || !r->policy_allows_retry || r->prior_attempts >= r->max_attempts) {
        return HACF_LOOP_REJECT;
    }
    switch (r->failure_class) {
    case HACF_FAIL_MISSING_EVIDENCE: return HACF_LOOP_RAG;
    case HACF_FAIL_AMBIGUOUS_STRUCTURE: return HACF_LOOP_PROJECTOR;
    case HACF_FAIL_LOCAL_INCONSISTENCY: return HACF_LOOP_TRM;
    case HACF_FAIL_COMPETING_CLAIMS: return HACF_LOOP_DARWINIAN;
    case HACF_FAIL_INVALID_ACTION: return HACF_LOOP_ACTION;
    case HACF_FAIL_RUNTIME: return HACF_LOOP_DIAGNOSTIC;
    case HACF_FAIL_MEMORY_PRESSURE: return HACF_LOOP_FMS;
    case HACF_FAIL_POLICY: return HACF_LOOP_REJECT;
    default: return HACF_LOOP_NONE;
    }
}
