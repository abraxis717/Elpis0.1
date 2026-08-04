#define _POSIX_C_SOURCE 200809L
/* context_reader.c — Read and validate P2 context objects from storage.
 *
 * Recalculates every identity. Rejects truncated, corrupt, or mismatched records.
 * A pre-existing destination is never overwritten by the writer.
 */
#include "elpis_semantic/context_requirement_set.h"
#include "elpis_semantic/context_deficit_policy.h"
#include "elpis_semantic/context_deficit_report.h"
#include "elpis_semantic/retrieval_requirement.h"
#include "elpis_semantic/retrieval_requirement_bundle.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

/* ──────────────────────────────────────────────────────────────────── */
/* Magic values (must match context_writer.c)                          */
/* ──────────────────────────────────────────────────────────────────── */

#define MAGIC_REQUIREMENT_SET    0x52515300u
#define MAGIC_DEFICIT_POLICY     0x44504C00u
#define MAGIC_DEFICIT_REPORT     0x44525000u
#define MAGIC_RETRIEVAL_REQ      0x52525100u
#define MAGIC_RETRIEVAL_BUNDLE   0x52424E00u

/* ──────────────────────────────────────────────────────────────────── */
/* Generic reader: reads file, checks magic, size, hash, validates     */
/* ──────────────────────────────────────────────────────────────────── */

static int read_record(const char *path,
                       uint32_t expected_magic,
                       size_t expected_size,
                       void *out_buf,
                       hacf_digest *on_disk_hash_out) {
    FILE *fp = fopen(path, "rb");
    if (!fp) return SEMANTIC_E_IO;

    /* Check file size */
    struct stat st;
    if (fstat(fileno(fp), &st) != 0) {
        fclose(fp);
        return SEMANTIC_E_IO;
    }

    /* File must be: 4 (magic) + 4 (record_size) + expected_size + 32 (hash) */
    size_t required = 4 + 4 + expected_size + HACF_DIGEST_BYTES;
    if ((size_t)st.st_size < required) {
        fclose(fp);
        return SEMANTIC_E_IO; /* truncated */
    }
    if ((size_t)st.st_size > required) {
        fclose(fp);
        return SEMANTIC_E_IO; /* trailing unauthorized bytes */
    }

    /* Read magic */
    uint32_t magic;
    if (fread(&magic, 4, 1, fp) != 1) { fclose(fp); return SEMANTIC_E_IO; }
    if (magic != expected_magic) { fclose(fp); return SEMANTIC_E_IO; }

    /* Read record size */
    uint32_t record_size;
    if (fread(&record_size, 4, 1, fp) != 1) { fclose(fp); return SEMANTIC_E_IO; }
    if ((size_t)record_size != 4 + 4 + expected_size) { fclose(fp); return SEMANTIC_E_IO; }

    /* Read payload */
    if (fread(out_buf, expected_size, 1, fp) != 1) { fclose(fp); return SEMANTIC_E_IO; }

    /* Read on-disk hash */
    hacf_digest on_disk_hash;
    if (fread(on_disk_hash.bytes, HACF_DIGEST_BYTES, 1, fp) != 1) {
        fclose(fp);
        return SEMANTIC_E_IO;
    }
    fclose(fp);

    /* Recompute hash and verify */
    hacf_digest computed_hash;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, &magic, 4);
    elpis_sha256_update(&ctx, &record_size, 4);
    elpis_sha256_update(&ctx, out_buf, expected_size);
    elpis_sha256_final(&ctx, computed_hash.bytes);

    if (memcmp(computed_hash.bytes, on_disk_hash.bytes, HACF_DIGEST_BYTES) != 0) {
        return SEMANTIC_E_IO; /* storage corruption */
    }

    if (on_disk_hash_out) {
        memcpy(on_disk_hash_out->bytes, on_disk_hash.bytes, HACF_DIGEST_BYTES);
    }

    return SEMANTIC_OK;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Public read functions                                               */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_read_requirement_set(const char *path,
                                elpis_semantic_context_requirement_set_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;

    hacf_digest disk_hash;
    int ret = read_record(path, MAGIC_REQUIREMENT_SET,
                          sizeof(elpis_semantic_context_requirement_set_v1),
                          out, &disk_hash);
    if (ret != SEMANTIC_OK) return ret;

    /* Validate ABI version */
    if (out->abi_version != CONTEXT_REQUIREMENT_SET_ABI_VERSION) return SEMANTIC_E_IO;

    /* Validate the set */
    int vret = elpis_context_requirement_set_validate(out);
    if (vret != SET_VALID) return SEMANTIC_E_IO;

    /* Recompute identity and verify */
    hacf_digest computed_identity;
    elpis_context_requirement_set_identity(out, &computed_identity);
    if (memcmp(computed_identity.bytes, out->requirement_set_identity.bytes,
               HACF_DIGEST_BYTES) != 0) {
        return SEMANTIC_E_IO; /* identity mismatch */
    }

    return SEMANTIC_OK;
}

