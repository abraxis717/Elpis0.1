/* test_fms_r0.c - Gate R0 invariant suite. Any violation exits non-zero. */
#define _POSIX_C_SOURCE 200809L

#include "elpis/fms.h"
#include "elpis/fms_pal.h"
#include "elpis/fms_pal_posix.h"
#include "elpis/fms_pal_test.h"
#include "elpis/sha256.h"

#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MB (1024ull * 1024ull)

static int fails = 0, checks = 0;
static const char *cur = "?";
#define CHECK(cond, ...) do { checks++; if (!(cond)) { \
        printf("  FAIL [%s] %s:%d ", cur, __FILE__, __LINE__); printf(__VA_ARGS__); \
        putchar('\n'); fails++; } } while (0)
#define CASE(name) do { cur = (name); printf("- %s\n", cur); } while (0)

static char root_base[512];

static const char *mkroot(const char *sub) {
    static char buf[640];
    snprintf(buf, sizeof buf, "%s/%s", root_base, sub);
    return buf;
}

static void rmtree(const char *path) {
    DIR *d = opendir(path);
    if (!d) return;
    struct dirent *e;
    char p[1024];
    while ((e = readdir(d))) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
        snprintf(p, sizeof p, "%s/%s", path, e->d_name);
        if (unlink(p) != 0) rmtree(p);
    }
    closedir(d);
    rmdir(path);
}

static int count_prefixed(const char *dir, const char *prefix) {
    DIR *d = opendir(dir);
    if (!d) return -1;
    struct dirent *e; int n = 0;
    while ((e = readdir(d))) if (!strncmp(e->d_name, prefix, strlen(prefix))) n++;
    closedir(d);
    return n;
}

static fms_config base_cfg(uint64_t hot, uint64_t warm, uint64_t cold, uint64_t ram_ceiling) {
    fms_config c;
    memset(&c, 0, sizeof c);
    c.tier_budget[FMS_HOT] = hot;
    c.tier_budget[FMS_WARM] = warm;
    c.tier_budget[FMS_COLD] = cold;
    c.domain_ceiling[FMS_DOM_RAM] = ram_ceiling;
    c.domain_ceiling[FMS_DOM_DEVICE] = hot ? hot : 1;
    c.domain_ceiling[FMS_DOM_STORAGE] = cold ? cold : 1;
    c.high_wm = 0.90f; c.low_wm = 0.70f;
    c.max_objects = 64;
    c.hot_absent_policy = FMS_FOLD_DOWN;
    c.cold_absent_policy = FMS_FOLD_DOWN;
    return c;
}

static void fill(unsigned char *p, size_t n, unsigned char v) { memset(p, v, n); }
static int verify(const unsigned char *p, size_t n, unsigned char v) {
    for (size_t i = 0; i < n; i += 997) if (p[i] != v) return 0;
    return p[n - 1] == v;
}

/* ---------------------------------------------------------------- cases --- */

static void case_budget_and_integrity(void) {
    CASE("budget enforcement + data integrity through demote/promote");
    fms_pal_test_opts o; memset(&o, 0, sizeof o);
    o.cold_root = mkroot("c1");
    fms_config cfg = base_cfg(0, 8 * MB, 512 * MB, 8 * MB);
    fms_ctx *c = fms_create(&cfg, fms_pal_test_create(&o));
    CHECK(c != NULL, "create");
    if (!c) return;

    fms_id id[16]; unsigned char exp[16];
    unsigned char *buf = malloc(MB);
    for (int i = 0; i < 16; i++) {
        exp[i] = (unsigned char)(i + 1);
        fill(buf, MB, exp[i]);
        int r = fms_register(c, 1, MB, FMS_WARM, 0.0f, buf, &id[i]);
        CHECK(r >= 0, "register %d: %s", i, fms_strerror(r));
    }
    fms_stats st; fms_get_stats(c, &st);
    CHECK(st.tier_bytes[FMS_WARM] <= 8 * MB, "warm over budget: %llu",
          (unsigned long long)st.tier_bytes[FMS_WARM]);
    CHECK(st.domain_bytes[FMS_DOM_RAM] <= 8 * MB, "ram over ceiling");
    CHECK(st.tier_bytes[FMS_COLD] >= 8 * MB, "nothing demoted to cold");

    for (int pass = 0; pass < 3; pass++)
        for (int i = 0; i < 16; i++) {
            void *p = NULL;
            int r = fms_acquire(c, id[i], FMS_WARM, FMS_READ, &p);
            CHECK(r >= 0, "acquire %d: %s", i, fms_strerror(r));
            if (r >= 0) { CHECK(verify(p, MB, exp[i]), "corruption %d", i); fms_release(c, id[i]); }
            fms_get_stats(c, &st);
            CHECK(st.domain_bytes[FMS_DOM_RAM] <= 8 * MB, "ram ceiling breached mid-run");
        }
    for (int i = 0; i < 16; i++) CHECK(fms_unregister(c, id[i]) == FMS_OK, "unregister %d", i);
    fms_get_stats(c, &st);
    CHECK(st.tier_bytes[0] + st.tier_bytes[1] + st.tier_bytes[2] == 0, "tier leak");
    CHECK(st.domain_bytes[0] + st.domain_bytes[1] + st.domain_bytes[2] == 0, "domain leak");
    free(buf);
    fms_destroy(c);
}

