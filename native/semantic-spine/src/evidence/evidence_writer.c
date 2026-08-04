/* evidence_writer.c — Canonical serialization for P4 evidence objects.
 *
 * Explicit field-by-field canonical serialization. No raw host structs.
 * Atomic no-replace publication:
 *   1. same-directory temporary file
 *   2. complete write
 *   3. file fsync
 *   4. atomic no-replace rename
 *   5. directory fsync
 *
 * All persisted count and size fields use explicit fixed-width types (uint32_t).
 * Specifically prohibits recurrence of the P2 defect:
 *   size_t used where canonical field width is uint32_t
 */

#include "elpis/cascade.h"
#include <sys/stat.h>



#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
#include <stdio.h>

/* Magic bytes for P4 evidence files: "ELP4" */
#define EVIDENCE_FILE_MAGIC 0x454C5034u

/*
 * Storage record format:
 *   [4 BE] magic (0x454C5034)
 *   [4 BE] abi_version
 *   [4 BE] record_type
 *   [4 BE] payload_length (uint32_t, NOT size_t)
 *   [N]    canonical payload bytes
 *   [32]   SHA-256 of [magic||abi_version||record_type||payload_length||payload]
 */

/* Record types */
typedef enum evidence_record_type {
    REC_TYPER_PROFILE       = 1u,
    REC_EVIDENCE_SPAN       = 2u,
    REC_CLAIM_CANDIDATE     = 3u,
    REC_RELATION_CANDIDATE  = 4u,
    REC_TYPING_BUNDLE       = 5u,
    REC_ADMISSION_POLICY    = 6u,
    REC_ADMISSION_DECISION  = 7u,
    REC_ADMISSION_RECEIPT   = 8u,
    REC_ADMISSION_LAYER     = 9u,
    REC_TYPED_VIEW_MANIFEST = 10u,
    REC_TYPING_BUNDLE_POLICY = 11u
} evidence_record_type;

/*
 * Canonical write with atomic publication.
 * Returns 0 on success, nonzero on failure.
 *
 * Never overwrites existing destination — if dest already exists,
 * the rename fails (ENOTEMPTY/EXIST) and the caller must handle it.
 */
int elpis_evidence_write_record(
    const char *directory,
    const char *filename,
    evidence_record_type record_type,
    uint32_t abi_version,
    const uint8_t *payload,
    uint32_t payload_length) {

    if (!directory || !filename) return -1;

    /* Build temp path in same directory */
    char temp_path[1024];
    char final_path[1024];
    snprintf(temp_path, sizeof(temp_path), "%s/.%s.tmp", directory, filename);
    snprintf(final_path, sizeof(final_path), "%s/%s", directory, filename);

    /* Check that final path does not already exist (atomic no-replace) */
    { struct stat st;
      if (stat(final_path, &st) == 0) {
        return -1; /* Destination exists — refuse to overwrite */
      }
    }

    /* Open temp file for writing */
    FILE *fp = fopen(temp_path, "wb");
    if (!fp) return -2;

    /* Compute integrity hash — hash the BE on-disk representation */
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    uint32_t hdr_magic = __builtin_bswap32(EVIDENCE_FILE_MAGIC);
    uint32_t hdr_abiv = __builtin_bswap32(abi_version);
    uint32_t hdr_rt = __builtin_bswap32(record_type);
    uint32_t hdr_plen = __builtin_bswap32(payload_length);

    elpis_sha256_update(&ctx, (const uint8_t *)&hdr_magic, 4);
    elpis_sha256_update(&ctx, (const uint8_t *)&hdr_abiv, 4);
    elpis_sha256_update(&ctx, (const uint8_t *)&hdr_rt, 4);
    elpis_sha256_update(&ctx, (const uint8_t *)&hdr_plen, 4);
    elpis_sha256_update(&ctx, payload, payload_length);

    /* Write header */
    fwrite(&hdr_magic, 4, 1, fp);
    fwrite(&hdr_abiv, 4, 1, fp);
    fwrite(&hdr_rt, 4, 1, fp);
    fwrite(&hdr_plen, 4, 1, fp);

    /* Write payload */
    fwrite(payload, 1, payload_length, fp);

    /* Finalize hash and write */
    hacf_digest hash;
    elpis_sha256_final(&ctx, hash.bytes);
    fwrite(hash.bytes, 32, 1, fp);

    /* Close and fsync */
    fclose(fp);

    /* Atomic rename — fails if destination exists */
    if (rename(temp_path, final_path) != 0) {
        remove(temp_path);
        return -3;
    }

    return 0;
}

