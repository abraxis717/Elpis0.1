/* fms_pal_posix.c - durable cold store. Per-instance state; no globals.
 *
 * Commit protocol (crash-atomic):
 *   1. mkstemp() in the cold root (same directory, same filesystem)
 *   2. write() every byte, retrying short writes
 *   3. fsync(file)
 *   4. SHA-256 computed over the same bytes that were written
 *   5. rename() onto the final content-addressed name
 *   6. fsync(directory)
 *   7. only then is the token published to the caller
 *
 * Load verifies size and digest before returning any data. A mismatch is
 * reported as FMS_PAL_EDIGEST and no bytes are handed back.
 */
#define _POSIX_C_SOURCE 200809L

#include "elpis/fms_pal_posix.h"
#include "elpis/sha256.h"

#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

struct fms_cold_token {
    uint8_t  digest[32];
    uint64_t bytes;
    char    *path;
};

typedef struct {
    char           *root;
    int             dirfd;
    pthread_mutex_t mu;
    uint64_t        serial;
} posix_pal;

/* ---- utilities ------------------------------------------------------------ */

static int mkdir_p(const char *path) {
    char buf[4096];
    size_t n = strlen(path);
    if (n == 0 || n >= sizeof buf) return -1;
    memcpy(buf, path, n + 1);
    for (size_t i = 1; i < n; i++) {
        if (buf[i] != '/') continue;
        buf[i] = 0;
        if (mkdir(buf, 0700) != 0 && errno != EEXIST) return -1;
        buf[i] = '/';
    }
    if (mkdir(buf, 0700) != 0 && errno != EEXIST) return -1;
    return 0;
}

static int write_all(int fd, const void *buf, size_t n) {
    const uint8_t *p = (const uint8_t *)buf;
    while (n) {
        ssize_t w = write(fd, p, n);
        if (w < 0) { if (errno == EINTR) continue; return -1; }
        if (w == 0) return -1;
        p += (size_t)w; n -= (size_t)w;
    }
    return 0;
}

static int read_all(int fd, void *buf, size_t n) {
    uint8_t *p = (uint8_t *)buf;
    while (n) {
        ssize_t r = read(fd, p, n);
        if (r < 0) { if (errno == EINTR) continue; return -1; }
        if (r == 0) return -1;
        p += (size_t)r; n -= (size_t)r;
    }
    return 0;
}

/* ---- PAL entry points ------------------------------------------------------ */