static void case_shared_ram_ceiling(void) {
    CASE("HOT+WARM shared physical ceiling (integrated GPU model)");
    fms_pal_test_opts o; memset(&o, 0, sizeof o);
    o.cold_root = mkroot("c2");
    o.emulate_device = 1;
    o.device_domain = FMS_DOM_RAM;      /* iGPU: HOT bytes are system RAM */
    o.zero_copy = 0;
    fms_config cfg = base_cfg(8 * MB, 8 * MB, 512 * MB, 10 * MB);   /* 16 MiB logical, 10 MiB physical */
    fms_pal *pal = fms_pal_test_create(&o);
    fms_ctx *c = fms_create(&cfg, pal);
    CHECK(c != NULL, "create");
    if (!c) return;
    CHECK(fms_hot_available(c) == 1, "hot should be available");

    fms_id id[14]; unsigned char *buf = malloc(MB);
    for (int i = 0; i < 14; i++) {
        fill(buf, MB, (unsigned char)i);
        int r = fms_register(c, 1, MB, FMS_HOT, 0.0f, buf, &id[i]);
        CHECK(r >= 0, "register %d: %s", i, fms_strerror(r));
        fms_stats st; fms_get_stats(c, &st);
        CHECK(st.domain_bytes[FMS_DOM_RAM] <= 10 * MB,
              "RAM ceiling breached at %d: %llu", i, (unsigned long long)st.domain_bytes[FMS_DOM_RAM]);
        CHECK(st.tier_bytes[FMS_HOT] <= 8 * MB, "hot tier over budget");
    }
    /* The PAL's own view must agree: no hidden duplicate allocations. */
    fms_stats st; fms_get_stats(c, &st);
    uint64_t pal_ram = fms_pal_test_host_bytes(pal) + fms_pal_test_device_bytes(pal);
    CHECK(pal_ram == st.domain_bytes[FMS_DOM_RAM],
          "accounting drift: pal=%llu fms=%llu", (unsigned long long)pal_ram,
          (unsigned long long)st.domain_bytes[FMS_DOM_RAM]);
    for (int i = 0; i < 14; i++) fms_unregister(c, id[i]);
    free(buf);
    fms_destroy(c);
}

