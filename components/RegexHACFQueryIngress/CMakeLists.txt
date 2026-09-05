cmake_minimum_required(VERSION 3.20)

set(ELPIS_REGEX_HACF_QUERY_INGRESS_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../..")
set(ELPIS_REGEX_HACF_QUERY_INGRESS_SEMANTIC_ROOT
    "${ELPIS_REGEX_HACF_QUERY_INGRESS_ROOT}/native/semantic-spine")
set(ELPIS_REGEX_HACF_QUERY_INGRESS_HACF_ROOT
    "${ELPIS_REGEX_HACF_QUERY_INGRESS_ROOT}/native/hacf")
set(ELPIS_REGEX_HACF_QUERY_INGRESS_QLP_ROOT
    "${ELPIS_REGEX_HACF_QUERY_INGRESS_ROOT}/components/QueryLocalProposalIngress")

find_package(Threads REQUIRED)

add_library(elpis_regex_hacf_query_ingress STATIC
    src/regex_hacf_query_ingress.cpp

    # Exact qualified QueryLocalProposalIngress source authority.
    "${ELPIS_REGEX_HACF_QUERY_INGRESS_QLP_ROOT}/src/query_local_proposal.c"
    "${ELPIS_REGEX_HACF_QUERY_INGRESS_QLP_ROOT}/src/query_local_proposal_batch.c"

    # Narrow real Semantic Spine support. These replace the qualification-only
    # link compatibility shim; no invented semantic implementation is shipped.
    "${ELPIS_REGEX_HACF_QUERY_INGRESS_SEMANTIC_ROOT}/src/graph/identity.c"
    "${ELPIS_REGEX_HACF_QUERY_INGRESS_SEMANTIC_ROOT}/src/graph/type_registry.c"
    "${ELPIS_REGEX_HACF_QUERY_INGRESS_SEMANTIC_ROOT}/src/graph/incidence_validate.c"
    "${ELPIS_REGEX_HACF_QUERY_INGRESS_SEMANTIC_ROOT}/src/graph/hypergraph_builder.c"
    "${ELPIS_REGEX_HACF_QUERY_INGRESS_SEMANTIC_ROOT}/src/graph/query_overlay.c"
    "${ELPIS_REGEX_HACF_QUERY_INGRESS_SEMANTIC_ROOT}/src/graph/snapshot_manifest.c"
    "${ELPIS_REGEX_HACF_QUERY_INGRESS_SEMANTIC_ROOT}/src/graph/snapshot_view.c"

    # The zero-vector path needs only the immutable context-graph source, not
    # the HACF hybrid/vector target graph.
    "${ELPIS_REGEX_HACF_QUERY_INGRESS_HACF_ROOT}/src/retrieval/hybrid/context_graph.cpp"
)

target_include_directories(elpis_regex_hacf_query_ingress
    PUBLIC
        "${CMAKE_CURRENT_SOURCE_DIR}/include"
    PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/src"
        "${ELPIS_REGEX_HACF_QUERY_INGRESS_ROOT}/components/StreamingRegexIngress/include"
        "${ELPIS_REGEX_HACF_QUERY_INGRESS_QLP_ROOT}/include"
        "${ELPIS_REGEX_HACF_QUERY_INGRESS_SEMANTIC_ROOT}/include"
        "${ELPIS_REGEX_HACF_QUERY_INGRESS_SEMANTIC_ROOT}/src/graph"
        "${ELPIS_REGEX_HACF_QUERY_INGRESS_HACF_ROOT}/include"
)

target_link_libraries(elpis_regex_hacf_query_ingress
    PUBLIC
        elpis_streaming_regex_ingress
        elpis_corpus
    PRIVATE
        elpis_hash
        Threads::Threads
)

target_compile_features(elpis_regex_hacf_query_ingress PUBLIC cxx_std_17)
set_target_properties(elpis_regex_hacf_query_ingress PROPERTIES
    POSITION_INDEPENDENT_CODE ON
)

if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang" OR
   CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(elpis_regex_hacf_query_ingress
      PRIVATE -Wall -Wextra -Wpedantic)
endif()

# B01 bounded-profile successor regression.
#
# Root-linked Regex -> HACF -> QueryLocalProposalIngress containment check.
# Oversized input must fail in Regex before proposal or batch publication.
add_executable(elpis_regex_hacf_b01_regression
    tests/test_b01_range_prepublication.cpp
)

target_link_libraries(elpis_regex_hacf_b01_regression
    PRIVATE elpis_regex_hacf_query_ingress
)

target_compile_features(
    elpis_regex_hacf_b01_regression
    PRIVATE cxx_std_17
)
