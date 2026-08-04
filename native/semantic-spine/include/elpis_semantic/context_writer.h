/* context_writer.h — Atomic persistence for P2 context objects. */
#ifndef ELPIS_SEMANTIC_CONTEXT_WRITER_H
#define ELPIS_SEMANTIC_CONTEXT_WRITER_H

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

int elpis_write_requirement_set(const char *path,
                                 const elpis_semantic_context_requirement_set_v1 *set);
int elpis_write_deficit_policy(const char *path,
                                const elpis_semantic_context_deficit_policy_v1 *policy);
int elpis_write_deficit_report(const char *path,
                                const elpis_semantic_context_deficit_report_v1 *report);
int elpis_write_retrieval_requirement(const char *path,
                                       const elpis_semantic_retrieval_requirement_v1 *req);
int elpis_write_retrieval_bundle(const char *path,
                                  const elpis_semantic_retrieval_requirement_bundle_v1 *bundle);

#ifdef __cplusplus
}
#endif
#endif
