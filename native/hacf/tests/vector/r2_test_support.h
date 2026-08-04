/* r2_test_support.h - shared helpers for the R2 test suites.
 * Test-only: never compiled into a library target. */
#ifndef HACF_R2_TEST_SUPPORT_H
#define HACF_R2_TEST_SUPPORT_H

#include "elpis/embedding_provider.h"
#include "elpis/fms.h"
#include "elpis/fms_pal_posix.h"
#include "elpis/sha256.h"
#include "elpis/vector_shard.h"

#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>

namespace r2t {

inline void rmtree(const std::string &p) {
    DIR *d = opendir(p.c_str());
    if (!d) return;
    struct dirent *e;
    while ((e = readdir(d))) {
        if (!std::strcmp(e->d_name, ".") || !std::strcmp(e->d_name, "..")) continue;
        std::string q = p + "/" + e->d_name;
        if (unlink(q.c_str()) != 0) rmtree(q);
    }
    closedir(d);
    rmdir(p.c_str());
}

inline void mkdirp(const std::string &p) {
    std::string cur;
    for (size_t i = 0; i < p.size(); i++) {
        cur.push_back(p[i]);
        if (p[i] == '/' && i) mkdir(cur.c_str(), 0700);
    }
    mkdir(p.c_str(), 0700);
}

/* WARM+COLD context. hot_absent_policy is REJECT on purpose: if any R2 code
 * path ever asked for FMS_HOT it would fail loudly instead of folding down. */
inline fms_ctx *make_fms(const std::string &cold_root, uint64_t warm_bytes,
                         uint64_t cold_bytes = 512ull << 20, uint32_t max_objects = 64) {
    mkdirp(cold_root);
    fms_config cfg;
    std::memset(&cfg, 0, sizeof cfg);
    cfg.tier_budget[FMS_WARM] = warm_bytes;
    cfg.tier_budget[FMS_COLD] = cold_bytes;
    cfg.domain_ceiling[FMS_DOM_RAM] = warm_bytes;
    cfg.domain_ceiling[FMS_DOM_DEVICE] = 1;
    cfg.domain_ceiling[FMS_DOM_STORAGE] = cold_bytes;
    cfg.high_wm = 0.90f;
    cfg.low_wm = 0.70f;
    cfg.max_objects = max_objects;
    cfg.hot_absent_policy = FMS_REJECT;
    cfg.cold_absent_policy = FMS_FOLD_DOWN;
    fms_pal *pal = fms_pal_posix_create(cold_root.c_str());
    if (!pal) return nullptr;
    fms_ctx *c = fms_create(&cfg, pal);
    if (!c) pal->destroy(pal->self);
    return c;
}

inline std::string hex_of(const std::string &s) {
    uint8_t d[32];
    char hex[65];
    elpis_sha256(s.data(), s.size(), d);
    elpis_hex32(d, hex);
    return std::string(hex);
}

/* Deterministic synthetic shard content. */
struct Corpus {
    elpis_embedding_profile profile{};
    std::vector<std::string> chunk, doc, ns, authority;
    std::vector<std::vector<float>> vec;
    std::vector<elpis_vshard_input> inputs;

    void build(const char *tag, uint32_t n, elpis_embedder *emb) {
        elpis_embedder_profile(emb, &profile);
        for (uint32_t i = 0; i < n; i++) {
            char b[160];
            std::snprintf(b, sizeof b, "%s/chunk/%u", tag, i);
            chunk.push_back(hex_of(b));
            std::snprintf(b, sizeof b, "%s/doc/%u", tag, i / 4);
            doc.push_back(hex_of(b));
            ns.push_back((i % 2) ? "elpis.docs" : "elpis.code");
            authority.push_back((i % 3 == 0) ? "canonical" : "reference");
            std::vector<float> v(ELPIS_EMBEDDING_DIM);
            std::snprintf(b, sizeof b, "%s/body/%u", tag, i);
            elpis_embedder_embed(emb, b, std::strlen(b), v.data(), ELPIS_EMBEDDING_DIM);
            vec.push_back(std::move(v));
        }
        refresh();
    }
    void refresh() {
        inputs.clear();
        for (size_t i = 0; i < chunk.size(); i++) {
            elpis_vshard_input in;
            std::snprintf(in.chunk_digest, sizeof in.chunk_digest, "%s", chunk[i].c_str());
            std::snprintf(in.doc_digest, sizeof in.doc_digest, "%s", doc[i].c_str());
            in.ns = ns[i].c_str();
            in.authority = authority[i].c_str();
            in.vector = vec[i].data();
            inputs.push_back(in);
        }
    }
};

inline std::vector<uint8_t> build_shard(const Corpus &c, const char *corpus_digest,
                                        char digest_out[65]) {
    void *b = nullptr;
    size_t n = 0;
    if (elpis_vshard_build(c.inputs.data(), c.inputs.size(), &c.profile, corpus_digest, &b, &n,
                           digest_out) != 0)
        return {};
    std::vector<uint8_t> v((uint8_t *)b, (uint8_t *)b + n);
    std::free(b);
    return v;
}

/* Flip one byte in every cold blob under a root, simulating bit rot. */
inline int corrupt_cold_blobs(const std::string &root) {
    DIR *d = opendir(root.c_str());
    if (!d) return 0;
    struct dirent *e;
    int n = 0;
    while ((e = readdir(d))) {
        if (!std::strstr(e->d_name, ".blob")) continue;
        std::string p = root + "/" + e->d_name;
        int fd = open(p.c_str(), O_RDWR);
        if (fd < 0) continue;
        unsigned char x = 0xA5;
        if (pwrite(fd, &x, 1, 512) == 1) n++;
        close(fd);
    }
    closedir(d);
    return n;
}

} // namespace r2t
#endif
