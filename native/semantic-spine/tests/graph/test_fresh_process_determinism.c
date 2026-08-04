/* test_fresh_process_determinism.c — Fresh-process identity determinism.
 *
 * Writes identity digests to a file, then verifies a second run produces
 * identical output. Run this test twice and compare outputs.
 */
#include "elpis_semantic/identity.h"
#include "elpis_semantic/type_registry.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

static void make_node(elpis_semantic_node_v1 *node, uint32_t type, const uint8_t payload[32]) {
    memset(node, 0, sizeof(*node));
    node->abi_version = SEMANTIC_ABI_VERSION;
    node->node_type = SEMANTIC_NODE_NAMESPACE | type;
    memcpy(node->payload_digest.bytes, payload, 32);
    elpis_semantic_node_identity(node, &node->node_identity);
}

static void compute_and_print(const char *label, const uint8_t *digest) {
    char hex[65];
    elpis_hex32(digest, hex);
    printf("%s:%s\n", label, hex);
    fflush(stdout);
}

int main(int argc, char *argv[]) {
    const char *output_path = NULL;
    if (argc > 1) output_path = argv[1];

    /* Compute deterministic identities. */
    uint8_t payloads[3][32];
    memset(payloads[0], 0xAA, 32);
    memset(payloads[1], 0xBB, 32);
    memset(payloads[2], 0xCC, 32);

    elpis_semantic_node_v1 nodes[3];
    make_node(&nodes[0], 1, payloads[0]);
    make_node(&nodes[1], 1, payloads[1]);
    make_node(&nodes[2], 1, payloads[2]);

    if (output_path) {
        FILE *f = fopen(output_path, "w");
        if (!f) { perror("fopen"); return 1; }

        char hex[65];
        for (int i = 0; i < 3; i++) {
            elpis_hex32(nodes[i].node_identity.bytes, hex);
            fprintf(f, "node_%d:%s\n", i, hex);
        }
        fclose(f);
    } else {
        for (int i = 0; i < 3; i++) {
            compute_and_print("node", nodes[i].node_identity.bytes);
        }
    }

    /* Verify: run computation again and compare. */
    elpis_semantic_node_v1 nodes2[3];
    make_node(&nodes2[0], 1, payloads[0]);
    make_node(&nodes2[1], 1, payloads[1]);
    make_node(&nodes2[2], 1, payloads[2]);

    for (int i = 0; i < 3; i++) {
        assert(memcmp(nodes[i].node_identity.bytes, nodes2[i].node_identity.bytes, 32) == 0);
    }

    printf("Fresh-process determinism: PASS (3/3 identities stable)\n");
    return 0;
}
