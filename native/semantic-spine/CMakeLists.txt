cmake_minimum_required(VERSION 3.20)
project(elpis_semantic_fabric LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# HACF root must be supplied externally — never hardcode /mnt/primesauce or /home/joe.
set(ELPIS_HACF_ROOT "" CACHE PATH "Path to HashAdressedCascadeFabric source root")
if(NOT ELPIS_HACF_ROOT)
  message(FATAL_ERROR "ELPIS_HACF_ROOT is required. Pass -DELPIS_HACF_ROOT=<path>")
endif()

option(ELPIS_ENABLE_ASAN "Enable AddressSanitizer" OFF)
option(ELPIS_ENABLE_UBSAN "Enable UndefinedBehaviorSanitizer" OFF)
option(ELPIS_ENABLE_TSAN "Enable ThreadSanitizer" OFF)

if(ELPIS_ENABLE_TSAN AND (ELPIS_ENABLE_ASAN OR ELPIS_ENABLE_UBSAN))
  message(FATAL_ERROR
    "ThreadSanitizer cannot be combined with AddressSanitizer or "
    "UndefinedBehaviorSanitizer in the same build.")
endif()

set(SF_SANITIZER_COMPILE_OPTIONS)
set(SF_SANITIZER_LINK_OPTIONS)

if(ELPIS_ENABLE_ASAN OR ELPIS_ENABLE_UBSAN OR ELPIS_ENABLE_TSAN)
  if(NOT (
      CMAKE_C_COMPILER_ID MATCHES "GNU|Clang"))
    message(FATAL_ERROR "Requested sanitizers require GCC-compatible compilers.")
  endif()

  list(APPEND SF_SANITIZER_COMPILE_OPTIONS
    -g
    -fno-omit-frame-pointer
    -fno-optimize-sibling-calls)

  if(ELPIS_ENABLE_TSAN)
    list(APPEND SF_SANITIZER_COMPILE_OPTIONS -fsanitize=thread)
    list(APPEND SF_SANITIZER_LINK_OPTIONS -fsanitize=thread)
  else()
    if(ELPIS_ENABLE_ASAN AND ELPIS_ENABLE_UBSAN)
      list(APPEND SF_SANITIZER_COMPILE_OPTIONS -fsanitize=address,undefined)
      list(APPEND SF_SANITIZER_LINK_OPTIONS -fsanitize=address,undefined)
    elseif(ELPIS_ENABLE_ASAN)
      list(APPEND SF_SANITIZER_COMPILE_OPTIONS -fsanitize=address)
      list(APPEND SF_SANITIZER_LINK_OPTIONS -fsanitize=address)
    elseif(ELPIS_ENABLE_UBSAN)
      list(APPEND SF_SANITIZER_COMPILE_OPTIONS -fsanitize=undefined)
      list(APPEND SF_SANITIZER_LINK_OPTIONS -fsanitize=undefined)
    endif()
  endif()

  add_compile_options(${SF_SANITIZER_COMPILE_OPTIONS})
  add_link_options(${SF_SANITIZER_LINK_OPTIONS})
endif()

enable_testing()

find_package(Threads REQUIRED)
find_package(OpenSSL REQUIRED)

function(sf_warnings target)
  if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
  endif()
endfunction()

# ---------------------------------------------------------------------------
# Semantic Fabric static library
# ---------------------------------------------------------------------------
add_library(elpis_semantic STATIC
  src/graph/identity.c
  src/graph/type_registry.c
  src/graph/hypergraph_builder.c
  src/graph/incidence_validate.c
  src/graph/hacf_mapping.c
  src/graph/segment_writer.c
  src/graph/segment_reader.c
  src/graph/snapshot_manifest.c
  src/graph/snapshot_view.c
  src/graph/query_overlay.c
  src/embedding/embedding_profile.c
  src/embedding/embedding_vector.c
  src/embedding/embedding_ref.c
  src/embedding/embedding_collection.c
  src/embedding/embedding_metric.c
  src/embedding/embedding_neighborhood.c
  src/embedding/embedding_writer.c
  src/embedding/embedding_reader.c
  src/embedding/embedding_view.c
  src/embedding/embedding_coverage.c
  # P2 — Context deficit controller
  src/context/context_requirement.c
  src/context/context_requirement_set.c
  src/context/context_deficit_policy.c
  src/context/context_deficit.c
  src/context/context_deficit_report.c
  src/context/retrieval_requirement.c
  src/context/retrieval_requirement_bundle.c
  src/context/context_writer.c
  src/context/context_reader.c
  # P3 — R3 retrieval bridge (C sources)
  src/retrieval/retrieval_materialization.c
  src/retrieval/retrieval_item_attachment.c
  src/retrieval/retrieval_expansion.c
  # P3 — R3 retrieval bridge (C++ sources — link against R3 C++ ABI)
  src/retrieval/r3_epoch.cpp
  src/retrieval/r3_query_plan.cpp
  src/retrieval/r3_bridge.cpp
  src/retrieval/retrieval_bundle_verify.cpp
  src/retrieval/retrieval_ingest.cpp
  # P4 — Evidence typing and admission
  src/evidence/evidence_typer_profile.c
  src/evidence/evidence_span.c
  src/evidence/evidence_claim_candidate.c
  src/evidence/evidence_relation_candidate.c
  src/evidence/evidence_typing_bundle.c
  src/evidence/evidence_candidate_validate.c
  src/evidence/evidence_admission_policy.c
  src/evidence/evidence_adjudicator.c
  src/evidence/evidence_admission_receipt.c
  src/evidence/evidence_semantic_builder.c
  src/evidence/evidence_admission_segment.c
  src/evidence/evidence_admission_layer.c
  src/evidence/typed_evidence_view.c
  src/evidence/evidence_writer.c
  src/evidence/evidence_reader.c
  # P5 — Context re-evaluation and bounded semantic view
  src/context/context_rebind.c
  src/context/context_iteration_policy.c
  src/context/context_iteration_state.c
  src/context/context_reevaluation.c
  src/context/context_progress.c
  src/view/bounded_view_policy.c
  src/view/bounded_view_seed.c
  src/view/bounded_view_candidate.c
  src/view/bounded_view_select.c
  src/view/bounded_view_closure.c
  src/view/bounded_semantic_view.c
  src/view/downstream_handoff.c
  src/view/p5_writer.c
  src/view/p5_writer.c
  src/view/p5_reader.c
  # P6 — Semantic topology compiler
  src/topology/topology_policy.c
  src/topology/topology_registry.c
  src/topology/topology_input.c
  src/topology/topology_graph.c
  src/topology/topology_anchor.c
  src/topology/topology_distance.c
  src/topology/topology_constellation.c
  src/topology/topology_roles.c
  src/topology/topology_conflict.c
  src/topology/topology_bridge.c
  src/topology/topology_metric.c
  src/topology/topology_address.c
  src/topology/topology_constraint.c
  src/topology/topology_compile.c
  src/topology/topology_persist.c
  # P7 — Grid81 structural compiler
  src/grid81/grid81_policy.c
  src/grid81/grid81_codebook.c
  src/grid81/grid81_input_validate.c
  src/grid81/grid81_capsule.c
  src/grid81/grid81_place.c
  src/grid81/grid81_sudoku_template.c
  src/grid81/grid81_cell.c
  src/grid81/grid81_constraint_projection.c
  src/grid81/grid81_packet.c
  src/grid81/grid81_compile_receipt.c
  src/grid81/grid81_handoff.c
  src/grid81/grid81_persist.c
  # P8 — TRM adapter, mutability policy, and output guard
  src/trm/trm_persist.c
  src/trm/trm_abi.c
  src/trm/trm_adapter_policy.c
  src/trm/trm_input_validate.c
  src/trm/trm_mutability.c
  src/trm/trm_input_tensor.c
  src/trm/trm_adapter_packet.c
  src/trm/trm_candidate_frame.c
  src/trm/trm_candidate_decode.c
  src/trm/trm_output_guard.c
  src/trm/trm_guarded_result.c
  src/trm/trm_execution_handoff.c
  # P13 — Structural spine integrated ABI
  src/structural_spine/structural_spine_policy.c
  src/structural_spine/structural_spine_request.c
  src/structural_spine/structural_spine_execute.c
  src/structural_spine/structural_spine_trace.c
  src/structural_spine/structural_observation.c
  src/structural_spine/structural_spine_result.c
  src/structural_spine/structural_spine_closure.c
  src/structural_spine/structural_spine_persist.c)

target_include_directories(elpis_semantic PUBLIC include)
target_include_directories(elpis_semantic SYSTEM PUBLIC "${ELPIS_HACF_ROOT}/include")
target_link_libraries(elpis_semantic PUBLIC elpis_graph elpis_hash elpis_hybrid elpis_vector elpis_corpus elpis_embedding elpis_fms Threads::Threads OpenSSL::SSL OpenSSL::Crypto)
sf_warnings(elpis_semantic)

# Add HACF targets from the external project
add_subdirectory("${ELPIS_HACF_ROOT}" "${CMAKE_BINARY_DIR}/hacf" EXCLUDE_FROM_ALL)

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
add_executable(test_semantic_identity tests/graph/test_identity.c)
target_link_libraries(test_semantic_identity PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_semantic_identity)
add_test(NAME semantic_identity COMMAND test_semantic_identity)

add_executable(test_type_registry tests/graph/test_type_registry.c)
target_link_libraries(test_type_registry PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_type_registry)
add_test(NAME type_registry COMMAND test_type_registry)

add_executable(test_hypergraph_builder tests/graph/test_hypergraph_builder.c)
target_link_libraries(test_hypergraph_builder PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_hypergraph_builder)
add_test(NAME hypergraph_builder COMMAND test_hypergraph_builder)

add_executable(test_hacf_mapping tests/graph/test_hacf_mapping.c)
target_link_libraries(test_hacf_mapping PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_hacf_mapping)
add_test(NAME hacf_mapping COMMAND test_hacf_mapping)

add_executable(test_segment_snapshot tests/graph/test_segment_snapshot.c)
target_link_libraries(test_segment_snapshot PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_segment_snapshot)
add_test(NAME segment_snapshot COMMAND test_segment_snapshot)

add_executable(test_snapshot_view tests/graph/test_snapshot_view.c)
target_link_libraries(test_snapshot_view PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_snapshot_view)
add_test(NAME snapshot_view COMMAND test_snapshot_view)

add_executable(test_query_overlay tests/graph/test_query_overlay.c)
target_link_libraries(test_query_overlay PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_query_overlay)
add_test(NAME query_overlay COMMAND test_query_overlay)

add_executable(test_fresh_process_determinism tests/graph/test_fresh_process_determinism.c)
target_link_libraries(test_fresh_process_determinism PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_fresh_process_determinism)
add_test(NAME fresh_process_determinism COMMAND test_fresh_process_determinism)

# ---------------------------------------------------------------------------
# P1 — Embedding tests
# ---------------------------------------------------------------------------
# Ensure -lm is available for embedding vector/metric math
find_library(M_LIB m)

add_executable(test_embedding_profile tests/embedding/test_embedding_profile.c)
target_link_libraries(test_embedding_profile PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_embedding_profile)
add_test(NAME embedding_profile COMMAND test_embedding_profile)

add_executable(test_embedding_vector tests/embedding/test_embedding_vector.c)
target_link_libraries(test_embedding_vector PRIVATE elpis_semantic elpis_hash ${M_LIB})
sf_warnings(test_embedding_vector)
add_test(NAME embedding_vector COMMAND test_embedding_vector)

add_executable(test_embedding_ref tests/embedding/test_embedding_ref.c)
target_link_libraries(test_embedding_ref PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_embedding_ref)
add_test(NAME embedding_ref COMMAND test_embedding_ref)

add_executable(test_embedding_collection tests/embedding/test_embedding_collection.c)
target_link_libraries(test_embedding_collection PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_embedding_collection)
add_test(NAME embedding_collection COMMAND test_embedding_collection)

add_executable(test_embedding_metric tests/embedding/test_embedding_metric.c)
target_link_libraries(test_embedding_metric PRIVATE elpis_semantic elpis_hash ${M_LIB})
sf_warnings(test_embedding_metric)
# Explicitly disable fast-math for metric tests
target_compile_options(test_embedding_metric PRIVATE -fno-fast-math)
add_test(NAME embedding_metric COMMAND test_embedding_metric)

add_executable(test_embedding_neighborhood tests/embedding/test_embedding_neighborhood.c)
target_link_libraries(test_embedding_neighborhood PRIVATE elpis_semantic elpis_hash ${M_LIB})
sf_warnings(test_embedding_neighborhood)
add_test(NAME embedding_neighborhood COMMAND test_embedding_neighborhood)

add_executable(test_embedding_storage tests/embedding/test_embedding_storage.c)
target_link_libraries(test_embedding_storage PRIVATE elpis_semantic elpis_hash ${M_LIB})
sf_warnings(test_embedding_storage)
add_test(NAME embedding_storage COMMAND test_embedding_storage)

add_executable(test_embedding_boundary tests/embedding/test_embedding_boundary.c)
target_link_libraries(test_embedding_boundary PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_embedding_boundary)
add_test(NAME embedding_boundary COMMAND test_embedding_boundary)

# ---------------------------------------------------------------------------
# P2 — Context deficit controller tests
# ---------------------------------------------------------------------------

add_executable(test_context_requirement tests/context/test_context_requirement.c)
target_link_libraries(test_context_requirement PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_context_requirement)
add_test(NAME context_requirement COMMAND test_context_requirement)

add_executable(test_context_requirement_set tests/context/test_context_requirement_set.c)
target_link_libraries(test_context_requirement_set PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_context_requirement_set)
add_test(NAME context_requirement_set COMMAND test_context_requirement_set)

add_executable(test_context_deficit_policy tests/context/test_context_deficit_policy.c)
target_link_libraries(test_context_deficit_policy PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_context_deficit_policy)
add_test(NAME context_deficit_policy COMMAND test_context_deficit_policy)

add_executable(test_context_evaluator tests/context/test_context_evaluator.c)
target_link_libraries(test_context_evaluator PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_context_evaluator)
add_test(NAME context_evaluator COMMAND test_context_evaluator)

add_executable(test_context_persistence tests/context/test_context_persistence.c)
target_link_libraries(test_context_persistence PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_context_persistence)
add_test(NAME context_persistence COMMAND test_context_persistence)

add_executable(test_retrieval_requirement tests/context/test_retrieval_requirement.c)
target_link_libraries(test_retrieval_requirement PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_retrieval_requirement)
add_test(NAME retrieval_requirement COMMAND test_retrieval_requirement)

add_executable(test_retrieval_requirement_bundle tests/context/test_retrieval_bundle.c)
target_link_libraries(test_retrieval_requirement_bundle PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_retrieval_requirement_bundle)
add_test(NAME retrieval_requirement_bundle COMMAND test_retrieval_requirement_bundle)

# Persistence test xfailed — API surface needs alignment
# add_executable(test_context_persistence tests/context/test_context_persistence.c)

add_executable(test_context_boundaries tests/context/test_context_boundaries.c)
target_link_libraries(test_context_boundaries PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_context_boundaries)
add_test(NAME context_boundaries COMMAND test_context_boundaries)

# ---------------------------------------------------------------------------
# P4 — Evidence typing and admission tests
# ---------------------------------------------------------------------------

add_executable(test_typer_profile tests/evidence/test_typer_profile.c)
target_link_libraries(test_typer_profile PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_typer_profile)
add_test(NAME typer_profile COMMAND test_typer_profile)

add_executable(test_evidence_span tests/evidence/test_evidence_span.c)
target_link_libraries(test_evidence_span PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_evidence_span)
add_test(NAME evidence_span COMMAND test_evidence_span)

add_executable(test_claim_candidate tests/evidence/test_claim_candidate.c)
target_link_libraries(test_claim_candidate PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_claim_candidate)
add_test(NAME claim_candidate COMMAND test_claim_candidate)

add_executable(test_relation_candidate tests/evidence/test_relation_candidate.c)
target_link_libraries(test_relation_candidate PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_relation_candidate)
add_test(NAME relation_candidate COMMAND test_relation_candidate)

add_executable(test_typing_bundle tests/evidence/test_typing_bundle.c)
target_link_libraries(test_typing_bundle PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_typing_bundle)
add_test(NAME typing_bundle COMMAND test_typing_bundle)

add_executable(test_admission_policy tests/evidence/test_admission_policy.c)
target_link_libraries(test_admission_policy PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_admission_policy)
add_test(NAME admission_policy COMMAND test_admission_policy)

add_executable(test_adjudicator tests/evidence/test_adjudicator.c)
target_link_libraries(test_adjudicator PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_adjudicator)
add_test(NAME adjudicator COMMAND test_adjudicator)

add_executable(test_semantic_builder tests/evidence/test_semantic_builder.c)
target_link_libraries(test_semantic_builder PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_semantic_builder)
add_test(NAME semantic_builder COMMAND test_semantic_builder)

add_executable(test_admission_segment tests/evidence/test_admission_segment.c)
target_link_libraries(test_admission_segment PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_admission_segment)
add_test(NAME admission_segment COMMAND test_admission_segment)

add_executable(test_typed_evidence_view tests/evidence/test_typed_evidence_view.c)
target_link_libraries(test_typed_evidence_view PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_typed_evidence_view)
add_test(NAME typed_evidence_view COMMAND test_typed_evidence_view)

add_executable(test_evidence_persistence tests/evidence/test_evidence_persistence.c)
target_link_libraries(test_evidence_persistence PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_evidence_persistence)
add_test(NAME evidence_persistence COMMAND test_evidence_persistence)

add_executable(test_evidence_determinism tests/evidence/test_evidence_determinism.c)
target_link_libraries(test_evidence_determinism PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_evidence_determinism)
add_test(NAME evidence_determinism COMMAND test_evidence_determinism)

add_executable(test_evidence_boundaries tests/evidence/test_evidence_boundaries.c)
target_link_libraries(test_evidence_boundaries PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_evidence_boundaries)
add_test(NAME evidence_boundaries COMMAND evidence_boundaries)

# ---------------------------------------------------------------------------
# P5 — Context re-evaluation and bounded semantic view tests
# ---------------------------------------------------------------------------

add_executable(test_context_rebind tests/p5/test_context_rebind.c)
target_link_libraries(test_context_rebind PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_context_rebind)
add_test(NAME context_rebind COMMAND test_context_rebind)

add_executable(test_iteration_policy tests/p5/test_iteration_policy.c)
target_link_libraries(test_iteration_policy PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_iteration_policy)
add_test(NAME iteration_policy COMMAND test_iteration_policy)

add_executable(test_iteration_state tests/p5/test_iteration_state.c)
target_link_libraries(test_iteration_state PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_iteration_state)
add_test(NAME iteration_state COMMAND test_iteration_state)

add_executable(test_context_reevaluation tests/p5/test_context_reevaluation.c)
target_link_libraries(test_context_reevaluation PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_context_reevaluation)
add_test(NAME context_reevaluation COMMAND test_context_reevaluation)

add_executable(test_context_progress tests/p5/test_context_progress.c)
target_link_libraries(test_context_progress PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_context_progress)
add_test(NAME context_progress COMMAND test_context_progress)

add_executable(test_bounded_view_policy tests/p5/test_bounded_view_policy.c)
target_link_libraries(test_bounded_view_policy PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_bounded_view_policy)
add_test(NAME bounded_view_policy COMMAND test_bounded_view_policy)

add_executable(test_seed_construction tests/p5/test_seed_construction.c)
target_link_libraries(test_seed_construction PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_seed_construction)
add_test(NAME seed_construction COMMAND test_seed_construction)

add_executable(test_candidate_enumeration tests/p5/test_candidate_enumeration.c)
target_link_libraries(test_candidate_enumeration PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_candidate_enumeration)
add_test(NAME candidate_enumeration COMMAND test_candidate_enumeration)

add_executable(test_bounded_selection tests/p5/test_bounded_selection.c)
target_link_libraries(test_bounded_selection PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_bounded_selection)
add_test(NAME bounded_selection COMMAND test_bounded_selection)

add_executable(test_conflict_closure tests/p5/test_conflict_closure.c)
target_link_libraries(test_conflict_closure PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_conflict_closure)
add_test(NAME conflict_closure COMMAND test_conflict_closure)

add_executable(test_provenance_closure tests/p5/test_provenance_closure.c)
target_link_libraries(test_provenance_closure PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_provenance_closure)
add_test(NAME provenance_closure COMMAND test_provenance_closure)

add_executable(test_metric_nonauthority tests/p5/test_metric_nonauthority.c)
target_link_libraries(test_metric_nonauthority PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_metric_nonauthority)
add_test(NAME metric_nonauthority COMMAND test_metric_nonauthority)

add_executable(test_bounded_view_identity tests/p5/test_bounded_view_identity.c)
target_link_libraries(test_bounded_view_identity PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_bounded_view_identity)
add_test(NAME bounded_view_identity COMMAND test_bounded_view_identity)

add_executable(test_downstream_handoff tests/p5/test_downstream_handoff.c)
target_link_libraries(test_downstream_handoff PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_downstream_handoff)
add_test(NAME downstream_handoff COMMAND test_downstream_handoff)

add_executable(test_p5_persistence tests/p5/test_p5_persistence.c)
target_link_libraries(test_p5_persistence PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_p5_persistence)
add_test(NAME p5_persistence COMMAND test_p5_persistence)

add_executable(test_p5_determinism tests/p5/test_p5_determinism.c)
target_link_libraries(test_p5_determinism PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_p5_determinism)
add_test(NAME p5_determinism COMMAND test_p5_determinism)

add_executable(test_p5_boundaries tests/p5/test_p5_boundaries.c)
target_link_libraries(test_p5_boundaries PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_p5_boundaries)
add_test(NAME p5_boundaries COMMAND test_p5_boundaries)

# ---------------------------------------------------------------------------
# P6 — Semantic topology compiler tests
# ---------------------------------------------------------------------------

add_executable(test_topology_compile tests/topology/test_topology_compile.c)
target_link_libraries(test_topology_compile PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_topology_compile)
add_test(NAME topology_compile COMMAND test_topology_compile)

# ---------------------------------------------------------------------------
# P7 — Grid81 structural compiler tests
# ---------------------------------------------------------------------------

add_executable(test_grid81_compiler tests/grid81/test_grid81_compiler.c)
target_link_libraries(test_grid81_compiler PRIVATE elpis_semantic elpis_hash)
sf_warnings(test_grid81_compiler)
add_test(NAME grid81_compiler COMMAND test_grid81_compiler)

# ---------------------------------------------------------------------------
# P8 — TRM adapter and mutability policy tests
# ---------------------------------------------------------------------------

add_executable(test_trm_adapter tests/trm/test_trm_adapter.c)
target_link_libraries(test_trm_adapter PRIVATE elpis_semantic elpis_hash ${M_LIB})
sf_warnings(test_trm_adapter)
# Disable fast-math for tensor float comparison tests
target_compile_options(test_trm_adapter PRIVATE -fno-fast-math)
add_test(NAME trm_adapter COMMAND test_trm_adapter)

# ---------------------------------------------------------------------------
# P10 — Guarded refinement efficacy and structural delta (C sources)
# ---------------------------------------------------------------------------

# P10 C sources compiled into the semantic fabric static library
# (declared via OBJECT library to avoid re-linking issues)
add_library(elpis_p10_eval STATIC
  src/trm_eval/sudoku_reference_solver.c
  src/trm_eval/trm_efficacy_policy.c
  src/trm_eval/trm_structural_delta.c
  src/trm_eval/trm_step_metrics.c
  src/trm_eval/trm_fixture_metrics.c
  src/trm_eval/trm_efficacy_report.c
  src/trm_eval/trm_delta_handoff.c
  src/trm_eval/trm_eval_persist.c)
target_include_directories(elpis_p10_eval PUBLIC include)
target_include_directories(elpis_p10_eval SYSTEM PUBLIC "${ELPIS_HACF_ROOT}/include")
target_link_libraries(elpis_p10_eval PUBLIC elpis_hash)
sf_warnings(elpis_p10_eval)

# ---------------------------------------------------------------------------
# P10 — Tests
# ---------------------------------------------------------------------------

add_executable(test_sudoku_reference_solver tests/trm_eval/test_sudoku_reference_solver.c)
target_link_libraries(test_sudoku_reference_solver PRIVATE elpis_semantic elpis_p10_eval elpis_hash)
sf_warnings(test_sudoku_reference_solver)
add_test(NAME sudoku_reference_solver COMMAND test_sudoku_reference_solver)

add_executable(test_structural_delta tests/trm_eval/test_structural_delta.c)
target_link_libraries(test_structural_delta PRIVATE elpis_semantic elpis_p10_eval elpis_hash)
sf_warnings(test_structural_delta)
add_test(NAME structural_delta COMMAND test_structural_delta)

add_executable(test_fixture_metrics tests/trm_eval/test_fixture_metrics.c)
target_link_libraries(test_fixture_metrics PRIVATE elpis_semantic elpis_p10_eval elpis_hash)
sf_warnings(test_fixture_metrics)
add_test(NAME fixture_metrics COMMAND test_fixture_metrics)

add_executable(test_efficacy_adjudication tests/trm_eval/test_efficacy_adjudication.c)
target_link_libraries(test_efficacy_adjudication PRIVATE elpis_semantic elpis_p10_eval elpis_hash)
sf_warnings(test_efficacy_adjudication)
add_test(NAME efficacy_adjudication COMMAND test_efficacy_adjudication)

# P10R — TRM Placement and ABI Alignment Review
add_library(elpis_p10r STATIC
  src/trm_align/trm_native_contract.c
  src/trm_align/trm_native_audit.c
  src/trm_align/trm_alignment_fixture.c
  src/trm_align/trm_fixture_generate.c
  src/trm_align/trm_alignment_policy.c
  src/trm_align/trm_alignment_lane.c
  src/trm_align/trm_representation_lanes.c
  src/trm_align/trm_placement_lanes.c
  src/trm_align/trm_decoder_analysis.c
  src/trm_align/trm_guard_granularity_analysis.c
  src/trm_align/trm_recursive_shift_analysis.c
  src/trm_align/trm_alignment_metrics.c
  src/trm_align/trm_alignment_report.c
  src/trm_align/trm_alignment_handoff.c
  src/trm_align/trm_alignment_persist.c)
target_include_directories(elpis_p10r PUBLIC include)
target_link_libraries(elpis_p10r PUBLIC elpis_semantic elpis_p10_eval elpis_hash)
sf_warnings(elpis_p10r)

# P10R tests
add_executable(test_p10r_native_contract tests/trm_align/test_p10r_native_contract.c)
target_link_libraries(test_p10r_native_contract PRIVATE elpis_p10r elpis_hash OpenSSL::Crypto)
sf_warnings(test_p10r_native_contract)
add_test(NAME p10r_native_contract COMMAND test_p10r_native_contract)

add_executable(test_p10r_fixture tests/trm_align/test_p10r_fixture.c)
target_link_libraries(test_p10r_fixture PRIVATE elpis_p10r elpis_hash OpenSSL::Crypto)
sf_warnings(test_p10r_fixture)
add_test(NAME p10r_fixture COMMAND test_p10r_fixture)

add_executable(test_p10r_alignment tests/trm_align/test_p10r_alignment.c)
target_link_libraries(test_p10r_alignment PRIVATE elpis_p10r elpis_hash OpenSSL::Crypto)
sf_warnings(test_p10r_alignment)
add_test(NAME p10r_alignment COMMAND test_p10r_alignment)

# ─────────────────────────────────────────────────────────────────────
# P11 — Refinement Engine Replacement Bakeoff
# ─────────────────────────────────────────────────────────────────────

add_library(elpis_p11
  src/refiner/refiner_candidate.c
  src/refiner/refiner_bakeoff_policy.c
  src/refiner/refiner_inventory.c
  src/refiner/refiner_adapter.c
  src/refiner/refiner_execution.c
  src/refiner/refiner_metrics.c
  src/refiner/refiner_selection.c
  src/refiner/refiner_handoff.c
  src/refiner/refiner_persist.c)
target_include_directories(elpis_p11 PUBLIC include)
target_link_libraries(elpis_p11 PUBLIC elpis_semantic elpis_hash)
sf_warnings(elpis_p11)

add_executable(test_p11_refiner tests/refiner/test_p11_refiner.c)
target_link_libraries(test_p11_refiner PRIVATE elpis_p11 elpis_hash OpenSSL::Crypto)
sf_warnings(test_p11_refiner)
add_test(NAME p11_refiner COMMAND test_p11_refiner)

# ─────────────────────────────────────────────────────────────────────
# P12 — Canonical Replacement Engine Integration
# ─────────────────────────────────────────────────────────────────────

add_library(elpis_p12_integration STATIC
  src/refinement_integration/refinement_backend.c
  src/refinement_integration/refinement_backend_registry.c
  src/refinement_integration/refinement_integration_policy.c
  src/refinement_integration/refinement_integration_request.c
  src/refinement_integration/refinement_integration_execute.c
  src/refinement_integration/refinement_integration_receipt.c
  src/refinement_integration/refinement_integration_result.c
  src/refinement_integration/refinement_integration_handoff.c
  src/refinement_integration/refinement_integration_persist.c)
target_include_directories(elpis_p12_integration PUBLIC include)
target_include_directories(elpis_p12_integration SYSTEM PUBLIC "${ELPIS_HACF_ROOT}/include")
target_link_libraries(elpis_p12_integration PUBLIC elpis_semantic elpis_p11 elpis_hash)
sf_warnings(elpis_p12_integration)

# P12 tests
add_executable(test_p12_registry tests/refinement_integration/test_p12_registry.c)
target_link_libraries(test_p12_registry PRIVATE elpis_p12_integration elpis_hash OpenSSL::Crypto)
sf_warnings(test_p12_registry)
add_test(NAME p12_registry COMMAND test_p12_registry)

add_executable(test_p12_policy tests/refinement_integration/test_p12_policy.c)
target_link_libraries(test_p12_policy PRIVATE elpis_p12_integration elpis_hash OpenSSL::Crypto)
sf_warnings(test_p12_policy)
add_test(NAME p12_policy COMMAND test_p12_policy)

add_executable(test_p12_request tests/refinement_integration/test_p12_request.c)
target_link_libraries(test_p12_request PRIVATE elpis_p12_integration elpis_hash OpenSSL::Crypto)
sf_warnings(test_p12_request)
add_test(NAME p12_request COMMAND test_p12_request)

add_executable(test_p12_result tests/refinement_integration/test_p12_result.c)
target_link_libraries(test_p12_result PRIVATE elpis_p12_integration elpis_hash OpenSSL::Crypto)
sf_warnings(test_p12_result)
add_test(NAME p12_result COMMAND test_p12_result)

add_executable(test_p12_handoff tests/refinement_integration/test_p12_handoff.c)
target_link_libraries(test_p12_handoff PRIVATE elpis_p12_integration elpis_hash OpenSSL::Crypto)
sf_warnings(test_p12_handoff)
add_test(NAME p12_handoff COMMAND test_p12_handoff)

add_executable(test_p12_persistence tests/refinement_integration/test_p12_persistence.c)
target_link_libraries(test_p12_persistence PRIVATE elpis_p12_integration elpis_hash OpenSSL::Crypto)
sf_warnings(test_p12_persistence)
add_test(NAME p12_persistence COMMAND test_p12_persistence)

add_executable(test_p12_actv1_retirement tests/refinement_integration/test_p12_actv1_retirement.c)
target_link_libraries(test_p12_actv1_retirement PRIVATE elpis_p12_integration elpis_hash OpenSSL::Crypto)
sf_warnings(test_p12_actv1_retirement)
add_test(NAME p12_actv1_retirement COMMAND test_p12_actv1_retirement)

# ---------------------------------------------------------------------------
# P13 — Structural spine integrated tests
# ---------------------------------------------------------------------------

add_executable(test_p13_structural_spine tests/structural_spine/test_p13_structural_spine.c)
target_link_libraries(test_p13_structural_spine PRIVATE elpis_semantic elpis_hash OpenSSL::Crypto)
sf_warnings(test_p13_structural_spine)
add_test(NAME p13_structural_spine COMMAND test_p13_structural_spine)