int elpis_read_deficit_policy(const char *path,
                               elpis_semantic_context_deficit_policy_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;

    hacf_digest disk_hash;
    int ret = read_record(path, MAGIC_DEFICIT_POLICY,
                          sizeof(elpis_semantic_context_deficit_policy_v1),
                          out, &disk_hash);
    if (ret != SEMANTIC_OK) return ret;

    if (out->abi_version != CONTEXT_DEFICIT_POLICY_ABI_VERSION) return SEMANTIC_E_IO;

    int vret = elpis_context_deficit_policy_validate(out);
    if (vret != SEMANTIC_OK) return SEMANTIC_E_IO;

    hacf_digest computed_identity;
    elpis_context_deficit_policy_identity(out, &computed_identity);
    if (memcmp(computed_identity.bytes, out->policy_identity.bytes,
               HACF_DIGEST_BYTES) != 0) {
        return SEMANTIC_E_IO;
    }

    return SEMANTIC_OK;
}

int elpis_read_deficit_report(const char *path,
                               elpis_semantic_context_deficit_report_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;

    hacf_digest disk_hash;
    int ret = read_record(path, MAGIC_DEFICIT_REPORT,
                          sizeof(elpis_semantic_context_deficit_report_v1),
                          out, &disk_hash);
    if (ret != SEMANTIC_OK) return ret;

    if (out->abi_version != CONTEXT_DEFICIT_REPORT_ABI_VERSION) return SEMANTIC_E_IO;

    /* Verify report identity */
    hacf_digest computed_identity;
    elpis_context_deficit_report_identity(out, &computed_identity);
    if (memcmp(computed_identity.bytes, out->report_identity.bytes,
               HACF_DIGEST_BYTES) != 0) {
        return SEMANTIC_E_IO;
    }

    /* Verify disposition wasn't altered */
    /* (Disposition is part of identity, so this is already covered above) */

    return SEMANTIC_OK;
}

int elpis_read_retrieval_requirement(const char *path,
                                      elpis_semantic_retrieval_requirement_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;

    hacf_digest disk_hash;
    int ret = read_record(path, MAGIC_RETRIEVAL_REQ,
                          sizeof(elpis_semantic_retrieval_requirement_v1),
                          out, &disk_hash);
    if (ret != SEMANTIC_OK) return ret;

    if (out->abi_version != RETRIEVAL_REQUIREMENT_ABI_VERSION) return SEMANTIC_E_IO;

    int vret = elpis_retrieval_requirement_validate(out);
    if (vret != SEMANTIC_OK) return SEMANTIC_E_IO;

    hacf_digest computed_identity;
    elpis_retrieval_requirement_identity(out, &computed_identity);
    if (memcmp(computed_identity.bytes, out->retrieval_identity.bytes,
               HACF_DIGEST_BYTES) != 0) {
        return SEMANTIC_E_IO;
    }

    return SEMANTIC_OK;
}

int elpis_read_retrieval_bundle(const char *path,
                                 elpis_semantic_retrieval_requirement_bundle_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;

    hacf_digest disk_hash;
    int ret = read_record(path, MAGIC_RETRIEVAL_BUNDLE,
                          sizeof(elpis_semantic_retrieval_requirement_bundle_v1),
                          out, &disk_hash);
    if (ret != SEMANTIC_OK) return ret;

    if (out->abi_version != RETRIEVAL_BUNDLE_ABI_VERSION) return SEMANTIC_E_IO;

    int vret = elpis_retrieval_bundle_validate(out);
    if (vret != SEMANTIC_OK) return SEMANTIC_E_IO;

    hacf_digest computed_identity;
    elpis_retrieval_requirement_bundle_identity(out, &computed_identity);
    if (memcmp(computed_identity.bytes, out->bundle_identity.bytes,
               HACF_DIGEST_BYTES) != 0) {
        return SEMANTIC_E_IO;
    }

    return SEMANTIC_OK;
}
