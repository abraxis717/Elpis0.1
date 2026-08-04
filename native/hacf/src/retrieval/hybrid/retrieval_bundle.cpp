#define _POSIX_C_SOURCE 200809L

#include "elpis/retrieval_bundle.h"
#include "elpis/cascade.h"
#include "elpis/corpus.h"
#include "elpis/sha256.h"
#include "hybrid_internal.h"

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <string>
#include <memory>
#include <sys/stat.h>
#include <unistd.h>
#include <utility>
#include <vector>

namespace {

static const char kZeroDigest[] =
    "0000000000000000000000000000000000000000000000000000000000000000";

static std::string json_escape(const char *s, size_t n) {
    static const char h[] = "0123456789abcdef";
    std::string o;
    o.reserve(n + 8);
    o.push_back('"');
    for (size_t i = 0; i < n; ++i) {
        unsigned char c = (unsigned char)s[i];
        switch (c) {
        case '"': o += "\\\""; break;
        case '\\': o += "\\\\"; break;
        case '\b': o += "\\b"; break;
        case '\f': o += "\\f"; break;
        case '\n': o += "\\n"; break;
        case '\r': o += "\\r"; break;
        case '\t': o += "\\t"; break;
        default:
            if (c < 0x20) {
                o += "\\u00";
                o.push_back(h[c >> 4]);
                o.push_back(h[c & 15]);
            } else {
                o.push_back((char)c);
            }
        }
    }
    o.push_back('"');
    return o;
}


static std::string hex_bytes(const char *s, size_t n) {
    static const char h[] = "0123456789abcdef";
    std::string o;
    o.resize(n * 2);
    for (size_t i = 0; i < n; ++i) {
        unsigned char c = (unsigned char)s[i];
        o[i * 2] = h[c >> 4];
        o[i * 2 + 1] = h[c & 15];
    }
    return o;
}

static int write_all(int fd, const void *data, size_t n) {
    const uint8_t *p = (const uint8_t *)data;
    while (n) {
        ssize_t w = ::write(fd, p, n);
        if (w < 0) { if (errno == EINTR) continue; return -1; }
        if (w == 0) return -1;
        p += (size_t)w;
        n -= (size_t)w;
    }
    return 0;
}


} // namespace

struct elpis_retrieval_bundle {
    std::string query_text;
    std::string namespace_filter;
    std::string authority_filter;
    char query_digest[65]{};
    char corpus_manifest_digest[65]{};
    char vector_index_manifest_digest[65]{};
    char graph_snapshot_digest[65]{};
    char fusion_policy_digest[65]{};
    char bundle_digest[65]{};
    char package_digest[65]{};
    std::vector<R3OwnedItem> items;
    std::string json;
};

