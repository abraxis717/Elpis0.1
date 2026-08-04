/* embedder_internal.h - shared layout for the embedding providers.
 * Private to src/retrieval/embedding; not installed and not part of the ABI. */
#ifndef ELPIS_EMBEDDER_INTERNAL_H
#define ELPIS_EMBEDDER_INTERNAL_H

#include "elpis/embedding_provider.h"
#include <stddef.h>

enum { ELPIS_EMBEDDER_KIND_FIXTURE = 1, ELPIS_EMBEDDER_KIND_EXTERNAL = 2 };

struct elpis_embedder {
    int                     kind = 0;
    elpis_embedding_profile profile{};
    char                    profile_digest[65] = {0};
    char                    error[192] = {0};
};

size_t elpis_embedder_bounded_len(const char *s, size_t cap);
/* Bounded checks for fixed-width ABI fields; never read past the declared width. */
int    elpis_embedder_valid_hex64(const char field[65]);
int    elpis_embedder_valid_text(const char *field, size_t cap, int allow_empty);
void   elpis_embedder_set_error(elpis_embedder *e, const char *message);

#endif
