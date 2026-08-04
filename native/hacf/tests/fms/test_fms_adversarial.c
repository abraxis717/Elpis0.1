#define _POSIX_C_SOURCE 200809L
#include "elpis/fms.h"
#include "elpis/fms_pal_test.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MB (1024ull * 1024ull)

static fms_config cfg_base(uint64_t hot, uint64_t warm, uint64_t cold) {
    fms_config c;
    memset(&c, 0, sizeof c);
    c.tier_budget[FMS_HOT] = hot;
    c.tier_budget[FMS_WARM] = warm;
    c.tier_budget[FMS_COLD] = cold;
    c.domain_ceiling[FMS_DOM_RAM] = warm + hot + 4 * MB;
    c.domain_ceiling[FMS_DOM_DEVICE] = hot ? hot : 1;
    c.domain_ceiling[FMS_DOM_STORAGE] = cold ? cold : 1;
    c.high_wm = 0.50f;
    c.low_wm = 0.40f;
    c.max_objects = 16;
    c.hot_absent_policy = FMS_FOLD_DOWN;
    c.cold_absent_policy = FMS_REJECT;
    return c;
}

static int lease_after_reap(const char *root) {
    fms_pal_test_opts opts;
    memset(&opts, 0, sizeof opts);
    opts.cold_root = root;
    opts.emulate_device = 1;
    opts.device_domain = FMS_DOM_DEVICE;
    opts.fence_mode = FMS_FENCE_PENDING;
    fms_pal *pal = fms_pal_test_create(&opts);
    fms_config cfg = cfg_base(2 * MB, 2 * MB, 8 * MB);
    fms_ctx *ctx = fms_create(&cfg, pal);
    if (!ctx) return 1;

    unsigned char *buf = malloc(MB);
    if (!buf) return 1;
    memset(buf, 0x5a, MB);
    fms_id id;
    if ((int)fms_register(ctx, 1, MB, FMS_HOT, 0.0f, buf, &id) != FMS_HOT) return 1;
    fms_lease *lease = NULL;
    if (fms_lease_acquire(ctx, id, FMS_HOT, FMS_READ, &lease) != FMS_OK) return 1;
    int fence = 1;
    if (fms_lease_bind_fence(ctx, lease, &fence) != FMS_OK) return 1;
    fms_pal_test_set_fence_mode(pal, FMS_FENCE_COMPLETE);
    if (fms_reap(ctx) != FMS_OK) return 1;
    if (fms_lease_release(ctx, lease) != FMS_OK) return 1;

    fms_object_info info;
    if (fms_query(ctx, id, &info) != FMS_OK || info.pin_count != 0 || info.lease_count != 0) return 1;
    fms_unregister(ctx, id);
    free(buf);
    fms_destroy(ctx);
    return 0;
}

static int pressure_does_not_poison(const char *root) {
    fms_pal_test_opts opts;
    memset(&opts, 0, sizeof opts);
    opts.cold_root = root;
    fms_config cfg = cfg_base(0, 4 * MB, 1 * MB);
    cfg.domain_ceiling[FMS_DOM_RAM] = 4 * MB;
    fms_ctx *ctx = fms_create(&cfg, fms_pal_test_create(&opts));
    if (!ctx) return 1;

    unsigned char *a = malloc(2 * MB), *b = malloc(2 * MB);
    if (!a || !b) return 1;
    memset(a, 0x11, 2 * MB);
    memset(b, 0x22, 2 * MB);
    fms_id ia, ib;
    if (fms_register(ctx, 1, 2 * MB, FMS_WARM, 0.0f, a, &ia) < 0) return 1;
    if (fms_register(ctx, 1, 2 * MB, FMS_WARM, 0.0f, b, &ib) < 0) return 1;
    if (fms_pump(ctx) != FMS_OK) return 1;

    void *p = NULL;
    if (fms_acquire(ctx, ia, FMS_WARM, FMS_READ, &p) < 0 || ((unsigned char *)p)[0] != 0x11) return 1;
    fms_release(ctx, ia);
    if (fms_acquire(ctx, ib, FMS_WARM, FMS_READ, &p) < 0 || ((unsigned char *)p)[0] != 0x22) return 1;
    fms_release(ctx, ib);
    fms_object_info x, y;
    fms_query(ctx, ia, &x);
    fms_query(ctx, ib, &y);
    if (x.state != FMS_ST_RESIDENT || y.state != FMS_ST_RESIDENT) return 1;

    fms_unregister(ctx, ia);
    fms_unregister(ctx, ib);
    free(a);
    free(b);
    fms_destroy(ctx);
    return 0;
}

int main(int argc, char **argv) {
    const char *base = argc > 1 ? argv[1] : "/tmp/elpis-fms-adversarial";
    char a[512], b[512];
    snprintf(a, sizeof a, "%s/lease", base);
    snprintf(b, sizeof b, "%s/pressure", base);
    if (lease_after_reap(a) != 0) {
        fprintf(stderr, "lease-after-reap invariant failed\n");
        return 1;
    }
    if (pressure_does_not_poison(b) != 0) {
        fprintf(stderr, "pressure poisoned an intact object\n");
        return 1;
    }
    puts("FMS adversarial checks: PASS");
    return 0;
}
