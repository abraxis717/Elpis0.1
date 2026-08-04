/* p5_writer.c — Unified P5 persistence utilities.
 *
 * Atomic write: temp → write → fsync → rename → dir fsync. O_EXCL.
 * Pre-existing destination is never overwritten.
 */
#define _POSIX_C_SOURCE 200809L
#include "elpis_semantic/context_rebind.h"
#include "elpis_semantic/context_iteration_policy.h"
#include "elpis_semantic/context_iteration_state.h"
#include "elpis_semantic/context_reevaluation.h"
#include "elpis_semantic/context_progress.h"
#include "elpis_semantic/bounded_view_policy.h"
#include "elpis_semantic/bounded_view_seed.h"
#include "elpis_semantic/bounded_view_candidate.h"
#include "elpis_semantic/bounded_semantic_view.h"
#include "elpis_semantic/downstream_handoff.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <errno.h>

/* Internal atomic write — returns SEMANTIC_OK or SEMANTIC_E_IO. */
int p5_simple_write(const char *path, const uint8_t *data, size_t sz) {
    /* Check destination doesn't already exist */
    if (access(path, F_OK) == 0) {
        return SEMANTIC_E_IO; /* pre-existing — never overwrite */
    }

    /* Extract directory for temp file */
    char tmp_path[512];
    const char *slash = strrchr(path, '/');
    if (slash) {
        size_t dir_len = (size_t)(slash - path);
        if (dir_len >= sizeof(tmp_path) - 16) return SEMANTIC_E_IO;
        snprintf(tmp_path, sizeof(tmp_path), "%.*s/.tmp_XXXXXX", (int)dir_len, path);
    } else {
        snprintf(tmp_path, sizeof(tmp_path), ".tmp_XXXXXX");
    }

    /* Create temp file with O_EXCL */
    int fd = mkstemp(tmp_path);
    if (fd < 0) return SEMANTIC_E_IO;

    /* Write data */
    const uint8_t *p = data;
    size_t remaining = sz;
    while (remaining > 0) {
        ssize_t n = write(fd, p, remaining);
        if (n < 0) { close(fd); unlink(tmp_path); return SEMANTIC_E_IO; }
        p += n;
        remaining -= (size_t)n;
    }

    /* fsync file */
    if (fsync(fd) != 0) { close(fd); unlink(tmp_path); return SEMANTIC_E_IO; }
    close(fd);

    /* Atomic rename */
    if (rename(tmp_path, path) != 0) {
        unlink(tmp_path);
        return SEMANTIC_E_IO;
    }

    /* fsync directory */
    if (slash) {
        char dir_path[512];
        size_t dir_len = (size_t)(slash - path);
        snprintf(dir_path, sizeof(dir_path), "%.*s", (int)dir_len, path);
        int dfd = open(dir_path, O_RDONLY | O_DIRECTORY);
        if (dfd >= 0) { fsync(dfd); close(dfd); }
    }

    return SEMANTIC_OK;
}

/* Public: sf_atomic_write used by P5 source files */
int sf_atomic_write(const char *path, const uint8_t *data, size_t sz, int unused) {
    (void)unused;
    return p5_simple_write(path, data, sz);
}

int elpis_p5_write_all(const char *dir,
                        const elpis_semantic_context_rebind_v1 *rebind,
                        const elpis_semantic_context_iteration_policy_v1 *policy,
                        const elpis_semantic_context_iteration_state_v1 *state,
                        const elpis_semantic_context_reevaluation_v1 *reeval,
                        const elpis_semantic_context_progress_v1 *progress,
                        const elpis_semantic_bounded_view_policy_v1 *bview_policy,
                        const elpis_semantic_bounded_view_seed_set_v1 *seeds,
                        const elpis_semantic_bounded_view_candidate_set_v1 *candidates,
                        const elpis_semantic_bounded_semantic_view_v1 *bview,
                        const elpis_semantic_downstream_handoff_v1 *handoff)
{
    if (!dir) return SEMANTIC_E_INVAL;
    int rc = SEMANTIC_OK;
    if (rebind) rc |= elpis_write_context_rebind(dir, rebind);
    if (policy) rc |= elpis_write_iteration_policy(dir, policy);
    if (state) rc |= elpis_write_iteration_state(dir, state);
    if (reeval) rc |= elpis_write_context_reevaluation(dir, reeval);
    if (progress) rc |= elpis_write_context_progress(dir, progress);
    if (bview_policy) rc |= elpis_write_bounded_view_policy(dir, bview_policy);
    if (seeds) rc |= elpis_write_bounded_view_seed_set(dir, seeds);
    if (candidates) rc |= elpis_write_bounded_view_candidate_set(dir, candidates);
    if (bview) rc |= elpis_write_bounded_semantic_view(dir, bview);
    if (handoff) rc |= elpis_write_downstream_handoff(dir, handoff);
    return rc;
}

int elpis_p5_verify_directory(const char *dir) {
    if (!dir) return SEMANTIC_E_INVAL;
    FILE *f = fopen(dir, "r");
    if (!f) return SEMANTIC_E_IO;
    fclose(f);
    return SEMANTIC_OK;
}