static int build_json_and_identities(elpis_retrieval_bundle *b) {
    try {
        std::string j = "{\"abi_version\":1,\"authority_filter\":";
        if (b->authority_filter.empty()) j += "null";
        else j += json_escape(b->authority_filter.data(), b->authority_filter.size());
        j += ",\"corpus_manifest_digest\":\"";
        j += b->corpus_manifest_digest;
        j += "\",\"fusion_policy_digest\":\"";
        j += b->fusion_policy_digest;
        j += "\",\"graph_snapshot_digest\":\"";
        j += b->graph_snapshot_digest;
        j += "\",\"items\":[";
        for (size_t i = 0; i < b->items.size(); ++i) {
            const R3OwnedItem &x = b->items[i];
            if (i) j.push_back(',');
            j += "{\"authority\":" + json_escape(x.authority.data(), x.authority.size());
            j += ",\"chunk_digest\":\"" + x.chunk_digest + "\"";
            j += ",\"dense_rank\":" + std::to_string(x.dense_rank);
            j += ",\"dense_score_key\":" + std::to_string(x.dense_score_key);
            j += ",\"doc_digest\":\"" + x.doc_digest + "\"";
            j += ",\"edge_authority\":" + std::to_string(x.edge_authority);
            j += ",\"edge_type\":" + std::to_string(x.edge_type);
            j += ",\"final_rank\":" + std::to_string(x.final_rank);
            j += ",\"fusion_score_key\":" + std::to_string(x.fusion_score_key);
            j += ",\"graph_hop\":" + std::to_string(x.graph_hop);
            j += ",\"graph_parent_digest\":\"" + x.graph_parent_digest + "\"";
            j += ",\"item_kind\":" + std::to_string(x.item_kind);
            j += ",\"lexical_rank\":" + std::to_string(x.lexical_rank);
            j += ",\"namespace_hex\":\"" + hex_bytes(x.ns.data(), x.ns.size()) + "\"";
            j += ",\"source_mask\":" + std::to_string(x.source_mask);
            j += ",\"text_hex\":\"" + hex_bytes(x.text.data(), x.text.size()) + "\"";
            j += ",\"text_bytes\":" + std::to_string(x.text.size());
            j += ",\"text_digest\":\"" + x.text_digest + "\"}";
        }
        j += "],\"namespace_filter_hex\":";
        if (b->namespace_filter.empty()) j += "null";
        else j += "\"" + hex_bytes(b->namespace_filter.data(), b->namespace_filter.size()) + "\"";
        j += ",\"query_digest\":\"";
        j += b->query_digest;
        j += "\",\"query_text_hex\":\"";
        j += hex_bytes(b->query_text.data(), b->query_text.size());
        j += "\"";
        j += ",\"schema\":\"" ELPIS_RETRIEVAL_BUNDLE_SCHEMA "\"";
        j += ",\"vector_index_manifest_digest\":\"";
        j += b->vector_index_manifest_digest;
        j += "\"}";

        uint8_t d[32];
        elpis_sha256(j.data(), j.size(), d);
        elpis_hex32(d, b->bundle_digest);
        b->json = std::move(j);

        hacf_digest schema{}, policy{}, parent{}, deps[3]{}, out{};
        elpis_sha256(ELPIS_RETRIEVAL_BUNDLE_SCHEMA,
                     std::strlen(ELPIS_RETRIEVAL_BUNDLE_SCHEMA), schema.bytes);
        if (elpis_unhex32(b->fusion_policy_digest, policy.bytes) != 0 ||
            elpis_unhex32(b->query_digest, parent.bytes) != 0 ||
            elpis_unhex32(b->corpus_manifest_digest, deps[0].bytes) != 0 ||
            elpis_unhex32(b->vector_index_manifest_digest, deps[1].bytes) != 0)
            return -1;
        uint32_t dep_count = 2;
        if (std::strcmp(b->graph_snapshot_digest, kZeroDigest) != 0) {
            if (elpis_unhex32(b->graph_snapshot_digest, deps[2].bytes) != 0) return -1;
            dep_count = 3;
        }
        hacf_package_spec spec{};
        spec.abi_version = 1;
        spec.object_type = HACF_OBJ_RETRIEVAL_BUNDLE;
        spec.schema_version = 1;
        spec.authority = HACF_AUTH_REFERENCE;
        spec.schema_digest = schema;
        spec.policy_digest = policy;
        spec.parents = &parent;
        spec.parent_count = 1;
        spec.dependencies = deps;
        spec.dependency_count = dep_count;
        spec.payload = b->json.data();
        spec.payload_bytes = b->json.size();
        if (hacf_digest_package(&spec, &out) != 0) return -1;
        hacf_digest_hex(&out, b->package_digest);
        return 0;
    } catch (...) {
        return -1;
    }
}

elpis_retrieval_bundle *r3_bundle_create(
    const std::string &query_text,
    const char query_digest[65],
    const char corpus_manifest_digest[65],
    const char vector_index_manifest_digest[65],
    const char graph_snapshot_digest[65],
    const char fusion_policy_digest[65],
    const char *namespace_filter,
    const char *authority_filter,
    std::vector<R3OwnedItem> &&items) {
    try {
        std::unique_ptr<elpis_retrieval_bundle> b(new elpis_retrieval_bundle());
        b->query_text = query_text;
        if (namespace_filter) b->namespace_filter = namespace_filter;
        if (authority_filter) b->authority_filter = authority_filter;
        std::memcpy(b->query_digest, query_digest, 65);
        std::memcpy(b->corpus_manifest_digest, corpus_manifest_digest, 65);
        std::memcpy(b->vector_index_manifest_digest, vector_index_manifest_digest, 65);
        std::memcpy(b->graph_snapshot_digest, graph_snapshot_digest, 65);
        std::memcpy(b->fusion_policy_digest, fusion_policy_digest, 65);
        b->items = std::move(items);
        if (build_json_and_identities(b.get()) != 0) return nullptr;
        return b.release();
    } catch (...) {
        return nullptr;
    }
}

