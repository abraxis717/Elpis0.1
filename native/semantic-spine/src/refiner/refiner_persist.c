/* refiner_persist.c — Persistence layer for P11 artifacts.
 *
 * P11 persistence is handled by the Python bakeoff runner.
 * This module provides stubs for the C API contract.
 */
#include "elpis_semantic/refiner_candidate.h"
#include "elpis_semantic/refiner_bakeoff_policy.h"
#include "elpis_semantic/refiner_execution.h"
#include "elpis_semantic/refiner_metrics.h"
#include "elpis_semantic/refiner_selection.h"
#include "elpis_semantic/refiner_handoff.h"

/* All persistence delegates to tools/refiner/run_p11_bakeoff.py
 * which produces JSON artifacts under reports/P11RefinementEngineBakeoff/ */
