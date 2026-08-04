/* elpis/fms.h - Fluid Memory Stabilizer, ABI v2.
 *
 * Changes from v1 (see docs/memory-accounting.md):
 *   - physical domain accounting decoupled from logical tiers (shared-RAM iGPU case)
 *   - opaque PAL-owned cold tokens; no path buffers in the core
 *   - explicit tier-collapse policy; no silent device emulation
 *   - leases with device fences; demotion forbidden while a fence is pending
 *   - context-level mutex; PAL owns its own state
 */
#ifndef ELPIS_FMS_H
#define ELPIS_FMS_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FMS_ABI_VERSION 2u

typedef uint64_t fms_id;

/* Logical latency tiers. */
enum { FMS_HOT = 0, FMS_WARM = 1, FMS_COLD = 2, FMS_NTIERS = 3 };

/* Physical resource domains. A tier is not a domain: on an integrated GPU both
 * HOT and WARM charge FMS_DOM_RAM. */
enum { FMS_DOM_RAM = 0, FMS_DOM_DEVICE = 1, FMS_DOM_STORAGE = 2, FMS_NDOMAINS = 3 };

typedef enum {
    FMS_OK            =  0,
    FMS_E_INVAL       = -1,
    FMS_E_NOMEM       = -2,
    FMS_E_NOTFOUND    = -3,
    FMS_E_BUSY        = -4,   /* pinned, fence pending, or move in flight */
    FMS_E_UNSUPPORTED = -5,   /* tier absent and policy is REJECT */
    FMS_E_IO          = -6,
    FMS_E_LIMIT       = -7,   /* no headroom obtainable without violating an invariant */
    FMS_E_STATE       = -8,
    FMS_E_DIGEST      = -9,   /* cold replica failed verification - never soft-recovered */
    FMS_E_DEVICE      = -10,  /* device lost or dispatch failed */
    FMS_E_TIMEOUT     = -11
} fms_status;

enum { FMS_ST_RESIDENT = 0, FMS_ST_MOVING = 1, FMS_ST_FAILED = 2, FMS_ST_LOST = 3 };

/* Access intent. WRITE invalidates the cold replica. */
enum { FMS_READ = 0x1u, FMS_WRITE = 0x2u };

/* Policy when a tier is unavailable. */
typedef enum { FMS_FOLD_DOWN = 0, FMS_REJECT = 1 } fms_absent_policy;

typedef struct fms_config {
    uint64_t tier_budget[FMS_NTIERS];      /* logical ceiling per tier, bytes */
    uint64_t domain_ceiling[FMS_NDOMAINS]; /* physical ceiling per domain, bytes; RAM covers HOT+WARM */
    float    high_wm;                      /* background demotion starts above this fraction */
    float    low_wm;                       /* and stops at or below this one */
    uint64_t move_rate_bps;                /* background mover budget; 0 = unlimited */
    uint64_t cooldown_ns;
    uint64_t min_residency_ns;
    uint64_t fence_timeout_ns;             /* 0 = wait forever */
    uint32_t max_objects;
    uint8_t  hot_absent_policy;            /* fms_absent_policy */
    uint8_t  cold_absent_policy;
} fms_config;

typedef struct fms_object_info {
    fms_id   id;
    uint32_t kind;
    uint8_t  tier;
    uint8_t  state;
    uint8_t  zero_copy;
    uint8_t  cold_replica;                 /* a verified cold copy exists */
    uint32_t pin_count;
    uint32_t lease_count;
    uint64_t size_bytes;
    uint64_t charge[FMS_NDOMAINS];
    uint64_t last_access_ns;
    uint64_t access_count;
    float    pin_priority;
    void    *ptr;
} fms_object_info;

typedef struct fms_stats {
    uint64_t tier_bytes[FMS_NTIERS];
    uint64_t domain_bytes[FMS_NDOMAINS];
    uint64_t objects, pinned_bytes, inflight_ops;
    uint64_t promotions, demotions;
    uint64_t bytes_promoted, bytes_demoted;
    uint64_t zero_copy_placements;
    uint64_t cold_replica_reuse;
    uint64_t cold_writes, cold_reads;
    uint64_t digest_failures;
    uint64_t device_failures;
    uint64_t forced_cpu_fallbacks;
    uint64_t forced_placements;
    uint64_t move_failures;
    uint64_t fence_timeouts;
    uint64_t move_p50_ns, move_p95_ns;     /* derived from an internal log2 histogram */
} fms_stats;

typedef struct fms_ctx   fms_ctx;
typedef struct fms_lease fms_lease;
typedef struct fms_pal   fms_pal;

/* Takes ownership of pal: fms_destroy() calls pal->destroy(). */
fms_ctx   *fms_create(const fms_config *cfg, fms_pal *pal);
void       fms_destroy(fms_ctx *c);

/* Returns the actual tier (>=0) or a negative fms_status. */
fms_status fms_register(fms_ctx *c, uint32_t kind, uint64_t bytes, int want_tier,
                        float pin_priority, const void *init, fms_id *out);
fms_status fms_unregister(fms_ctx *c, fms_id id);

/* Unfenced pin. Returns the actual tier (>=0). */
fms_status fms_acquire(fms_ctx *c, fms_id id, int want_tier, unsigned mode, void **ptr);
fms_status fms_release(fms_ctx *c, fms_id id);

/* Fenced pin for accelerator dispatch. The object cannot be demoted, freed or
 * unregistered until the bound fence reports completion. */
fms_status fms_lease_acquire(fms_ctx *c, fms_id id, int want_tier, unsigned mode, fms_lease **out);
fms_status fms_lease_bind_fence(fms_ctx *c, fms_lease *l, void *fence);
void      *fms_lease_ptr(const fms_lease *l);
int        fms_lease_tier(const fms_lease *l);
fms_status fms_lease_release(fms_ctx *c, fms_lease *l);   /* FMS_E_BUSY while the fence is pending */
fms_status fms_reap(fms_ctx *c);                          /* poll fences; release completed leases */

fms_status fms_touch(fms_ctx *c, fms_id id);
fms_status fms_pump(fms_ctx *c);

fms_status fms_query(fms_ctx *c, fms_id id, fms_object_info *out);
void       fms_get_stats(fms_ctx *c, fms_stats *out);
int        fms_hot_available(fms_ctx *c);
const char *fms_backend_name(fms_ctx *c);
const char *fms_strerror(int status);

#ifdef __cplusplus
}
#endif
#endif /* ELPIS_FMS_H */