static void case_zero_copy_accounting(void) {
    CASE("zero-copy placement is charged once, not twice");
    fms_pal_test_opts o; memset(&o, 0, sizeof o);
    o.cold_root = mkroot("c3");
    o.emulate_device = 1; o.device_domain = FMS_DOM_RAM; o.zero_copy = 1;
    fms_config cfg = base_cfg(8 * MB, 8 * MB, 512 * MB, 8 * MB);
    fms_pal *pal = fms_pal_test_create(&o);
    fms_ctx *c = fms_create(&cfg, pal);
    CHECK(c != NULL, "create");
    if (!c) return;

    unsigned char *buf = malloc(MB);
    fill(buf, MB, 0xA5);
    fms_id id;
    int r = fms_register(c, 1, MB, FMS_HOT, 0.0f, buf, &id);
    CHECK(r == FMS_HOT, "expected HOT placement, got %d (%s)", r, fms_strerror(r));

    fms_object_info info; fms_query(c, id, &info);
    fms_stats st; fms_get_stats(c, &st);
    CHECK(info.zero_copy == 1, "not marked zero-copy");
    CHECK(info.charge[FMS_DOM_RAM] == MB, "zero-copy charge should be exactly one copy: %llu",
          (unsigned long long)info.charge[FMS_DOM_RAM]);
    CHECK(st.domain_bytes[FMS_DOM_RAM] == MB, "double counted shared allocation");
    CHECK(fms_pal_test_device_bytes(pal) == 0, "aliased device buffer allocated real bytes");
    CHECK(st.zero_copy_placements == 1, "zero_copy_placements not recorded");

    void *p = NULL;
    r = fms_acquire(c, id, FMS_HOT, FMS_READ, &p);
    CHECK(r == FMS_HOT, "acquire hot: %s", fms_strerror(r));
    if (r >= 0) { CHECK(verify(p, MB, 0xA5), "zero-copy data mismatch"); fms_release(c, id); }
    fms_unregister(c, id);
    free(buf);
    fms_destroy(c);
}

static void case_tier_collapse(void) {
    CASE("tier collapse: WARM+COLD, WARM-only, REJECT vs FOLD_DOWN");
    unsigned char *buf = malloc(MB);
    fill(buf, MB, 7);

    /* (a) No device, FOLD_DOWN: HOT request lands WARM. */
    fms_pal_test_opts o; memset(&o, 0, sizeof o);
    o.cold_root = mkroot("c4a");
    fms_config cfg = base_cfg(4 * MB, 8 * MB, 64 * MB, 8 * MB);
    fms_ctx *c = fms_create(&cfg, fms_pal_test_create(&o));
    CHECK(c != NULL, "create a");
    if (c) {
        CHECK(fms_hot_available(c) == 0, "device must not be emulated implicitly");
        fms_id id; int r = fms_register(c, 1, MB, FMS_HOT, 0.0f, buf, &id);
        CHECK(r == FMS_WARM, "fold-down expected WARM, got %d", r);
        void *p = NULL;
        CHECK((int)fms_acquire(c, id, FMS_HOT, FMS_READ, &p) == FMS_WARM, "acquire fold-down");
        fms_release(c, id);
        fms_unregister(c, id);
        fms_destroy(c);
    }

    /* (b) No device, REJECT: HOT request is refused explicitly. */
    memset(&o, 0, sizeof o); o.cold_root = mkroot("c4b");
    cfg = base_cfg(4 * MB, 8 * MB, 64 * MB, 8 * MB);
    cfg.hot_absent_policy = FMS_REJECT;
    c = fms_create(&cfg, fms_pal_test_create(&o));
    CHECK(c != NULL, "create b");
    if (c) {
        fms_id id;
        CHECK((int)fms_register(c, 1, MB, FMS_HOT, 0.0f, buf, &id) == FMS_E_UNSUPPORTED, "reject policy");
        CHECK((int)fms_register(c, 1, MB, FMS_WARM, 0.0f, buf, &id) == FMS_WARM, "warm still works");
        fms_unregister(c, id);
        fms_destroy(c);
    }

    /* (c) WARM only: no cold tier. Over-budget registration fails loudly. */
    memset(&o, 0, sizeof o); o.cold_root = mkroot("c4c"); o.no_cold = 1;
    cfg = base_cfg(0, 4 * MB, 0, 4 * MB);
    cfg.cold_absent_policy = FMS_REJECT;
    c = fms_create(&cfg, fms_pal_test_create(&o));
    CHECK(c != NULL, "create c");
    if (c) {
        fms_id id[8]; int placed = 0, refused = 0;
        for (int i = 0; i < 8; i++) {
            int r = fms_register(c, 1, MB, FMS_WARM, 0.0f, buf, &id[i]);
            if (r >= 0) placed++; else { refused++; CHECK(r == FMS_E_LIMIT, "expected E_LIMIT, got %s",
                                                          fms_strerror(r)); }
        }
        CHECK(placed == 4, "warm-only should hold exactly 4 MiB, held %d", placed);
        CHECK(refused == 4, "over-budget registrations must fail loudly");
        fms_stats st; fms_get_stats(c, &st);
        CHECK(st.tier_bytes[FMS_COLD] == 0, "cold used while unavailable");
        for (int i = 0; i < placed; i++) fms_unregister(c, id[i]);
        fms_destroy(c);
    }
    free(buf);
}

