/* elpis/fms_pal.h - Platform Abstraction Layer, ABI v2.
 * Every PAL instance owns its state. No globals. All entry points must be
 * callable concurrently from multiple threads on distinct objects. */
#ifndef ELPIS_FMS_PAL_H
#define ELPIS_FMS_PAL_H

#include "elpis/fms.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Capability bits reported by the PAL. The core honours these literally. */
enum { FMS_CAP_DEVICE = 0x1u, FMS_CAP_COLD = 0x2u, FMS_CAP_ZERO_COPY = 0x4u };

/* PAL cold return codes (negative). Mapped by the core onto fms_status. */
enum { FMS_PAL_OK = 0, FMS_PAL_EIO = -1, FMS_PAL_EDIGEST = -2, FMS_PAL_ESIZE = -3,
       FMS_PAL_ENOMEM = -4, FMS_PAL_EDEVICE = -5 };

/* Opaque, PAL-owned reference to a durable cold object. The core stores the
 * pointer and nothing else; it never sees a path. */
typedef struct fms_cold_token fms_cold_token;

/* How a HOT allocation consumes physical resources. */
typedef struct fms_hot_profile {
    uint8_t  available;        /* 0 => the core must apply hot_absent_policy */
    uint8_t  domain;           /* FMS_DOM_* charged by a HOT allocation */
    uint8_t  zero_copy;        /* 1 => hot_alloc aliases the host allocation; no duplicate bytes */
    uint8_t  reserved;
    uint64_t stage_bytes_max;  /* transient staging buffer charged to FMS_DOM_RAM during a hop */
    char     backend[32];      /* "cpu-reference", "vulkan", ... */
    char     device[96];
} fms_hot_profile;

/* Fence query result. */
enum { FMS_FENCE_COMPLETE = 0, FMS_FENCE_PENDING = 1, FMS_FENCE_LOST = -1 };

struct fms_pal {
    void    *self;
    uint32_t abi;              /* must equal FMS_ABI_VERSION */
    uint32_t caps;

    void     (*destroy)(void *self);
    uint64_t (*now_ns)(void *self);

    /* --- HOT (accelerator-addressable residency) --------------------------- */
    int  (*hot_profile)(void *self, fms_hot_profile *out);
    /* host_alias is non-NULL only when the profile advertises zero_copy. */
    int  (*hot_alloc)(void *self, uint64_t bytes, void *host_alias, void **out);
    void (*hot_free)(void *self, void *p, uint64_t bytes);
    int  (*hot_upload)(void *self, void *dev_dst, const void *host_src, uint64_t bytes);
    int  (*hot_download)(void *self, void *host_dst, const void *dev_src, uint64_t bytes);
    int  (*fence_query)(void *self, void *fence);   /* FMS_FENCE_* */

    /* --- WARM (CPU-addressable residency) ---------------------------------- */
    int  (*ram_alloc)(void *self, uint64_t bytes, void **out);
    void (*ram_free)(void *self, void *p, uint64_t bytes);

    /* --- COLD (durable, content-verified) ---------------------------------- */
    /* Must be crash-atomic: temp file -> full write -> fsync -> digest -> rename
     * -> fsync(dir). The token is published only after all of that succeeds. */
    int  (*cold_put)(void *self, const void *src, uint64_t bytes, fms_cold_token **out);
    /* Must verify byte count and digest before returning any data. */
    int  (*cold_get)(void *self, const fms_cold_token *t, void *dst, uint64_t bytes);
    void (*cold_drop)(void *self, fms_cold_token *t);   /* unlink backing store, free token */
    int  (*cold_digest)(const fms_cold_token *t, uint8_t out[32]);
    uint64_t (*cold_bytes)(const fms_cold_token *t);

    uint64_t (*bandwidth)(void *self, int from_tier, int to_tier);
};

#ifdef __cplusplus
}
#endif
#endif /* ELPIS_FMS_PAL_H */
