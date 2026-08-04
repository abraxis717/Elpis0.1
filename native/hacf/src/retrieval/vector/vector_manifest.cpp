/* vector_manifest.cpp - canonical manifests for R2 artifacts.
 *
 * Rules for every identity-bearing manifest:
 *   - keys emitted in ascending order, fixed by construction
 *   - integers only; no floating point ever enters an identity-bearing manifest,
 *     so there is no NaN, no infinity and no printf rounding to disagree about
 *   - digests are lowercase hex
 *   - compiler and host details appear only in benchmark and qualification
 *     manifests, which are explicitly not identity-bearing */

#include "elpis/vector_index.h"
#include "elpis/vector_shard.h"
#include "elpis/sha256.h"

#include <array>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>

namespace {

std::string q(const std::string &s) { return "\"" + s + "\""; }
std::string kv(const char *k, const std::string &v) { return q(k) + ":" + q(v); }
std::string ku(const char *k, uint64_t v) { return q(k) + ":" + std::to_string(v); }

char *dup_cstr(const std::string &s) {
    char *p = (char *)std::malloc(s.size() + 1);
    if (!p) return nullptr;
    std::memcpy(p, s.data(), s.size());
    p[s.size()] = 0;
    return p;
}

void digest_of(const std::string &s, char out[65]) {
    uint8_t d[32];
    elpis_sha256(s.data(), s.size(), d);
    elpis_hex32(d, out);
}

} // namespace

extern "C" {

static int vshard_manifest_impl(const elpis_vshard_header *h, char **json_out, char digest_out[65]) {
    if (!h || !json_out) return -1;
    std::string j = "{";
    j += ku("abi_version", h->abi_version) + ",";
    j += kv("corpus_manifest_digest", h->corpus_manifest_digest) + ",";
    j += ku("dimensions", h->dimensions) + ",";
    j += ku("element_type", h->element_type) + ",";
    j += kv("embedding_profile_digest", h->embedding_profile_digest) + ",";
    j += ku("header_bytes", h->header_bytes) + ",";
    j += ku("metadata_bytes", h->metadata_bytes) + ",";
    j += kv("metadata_map_digest", h->metadata_map_digest) + ",";
    j += ku("metric", h->metric) + ",";
    j += ku("normalization", h->normalization) + ",";
    j += ku("payload_bytes", h->payload_bytes) + ",";
    j += kv("payload_digest", h->payload_digest) + ",";
    j += ku("record_bytes", h->record_bytes) + ",";
    j += kv("shard_digest", h->shard_digest) + ",";
    j += ku("vector_count", h->vector_count);
    j += "}";
    if (digest_out) digest_of(j, digest_out);
    char *p = dup_cstr(j);
    if (!p) return -1;
    *json_out = p;
    return 0;
}

/* Manifest writers build std::string; no exception may reach a C caller. */
int elpis_vshard_manifest_json(const elpis_vshard_header *h, char **json_out, char digest_out[65]) {
    try { return vshard_manifest_impl(h, json_out, digest_out); } catch (...) { return -1; }
}

/* Defined in vector_index.cpp: acquires the index shared lock exactly once and
 * returns everything the manifest needs. Calling the public accessors here
 * would re-enter a non-recursive shared_mutex. */
extern int elpis_vector_index_manifest_locked(elpis_vector_index *ix, char (*ids)[65], uint32_t cap,
                                              uint32_t *n_out, elpis_vshard_header *hdrs,
                                              char profile_digest_out[65],
                                              char corpus_digest_out[65]);

static int index_manifest_impl(elpis_vector_index *ix, char **json_out, char digest_out[65]) {
    if (!ix || !json_out) return -1;

    uint32_t n = 0;
    if (elpis_vector_index_manifest_locked(ix, nullptr, 0, &n, nullptr, nullptr, nullptr) != 0)
        return -1;
    std::vector<std::array<char, 65>> ids(n ? n : 1);
    std::vector<elpis_vshard_header> hdrs(n ? n : 1);
    char prof_dg[65] = {0}, corpus_dg[65] = {0};
    if (elpis_vector_index_manifest_locked(ix, reinterpret_cast<char (*)[65]>(ids.data()),
                                           n ? n : 1, &n, hdrs.data(), prof_dg, corpus_dg) != 0)
        return -1;

    uint64_t total_vectors = 0;
    std::string shards = "[";
    for (uint32_t i = 0; i < n; i++) {
        const elpis_vshard_header &h = hdrs[i];
        total_vectors += h.vector_count;
        if (i) shards += ",";
        shards += "{" + kv("digest", ids[i].data()) + "," + ku("vector_count", h.vector_count) + "}";
    }
    shards += "]";

    std::string j = "{";
    j += ku("abi_version", ELPIS_VINDEX_ABI_VERSION) + ",";
    j += kv("corpus_manifest_digest", corpus_dg) + ",";
    j += ku("dimensions", ELPIS_EMBEDDING_DIM) + ",";
    j += kv("embedding_profile_digest", prof_dg) + ",";
    j += q("shards") + ":" + shards + ",";
    j += ku("shard_count", n) + ",";
    j += ku("vector_count", total_vectors);
    j += "}";

    if (digest_out) digest_of(j, digest_out);
    char *p = dup_cstr(j);
    if (!p) return -1;
    *json_out = p;
    return 0;
}

int elpis_vector_index_manifest_json(elpis_vector_index *ix, char **json_out, char digest_out[65]) {
    try { return index_manifest_impl(ix, json_out, digest_out); } catch (...) { return -1; }
}

} // extern "C"