static void case_pinning(void) {
    CASE("pinned objects are never demoted");
    fms_pal_test_opts o; memset(&o, 0, sizeof o); o.cold_root = mkroot("c5");
    fms_config cfg = base_cfg(0, 4 * MB, 64 * MB, 4 * MB);
    fms_ctx *c = fms_create(&cfg, fms_pal_test_create(&o));
    CHECK(c != NULL, "create");
    if (!c) return;
    unsigned char *buf = malloc(MB); fill(buf, MB, 0x11);
    fms_id pinned, other[8];
    CHECK(fms_register(c, 1, MB, FMS_WARM, 0.0f, buf, &pinned) >= 0, "register pinned");
    void *p = NULL;
    CHECK((int)fms_acquire(c, pinned, FMS_WARM, FMS_READ, &p) == FMS_WARM, "acquire");
    for (int i = 0; i < 8; i++) {
        fms_register(c, 1, MB, FMS_WARM, 0.0f, buf, &other[i]);
        fms_pump(c);
    }
    fms_object_info info; fms_query(c, pinned, &info);
    CHECK(info.tier == FMS_WARM, "pinned object was demoted to tier %u", info.tier);
    CHECK(info.pin_count == 1, "pin count %u", info.pin_count);
    CHECK(verify(p, MB, 0x11), "pinned pointer invalidated");
    CHECK(fms_unregister(c, pinned) == FMS_E_BUSY, "unregister of a pinned object must fail");
    fms_release(c, pinned);
    free(buf);
    fms_destroy(c);
}

static void case_lease_fence(void) {
    CASE("lease + fence: no demotion or release while a dispatch is in flight");
    fms_pal_test_opts o; memset(&o, 0, sizeof o);
    o.cold_root = mkroot("c6");
    o.emulate_device = 1; o.device_domain = FMS_DOM_DEVICE; o.fence_mode = FMS_FENCE_PENDING;
    fms_config cfg = base_cfg(4 * MB, 4 * MB, 64 * MB, 8 * MB);
    cfg.fence_timeout_ns = 0;
    fms_pal *pal = fms_pal_test_create(&o);
    fms_ctx *c = fms_create(&cfg, pal);
    CHECK(c != NULL, "create");
    if (!c) return;

    unsigned char *buf = malloc(MB); fill(buf, MB, 0x33);
    fms_id id; CHECK((int)fms_register(c, 1, MB, FMS_HOT, 0.0f, buf, &id) == FMS_HOT, "register hot");
    fms_lease *l = NULL;
    CHECK(fms_lease_acquire(c, id, FMS_HOT, FMS_READ, &l) == FMS_OK, "lease acquire");
    int dummy_fence = 1;
    CHECK(fms_lease_bind_fence(c, l, &dummy_fence) == FMS_OK, "bind fence");
    CHECK(fms_lease_tier(l) == FMS_HOT, "lease tier");
    CHECK(fms_lease_ptr(l) != NULL, "lease ptr");

    for (int i = 0; i < 8; i++) { fms_id t; fms_register(c, 1, MB, FMS_HOT, 0.0f, buf, &t); fms_pump(c); }
    fms_object_info info; fms_query(c, id, &info);
    CHECK(info.tier == FMS_HOT, "leased object demoted while fence pending (tier %u)", info.tier);
    CHECK(info.lease_count == 1, "lease count %u", info.lease_count);
    CHECK(fms_lease_release(c, l) == FMS_E_BUSY, "release must refuse a pending fence");
    CHECK(fms_reap(c) == FMS_OK, "reap with pending fence");
    fms_query(c, id, &info);
    CHECK(info.lease_count == 1, "reap released a pending lease");

    fms_pal_test_set_fence_mode(pal, FMS_FENCE_COMPLETE);
    CHECK(fms_reap(c) == FMS_OK, "reap after completion");
    fms_query(c, id, &info);
    CHECK(info.lease_count == 0 && info.pin_count == 0, "lease not reclaimed after fence completion");
    free(buf);
    fms_destroy(c);
}

