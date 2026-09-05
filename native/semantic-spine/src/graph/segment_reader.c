/* segment_reader.c — Verify the writer's native header and record arrays.
 * The v1 identity binds the HACF projection, not a hash of the file bytes.
 * Registry definitions are not persisted; schema admission remains a builder
 * responsibility. Here we verify record fields, identities, references, order,
 * and the exact projection committed by the header, without changing v1 IDs.
 */
#define _POSIX_C_SOURCE 200809L
#include "elpis_semantic/segment.h"
#include "elpis_semantic/hacf_mapping.h"
#include "builder_internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <stdint.h>

static int digest_equal(const hacf_digest *a, const hacf_digest *b) {
    return memcmp(a->bytes, b->bytes, HACF_DIGEST_BYTES) == 0;
}

static int add_record_bytes(size_t *total, uint32_t count, size_t record_size) {
    if (count > (SIZE_MAX - *total) / record_size) return SEMANTIC_E_INVAL;
    *total += (size_t)count * record_size;
    /* No allocation or pointer subtraction may exceed the addressable range. */
    return *total > PTRDIFF_MAX ? SEMANTIC_E_INVAL : SEMANTIC_OK;
}

/* Validate the same structural references required by the production builder.
 * The arrays are already in writer order; do not silently sort or deduplicate. */
