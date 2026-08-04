#include "elpis/chunking.h"

#include <cstdio>
#include <cstring>
#include <string>

int main() {
    elpis_chunk_profile p;
    elpis_chunk_profile_default(&p);

    std::string media(8192, 'x');
    char digest[65];
    if (elpis_chunk_profile_digest_checked(&p, media.c_str(), digest) != 0 || std::strlen(digest) != 64) {
        std::fprintf(stderr, "long media-type profile digest failed\n");
        return 1;
    }

    elpis_chunk_profile bad = p;
    bad.target_bytes = 4096;
    bad.max_bytes = 1024;
    elpis_chunk *chunks = nullptr;
    size_t n = 0;
    const char text[] = "abcdef";
    if (elpis_chunk_document(text, sizeof text - 1, ELPIS_MT_TEXT, &bad, "deadbeef", &chunks, &n) == 0) {
        std::fprintf(stderr, "invalid profile accepted\n");
        return 1;
    }

    const char json[] = "[1, 2, 3, true, null, \"x\", {\"a\":1}, [4,5]]";
    p.min_bytes = 0;
    if (elpis_chunk_document(json, sizeof json - 1, ELPIS_MT_JSON, &p, "deadbeef", &chunks, &n) != 0) {
        return 1;
    }
    if (n != 8) {
        std::fprintf(stderr, "primitive JSON array produced %zu chunks, expected 8\n", n);
        elpis_chunks_free(chunks);
        return 1;
    }
    for (size_t i = 0; i < n; ++i) {
        if (chunks[i].byte_end - chunks[i].byte_start > p.max_bytes) {
            std::fprintf(stderr, "chunk exceeds max_bytes\n");
            elpis_chunks_free(chunks);
            return 1;
        }
    }
    elpis_chunks_free(chunks);
    puts("chunking adversarial checks: PASS");
    return 0;
}