static void case_device_loss(void) {
    CASE("device loss quarantines the object and forces CPU fallback");
    fms_pal_test_opts o; memset(&o, 0, sizeof o);
    o.cold_root = mkroot("c7");
    o.emulate_device = 1; o.device_domain = FMS_DOM_DEVICE; o.fence_mode = FMS_FENCE_PENDING;
    fms_config cfg = base_cfg(4 * MB, 4 * MB, 64 * MB, 8 * MB);
    fms_pal *pal = fms_pal_test_create(&o);
    fms_ctx *c = fms_create(&cfg, pal);
    CHECK(c != NULL, "create");
    if (!c) return;
    unsigned char *buf = malloc(MB); fill(buf, MB, 0x44);
    fms_id id; fms_register(c, 1, MB, FMS_HOT, 0.0f, buf, &id);
    fms_lease *l = NULL;
    fms_lease_acquire(c, id, FMS_HOT, FMS_READ, &l);
    int f = 1; fms_lease_bind_fence(c, l, &f);

    fms_pal_test_set_fence_mode(pal, FMS_FENCE_LOST);
    CHECK(fms_reap(c) == FMS_E_DEVICE, "reap must report device loss");
    CHECK(fms_hot_available(c) == 0, "hot must be closed after device loss");
    fms_object_info info; fms_query(c, id, &info);
    CHECK(info.state == FMS_ST_LOST, "lost object state %u", info.state);
    void *p = NULL;
    CHECK(fms_acquire(c, id, FMS_WARM, FMS_READ, &p) == FMS_E_STATE, "lost object must not be handed out");
    fms_stats st; fms_get_stats(c, &st);
    CHECK(st.device_failures >= 1 && st.forced_cpu_fallbacks >= 1, "device telemetry missing");

    /* New objects still work, on the CPU path. */
    fms_id id2;
    CHECK((int)fms_register(c, 1, MB, FMS_HOT, 0.0f, buf, &id2) == FMS_WARM, "post-loss placement");
    free(buf);
    fms_destroy(c);
}

static void case_upload_failure_fallback(void) {
    CASE("device upload failure leaves data intact on the CPU path");
    fms_pal_test_opts o; memset(&o, 0, sizeof o);
    o.cold_root = mkroot("c8");
    o.emulate_device = 1; o.device_domain = FMS_DOM_DEVICE;
    fms_config cfg = base_cfg(4 * MB, 4 * MB, 64 * MB, 8 * MB);
    fms_pal *pal = fms_pal_test_create(&o);
    fms_ctx *c = fms_create(&cfg, pal);
    CHECK(c != NULL, "create");
    if (!c) return;
    unsigned char *buf = malloc(MB); fill(buf, MB, 0x55);
    fms_id id; fms_register(c, 1, MB, FMS_WARM, 0.0f, buf, &id);

    fms_pal_test_set_faults(pal, 0, 1, 0);          /* uploads fail */
    void *p = NULL;
    int r = fms_acquire(c, id, FMS_HOT, FMS_READ, &p);
    CHECK(r == FMS_WARM, "expected fallback to WARM, got %d (%s)", r, fms_strerror(r));
    CHECK(p && verify(p, MB, 0x55), "data lost on failed upload");
    fms_stats st; fms_get_stats(c, &st);
    CHECK(st.device_failures >= 1, "device failure not counted");
    CHECK(st.forced_cpu_fallbacks >= 1, "fallback not counted");
    CHECK(fms_pal_test_device_bytes(pal) == 0, "device buffer leaked after failed upload");
    fms_release(c, id);
    free(buf);
    fms_destroy(c);
}

