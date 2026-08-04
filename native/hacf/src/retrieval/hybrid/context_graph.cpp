#include "elpis/context_graph.h"
#include "elpis/corpus.h"
#include "elpis/sha256.h"

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <memory>
#include <vector>

namespace {

struct Edge {
    uint8_t subject[32];
    uint8_t object[32];
    uint8_t provenance[32];
    uint32_t type;
    uint32_t authority;
};

static bool canonical_hex64(const char *s) {
    if (!s || strnlen(s, 65) != 64) return false;
    for (size_t i = 0; i < 64; ++i) {
        unsigned char c = (unsigned char)s[i];
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    }
    return true;
}

static int edge_cmp(const Edge &a, const Edge &b) {
    int c = std::memcmp(a.subject, b.subject, 32);
    if (c) return c;
    if (a.type != b.type) return a.type < b.type ? -1 : 1;
    c = std::memcmp(a.object, b.object, 32);
    if (c) return c;
    c = std::memcmp(a.provenance, b.provenance, 32);
    if (c) return c;
    if (a.authority != b.authority) return a.authority < b.authority ? -1 : 1;
    return 0;
}

static void put_le32(elpis_sha256_ctx *h, uint32_t v) {
    uint8_t b[4] = {(uint8_t)v, (uint8_t)(v >> 8), (uint8_t)(v >> 16), (uint8_t)(v >> 24)};
    elpis_sha256_update(h, b, sizeof b);
}
static void put_le64(elpis_sha256_ctx *h, uint64_t v) {
    uint8_t b[8];
    for (unsigned i = 0; i < 8; ++i) b[i] = (uint8_t)(v >> (8u * i));
    elpis_sha256_update(h, b, sizeof b);
}

static void graph_digest(const std::vector<Edge> &edges, char out[65]) {
    static const char domain[] = "elpis.context_graph.v1";
    elpis_sha256_ctx h;
    elpis_sha256_init(&h);
    elpis_sha256_update(&h, domain, sizeof domain); /* includes NUL */
    put_le64(&h, edges.size());
    for (const Edge &e : edges) {
        elpis_sha256_update(&h, e.subject, 32);
        elpis_sha256_update(&h, e.object, 32);
        elpis_sha256_update(&h, e.provenance, 32);
        put_le32(&h, e.type);
        put_le32(&h, e.authority);
    }
    uint8_t d[32];
    elpis_sha256_final(&h, d);
    elpis_hex32(d, out);
}

} // namespace

struct elpis_context_graph {
    std::vector<Edge> edges;
    char digest[65]{};
    char error[192]{};
};

