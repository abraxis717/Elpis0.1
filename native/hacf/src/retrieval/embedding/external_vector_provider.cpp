/* external_vector_provider.cpp - admits precomputed vectors produced outside
 * HACF (for example on Ouroboros) and transferred to the target host.
 *
 * It generates nothing. It validates dimension, finiteness, the declared
 * normalization policy and the embedding-profile digest, and refuses anything
 * that does not match. It executes no Python, downloads no model and opens no
 * socket. */

#include "embedder_internal.h"

#include "elpis/sha256.h"

#include <cmath>
#include <cstring>
#include <new>

extern "C" {

int elpis_embedder_external_create(const elpis_embedding_profile *profile, elpis_embedder **out) {
    if (!out || !profile) return -1;
    if (elpis_embedding_profile_validate(profile) != 0) return -1;
    auto *e = new (std::nothrow) elpis_embedder();
    if (!e) return -1;
    e->kind = ELPIS_EMBEDDER_KIND_EXTERNAL;
    e->profile = *profile;
    if (elpis_embedding_profile_digest(&e->profile, e->profile_digest) != 0) { delete e; return -1; }
    *out = e;
    return 0;
}

int elpis_embedder_accept(elpis_embedder *e, const float *in, uint32_t in_dim,
                          const char *profile_digest, float *out, uint32_t out_dim) {
    if (!e || !in || !out) return -1;
    if (e->kind != ELPIS_EMBEDDER_KIND_EXTERNAL) { elpis_embedder_set_error(e, "fixture provider does not admit external vectors"); return -1; }
    if (in_dim != e->profile.dimensions) { elpis_embedder_set_error(e, "external vector dimension mismatch"); return -1; }
    if (out_dim != e->profile.dimensions) { elpis_embedder_set_error(e, "output dimension mismatch"); return -1; }
    if (!elpis_vector_all_finite(in, in_dim)) { elpis_embedder_set_error(e, "external vector is not finite"); return -1; }
    if (profile_digest && std::strcmp(profile_digest, e->profile_digest) != 0) {
        elpis_embedder_set_error(e, "external vector embedding-profile digest mismatch");
        return -1;
    }
    if (e->profile.normalization == ELPIS_NORM_L2) {
        double n = elpis_vector_l2_norm(in, in_dim);
        if (!(n > 0.0)) { elpis_embedder_set_error(e, "external vector has zero norm under an L2 profile"); return -1; }
        /* The producer declared normalized output; admit only what is already
         * normalized rather than silently rescaling it. */
        if (n < 0.999 || n > 1.001) { elpis_embedder_set_error(e, "external vector violates the L2 normalization policy"); return -1; }
    }
    std::memcpy(out, in, (size_t)out_dim * sizeof(float));
    return 0;
}

} // extern "C"
