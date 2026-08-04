/* trm_eval_persist.c — P10 evaluation persistence utilities. */
#include "elpis_semantic/trm_evaluation_fixture.h"
#include "elpis_semantic/trm_evaluation_corpus.h"
#include <stdio.h>
#include <string.h>
#include "elpis/sha256.h"

void elpis_trm_evaluation_fixture_init(
    elpis_semantic_trm_evaluation_fixture_v1 *fixture, uint32_t ordinal) {
    memset(fixture, 0, sizeof(*fixture));
    fixture->abi_version = TRM_EVALUATION_FIXTURE_VERSION;
    fixture->fixture_ordinal = ordinal;
}

int elpis_trm_evaluation_fixture_identity(
    const elpis_semantic_trm_evaluation_fixture_v1 *f, hacf_digest *out) {
    uint8_t hash[32];
    elpis_sha256((const void *)f, offsetof(elpis_semantic_trm_evaluation_fixture_v1, reserved), hash);
    memcpy(out->bytes, hash, sizeof(out->bytes));
    return 0;
}

int elpis_trm_evaluation_fixture_validate(
    const elpis_semantic_trm_evaluation_fixture_v1 *f) {
    if (f->abi_version != TRM_EVALUATION_FIXTURE_VERSION) return -1;
    return 0;
}

int elpis_write_trm_evaluation_fixture(const char *path,
    const elpis_semantic_trm_evaluation_fixture_v1 *f) {
    FILE *fp = fopen(path, "wb"); if (!fp) return -1;
    size_t sz = sizeof(*f);
    if (fwrite(f, 1, sz, fp) != sz) { fclose(fp); return -1; }
    fclose(fp); return 0;
}

int elpis_read_trm_evaluation_fixture(const char *path,
    elpis_semantic_trm_evaluation_fixture_v1 *out) {
    FILE *fp = fopen(path, "rb"); if (!fp) return -1;
    size_t sz = sizeof(*out);
    if (fread(out, 1, sz, fp) != sz) { fclose(fp); return -1; }
    fclose(fp); return elpis_trm_evaluation_fixture_validate(out);
}

void elpis_trm_evaluation_corpus_init(
    elpis_semantic_trm_evaluation_corpus_v1 *corpus) {
    memset(corpus, 0, sizeof(*corpus));
    corpus->abi_version = TRM_EVALUATION_CORPUS_VERSION;
    corpus->fixture_count = TRM_EVALUATION_CORPUS_FIXTURE_COUNT;
}

int elpis_trm_evaluation_corpus_identity(
    const elpis_semantic_trm_evaluation_corpus_v1 *c, hacf_digest *out) {
    uint8_t hash[32];
    elpis_sha256((const void *)c, offsetof(elpis_semantic_trm_evaluation_corpus_v1, reserved), hash);
    memcpy(out->bytes, hash, sizeof(out->bytes));
    return 0;
}

int elpis_trm_evaluation_corpus_validate(
    const elpis_semantic_trm_evaluation_corpus_v1 *c) {
    if (c->abi_version != TRM_EVALUATION_CORPUS_VERSION) return -1;
    return 0;
}

int elpis_write_trm_evaluation_corpus(const char *path,
    const elpis_semantic_trm_evaluation_corpus_v1 *c) {
    FILE *fp = fopen(path, "wb"); if (!fp) return -1;
    size_t sz = sizeof(*c);
    if (fwrite(c, 1, sz, fp) != sz) { fclose(fp); return -1; }
    fclose(fp); return 0;
}

int elpis_read_trm_evaluation_corpus(const char *path,
    elpis_semantic_trm_evaluation_corpus_v1 *out) {
    FILE *fp = fopen(path, "rb"); if (!fp) return -1;
    size_t sz = sizeof(*out);
    if (fread(out, 1, sz, fp) != sz) { fclose(fp); return -1; }
    fclose(fp); return elpis_trm_evaluation_corpus_validate(out);
}