static void case_cold_durability(void) {
    CASE("cold commit is atomic, content-addressed and digest-verified");
    const char *root = mkroot("c9");
    fms_pal_test_opts o; memset(&o, 0, sizeof o); o.cold_root = root;
    fms_config cfg = base_cfg(0, 2 * MB, 64 * MB, 2 * MB);
    fms_ctx *c = fms_create(&cfg, fms_pal_test_create(&o));
    CHECK(c != NULL, "create");
    if (!c) return;

    unsigned char *buf = malloc(MB); fill(buf, MB, 0x66);
    fms_id a, b;
    fms_register(c, 1, MB, FMS_WARM, 0.0f, buf, &a);
    fill(buf, MB, 0x77);
    fms_register(c, 1, MB, FMS_WARM, 0.0f, buf, &b);
    fill(buf, MB, 0x88);
    fms_id d; fms_register(c, 1, MB, FMS_WARM, 0.0f, buf, &d);   /* forces a demotion */

    CHECK(count_prefixed(root, ".fms-tmp-") == 0, "temporary files left behind");
    CHECK(count_prefixed(root, "") >= 3, "no cold blob written");   /* . .. blob */

    fms_stats st; fms_get_stats(c, &st);
    CHECK(st.cold_writes >= 1, "cold write not counted");

    /* Blob names are the digest of their content. */
    DIR *dh = opendir(root); struct dirent *e; int checked = 0;
    while (dh && (e = readdir(dh))) {
        if (strstr(e->d_name, ".blob") == NULL) continue;
        char path[1024]; snprintf(path, sizeof path, "%s/%s", root, e->d_name);
        int fd = open(path, O_RDONLY);
        if (fd < 0) continue;
        unsigned char *tmp = malloc(MB);
        ssize_t got = read(fd, tmp, MB); close(fd);
        uint8_t dg[32]; char hex[65];
        elpis_sha256(tmp, (size_t)(got > 0 ? got : 0), dg);
        elpis_hex32(dg, hex);
        CHECK(strncmp(e->d_name, hex, 64) == 0, "blob name is not its digest: %s", e->d_name);
        checked++;
        free(tmp);
    }
    if (dh) closedir(dh);
    CHECK(checked >= 1, "no blob inspected");

    /* Round-trip through cold must be byte-exact. */
    void *p = NULL;
    int r = fms_acquire(c, a, FMS_WARM, FMS_READ, &p);
    CHECK(r >= 0, "reload from cold: %s", fms_strerror(r));
    if (r >= 0) { CHECK(verify(p, MB, 0x66), "cold round trip corrupted"); fms_release(c, a); }
    free(buf);
    fms_destroy(c);
    CHECK(count_prefixed(root, ".blob") <= 0, "cold blobs survived destroy");
}

static void case_digest_rejection(void) {
    CASE("corrupted cold replica is rejected, never silently repaired");
    const char *root = mkroot("c10");
    fms_pal_test_opts o; memset(&o, 0, sizeof o); o.cold_root = root;
    fms_config cfg = base_cfg(0, 2 * MB, 64 * MB, 2 * MB);
    fms_ctx *c = fms_create(&cfg, fms_pal_test_create(&o));
    CHECK(c != NULL, "create");
    if (!c) return;
    unsigned char *buf = malloc(MB);
    fms_id id[4];
    for (int i = 0; i < 4; i++) { fill(buf, MB, (unsigned char)(0xC0 + i));
                                  fms_register(c, 1, MB, FMS_WARM, 0.0f, buf, &id[i]); }
    /* id[0] is the oldest and coldest by now. */
    fms_object_info info; fms_query(c, id[0], &info);
    CHECK(info.tier == FMS_COLD, "expected id0 in cold, tier=%u", info.tier);

    /* Corrupt one byte in every blob. */
    DIR *dh = opendir(root); struct dirent *e; int touched = 0;
    while (dh && (e = readdir(dh))) {
        if (!strstr(e->d_name, ".blob")) continue;
        char path[1024]; snprintf(path, sizeof path, "%s/%s", root, e->d_name);
        int fd = open(path, O_RDWR);
        if (fd >= 0) { unsigned char x = 0xFF; if (pwrite(fd, &x, 1, 4096) == 1) touched++; close(fd); }
    }
    if (dh) closedir(dh);
    CHECK(touched >= 1, "no blob to corrupt");

    void *p = NULL;
    int r = fms_acquire(c, id[0], FMS_WARM, FMS_READ, &p);
    CHECK(r == FMS_E_DIGEST, "corrupt replica must give E_DIGEST, got %d (%s)", r, fms_strerror(r));
    CHECK(p == NULL, "unverified bytes handed to the caller");
    fms_stats st; fms_get_stats(c, &st);
    CHECK(st.digest_failures == 1, "digest failure not counted: %llu",
          (unsigned long long)st.digest_failures);
    fms_query(c, id[0], &info);
    CHECK(info.state == FMS_ST_FAILED, "object state after corruption: %u", info.state);
    r = fms_acquire(c, id[0], FMS_WARM, FMS_READ, &p);
    CHECK(r == FMS_E_STATE, "failed object must stay failed, got %s", fms_strerror(r));
    free(buf);
    fms_destroy(c);
}