extern "C" {

void elpis_retrieval_bundle_destroy(elpis_retrieval_bundle *b) { delete b; }
uint32_t elpis_retrieval_bundle_item_count(const elpis_retrieval_bundle *b) {
    return b && b->items.size() <= UINT32_MAX ? (uint32_t)b->items.size() : 0;
}

int elpis_retrieval_bundle_item(const elpis_retrieval_bundle *b, uint32_t index,
                                elpis_retrieval_item_view *out) {
    if (!b || !out || index >= b->items.size()) return -1;
    const R3OwnedItem &x = b->items[index];
    std::memset(out, 0, sizeof *out);
    std::snprintf(out->chunk_digest, sizeof out->chunk_digest, "%s", x.chunk_digest.c_str());
    std::snprintf(out->doc_digest, sizeof out->doc_digest, "%s", x.doc_digest.c_str());
    std::snprintf(out->ns, sizeof out->ns, "%s", x.ns.c_str());
    std::snprintf(out->authority, sizeof out->authority, "%s", x.authority.c_str());
    std::snprintf(out->graph_parent_digest, sizeof out->graph_parent_digest, "%s",
                  x.graph_parent_digest.c_str());
    std::snprintf(out->text_digest, sizeof out->text_digest, "%s", x.text_digest.c_str());
    out->fusion_score_key = x.fusion_score_key;
    out->dense_score_key = x.dense_score_key;
    out->lexical_rank = x.lexical_rank;
    out->dense_rank = x.dense_rank;
    out->final_rank = x.final_rank;
    out->source_mask = x.source_mask;
    out->item_kind = x.item_kind;
    out->graph_hop = x.graph_hop;
    out->edge_type = x.edge_type;
    out->edge_authority = x.edge_authority;
    out->text = x.text.c_str();
    out->text_bytes = (uint32_t)x.text.size();
    return 0;
}

int elpis_retrieval_bundle_identity(const elpis_retrieval_bundle *b,
                                    char q[65], char c[65], char v[65], char g[65],
                                    char p[65], char d[65], char h[65]) {
    if (!b) return -1;
    if (q) std::memcpy(q, b->query_digest, 65);
    if (c) std::memcpy(c, b->corpus_manifest_digest, 65);
    if (v) std::memcpy(v, b->vector_index_manifest_digest, 65);
    if (g) std::memcpy(g, b->graph_snapshot_digest, 65);
    if (p) std::memcpy(p, b->fusion_policy_digest, 65);
    if (d) std::memcpy(d, b->bundle_digest, 65);
    if (h) std::memcpy(h, b->package_digest, 65);
    return 0;
}

int elpis_retrieval_bundle_json(const elpis_retrieval_bundle *b,
                                char **json_out, char digest_out[65]) {
    if (!b || !json_out || !digest_out) return -1;
    *json_out = nullptr;
    char *p = (char *)std::malloc(b->json.size() + 1);
    if (!p) return -1;
    std::memcpy(p, b->json.data(), b->json.size());
    p[b->json.size()] = 0;
    *json_out = p;
    std::memcpy(digest_out, b->bundle_digest, 65);
    return 0;
}

int elpis_retrieval_bundle_write(const elpis_retrieval_bundle *b, const char *path,
                                 char digest_out[65]) {
    if (!b || !path || !*path || !digest_out) return -1;
    try {
        std::string p(path);
        size_t slash = p.find_last_of('/');
        std::string dir = slash == std::string::npos ? "." : p.substr(0, slash);
        std::string tmpl = dir + "/.retrieval-bundle-XXXXXX";
        std::vector<char> tmp(tmpl.begin(), tmpl.end());
        tmp.push_back(0);
        int fd = ::mkstemp(tmp.data());
        if (fd < 0) return -1;
        auto fail = [&](int open_fd) {
            if (open_fd >= 0) ::close(open_fd);
            ::unlink(tmp.data());
            return -1;
        };
        if (write_all(fd, b->json.data(), b->json.size()) != 0 || ::fsync(fd) != 0)
            return fail(fd);
        if (::close(fd) != 0) return fail(-1);
        if (::link(tmp.data(), path) != 0) return fail(-1);
        (void)::unlink(tmp.data());
        int dfd = ::open(dir.c_str(), O_RDONLY | O_DIRECTORY);
        if (dfd < 0) return -1;
        if (::fsync(dfd) != 0) { ::close(dfd); return -1; }
        if (::close(dfd) != 0) return -1;
        std::memcpy(digest_out, b->bundle_digest, 65);
        return 0;
    } catch (...) {
        return -1;
    }
}

} // extern C
