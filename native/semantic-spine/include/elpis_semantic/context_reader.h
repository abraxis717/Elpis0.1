/* context_reader.h — Read and validate P2 context objects from storage. */
#ifndef ELPIS_SEMANTIC_CONTEXT_READER_H
#define ELPIS_SEMANTIC_CONTEXT_READER_H

#include "elpis_semantic/context_requirement_set.h"
#include "elpis_semantic/context_deficit_policy.h"
#include "elpis_semantic/context_deficit_report.h"
#include "elpis_semantic/retrieval_requirement.h"
#include "elpis_semantic/retrieval_requirement_bundle.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

int elpis_read_requirement_set(const char *path,
                                elpis_semantic_context_requirement_set_v1 *out);
int elpis_read_deficit_policy(const char *path,
                               elpis_semantic_context_deficit_policy_v1 *out);
int elpis_read_deficit_report(const char *path,
                               elpis_semantic_context_deficit_report_v1 *out);
int elpis_read_retrieval_requirement(const char *path,
                                      elpis_semantic_retrieval_requirement_v1 *out);
int elpis_read_retrieval_bundle(const char *path,
                                 elpis_semantic_retrieval_requirement_bundle_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
