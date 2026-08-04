/* structural_spine_persist.c — Persistence for structural spine v1. */
#include "elpis_semantic/structural_spine_policy.h"
#include "elpis_semantic/structural_spine_request.h"
#include "elpis_semantic/structural_spine_result.h"
#include "elpis_semantic/structural_spine_closure.h"
#include "elpis_semantic/structural_observation.h"
#include "elpis/cascade.h"
#include <stdio.h>
#include <string.h>
#include <stdint.h>

int elpis_spine_policy_persist(
    const elpis_semantic_structural_spine_policy_v1 *policy,
    const char *path) {
    if (!policy || !path) return SEMANTIC_E_INVAL;
    FILE *fp = fopen(path, "wb");
    if (!fp) return SEMANTIC_E_IO;
    size_t written = fwrite(policy, sizeof(*policy), 1, fp);
    fclose(fp);
    return (written == 1) ? SEMANTIC_OK : SEMANTIC_E_IO;
}

int elpis_spine_policy_load(
    elpis_semantic_structural_spine_policy_v1 *policy,
    const char *path) {
    if (!policy || !path) return SEMANTIC_E_INVAL;
    FILE *fp = fopen(path, "rb");
    if (!fp) return SEMANTIC_E_IO;
    size_t rd = fread(policy, sizeof(*policy), 1, fp);
    fclose(fp);
    if (rd != 1) return SEMANTIC_E_IO;
    return elpis_spine_policy_validate(policy);
}

int elpis_spine_request_persist(
    const elpis_semantic_structural_spine_request_v1 *req,
    const char *path) {
    if (!req || !path) return SEMANTIC_E_INVAL;
    FILE *fp = fopen(path, "wb");
    if (!fp) return SEMANTIC_E_IO;
    size_t written = fwrite(req, sizeof(*req), 1, fp);
    fclose(fp);
    return (written == 1) ? SEMANTIC_OK : SEMANTIC_E_IO;
}

int elpis_spine_request_load(
    elpis_semantic_structural_spine_request_v1 *req,
    const char *path) {
    if (!req || !path) return SEMANTIC_E_INVAL;
    FILE *fp = fopen(path, "rb");
    if (!fp) return SEMANTIC_E_IO;
    size_t rd = fread(req, sizeof(*req), 1, fp);
    fclose(fp);
    if (rd != 1) return SEMANTIC_E_IO;
    return elpis_spine_request_validate(req);
}

int elpis_spine_result_persist(
    const elpis_semantic_structural_spine_result_v1 *result,
    const char *path) {
    if (!result || !path) return SEMANTIC_E_INVAL;
    FILE *fp = fopen(path, "wb");
    if (!fp) return SEMANTIC_E_IO;
    size_t written = fwrite(result, sizeof(*result), 1, fp);
    fclose(fp);
    return (written == 1) ? SEMANTIC_OK : SEMANTIC_E_IO;
}

int elpis_spine_result_load(
    elpis_semantic_structural_spine_result_v1 *result,
    const char *path) {
    if (!result || !path) return SEMANTIC_E_INVAL;
    FILE *fp = fopen(path, "rb");
    if (!fp) return SEMANTIC_E_IO;
    size_t rd = fread(result, sizeof(*result), 1, fp);
    fclose(fp);
    if (rd != 1) return SEMANTIC_E_IO;
    return elpis_spine_result_validate(result);
}

int elpis_spine_closure_persist(
    const elpis_semantic_structural_spine_closure_v1 *closure,
    const char *path) {
    if (!closure || !path) return SEMANTIC_E_INVAL;
    FILE *fp = fopen(path, "wb");
    if (!fp) return SEMANTIC_E_IO;
    size_t written = fwrite(closure, sizeof(*closure), 1, fp);
    fclose(fp);
    return (written == 1) ? SEMANTIC_OK : SEMANTIC_E_IO;
}

int elpis_spine_closure_load(
    elpis_semantic_structural_spine_closure_v1 *closure,
    const char *path) {
    if (!closure || !path) return SEMANTIC_E_INVAL;
    FILE *fp = fopen(path, "rb");
    if (!fp) return SEMANTIC_E_IO;
    size_t rd = fread(closure, sizeof(*closure), 1, fp);
    fclose(fp);
    if (rd != 1) return SEMANTIC_E_IO;
    return elpis_spine_closure_validate(closure);
}

int elpis_spine_observation_persist(
    const elpis_semantic_structural_observation_v1 *obs,
    const char *path) {
    if (!obs || !path) return SEMANTIC_E_INVAL;
    FILE *fp = fopen(path, "wb");
    if (!fp) return SEMANTIC_E_IO;
    size_t written = fwrite(obs, sizeof(*obs), 1, fp);
    fclose(fp);
    return (written == 1) ? SEMANTIC_OK : SEMANTIC_E_IO;
}

int elpis_spine_observation_load(
    elpis_semantic_structural_observation_v1 *obs,
    const char *path) {
    if (!obs || !path) return SEMANTIC_E_INVAL;
    FILE *fp = fopen(path, "rb");
    if (!fp) return SEMANTIC_E_IO;
    size_t rd = fread(obs, sizeof(*obs), 1, fp);
    fclose(fp);
    if (rd != 1) return SEMANTIC_E_IO;
    return elpis_spine_observation_validate(obs);
}