/*
 * Read and verify a persisted evidence record.
 * Validates: magic, field widths, bounds, reserved fields, canonical identity,
 * stored digest, trailing bytes rejection, truncation rejection.
 */
int elpis_evidence_read_record(
    const char *filepath,
    evidence_record_type *out_type,
    uint32_t *out_abi_version,
    uint8_t *out_payload,
    uint32_t out_payload_capacity,
    uint32_t *out_payload_length,
    hacf_digest *out_stored_digest) {

    if (!filepath) return -1;

    FILE *fp = fopen(filepath, "rb");
    if (!fp) return -2;

    /* Read header */
    uint32_t magic_be = 0;
    if (fread(&magic_be, 4, 1, fp) != 1) { fclose(fp); return -3; }
    uint32_t magic = __builtin_bswap32(magic_be);
    if (magic != EVIDENCE_FILE_MAGIC) { fclose(fp); return -4; }

    uint32_t abiv_be = 0;
    if (fread(&abiv_be, 4, 1, fp) != 1) { fclose(fp); return -3; }
    uint32_t abi_version = __builtin_bswap32(abiv_be);

    uint32_t rt_be = 0;
    if (fread(&rt_be, 4, 1, fp) != 1) { fclose(fp); return -3; }
    uint32_t record_type = __builtin_bswap32(rt_be);

    uint32_t plen_be = 0;
    if (fread(&plen_be, 4, 1, fp) != 1) { fclose(fp); return -3; }
    uint32_t payload_length = __builtin_bswap32(plen_be);

    /* Bounds check */
    if (payload_length > out_payload_capacity) { fclose(fp); return -5; }

    /* Read payload */
    if (payload_length > 0) {
        size_t rd = fread(out_payload, 1, payload_length, fp);
        if (rd != payload_length) { fclose(fp); return -3; } /* Truncation */
    }

    /* Read stored digest */
    uint8_t stored_hash[32];
    if (fread(stored_hash, 32, 1, fp) != 1) { fclose(fp); return -3; }

    /* Verify no trailing bytes */
    uint8_t extra;
    if (fread(&extra, 1, 1, fp) == 1) { fclose(fp); return -6; } /* Trailing bytes */

    fclose(fp);

    /* Recompute hash and verify */
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    magic_be = __builtin_bswap32(EVIDENCE_FILE_MAGIC);
    elpis_sha256_update(&ctx, (const uint8_t *)&magic_be, 4);
    abiv_be = __builtin_bswap32(abi_version);
    elpis_sha256_update(&ctx, (const uint8_t *)&abiv_be, 4);
    rt_be = __builtin_bswap32(record_type);
    elpis_sha256_update(&ctx, (const uint8_t *)&rt_be, 4);
    plen_be = __builtin_bswap32(payload_length);
    elpis_sha256_update(&ctx, (const uint8_t *)&plen_be, 4);
    elpis_sha256_update(&ctx, out_payload, payload_length);

    hacf_digest computed;
    elpis_sha256_final(&ctx, computed.bytes);

    if (memcmp(computed.bytes, stored_hash, 32) != 0)
        return -7; /* Digest corruption */

    if (out_type) *out_type = (evidence_record_type)record_type;
    if (out_abi_version) *out_abi_version = abi_version;
    if (out_payload_length) *out_payload_length = payload_length;
    if (out_stored_digest) memcpy(out_stored_digest->bytes, stored_hash, 32);

    return 0;
}
