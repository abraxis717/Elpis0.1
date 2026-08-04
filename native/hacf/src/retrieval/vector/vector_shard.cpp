/* vector_shard.cpp - immutable vector shard format (Gate R2).
 *
 * All integers little-endian, assembled byte by byte. Nothing in the on-disk
 * image depends on host endianness, struct padding or compiler layout. */

#include "elpis/vector_shard.h"
#include "elpis/sha256.h"

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <exception>
#include <new>
#include <string>
#include <vector>

namespace {

/* Header field offsets. Fixed forever for ABI 1. */
enum : size_t {
    OFF_MAGIC        = 0,    /* 8  */
    OFF_ABI          = 8,    /* u32 */
    OFF_HEADER_BYTES = 12,   /* u32 */
    OFF_VCOUNT       = 16,   /* u64 */
    OFF_DIM          = 24,   /* u32 */
    OFF_ELEM         = 28,   /* u32 */
    OFF_METRIC       = 32,   /* u32 */
    OFF_NORM         = 36,   /* u32 */
    OFF_RECBYTES     = 40,   /* u32 */
    OFF_FLAGS        = 44,   /* u32 */
    OFF_PAYLOAD_LEN  = 48,   /* u64 */
    OFF_META_LEN     = 56,   /* u64 */
    OFF_PROFILE_DG   = 64,   /* 32 */
    OFF_CORPUS_DG    = 96,   /* 32 */
    OFF_METAMAP_DG   = 128,  /* 32 */
    OFF_PAYLOAD_DG   = 160,  /* 32 */
    OFF_HEADER_DG    = 192,  /* 32, computed over the header with this field zeroed */
    OFF_RESERVED     = 224   /* 32 zero bytes */
};

void put_u32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24);
}
void put_u64(uint8_t *p, uint64_t v) {
    for (int i = 0; i < 8; i++) p[i] = (uint8_t)(v >> (8 * i));
}
uint32_t get_u32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
uint64_t get_u64(const uint8_t *p) {
    uint64_t v = 0;
    for (int i = 0; i < 8; i++) v |= (uint64_t)p[i] << (8 * i);
    return v;
}
void put_f32(uint8_t *p, float f) {
    uint32_t bits;
    std::memcpy(&bits, &f, 4);
    put_u32(p, bits);
}
float get_f32(const uint8_t *p) {
    uint32_t bits = get_u32(p);
    float f;
    std::memcpy(&f, &bits, 4);
    return f;
}

void fail(char *reason, size_t cap, const char *code) {
    if (reason && cap) std::snprintf(reason, cap, "%s", code);
}

/* Canonical digest field: exactly 64 lowercase hex characters then NUL,
 * inspected with a hard bound so an unterminated fixed-width array can never be
 * read past byte 64. Uppercase and mixed case are rejected rather than folded,
 * so two spellings of one digest can never become two identities. */
int canonical_hex64(const char field[65], uint8_t out[32]) {
    if (!field) return -1;
    for (int i = 0; i < 64; i++) {
        char c = field[i];
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return -1;
    }
    if (field[64] != '\0') return -1;
    if (!out) return 0;
    for (int i = 0; i < 32; i++) {
        auto nib = [](char c) -> int { return (c <= '9') ? (c - '0') : (c - 'a' + 10); };
        out[i] = (uint8_t)((nib(field[i * 2]) << 4) | nib(field[i * 2 + 1]));
    }
    return 0;
}

int hex_to_raw(const char *hex, uint8_t out[32]) { return canonical_hex64(hex, out); }

/* Namespace and authority admitted into a shard side table follow the corpus
 * policy: printable text, and one of the four declared authority classes. */
bool shard_valid_ns(const char *s, size_t cap) {
    if (!s) return false;
    size_t n = 0;
    while (n < cap && s[n]) n++;
    if (n == cap || n == 0) return false;
    for (size_t i = 0; i < n; i++) {
        unsigned char ch = (unsigned char)s[i];
        if (ch < 0x20 || ch == 0x7f) return false;
    }
    return true;
}

