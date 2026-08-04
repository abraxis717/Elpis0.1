/* fms_pal_test.c - test PAL: real durable cold store, explicitly emulated device. */
#define _POSIX_C_SOURCE 200809L

#include "elpis/fms_pal_test.h"
#include "elpis/fms_pal_posix.h"

#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

typedef struct {
    fms_pal          *inner;      /* posix PAL, owns the cold store */
    fms_pal_test_opts o;
    pthread_mutex_t   mu;
    uint64_t          host_bytes, device_bytes;
} tpal;

typedef struct { fms_pal pal; tpal st; } tbundle;

static tpal *S(void *self) { return (tpal *)self; }

static uint64_t t_now(void *self) { tpal *t = S(self); return t->inner->now_ns(t->inner->self); }

static int t_ram_alloc(void *self, uint64_t n, void **out) {
    tpal *t = S(self);
    int r = t->inner->ram_alloc(t->inner->self, n, out);
    if (r == 0) { pthread_mutex_lock(&t->mu); t->host_bytes += n; pthread_mutex_unlock(&t->mu); }
    return r;
}

static void t_ram_free(void *self, void *p, uint64_t n) {
    tpal *t = S(self);
    pthread_mutex_lock(&t->mu); t->host_bytes -= n; pthread_mutex_unlock(&t->mu);
    t->inner->ram_free(t->inner->self, p, n);
}

static int t_hot_profile(void *self, fms_hot_profile *out) {
    tpal *t = S(self);
    memset(out, 0, sizeof *out);
    out->available = (uint8_t)(t->o.emulate_device != 0);
    out->domain = (uint8_t)t->o.device_domain;
    out->zero_copy = (uint8_t)(t->o.zero_copy != 0);
    out->stage_bytes_max = t->o.stage_bytes_max;
    snprintf(out->backend, sizeof out->backend, "test-emulated");
    snprintf(out->device, sizeof out->device, "emulated device (domain=%d, zero_copy=%d)",
             t->o.device_domain, t->o.zero_copy);
    return 0;
}

static int t_hot_alloc(void *self, uint64_t n, void *host_alias, void **out) {
    tpal *t = S(self);
    if (t->o.fail_hot_alloc) return FMS_PAL_EDEVICE;
    if (t->o.zero_copy) {
        if (!host_alias) return FMS_PAL_EDEVICE;
        *out = host_alias;                        /* aliased: no new physical bytes */
        return FMS_PAL_OK;
    }
    void *p = malloc((size_t)n);
    if (!p) return FMS_PAL_ENOMEM;
    pthread_mutex_lock(&t->mu); t->device_bytes += n; pthread_mutex_unlock(&t->mu);
    *out = p;
    return FMS_PAL_OK;
}

static void t_hot_free(void *self, void *p, uint64_t n) {
    tpal *t = S(self);
    if (t->o.zero_copy) return;                   /* alias: the host allocation owns the bytes */
    pthread_mutex_lock(&t->mu); t->device_bytes -= n; pthread_mutex_unlock(&t->mu);
    free(p);
}

static int t_hot_upload(void *self, void *d, const void *s, uint64_t n) {
    tpal *t = S(self);
    if (t->o.fail_hot_upload) return FMS_PAL_EDEVICE;
    if (d != s) memcpy(d, s, (size_t)n);
    return FMS_PAL_OK;
}

static int t_hot_download(void *self, void *d, const void *s, uint64_t n) {
    tpal *t = S(self);
    if (t->o.fail_hot_download) return FMS_PAL_EDEVICE;
    if (d != s) memcpy(d, s, (size_t)n);
    return FMS_PAL_OK;
}

static int t_fence_query(void *self, void *fence) {
    tpal *t = S(self);
    (void)fence;
    return t->o.fence_mode;
}

static int t_cold_put(void *self, const void *src, uint64_t n, fms_cold_token **out) {
    tpal *t = S(self);
    if (t->o.fail_cold_put) return FMS_PAL_EIO;
    return t->inner->cold_put(t->inner->self, src, n, out);
}
static int t_cold_get(void *self, const fms_cold_token *tok, void *dst, uint64_t n) {
    tpal *t = S(self);
    return t->inner->cold_get(t->inner->self, tok, dst, n);
}
static void t_cold_drop(void *self, fms_cold_token *tok) {
    tpal *t = S(self);
    t->inner->cold_drop(t->inner->self, tok);
}
/* The cold store is the posix PAL's, so its token accessors are used directly. */

static uint64_t t_bandwidth(void *self, int from, int to) {
    tpal *t = S(self);
    return t->inner->bandwidth(t->inner->self, from, to);
}

static void t_destroy(void *self) {
    tpal *t = S(self);
    tbundle *b = (tbundle *)((char *)t - offsetof(tbundle, st));
    t->inner->destroy(t->inner->self);
    pthread_mutex_destroy(&t->mu);
    free(b);
}

fms_pal *fms_pal_test_create(const fms_pal_test_opts *o) {
    if (!o || !o->cold_root) return NULL;
    fms_pal *inner = fms_pal_posix_create(o->cold_root);
    if (!inner) return NULL;

    tbundle *b = (tbundle *)calloc(1, sizeof *b);
    if (!b) { inner->destroy(inner->self); return NULL; }
    b->st.inner = inner;
    b->st.o = *o;
    if (pthread_mutex_init(&b->st.mu, NULL) != 0) { inner->destroy(inner->self); free(b); return NULL; }

    fms_pal *p = &b->pal;
    p->self = &b->st;
    p->abi = FMS_ABI_VERSION;
    p->caps = 0;
    if (!o->no_cold) p->caps |= FMS_CAP_COLD;
    if (o->emulate_device) {
        p->caps |= FMS_CAP_DEVICE;
        if (o->zero_copy) p->caps |= FMS_CAP_ZERO_COPY;
    }
    p->destroy = t_destroy;
    p->now_ns = t_now;
    p->hot_profile = t_hot_profile;
    p->hot_alloc = t_hot_alloc; p->hot_free = t_hot_free;
    p->hot_upload = t_hot_upload; p->hot_download = t_hot_download;
    p->fence_query = t_fence_query;
    p->ram_alloc = t_ram_alloc; p->ram_free = t_ram_free;
    p->cold_put = t_cold_put; p->cold_get = t_cold_get; p->cold_drop = t_cold_drop;
    p->cold_digest = fms_pal_posix_token_digest; p->cold_bytes = fms_pal_posix_token_bytes;
    p->bandwidth = t_bandwidth;
    return p;
}

void fms_pal_test_set_fence_mode(fms_pal *p, int mode) {
    if (p) S(p->self)->o.fence_mode = mode;
}

void fms_pal_test_set_faults(fms_pal *p, int alloc, int upload, int download) {
    if (!p) return;
    tpal *t = S(p->self);
    t->o.fail_hot_alloc = alloc; t->o.fail_hot_upload = upload; t->o.fail_hot_download = download;
}

uint64_t fms_pal_test_host_bytes(fms_pal *p)   { return p ? S(p->self)->host_bytes : 0; }
uint64_t fms_pal_test_device_bytes(fms_pal *p) { return p ? S(p->self)->device_bytes : 0; }
