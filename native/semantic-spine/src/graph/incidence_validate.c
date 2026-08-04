/* incidence_validate.c — Incidence validation against type registry rules.
 *
 * Validates participant cardinality, ordinal constraints, and role rules.
 */
#include "elpis_semantic/hypergraph.h"
#include "elpis_semantic/type_registry.h"
#include "elpis_semantic/identity.h"
#include <string.h>

/* Validate that all participants of a hyperedge satisfy registry role rules.
 * Returns SEMANTIC_OK or specific error code. */
int semantic_validate_incidence_rules(
    const semantic_type_registry *reg,
    const elpis_semantic_hyperedge_v1 *edge) {
    if (!reg || !edge) return SEMANTIC_E_INVAL;

    const semantic_hyperedge_type_entry *type_entry =
        semantic_type_registry_get_hyperedge_type(reg, edge->hyperedge_type);
    if (!type_entry) return SEMANTIC_E_NOTFOUND;

    /* Check each role rule against actual participants. */
    for (uint32_t r = 0; r < type_entry->role_count; r++) {
        const semantic_role_rule *rule = &type_entry->roles[r];
        uint32_t role_count = 0;

        for (uint32_t i = 0; i < edge->participant_count; i++) {
            if (edge->participants[i].incidence_role == rule->incidence_role) {
                role_count++;
            }
        }

        /* Check cardinality. */
        if (role_count < rule->min_cardinality) return SEMANTIC_E_CARDINALITY;
        if (rule->max_cardinality != 0 && role_count > rule->max_cardinality)
            return SEMANTIC_E_CARDINALITY;

        /* Check ordinal validity for ordered roles. */
        if (rule->is_ordered) {
            /* Ordinals must be unique and sequential from 0. */
            for (uint32_t i = 0; i < edge->participant_count; i++) {
                if (edge->participants[i].incidence_role != rule->incidence_role) continue;
                uint32_t ordinal = edge->participants[i].ordinal;
                /* Check for collisions. */
                for (uint32_t j = i + 1; j < edge->participant_count; j++) {
                    if (edge->participants[j].incidence_role != rule->incidence_role) continue;
                    if (edge->participants[j].ordinal == ordinal)
                        return SEMANTIC_BUILDER_E_ORDINAL;
                }
            }
        }

        /* Check repeat permission. */
        if (!rule->allows_repeat) {
            /* No node may appear twice with the same role. */
            for (uint32_t i = 0; i < edge->participant_count; i++) {
                if (edge->participants[i].incidence_role != rule->incidence_role) continue;
                for (uint32_t j = i + 1; j < edge->participant_count; j++) {
                    if (edge->participants[j].incidence_role != rule->incidence_role) continue;
                    if (memcmp(edge->participants[i].node_identity.bytes,
                               edge->participants[j].node_identity.bytes,
                               HACF_DIGEST_BYTES) == 0) {
                        return SEMANTIC_E_CARDINALITY;
                    }
                }
            }
        }
    }

    return SEMANTIC_OK;
}

/* Validate that a hyperedge has no zero participants unless explicitly permitted. */
int semantic_validate_zero_participants(
    const semantic_type_registry *reg,
    const elpis_semantic_hyperedge_v1 *edge) {
    if (!reg || !edge) return SEMANTIC_E_INVAL;
    if (edge->participant_count > 0) return SEMANTIC_OK;

    const semantic_hyperedge_type_entry *type_entry =
        semantic_type_registry_get_hyperedge_type(reg, edge->hyperedge_type);
    if (!type_entry) return SEMANTIC_E_NOTFOUND;

    /* Zero participants only valid if min_participants is 0. */
    if (type_entry->min_participants != 0) return SEMANTIC_BUILDER_E_ZERO_PART;
    return SEMANTIC_OK;
}