static uint64_t p_now(void *self) {
    (void)self;
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

static int p_ram_alloc(void *self, uint64_t n, void **out) {
    (void)self;
    *out = malloc((size_t)n);
    return *out ? 0 : FMS_PAL_ENOMEM;
}

static void p_ram_free(void *self, void *p, uint64_t n) { (void)self; (void)n; free(p); }

static int p_hot_profile(void *self, fms_hot_profile *out) {
    (void)self;
    memset(out, 0, sizeof *out);
    out->available = 0;
    out->domain = FMS_DOM_DEVICE;
    snprintf(out->backend, sizeof out->backend, "none");
    snprintf(out->device, sizeof out->device, "no accelerator probed");
    return 0;
}

static int p_cold_put(void *self, const void *src, uint64_t bytes, fms_cold_token **out) {
    posix_pal *pp = (posix_pal *)self;
    char tmpl[4200], final[4200], hex[65];
    uint8_t digest[32];
    int fd = -1;

    snprintf(tmpl, sizeof tmpl, "%s/.fms-tmp-XXXXXX", pp->root);
    fd = mkstemp(tmpl);
    if (fd < 0) return FMS_PAL_EIO;

    if (write_all(fd, src, (size_t)bytes) != 0) goto fail;
    if (fsync(fd) != 0) goto fail;
    close(fd); fd = -1;

    elpis_sha256(src, (size_t)bytes, digest);
    elpis_hex32(digest, hex);

    pthread_mutex_lock(&pp->mu);
    uint64_t serial = ++pp->serial;
    pthread_mutex_unlock(&pp->mu);
    snprintf(final, sizeof final, "%s/%s.%llu.blob", pp->root, hex, (unsigned long long)serial);

    if (rename(tmpl, final) != 0) goto fail;
    if (pp->dirfd >= 0 && fsync(pp->dirfd) != 0) { unlink(final); return FMS_PAL_EIO; }

    fms_cold_token *t = (fms_cold_token *)calloc(1, sizeof *t);
    if (!t) { unlink(final); return FMS_PAL_ENOMEM; }
    memcpy(t->digest, digest, 32);
    t->bytes = bytes;
    t->path = strdup(final);
    if (!t->path) { free(t); unlink(final); return FMS_PAL_ENOMEM; }
    *out = t;
    return FMS_PAL_OK;

fail:
    if (fd >= 0) close(fd);
    unlink(tmpl);
    return FMS_PAL_EIO;
}

static int p_cold_get(void *self, const fms_cold_token *t, void *dst, uint64_t bytes) {
    (void)self;
    if (!t || !t->path) return FMS_PAL_EIO;
    if (t->bytes != bytes) return FMS_PAL_ESIZE;

    int fd = open(t->path, O_RDONLY);
    if (fd < 0) return FMS_PAL_EIO;

    struct stat sb;
    if (fstat(fd, &sb) != 0) { close(fd); return FMS_PAL_EIO; }
    if ((uint64_t)sb.st_size != bytes) { close(fd); return FMS_PAL_ESIZE; }

    /* dst is an unpublished MOVING allocation reserved by the core. Reading
     * directly avoids an unaccounted second full-size RAM allocation. */
    if (read_all(fd, dst, (size_t)bytes) != 0) {
        memset(dst, 0, (size_t)bytes);
        close(fd);
        return FMS_PAL_EIO;
    }
    close(fd);

    uint8_t got[32];
    elpis_sha256(dst, (size_t)bytes, got);
    if (memcmp(got, t->digest, 32) != 0) {
        memset(dst, 0, (size_t)bytes);
        return FMS_PAL_EDIGEST;
    }
    return FMS_PAL_OK;
}

static void p_cold_drop(void *self, fms_cold_token *t) {
    (void)self;
    if (!t) return;
    if (t->path) { unlink(t->path); free(t->path); }
    free(t);
}

int fms_pal_posix_token_digest(const fms_cold_token *t, uint8_t out[32]) {
    if (!t) return FMS_PAL_EIO;
    memcpy(out, t->digest, 32);
    return FMS_PAL_OK;
}

uint64_t fms_pal_posix_token_bytes(const fms_cold_token *t) { return t ? t->bytes : 0; }

static uint64_t p_bandwidth(void *self, int from, int to) {
    (void)self;
    int lo = from < to ? from : to, hi = from < to ? to : from;
    if (lo == FMS_HOT && hi == FMS_WARM)  return 12ull << 30;
    if (lo == FMS_WARM && hi == FMS_COLD) return (from == FMS_COLD) ? (2ull << 30) : (1ull << 30);
    return 1ull << 30;
}

/* The fms_pal struct is allocated together with the instance state so that
 * destroy() releases both. */
typedef struct { fms_pal pal; posix_pal state; } posix_bundle;

static void bundle_destroy(void *self) {
    posix_pal *pp = (posix_pal *)self;
    posix_bundle *b = (posix_bundle *)((char *)pp - offsetof(posix_bundle, state));
    if (pp->dirfd >= 0) close(pp->dirfd);
    pthread_mutex_destroy(&pp->mu);
    free(pp->root);
    free(b);
}

fms_pal *fms_pal_posix_create(const char *cold_root) {
    if (!cold_root || !*cold_root) return NULL;
    if (mkdir_p(cold_root) != 0) return NULL;

    posix_bundle *b = (posix_bundle *)calloc(1, sizeof *b);
    if (!b) return NULL;
    b->state.root = strdup(cold_root);
    if (!b->state.root) { free(b); return NULL; }
    if (pthread_mutex_init(&b->state.mu, NULL) != 0) { free(b->state.root); free(b); return NULL; }
    b->state.dirfd = open(cold_root, O_RDONLY | O_DIRECTORY);

    fms_pal *p = &b->pal;
    p->self = &b->state;
    p->abi = FMS_ABI_VERSION;
    p->caps = FMS_CAP_COLD;
    p->destroy = bundle_destroy;
    p->now_ns = p_now;
    p->hot_profile = p_hot_profile;
    p->hot_alloc = NULL; p->hot_free = NULL; p->hot_upload = NULL; p->hot_download = NULL;
    p->fence_query = NULL;
    p->ram_alloc = p_ram_alloc; p->ram_free = p_ram_free;
    p->cold_put = p_cold_put; p->cold_get = p_cold_get; p->cold_drop = p_cold_drop;
    p->cold_digest = fms_pal_posix_token_digest; p->cold_bytes = fms_pal_posix_token_bytes;
    p->bandwidth = p_bandwidth;
    return p;
}

const char *fms_pal_posix_token_path(const fms_cold_token *t) { return t ? t->path : NULL; }