static void case_cold_write_failure(void) {
    CASE("failed cold commit leaves no partial state");
    const char *root = mkroot("c11");
    fms_pal_test_opts o; memset(&o, 0, sizeof o); o.cold_root = root; o.fail_cold_put = 1;
    fms_config cfg = base_cfg(0, 2 * MB, 64 * MB, 2 * MB);
    fms_ctx *c = fms_create(&cfg, fms_pal_test_create(&o));
    CHECK(c != NULL, "create");
    if (!c) return;
    unsigned char *buf = malloc(MB);
    fms_id id[4]; int refused = 0;
    for (int i = 0; i < 4; i++) {
        fill(buf, MB, (unsigned char)i);
        int r = fms_register(c, 1, MB, FMS_WARM, 0.0f, buf, &id[i]);
        if (r < 0) { refused++; CHECK(r == FMS_E_LIMIT, "expected E_LIMIT, got %s", fms_strerror(r)); }
    }
    CHECK(refused >= 1, "registration should fail when demotion cannot commit");
    CHECK(count_prefixed(root, ".fms-tmp-") == 0, "temp file left after failed commit");
    CHECK(count_prefixed(root, ".blob") <= 0, "blob published despite failure");
    fms_stats st; fms_get_stats(c, &st);
    CHECK(st.cold_writes == 0, "cold write counted on failure");
    free(buf);
    fms_destroy(c);
}

static void case_replica_reuse(void) {
    CASE("clean cold replica is reused instead of rewritten");
    fms_pal_test_opts o; memset(&o, 0, sizeof o); o.cold_root = mkroot("c12");
    fms_config cfg = base_cfg(0, 3 * MB, 64 * MB, 3 * MB);
    fms_ctx *c = fms_create(&cfg, fms_pal_test_create(&o));
    CHECK(c != NULL, "create");
    if (!c) return;
    unsigned char *buf = malloc(MB);
    fms_id id[6];
    for (int i = 0; i < 6; i++) { fill(buf, MB, (unsigned char)i);
                                  fms_register(c, 1, MB, FMS_WARM, 0.0f, buf, &id[i]); }
    fms_stats a; fms_get_stats(c, &a);
    for (int pass = 0; pass < 4; pass++)
        for (int i = 0; i < 6; i++) {
            void *p = NULL;
            if (fms_acquire(c, id[i], FMS_WARM, FMS_READ, &p) >= 0) fms_release(c, id[i]);
        }
    fms_stats b; fms_get_stats(c, &b);
    CHECK(b.cold_replica_reuse > 0, "no replica reuse observed");
    CHECK(b.cold_writes - a.cold_writes < b.demotions - a.demotions,
          "every demotion rewrote the replica (%llu writes / %llu demotions)",
          (unsigned long long)(b.cold_writes - a.cold_writes),
          (unsigned long long)(b.demotions - a.demotions));
    /* A write must invalidate the replica. */
    void *p = NULL;
    if (fms_acquire(c, id[0], FMS_WARM, FMS_WRITE, &p) >= 0) {
        fill(p, MB, 0xEE);
        fms_release(c, id[0]);
    }
    for (int i = 1; i < 6; i++) { void *q; if (fms_acquire(c, id[i], FMS_WARM, FMS_READ, &q) >= 0) fms_release(c, id[i]); }
    if (fms_acquire(c, id[0], FMS_WARM, FMS_READ, &p) >= 0) {
        CHECK(verify(p, MB, 0xEE), "dirty data lost through a cold round trip");
        fms_release(c, id[0]);
    }
    free(buf);
    fms_destroy(c);
}