extern "C" {

int elpis_context_graph_create(const elpis_context_edge_input *in, uint32_t n,
                               elpis_context_graph **out) {
    if (!out || (n && !in) || n > ELPIS_CGRAPH_MAX_EDGES) return -1;
    *out = nullptr;
    try {
        std::unique_ptr<elpis_context_graph> g(new elpis_context_graph());
        g->edges.reserve(n);
        for (uint32_t i = 0; i < n; ++i) {
            if (!canonical_hex64(in[i].subject_chunk_digest) ||
                !canonical_hex64(in[i].object_chunk_digest) ||
                !canonical_hex64(in[i].provenance_digest) ||
                in[i].edge_type == 0 || in[i].authority > 3) {
                return -1;
            }
            Edge e{};
            if (elpis_unhex32(in[i].subject_chunk_digest, e.subject) != 0 ||
                elpis_unhex32(in[i].object_chunk_digest, e.object) != 0 ||
                elpis_unhex32(in[i].provenance_digest, e.provenance) != 0 ||
                std::memcmp(e.subject, e.object, 32) == 0) {
                return -1;
            }
            e.type = in[i].edge_type;
            e.authority = in[i].authority;
            g->edges.push_back(e);
        }
        std::sort(g->edges.begin(), g->edges.end(), [](const Edge &a, const Edge &b) {
            return edge_cmp(a, b) < 0;
        });
        g->edges.erase(std::unique(g->edges.begin(), g->edges.end(), [](const Edge &a, const Edge &b) {
            return edge_cmp(a, b) == 0;
        }), g->edges.end());
        graph_digest(g->edges, g->digest);
        *out = g.release();
        return 0;
    } catch (...) {
        return -1;
    }
}

void elpis_context_graph_destroy(elpis_context_graph *g) { delete g; }
const char *elpis_context_graph_error(const elpis_context_graph *g) {
    return g ? g->error : "invalid context graph";
}
uint32_t elpis_context_graph_edge_count(const elpis_context_graph *g) {
    return g && g->edges.size() <= UINT32_MAX ? (uint32_t)g->edges.size() : 0;
}
int elpis_context_graph_digest(const elpis_context_graph *g, char out[65]) {
    if (!g || !out) return -1;
    std::memcpy(out, g->digest, 65);
    return 0;
}

int elpis_context_graph_neighbors(const elpis_context_graph *g, const char *subject,
                                  uint32_t min_authority, uint32_t offset, uint32_t limit,
                                  elpis_context_neighbor *out, uint32_t *n_out) {
    if (!g || !n_out || min_authority > 3 || (limit && !out) || !canonical_hex64(subject))
        return -1;
    *n_out = 0;
    if (!limit) return 0;
    uint8_t key[32];
    if (elpis_unhex32(subject, key) != 0) return -1;
    Edge probe{};
    std::memcpy(probe.subject, key, 32);
    auto it = std::lower_bound(g->edges.begin(), g->edges.end(), probe,
        [](const Edge &a, const Edge &b) { return std::memcmp(a.subject, b.subject, 32) < 0; });
    uint32_t eligible = 0;
    while (it != g->edges.end() && std::memcmp(it->subject, key, 32) == 0 && *n_out < limit) {
        if (it->authority >= min_authority && eligible++ >= offset) {
            elpis_context_neighbor &v = out[*n_out];
            std::memset(&v, 0, sizeof v);
            elpis_hex32(it->object, v.chunk_digest);
            elpis_hex32(it->provenance, v.provenance_digest);
            v.edge_type = it->type;
            v.authority = it->authority;
            ++*n_out;
        }
        ++it;
    }
    return 0;
}

int elpis_context_graph_manifest_json(const elpis_context_graph *g,
                                      char **json_out, char digest_out[65]) {
    if (!g || !json_out || !digest_out) return -1;
    *json_out = nullptr;
    try {
        std::string j = "{\"abi_version\":1,\"edge_count\":" +
                        std::to_string(g->edges.size()) + ",\"edges\":[";
        for (size_t i = 0; i < g->edges.size(); ++i) {
            if (i) j.push_back(',');
            char s[65], o[65], p[65];
            elpis_hex32(g->edges[i].subject, s);
            elpis_hex32(g->edges[i].object, o);
            elpis_hex32(g->edges[i].provenance, p);
            j += "{\"authority\":" + std::to_string(g->edges[i].authority) +
                 ",\"edge_type\":" + std::to_string(g->edges[i].type) +
                 ",\"object\":\"" + o + "\",\"provenance\":\"" + p +
                 "\",\"subject\":\"" + s + "\"}";
        }
        j += "],\"schema\":\"elpis.context_graph.v1\",\"snapshot_digest\":\"";
        j += g->digest;
        j += "\"}";
        uint8_t d[32];
        elpis_sha256(j.data(), j.size(), d);
        elpis_hex32(d, digest_out);
        char *p = (char *)std::malloc(j.size() + 1);
        if (!p) return -1;
        std::memcpy(p, j.data(), j.size());
        p[j.size()] = 0;
        *json_out = p;
        return 0;
    } catch (...) {
        return -1;
    }
}

} // extern C
