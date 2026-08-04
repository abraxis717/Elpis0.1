#include "elpis_semantic/trm_native_contract.h"
#include "elpis_semantic/trm_alignment_policy.h"
#include "elpis_semantic/trm_alignment_fixture.h"
#include "elpis_semantic/trm_alignment_lane.h"
#include "elpis_semantic/trm_alignment_metrics.h"
#include "elpis_semantic/trm_alignment_report.h"
#include "elpis_semantic/trm_alignment_handoff.h"
#include <stdio.h>
#include <string.h>

/* Persistence: write C structures to JSON for the evidence package.
 * Primary JSON generation happens in Python; C provides serialization helpers. */

int trm_persist_native_contract(const char *path, const trm_native_contract_t *contract) {
    FILE *f = fopen(path, "w");
    if (!f) return 0;
    fprintf(f, "{\n");
    fprintf(f, "  \"abi_version\": %u,\n", contract->abi_version);
    fprintf(f, "  \"native_input_rank\": %u,\n", contract->native_input_rank);
    fprintf(f, "  \"native_input_dtype\": \"%s\",\n", contract->native_input_dtype);
    fprintf(f, "  \"native_output_rank\": %u,\n", contract->native_output_rank);
    fprintf(f, "  \"native_output_dtype\": \"%s\",\n", contract->native_output_dtype);
    fprintf(f, "  \"contract_confidence\": \"%s\",\n", contract->contract_confidence);
    fprintf(f, "  \"contract_digest\": \"%s\"\n", contract->contract_digest);
    fprintf(f, "}\n");
    fclose(f);
    return 1;
}

int trm_persist_report(const char *path, const trm_alignment_report_t *report) {
    FILE *f = fopen(path, "w");
    if (!f) return 0;
    fprintf(f, "{\n");
    fprintf(f, "  \"abi_version\": %u,\n", report->abi_version);
    fprintf(f, "  \"primary_diagnosis\": \"%s\",\n", trm_diagnosis_verdict_string(report->primary_diagnosis));
    fprintf(f, "  \"remediation\": \"%s\",\n", trm_remediation_string(report->remediation));
    fprintf(f, "  \"diagnosis_digest\": \"%s\"\n", report->diagnosis_digest);
    fprintf(f, "}\n");
    fclose(f);
    return 1;
}

int trm_persist_handoff(const char *path, const trm_alignment_handoff_t *handoff) {
    FILE *f = fopen(path, "w");
    if (!f) return 0;
    fprintf(f, "{\n");
    fprintf(f, "  \"abi_version\": %u,\n", handoff->abi_version);
    fprintf(f, "  \"handoff_kind\": \"FROZEN_TRM_ALIGNMENT_DIAGNOSIS\",\n");
    fprintf(f, "  \"p10r_statement\": \"%s\",\n", handoff->p10r_statement);
    fprintf(f, "  \"handoff_digest\": \"%s\"\n", handoff->handoff_digest);
    fprintf(f, "}\n");
    fclose(f);
    return 1;
}