bool shard_valid_authority(const char *s) {
    return s && (!std::strcmp(s, "canonical") || !std::strcmp(s, "reference") ||
                 !std::strcmp(s, "advisory") || !std::strcmp(s, "provisional"));
}

/* Documented L2 tolerance. A float32 unit vector over 384 dimensions
 * accumulated in double stays far inside this; the fixture provider is exact. */
const double kL2Tolerance = 1.0e-4;

/* Canonical metadata side table:
 *   u32 ns_count, ns_count * (u16 len + bytes)          sorted, unique
 *   u32 auth_count, auth_count * (u16 len + bytes)      sorted, unique
 *   vector_count * (u32 ns_index, u32 auth_index)       record order
 * No text lives in the payload; this table is digest-bound into the header. */
std::string build_metadata(const elpis_vshard_input *recs, const std::vector<uint64_t> &order,
                           const std::vector<std::string> &ns_tab,
                           const std::vector<std::string> &auth_tab) {
    std::string out;
    uint8_t tmp[8];
    auto put_table = [&](const std::vector<std::string> &t) {
        put_u32(tmp, (uint32_t)t.size());
        out.append((const char *)tmp, 4);
        for (const std::string &s : t) {
            tmp[0] = (uint8_t)(s.size() & 0xffu);
            tmp[1] = (uint8_t)((s.size() >> 8) & 0xffu);
            out.append((const char *)tmp, 2);
            out.append(s);
        }
    };
    put_table(ns_tab);
    put_table(auth_tab);
    for (uint64_t idx : order) {
        const char *ns = recs[idx].ns ? recs[idx].ns : "";
        const char *au = recs[idx].authority ? recs[idx].authority : "";
        uint32_t ni = (uint32_t)(std::lower_bound(ns_tab.begin(), ns_tab.end(), std::string(ns)) - ns_tab.begin());
        uint32_t ai = (uint32_t)(std::lower_bound(auth_tab.begin(), auth_tab.end(), std::string(au)) - auth_tab.begin());
        put_u32(tmp, ni);     out.append((const char *)tmp, 4);
        put_u32(tmp, ai);     out.append((const char *)tmp, 4);
    }
    return out;
}

struct MetaView {
    std::vector<std::string> ns, auth;
    const uint8_t *pairs = nullptr;
    uint64_t count = 0;
    bool ok = false;
};

MetaView parse_metadata(const uint8_t *m, uint64_t len, uint64_t vcount) {
    MetaView v;
    uint64_t o = 0;
    auto read_table = [&](std::vector<std::string> &t) -> bool {
        if (o + 4 > len) return false;
        uint32_t n = get_u32(m + o);
        o += 4;
        if (n > 1u << 20) return false;
        t.reserve(n);
        for (uint32_t i = 0; i < n; i++) {
            if (o + 2 > len) return false;
            uint32_t sl = (uint32_t)m[o] | ((uint32_t)m[o + 1] << 8);
            o += 2;
            if (o + sl > len) return false;
            t.emplace_back((const char *)m + o, sl);
            o += sl;
            if (i && !(t[i - 1] < t[i])) return false;      /* sorted and unique */
        }
        return true;
    };
    if (!read_table(v.ns) || !read_table(v.auth)) return v;
    for (const std::string &t : v.ns) {
        if (t.empty() || t.size() > 95) return v;
        for (unsigned char ch : t) if (ch < 0x20 || ch == 0x7f) return v;   /* no control chars */
    }
    for (const std::string &t : v.auth)
        if (!shard_valid_authority(t.c_str())) return v;                    /* declared classes only */
    if (o + vcount * 8ull != len) return v;
    v.pairs = m + o;
    v.count = vcount;
    for (uint64_t i = 0; i < vcount; i++) {
        uint32_t ni = get_u32(v.pairs + i * 8), ai = get_u32(v.pairs + i * 8 + 4);
        if (ni >= v.ns.size() || ai >= v.auth.size()) return v;
    }
    v.ok = true;
    return v;
}

} // namespace