static int validate_references(const semantic_hypergraph_builder *b) {
    for (uint32_t i = 0; i < b->assertion_count; ++i) {
        const elpis_semantic_assertion_v1 *a = &b->assertions[i];
        if (a->asserted_object_kind == SEMANTIC_OBJECT_KIND_NODE) {
            if (!semantic_builder_has_node(b, &a->asserted_object_digest))
                return SEMANTIC_E_INVAL;
        } else if (!semantic_builder_has_hyperedge(b, &a->asserted_object_digest)) {
            return SEMANTIC_E_INVAL;
        }
    }
    for (uint32_t i = 0; i < b->hyperedge_count; ++i) {
        const elpis_semantic_hyperedge_v1 *e = &b->hyperedges[i];
        for (uint32_t j = 0; j < e->participant_count; ++j) {
            if (!semantic_builder_has_node(b, &e->participants[j].node_identity))
                return SEMANTIC_E_INVAL;
        }
    }
    for (uint32_t i = 0; i < b->incidence_count; ++i) {
        const elpis_semantic_incidence_v1 *inc = &b->incidences[i];
        if (!semantic_builder_has_node(b, &inc->node_digest) ||
            !semantic_builder_has_hyperedge(b, &inc->hyperedge_digest))
            return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int semantic_segment_read(const char *path,
                           semantic_segment_record *segment_out,
                           hacf_digest *segment_digest_out) {
    if (!path || !segment_out) return SEMANTIC_E_INVAL;
    FILE *f = fopen(path, "rb");
    if (!f) return SEMANTIC_E_IO;

    int rc = SEMANTIC_E_IO;
    semantic_segment_record candidate;
    semantic_hypergraph_builder records = {0};
    hacf_graph_op *ops = NULL;
    hacf_digest computed, delta, next;
    uint32_t op_count = 0;
    if (fread(&candidate, sizeof(candidate), 1, f) != 1) goto done;
    rc = SEMANTIC_E_INVAL;
    if (candidate.abi_version != SEMANTIC_SEGMENT_ABI_VERSION) goto done;
    const uint8_t zero[sizeof(candidate.reserved)] = {0};
    rc = SEMANTIC_E_RESERVATION;
    if (memcmp(candidate.reserved, zero, sizeof(zero)) != 0) goto done;
    rc = semantic_segment_identity(&candidate, &computed);
    if (rc != SEMANTIC_OK) goto done;
    rc = SEMANTIC_E_DIGEST;
    if (!digest_equal(&computed, &candidate.segment_identity) ||
        !digest_equal(&computed, &candidate.hacf_package_digest)) goto done;

    size_t expected = sizeof(candidate);
    rc = SEMANTIC_E_INVAL;
    if (add_record_bytes(&expected, candidate.node_count, sizeof(*records.nodes)) ||
        add_record_bytes(&expected, candidate.assertion_count, sizeof(*records.assertions)) ||
        add_record_bytes(&expected, candidate.hyperedge_count, sizeof(*records.hyperedges)) ||
        add_record_bytes(&expected, candidate.incidence_count, sizeof(*records.incidences)))
        goto done;
    /* Reject inconsistent regular-file lengths before allocating from counts.
     * Streams still require complete record reads and a final EOF check. */
    struct stat st;
    rc = SEMANTIC_E_IO;
    if (fstat(fileno(f), &st) != 0) goto done;
    if (S_ISREG(st.st_mode)) {
        if (st.st_size < 0 || (uintmax_t)st.st_size < expected) goto done;
        rc = SEMANTIC_E_INVAL;
        if ((uintmax_t)st.st_size != expected) goto done;
    }

    /* The writer emits these four arrays, in this order, as full native structs.
     * Each validator runs before identity hashing (notably participant bounds). */
#define READ_RECORDS(member, count_field, prefix, identity_field) do { \
    records.count_field = candidate.count_field; \
    if (records.count_field) { \
        records.member = malloc((size_t)records.count_field * sizeof(*records.member)); \
        rc = SEMANTIC_E_NOMEM; \
        if (!records.member) goto done; \
    } \
    for (uint32_t i = 0; i < records.count_field; ++i) { \
        rc = SEMANTIC_E_IO; \
        if (fread(&records.member[i], sizeof(*records.member), 1, f) != 1) goto done; \
        rc = prefix##_validate(&records.member[i]); \
        if (rc != SEMANTIC_OK) goto done; \
        hacf_digest identity; \
        rc = prefix##_identity(&records.member[i], &identity); \
        if (rc != SEMANTIC_OK) goto done; \
        rc = SEMANTIC_E_DIGEST; \
        if (!digest_equal(&identity, &records.member[i].identity_field)) goto done; \
        rc = SEMANTIC_E_INVAL; \
        if (i && prefix##_cmp(&records.member[i - 1], &records.member[i]) >= 0) goto done; \
    } \
} while (0)
    READ_RECORDS(nodes, node_count, elpis_semantic_node, node_identity);
    READ_RECORDS(assertions, assertion_count, elpis_semantic_assertion, assertion_identity);
    READ_RECORDS(hyperedges, hyperedge_count, elpis_semantic_hyperedge, hyperedge_identity);
    READ_RECORDS(incidences, incidence_count, elpis_semantic_incidence, incidence_identity);
#undef READ_RECORDS

    int trailing = fgetc(f);
    rc = SEMANTIC_E_IO;
    if (ferror(f)) goto done;
    rc = SEMANTIC_E_INVAL;
    if (trailing != EOF) goto done;
    rc = validate_references(&records);
    if (rc != SEMANTIC_OK) goto done;
    rc = semantic_map_to_hacf_ops(&records, &ops, &op_count);
    if (rc != SEMANTIC_OK) goto done;
    rc = SEMANTIC_E_DIGEST;
    if (op_count != candidate.hacf_op_count) goto done;
    rc = semantic_compute_hacf_delta(&candidate.prior_snapshot_digest, ops,
                                     op_count, &delta, &next);
    if (rc != SEMANTIC_OK) goto done;
    rc = SEMANTIC_E_DIGEST;
    if (!digest_equal(&delta, &candidate.hacf_delta_digest) ||
        !digest_equal(&next, &candidate.hacf_next_snapshot)) goto done;
    rc = SEMANTIC_OK;

done:
    semantic_free_hacf_ops(ops);
    free(records.nodes);
    free(records.assertions);
    free(records.hyperedges);
    free(records.incidences);
    if (fclose(f) != 0 && rc == SEMANTIC_OK) rc = SEMANTIC_E_IO;
    if (rc == SEMANTIC_OK) {
        *segment_out = candidate;
        if (segment_digest_out) *segment_digest_out = computed;
    }
    return rc;
}