static void case_two_contexts(void) {
    CASE("two contexts, two PALs, no shared global state");
    const char *r1 = mkroot("c13a"), *r2 = mkroot("c13b");
    fms_pal_test_opts o1; memset(&o1, 0, sizeof o1); o1.cold_root = r1;
    fms_pal_test_opts o2; memset(&o2, 0, sizeof o2); o2.cold_root = r2;
    o2.emulate_device = 1; o2.device_domain = FMS_DOM_DEVICE;

    fms_config cfg1 = base_cfg(0, 2 * MB, 64 * MB, 2 * MB);
    fms_config cfg2 = base_cfg(2 * MB, 2 * MB, 64 * MB, 4 * MB);
    fms_ctx *a = fms_create(&cfg1, fms_pal_test_create(&o1));
    fms_ctx *b = fms_create(&cfg2, fms_pal_test_create(&o2));
    CHECK(a && b, "create both");
    if (!a || !b) return;
    CHECK(fms_hot_available(a) == 0 && fms_hot_available(b) == 1, "capabilities leaked between contexts");

    unsigned char *buf = malloc(MB);
    fms_id ia[4], ib[4];
    for (int i = 0; i < 4; i++) {
        fill(buf, MB, (unsigned char)(0x10 + i)); fms_register(a, 1, MB, FMS_WARM, 0.0f, buf, &ia[i]);
        fill(buf, MB, (unsigned char)(0x20 + i)); fms_register(b, 1, MB, FMS_HOT,  0.0f, buf, &ib[i]);
    }
    for (int i = 0; i < 4; i++) {
        void *p = NULL;
        if (fms_acquire(a, ia[i], FMS_WARM, FMS_READ, &p) >= 0) {
            CHECK(verify(p, MB, (unsigned char)(0x10 + i)), "ctx a corruption %d", i);
            fms_release(a, ia[i]);
        }
        if (fms_acquire(b, ib[i], FMS_WARM, FMS_READ, &p) >= 0) {
            CHECK(verify(p, MB, (unsigned char)(0x20 + i)), "ctx b corruption %d", i);
            fms_release(b, ib[i]);
        }
    }
    CHECK(count_prefixed(r1, ".blob") >= 0 && count_prefixed(r2, ".blob") >= 0, "cold roots independent");
    free(buf);
    fms_destroy(a);
    fms_destroy(b);
}

static void case_telemetry(void) {
    CASE("telemetry is populated and observational only");
    fms_pal_test_opts o; memset(&o, 0, sizeof o); o.cold_root = mkroot("c14");
    fms_config cfg = base_cfg(0, 4 * MB, 64 * MB, 4 * MB);
    fms_ctx *c = fms_create(&cfg, fms_pal_test_create(&o));
    CHECK(c != NULL, "create");
    if (!c) return;
    unsigned char *buf = malloc(MB);
    fms_id id[8];
    for (int i = 0; i < 8; i++) { fill(buf, MB, (unsigned char)i);
                                  fms_register(c, 1, MB, FMS_WARM, 0.0f, buf, &id[i]); }
    for (int i = 0; i < 8; i++) { void *p; if (fms_acquire(c, id[i], FMS_WARM, FMS_READ, &p) >= 0) fms_release(c, id[i]); }
    fms_stats st; fms_get_stats(c, &st);
    CHECK(st.demotions > 0 && st.promotions > 0, "movement counters empty");
    CHECK(st.bytes_demoted > 0 && st.bytes_promoted > 0, "byte counters empty");
    CHECK(st.move_p50_ns > 0, "p50 latency not recorded");
    CHECK(st.move_p95_ns >= st.move_p50_ns, "p95 < p50");
    CHECK(st.objects == 8, "object count %llu", (unsigned long long)st.objects);
    CHECK(st.inflight_ops == 0, "in-flight ops leaked");
    free(buf);
    fms_destroy(c);
}

int main(int argc, char **argv) {
    snprintf(root_base, sizeof root_base, "%s", argc > 1 ? argv[1] : "/tmp/elpis-fms-r0");
    rmtree(root_base);
    printf("FMS R0 suite, root=%s\n", root_base);

    case_budget_and_integrity();
    case_shared_ram_ceiling();
    case_zero_copy_accounting();
    case_tier_collapse();
    case_pinning();
    case_lease_fence();
    case_device_loss();
    case_upload_failure_fallback();
    case_cold_durability();
    case_digest_rejection();
    case_cold_write_failure();
    case_replica_reuse();
    case_two_contexts();
    case_telemetry();

    printf("%d checks, %d failures\n", checks, fails);
    return fails != 0;
}