extern "C" {

static int vshard_build_impl(const elpis_vshard_input *records, uint64_t count,
                             const elpis_embedding_profile *profile,
                             const char *corpus_manifest_digest,
                             void **bytes_out, size_t *len_out, char shard_digest_out[65]) {
    if (!records || !profile || !bytes_out || !len_out) return -1;
    if (count == 0 || count > ELPIS_VSHARD_MAX_VECTORS) return -1;
    if (elpis_embedding_profile_validate(profile) != 0) return -1;
    if (profile->dimensions != ELPIS_EMBEDDING_DIM) return -1;

    char profile_dg[65];
    if (elpis_embedding_profile_digest(profile, profile_dg) != 0) return -1;
    uint8_t corpus_raw[32];
    std::memset(corpus_raw, 0, sizeof corpus_raw);
    if (corpus_manifest_digest && hex_to_raw(corpus_manifest_digest, corpus_raw) != 0) return -1;

    /* Validate every input before allocating the image. */
    std::vector<uint64_t> order(count);
    std::vector<std::string> ns_tab, auth_tab;
    /* Raw 32-byte identities, parsed once. Ordering and duplicate detection use
     * these bytes, never the source text, so no unnormalized string ever
     * participates in an identity comparison. */
    std::vector<uint8_t> chunk_raw((size_t)count * 32), doc_raw((size_t)count * 32);
    for (uint64_t i = 0; i < count; i++) {
        const elpis_vshard_input &r = records[i];
        if (canonical_hex64(r.chunk_digest, &chunk_raw[(size_t)i * 32]) != 0) return -1;
        if (canonical_hex64(r.doc_digest, &doc_raw[(size_t)i * 32]) != 0) return -1;
        if (!r.vector || !elpis_vector_all_finite(r.vector, profile->dimensions)) return -1;
        if (!shard_valid_ns(r.ns ? r.ns : "", 96)) return -1;
        if (!shard_valid_authority(r.authority)) return -1;
        if (std::strlen(r.ns) > 95) return -1;
        /* A shard that declares L2 must actually contain unit vectors. */
        if (profile->normalization == ELPIS_NORM_L2) {
            double sq = 0.0;
            for (uint32_t d = 0; d < profile->dimensions; d++)
                sq += (double)r.vector[d] * (double)r.vector[d];
            if (!(sq > 0.0)) return -1;
            double nrm = std::sqrt(sq);
            if (!(nrm > 0.0) || std::isnan(nrm) || std::isinf(nrm)) return -1;
            if (std::fabs(nrm - 1.0) > kL2Tolerance) return -1;
        }
        ns_tab.emplace_back(r.ns);
        auth_tab.emplace_back(r.authority);
        order[i] = i;
    }
    std::sort(ns_tab.begin(), ns_tab.end());
    ns_tab.erase(std::unique(ns_tab.begin(), ns_tab.end()), ns_tab.end());
    std::sort(auth_tab.begin(), auth_tab.end());
    auth_tab.erase(std::unique(auth_tab.begin(), auth_tab.end()), auth_tab.end());

    /* Deterministic record order: chunk digest ascending, independent of input order. */
    std::sort(order.begin(), order.end(), [&](uint64_t a, uint64_t b) {
        return std::memcmp(&chunk_raw[(size_t)a * 32], &chunk_raw[(size_t)b * 32], 32) < 0;
    });
    for (uint64_t i = 1; i < count; i++)
        if (std::memcmp(&chunk_raw[(size_t)order[i - 1] * 32], &chunk_raw[(size_t)order[i] * 32], 32) == 0)
            return -1;                                   /* duplicate chunk digest */

    const uint64_t rec_bytes = ELPIS_VSHARD_RECORD_BYTES;
    if (count > (UINT64_MAX - ELPIS_VSHARD_HEADER_BYTES) / rec_bytes) return -1;
    const uint64_t payload_bytes = count * rec_bytes;

    std::string meta = build_metadata(records, order, ns_tab, auth_tab);
    const uint64_t total = ELPIS_VSHARD_HEADER_BYTES + payload_bytes + (uint64_t)meta.size();
    if (total > (uint64_t)SIZE_MAX) return -1;

    uint8_t *img = (uint8_t *)std::calloc(1, (size_t)total);
    if (!img) return -1;

    uint8_t *pay = img + ELPIS_VSHARD_HEADER_BYTES;
    for (uint64_t i = 0; i < count; i++) {
        const elpis_vshard_input &r = records[order[i]];
        uint8_t *rp = pay + i * rec_bytes;
        std::memcpy(rp, &chunk_raw[(size_t)order[i] * 32], 32);
        std::memcpy(rp + 32, &doc_raw[(size_t)order[i] * 32], 32);
        (void)r;
        for (uint32_t d = 0; d < profile->dimensions; d++) put_f32(rp + 64 + d * 4u, r.vector[d]);
    }
    std::memcpy(img + ELPIS_VSHARD_HEADER_BYTES + payload_bytes, meta.data(), meta.size());

    uint8_t payload_dg[32], meta_dg[32], profile_raw[32];
    elpis_sha256(pay, (size_t)payload_bytes, payload_dg);
    elpis_sha256(meta.data(), meta.size(), meta_dg);
    if (hex_to_raw(profile_dg, profile_raw) != 0) { std::free(img); return -1; }

    std::memcpy(img + OFF_MAGIC, ELPIS_VSHARD_MAGIC, ELPIS_VSHARD_MAGIC_BYTES);
    put_u32(img + OFF_ABI, ELPIS_VSHARD_ABI_VERSION);
    put_u32(img + OFF_HEADER_BYTES, ELPIS_VSHARD_HEADER_BYTES);
    put_u64(img + OFF_VCOUNT, count);
    put_u32(img + OFF_DIM, profile->dimensions);
    put_u32(img + OFF_ELEM, profile->element_type);
    put_u32(img + OFF_METRIC, profile->metric);
    put_u32(img + OFF_NORM, profile->normalization);
    put_u32(img + OFF_RECBYTES, (uint32_t)rec_bytes);
    put_u32(img + OFF_FLAGS, 0);
    put_u64(img + OFF_PAYLOAD_LEN, payload_bytes);
    put_u64(img + OFF_META_LEN, (uint64_t)meta.size());
    std::memcpy(img + OFF_PROFILE_DG, profile_raw, 32);
    std::memcpy(img + OFF_CORPUS_DG, corpus_raw, 32);
    std::memcpy(img + OFF_METAMAP_DG, meta_dg, 32);
    std::memcpy(img + OFF_PAYLOAD_DG, payload_dg, 32);
    /* header digest covers the header with its own field zeroed */
    uint8_t hdr_dg[32];
    elpis_sha256(img, ELPIS_VSHARD_HEADER_BYTES, hdr_dg);
    std::memcpy(img + OFF_HEADER_DG, hdr_dg, 32);

    if (shard_digest_out) {
        uint8_t whole[32];
        elpis_sha256(img, (size_t)total, whole);
        elpis_hex32(whole, shard_digest_out);
    }
    *bytes_out = img;
    *len_out = (size_t)total;
    return 0;
}

static int vshard_verify_impl(const void *bytes, size_t len, elpis_vshard_header *out,
                              char *reason, size_t reason_cap) {
    if (reason && reason_cap) reason[0] = 0;
    if (!bytes) { fail(reason, reason_cap, "null_buffer"); return -1; }
    if (len < ELPIS_VSHARD_HEADER_BYTES) { fail(reason, reason_cap, "truncated_header"); return -1; }

    const uint8_t *b = (const uint8_t *)bytes;
    if (std::memcmp(b + OFF_MAGIC, ELPIS_VSHARD_MAGIC, ELPIS_VSHARD_MAGIC_BYTES) != 0) {
        fail(reason, reason_cap, "bad_magic");
        return -1;
    }
    uint32_t abi = get_u32(b + OFF_ABI);
    if (abi != ELPIS_VSHARD_ABI_VERSION) { fail(reason, reason_cap, "unsupported_abi"); return -1; }
    uint32_t hbytes = get_u32(b + OFF_HEADER_BYTES);
    if (hbytes != ELPIS_VSHARD_HEADER_BYTES) { fail(reason, reason_cap, "bad_header_bytes"); return -1; }

    /* Header digest before trusting any other field. */
    uint8_t stored_hdr[32], calc_hdr[32];
    std::memcpy(stored_hdr, b + OFF_HEADER_DG, 32);
    {
        uint8_t hdr[ELPIS_VSHARD_HEADER_BYTES];
        std::memcpy(hdr, b, ELPIS_VSHARD_HEADER_BYTES);
        std::memset(hdr + OFF_HEADER_DG, 0, 32);
        elpis_sha256(hdr, sizeof hdr, calc_hdr);
    }
    if (!elpis_digest_equal(stored_hdr, calc_hdr)) { fail(reason, reason_cap, "header_digest_mismatch"); return -1; }

    uint64_t vcount = get_u64(b + OFF_VCOUNT);
    uint32_t dim = get_u32(b + OFF_DIM);
    uint32_t elem = get_u32(b + OFF_ELEM);
    uint32_t metric = get_u32(b + OFF_METRIC);
    uint32_t norm = get_u32(b + OFF_NORM);
    uint32_t recb = get_u32(b + OFF_RECBYTES);
    uint64_t paylen = get_u64(b + OFF_PAYLOAD_LEN);
    uint64_t metalen = get_u64(b + OFF_META_LEN);

    if (dim != ELPIS_EMBEDDING_DIM) { fail(reason, reason_cap, "bad_dimensions"); return -1; }
    if (elem != ELPIS_ELEM_F32) { fail(reason, reason_cap, "unknown_element_type"); return -1; }
    if (metric != ELPIS_METRIC_DOT && metric != ELPIS_METRIC_COSINE) {
        fail(reason, reason_cap, "unknown_metric"); return -1;
    }
    if (norm != ELPIS_NORM_NONE && norm != ELPIS_NORM_L2) {
        fail(reason, reason_cap, "unknown_normalization"); return -1;
    }
    if (recb != ELPIS_VSHARD_RECORD_BYTES) { fail(reason, reason_cap, "bad_record_bytes"); return -1; }
    if (get_u32(b + OFF_FLAGS) != 0u) { fail(reason, reason_cap, "unknown_flags"); return -1; }
    for (size_t i = OFF_RESERVED; i < ELPIS_VSHARD_HEADER_BYTES; i++)
        if (b[i] != 0) { fail(reason, reason_cap, "nonzero_reserved"); return -1; }
    if (vcount == 0 || vcount > ELPIS_VSHARD_MAX_VECTORS) { fail(reason, reason_cap, "bad_vector_count"); return -1; }
    if (vcount > (UINT64_MAX - ELPIS_VSHARD_HEADER_BYTES) / recb) {
        fail(reason, reason_cap, "integer_overflow"); return -1;
    }
    if (paylen != vcount * (uint64_t)recb) { fail(reason, reason_cap, "payload_size_mismatch"); return -1; }
    if (metalen > (uint64_t)len) { fail(reason, reason_cap, "integer_overflow"); return -1; }

    uint64_t expect = (uint64_t)ELPIS_VSHARD_HEADER_BYTES + paylen + metalen;
    if ((uint64_t)len < expect) { fail(reason, reason_cap, "truncated_payload"); return -1; }
    if ((uint64_t)len > expect) { fail(reason, reason_cap, "extra_undeclared_payload"); return -1; }

    const uint8_t *pay = b + ELPIS_VSHARD_HEADER_BYTES;
    uint8_t calc[32];
    elpis_sha256(pay, (size_t)paylen, calc);
    if (!elpis_digest_equal(calc, b + OFF_PAYLOAD_DG)) {
        fail(reason, reason_cap, "payload_digest_mismatch"); return -1;
    }
    elpis_sha256(pay + paylen, (size_t)metalen, calc);
    if (!elpis_digest_equal(calc, b + OFF_METAMAP_DG)) {
        fail(reason, reason_cap, "metadata_map_digest_mismatch"); return -1;
    }

    MetaView mv = parse_metadata(pay + paylen, metalen, vcount);
    if (!mv.ok) { fail(reason, reason_cap, "bad_metadata_map"); return -1; }

    /* Record-level checks: ordering (which also proves uniqueness) and finiteness. */
    for (uint64_t i = 0; i < vcount; i++) {
        const uint8_t *rp = pay + i * (uint64_t)recb;
        if (i && std::memcmp(rp - recb, rp, 32) >= 0) {
            fail(reason, reason_cap,
                 std::memcmp(rp - recb, rp, 32) == 0 ? "duplicate_chunk_digest" : "unsorted_records");
            return -1;
        }
        double sq = 0.0;
        for (uint32_t d = 0; d < dim; d++) {
            float f = get_f32(rp + 64 + d * 4u);
            if (std::isnan(f) || std::isinf(f)) { fail(reason, reason_cap, "non_finite_vector"); return -1; }
            sq += (double)f * (double)f;
        }
        if (norm == ELPIS_NORM_L2) {
            /* A shard that declares L2 must contain unit vectors; a zero or
             * mis-scaled vector is a format violation, not a scoring surprise. */
            if (!(sq > 0.0)) { fail(reason, reason_cap, "zero_norm_vector"); return -1; }
            double nrm = std::sqrt(sq);
            if (std::isnan(nrm) || std::isinf(nrm) || std::fabs(nrm - 1.0) > kL2Tolerance) {
                fail(reason, reason_cap, "l2_policy_violation");
                return -1;
            }
        }
    }

    if (out) {
        std::memset(out, 0, sizeof *out);
        out->abi_version = abi;
        out->header_bytes = hbytes;
        out->vector_count = vcount;
        out->dimensions = dim;
        out->element_type = elem;
        out->metric = metric;
        out->normalization = norm;
        out->record_bytes = recb;
        out->flags = get_u32(b + OFF_FLAGS);
        out->payload_bytes = paylen;
        out->metadata_bytes = metalen;
        elpis_hex32(b + OFF_PROFILE_DG, out->embedding_profile_digest);
        elpis_hex32(b + OFF_CORPUS_DG, out->corpus_manifest_digest);
        elpis_hex32(b + OFF_METAMAP_DG, out->metadata_map_digest);
        elpis_hex32(b + OFF_PAYLOAD_DG, out->payload_digest);
        uint8_t whole[32];
        elpis_sha256(b, len, whole);
        elpis_hex32(whole, out->shard_digest);
    }
    return 0;
}

int elpis_vshard_verify(const void *bytes, size_t len, elpis_vshard_header *out,
                        char *reason, size_t reason_cap) {
    if (out) std::memset(out, 0, sizeof *out);
    if (reason && reason_cap) reason[0] = 0;
    try {
        return vshard_verify_impl(bytes, len, out, reason, reason_cap);
    } catch (const std::bad_alloc &) {
        if (out) std::memset(out, 0, sizeof *out);
        fail(reason, reason_cap, "allocation_failure");
        return -1;
    } catch (const std::exception &) {
        if (out) std::memset(out, 0, sizeof *out);
        fail(reason, reason_cap, "internal_exception");
        return -1;
    } catch (...) {
        if (out) std::memset(out, 0, sizeof *out);
        fail(reason, reason_cap, "unknown_exception");
        return -1;
    }
}

const uint8_t *elpis_vshard_record(const void *bytes, uint64_t index) {
    return (const uint8_t *)bytes + ELPIS_VSHARD_HEADER_BYTES + index * ELPIS_VSHARD_RECORD_BYTES;
}

const char *elpis_vshard_record_chunk_hex(const void *bytes, uint64_t index, char out[65]) {
    elpis_hex32(elpis_vshard_record(bytes, index), out);
    return out;
}

const float *elpis_vshard_record_vector(const void *bytes, uint64_t index) {
    /* Records are 4-byte aligned within a 256-byte header offset, and floats are
     * stored little-endian; on a big-endian host the caller must use get_f32.
     * HACF targets are x86-64 and aarch64-LE, checked at build time below. */
    return (const float *)(const void *)(elpis_vshard_record(bytes, index) + 64);
}

static int vshard_record_meta_impl(const void *bytes, size_t len, uint64_t index,
                                   const char **ns_out, const char **authority_out) {
    if (!bytes) return -1;
    const uint8_t *b = (const uint8_t *)bytes;
    uint64_t vcount = get_u64(b + OFF_VCOUNT);
    uint64_t paylen = get_u64(b + OFF_PAYLOAD_LEN);
    uint64_t metalen = get_u64(b + OFF_META_LEN);
    if (index >= vcount) return -1;
    if ((uint64_t)len != ELPIS_VSHARD_HEADER_BYTES + paylen + metalen) return -1;

    /* The cache is keyed on immutable content identity, not on the buffer
     * address. An address is not an identity: a caller may free one shard and
     * allocate another at the same address, or overwrite a buffer in place, and
     * an address-keyed cache would then serve the previous shard's namespaces.
     * The key is the metadata-map digest plus the three declared lengths. */
    struct MetaCacheKey {
        const void *addr;
        uint8_t     meta_digest[32];
        uint64_t    vcount, paylen, metalen;
        bool matches(const void *a, const uint8_t *dg, uint64_t vc, uint64_t pl, uint64_t ml) const {
            return addr == a && vcount == vc && paylen == pl && metalen == ml &&
                   std::memcmp(meta_digest, dg, 32) == 0;
        }
    };
    static thread_local std::vector<std::string> ns_cache, auth_cache;
    static thread_local MetaCacheKey cache_key = {nullptr, {0}, 0, 0, 0};

    const uint8_t *meta_dg = b + OFF_METAMAP_DG;
    if (!cache_key.matches(bytes, meta_dg, vcount, paylen, metalen)) {
        MetaView mv = parse_metadata(b + ELPIS_VSHARD_HEADER_BYTES + paylen, metalen, vcount);
        if (!mv.ok) {
            cache_key.addr = nullptr;                  /* never leave a half-valid key */
            return -1;
        }
        ns_cache = mv.ns;
        auth_cache = mv.auth;
        cache_key.addr = bytes;
        std::memcpy(cache_key.meta_digest, meta_dg, 32);
        cache_key.vcount = vcount;
        cache_key.paylen = paylen;
        cache_key.metalen = metalen;
    }
    const uint8_t *pairs = b + ELPIS_VSHARD_HEADER_BYTES + paylen + metalen - vcount * 8ull;
    uint32_t ni = get_u32(pairs + index * 8), ai = get_u32(pairs + index * 8 + 4);
    if (ni >= ns_cache.size() || ai >= auth_cache.size()) return -1;
    if (ns_out) *ns_out = ns_cache[ni].c_str();
    if (authority_out) *authority_out = auth_cache[ai].c_str();
    return 0;
}

int elpis_vshard_record_meta(const void *bytes, size_t len, uint64_t index,
                             const char **ns_out, const char **authority_out) {
    try {
        return vshard_record_meta_impl(bytes, len, index, ns_out, authority_out);
    } catch (...) {
        return -1;
    }
}

/* No C++ exception may cross the C ABI: the builder allocates vectors and
 * strings, so std::bad_alloc is converted to a plain failure code here. */
int elpis_vshard_build(const elpis_vshard_input *records, uint64_t count,
                       const elpis_embedding_profile *profile,
                       const char *corpus_manifest_digest,
                       void **bytes_out, size_t *len_out, char shard_digest_out[65]) {
    try {
        return vshard_build_impl(records, count, profile, corpus_manifest_digest,
                                 bytes_out, len_out, shard_digest_out);
    } catch (...) {
        return -1;
    }
}

static int vshard_write_impl(const char *path, const void *bytes, size_t len) {
    if (!path || !bytes) return -1;

    /* Publication must be atomically no-replace. A stat() guard followed by
     * rename() is not: another writer can create the destination in the window
     * between them, and POSIX rename() then silently replaces it. link() fails
     * with EEXIST atomically instead, so exactly one of two concurrent writers
     * to the same destination can win and the winner's bytes are never
     * clobbered. renameat2(RENAME_NOREPLACE) would also do, but it is Linux
     * only and needs a fallback anyway. */
    std::string p(path);
    size_t slash = p.find_last_of('/');
    std::string dir = slash == std::string::npos ? std::string(".") : p.substr(0, slash);
    std::string tmpl = dir + "/.vshard-XXXXXX";
    std::vector<char> t(tmpl.begin(), tmpl.end());
    t.push_back(0);
    int fd = mkstemp(t.data());
    if (fd < 0) return -1;

    auto cleanup_fail = [&](int fd_open) -> int {
        if (fd_open >= 0) close(fd_open);
        unlink(t.data());                       /* temporaries never survive a failure */
        return -1;
    };

    const uint8_t *q = (const uint8_t *)bytes;
    size_t left = len;
    while (left) {
        ssize_t w = write(fd, q, left);
        if (w <= 0) {
            if (w < 0 && errno == EINTR) continue;
            return cleanup_fail(fd);
        }
        q += (size_t)w;
        left -= (size_t)w;
    }
    if (fsync(fd) != 0) return cleanup_fail(fd);
    if (close(fd) != 0) return cleanup_fail(-1);

    if (link(t.data(), path) != 0) {
        /* EEXIST here is the no-overwrite guarantee doing its job. */
        unlink(t.data());
        return -1;
    }
    if (unlink(t.data()) != 0) { /* destination is already published; keep going */ }

    int dfd = open(dir.c_str(), O_RDONLY | O_DIRECTORY);
    if (dfd < 0) return -1;
    /* A directory fsync failure means the publication may not survive a crash,
     * so it is reported rather than ignored. */
    if (fsync(dfd) != 0) { close(dfd); return -1; }
    if (close(dfd) != 0) return -1;
    return 0;
}

int elpis_vshard_write(const char *path, const void *bytes, size_t len) {
    try {
        return vshard_write_impl(path, bytes, len);
    } catch (...) {
        return -1;
    }
}

int elpis_vshard_read_file(const char *path, void **bytes_out, size_t *len_out) {
    if (!path || !bytes_out || !len_out) return -1;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    struct stat sb;
    if (fstat(fd, &sb) != 0) { close(fd); return -1; }
    size_t n = (size_t)sb.st_size;
    uint8_t *buf = (uint8_t *)std::malloc(n ? n : 1);
    if (!buf) { close(fd); return -1; }
    size_t off = 0;
    while (off < n) {
        ssize_t r = read(fd, buf + off, n - off);
        if (r <= 0) { if (errno == EINTR) continue; std::free(buf); close(fd); return -1; }
        off += (size_t)r;
    }
    close(fd);
    *bytes_out = buf;
    *len_out = n;
    return 0;
}

} // extern "C"
