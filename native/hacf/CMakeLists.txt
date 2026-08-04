cmake_minimum_required(VERSION 3.20)
project(elpis_hacf LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(HACF_WARNINGS_AS_ERRORS "Treat project warnings as errors" ON)
option(HACF_BUILD_FMS "Build the Fluid Memory Stabilizer" ON)

option(ELPIS_ENABLE_ASAN "Enable AddressSanitizer" OFF)
option(ELPIS_ENABLE_UBSAN "Enable UndefinedBehaviorSanitizer" OFF)
option(ELPIS_ENABLE_TSAN "Enable ThreadSanitizer" OFF)

if(ELPIS_ENABLE_TSAN AND (ELPIS_ENABLE_ASAN OR ELPIS_ENABLE_UBSAN))
  message(FATAL_ERROR
    "ThreadSanitizer cannot be combined with AddressSanitizer or "
    "UndefinedBehaviorSanitizer in the same build.")
endif()

set(HACF_SANITIZER_COMPILE_OPTIONS)
set(HACF_SANITIZER_LINK_OPTIONS)

if(ELPIS_ENABLE_ASAN OR ELPIS_ENABLE_UBSAN OR ELPIS_ENABLE_TSAN)
  if(NOT (
      CMAKE_C_COMPILER_ID MATCHES "GNU|Clang"
      AND CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang"))
    message(FATAL_ERROR
      "Requested sanitizers require GCC-compatible or Clang-compatible compilers.")
  endif()

  list(APPEND HACF_SANITIZER_COMPILE_OPTIONS
    -g
    -fno-omit-frame-pointer
    -fno-optimize-sibling-calls)

  if(ELPIS_ENABLE_TSAN)
    list(APPEND HACF_SANITIZER_COMPILE_OPTIONS -fsanitize=thread)
    list(APPEND HACF_SANITIZER_LINK_OPTIONS -fsanitize=thread)
  else()
    if(ELPIS_ENABLE_ASAN AND ELPIS_ENABLE_UBSAN)
      list(APPEND HACF_SANITIZER_COMPILE_OPTIONS -fsanitize=address,undefined)
      list(APPEND HACF_SANITIZER_LINK_OPTIONS -fsanitize=address,undefined)
    elseif(ELPIS_ENABLE_ASAN)
      list(APPEND HACF_SANITIZER_COMPILE_OPTIONS -fsanitize=address)
      list(APPEND HACF_SANITIZER_LINK_OPTIONS -fsanitize=address)
    elseif(ELPIS_ENABLE_UBSAN)
      list(APPEND HACF_SANITIZER_COMPILE_OPTIONS -fsanitize=undefined)
      list(APPEND HACF_SANITIZER_LINK_OPTIONS -fsanitize=undefined)
    endif()
  endif()

  add_compile_options(${HACF_SANITIZER_COMPILE_OPTIONS})
  add_link_options(${HACF_SANITIZER_LINK_OPTIONS})
endif()


enable_testing()
find_package(Threads REQUIRED)
find_package(SQLite3 REQUIRED)

# Compatibility shim (additive, no-op where SQLite3::SQLite3 already exists).
# CMake's upstream FindSQLite3 module defines SQLite::SQLite3; the authoritative
# HACF target name remains SQLite3::SQLite3 and is not renamed.
if(NOT TARGET SQLite3::SQLite3)
  if(TARGET SQLite::SQLite3)
    add_library(SQLite3::SQLite3 ALIAS SQLite::SQLite3)
  else()
    add_library(SQLite3::SQLite3 INTERFACE IMPORTED)
    set_target_properties(SQLite3::SQLite3 PROPERTIES
      INTERFACE_INCLUDE_DIRECTORIES "${SQLite3_INCLUDE_DIRS}"
      INTERFACE_LINK_LIBRARIES "${SQLite3_LIBRARIES}")
  endif()
endif()

function(hacf_warnings target)
  if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang" OR CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
    if(HACF_WARNINGS_AS_ERRORS)
      target_compile_options(${target} PRIVATE -Werror)
    endif()
  endif()
endfunction()

add_library(elpis_hash STATIC src/hash/sha256.c)
target_include_directories(elpis_hash PUBLIC include)
hacf_warnings(elpis_hash)

add_library(elpis_chunking STATIC src/retrieval/chunking/chunker.cpp)
target_include_directories(elpis_chunking PUBLIC include)
target_link_libraries(elpis_chunking PUBLIC elpis_hash)
hacf_warnings(elpis_chunking)

add_library(elpis_corpus STATIC src/retrieval/corpus/corpus.cpp)
target_include_directories(elpis_corpus PUBLIC include)
target_link_libraries(elpis_corpus PUBLIC elpis_chunking elpis_hash SQLite3::SQLite3)
hacf_warnings(elpis_corpus)

add_library(elpis_cascade STATIC src/kernel/cascade.c)
target_include_directories(elpis_cascade PUBLIC include)
target_link_libraries(elpis_cascade PUBLIC elpis_hash Threads::Threads)
hacf_warnings(elpis_cascade)

add_library(elpis_graph STATIC src/graph/graph.c)
target_include_directories(elpis_graph PUBLIC include)
target_link_libraries(elpis_graph PUBLIC elpis_cascade elpis_hash)
hacf_warnings(elpis_graph)

if(HACF_BUILD_FMS)
  add_library(elpis_fms STATIC src/memory/fms/fms_core.c src/memory/fms/fms_pal_posix.c)
  target_include_directories(elpis_fms PUBLIC include)
  target_link_libraries(elpis_fms PUBLIC elpis_hash Threads::Threads)
  hacf_warnings(elpis_fms)

  add_library(elpis_fms_test_pal STATIC tests/support/fms_pal_test.c)
  target_include_directories(elpis_fms_test_pal PUBLIC include tests/support/include)
  target_link_libraries(elpis_fms_test_pal PUBLIC elpis_fms elpis_hash Threads::Threads)
  hacf_warnings(elpis_fms_test_pal)

  add_executable(test_fms_r0 tests/fms/test_fms_r0.c)
  target_include_directories(test_fms_r0 PRIVATE include tests/support/include)
  target_link_libraries(test_fms_r0 PRIVATE elpis_fms_test_pal elpis_fms elpis_hash Threads::Threads)
  hacf_warnings(test_fms_r0)
  add_test(NAME fms_r0 COMMAND test_fms_r0 ${CMAKE_BINARY_DIR}/fms-r0-state)

  add_executable(test_fms_concurrency tests/fms/test_fms_concurrency.c)
  target_include_directories(test_fms_concurrency PRIVATE include tests/support/include)
  target_link_libraries(test_fms_concurrency PRIVATE elpis_fms_test_pal elpis_fms elpis_hash Threads::Threads)
  hacf_warnings(test_fms_concurrency)
  add_test(NAME fms_concurrency COMMAND test_fms_concurrency ${CMAKE_BINARY_DIR}/fms-concurrency-state)

  add_executable(test_fms_adversarial tests/fms/test_fms_adversarial.c)
  target_include_directories(test_fms_adversarial PRIVATE include tests/support/include)
  target_link_libraries(test_fms_adversarial PRIVATE elpis_fms_test_pal elpis_fms elpis_hash Threads::Threads)
  hacf_warnings(test_fms_adversarial)
  add_test(NAME fms_adversarial COMMAND test_fms_adversarial ${CMAKE_BINARY_DIR}/fms-adversarial-state)
endif()

add_executable(test_hash tests/hash_test.c)
target_link_libraries(test_hash PRIVATE elpis_hash)
hacf_warnings(test_hash)
add_test(NAME hash COMMAND test_hash)

add_executable(test_r1_corpus tests/retrieval/test_r1_corpus.cpp)
target_link_libraries(test_r1_corpus PRIVATE elpis_corpus elpis_chunking elpis_hash SQLite3::SQLite3)
hacf_warnings(test_r1_corpus)
add_test(NAME r1_corpus COMMAND test_r1_corpus ${CMAKE_BINARY_DIR}/r1-state)

add_executable(test_chunking_adversarial tests/retrieval/test_chunking_adversarial.cpp)
target_link_libraries(test_chunking_adversarial PRIVATE elpis_chunking elpis_hash)
hacf_warnings(test_chunking_adversarial)
add_test(NAME chunking_adversarial COMMAND test_chunking_adversarial)

add_executable(test_cascade tests/kernel/test_cascade.c)
target_link_libraries(test_cascade PRIVATE elpis_cascade elpis_hash Threads::Threads)
hacf_warnings(test_cascade)
add_test(NAME cascade COMMAND test_cascade)

add_executable(test_graph tests/graph/test_graph.c)
target_link_libraries(test_graph PRIVATE elpis_graph elpis_cascade elpis_hash)
hacf_warnings(test_graph)
add_test(NAME graph COMMAND test_graph)

# ---------------------------------------------------------------------------
# Gate R2: exact deterministic dense-vector retrieval (CPU only).
# Additive. No existing target, source or test is altered.
# ---------------------------------------------------------------------------
add_library(elpis_embedding STATIC
  src/retrieval/embedding/fixture_embedder.cpp
  src/retrieval/embedding/external_vector_provider.cpp)
target_include_directories(elpis_embedding
  PUBLIC include
  PRIVATE src/retrieval/embedding)
target_link_libraries(elpis_embedding PUBLIC elpis_hash)
hacf_warnings(elpis_embedding)

add_library(elpis_vector STATIC
  src/retrieval/vector/vector_shard.cpp
  src/retrieval/vector/cpu_exact.cpp
  src/retrieval/vector/vector_index.cpp
  src/retrieval/vector/vector_manifest.cpp)
target_include_directories(elpis_vector PUBLIC include)
target_link_libraries(elpis_vector PUBLIC elpis_embedding elpis_hash Threads::Threads)
# The exact CPU kernel is the qualification oracle: no fast-math, and floating
# point contraction is disabled so a fused multiply-add cannot silently change
# a reference score between hosts or compilers.
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(elpis_vector PRIVATE -ffp-contract=off)
endif()
if(HACF_BUILD_FMS)
  target_link_libraries(elpis_vector PUBLIC elpis_fms)
endif()
hacf_warnings(elpis_vector)

add_executable(test_embedding_provider tests/vector/test_embedding_provider.cpp)
target_link_libraries(test_embedding_provider PRIVATE elpis_embedding elpis_hash)
hacf_warnings(test_embedding_provider)
add_test(NAME embedding_provider COMMAND test_embedding_provider)

add_executable(test_vector_shard tests/vector/test_vector_shard.cpp)
target_link_libraries(test_vector_shard PRIVATE elpis_vector elpis_embedding elpis_hash)
target_include_directories(test_vector_shard PRIVATE tests/vector)
hacf_warnings(test_vector_shard)
add_test(NAME vector_shard COMMAND test_vector_shard ${CMAKE_BINARY_DIR}/vector-shard-state)

if(HACF_BUILD_FMS)
  add_executable(test_vector_search tests/vector/test_vector_search.cpp)
  target_include_directories(test_vector_search PRIVATE tests/vector)
  target_link_libraries(test_vector_search PRIVATE elpis_vector elpis_embedding elpis_fms elpis_hash Threads::Threads)
  hacf_warnings(test_vector_search)
  add_test(NAME vector_search COMMAND test_vector_search ${CMAKE_BINARY_DIR}/vector-search-state)

  add_executable(test_vector_fms tests/vector/test_vector_fms.cpp)
  target_include_directories(test_vector_fms PRIVATE tests/vector)
  target_link_libraries(test_vector_fms PRIVATE elpis_vector elpis_embedding elpis_fms elpis_hash Threads::Threads)
  hacf_warnings(test_vector_fms)
  add_test(NAME vector_fms COMMAND test_vector_fms ${CMAKE_BINARY_DIR}/vector-fms-state)

  add_executable(test_vector_concurrency tests/vector/test_vector_concurrency.cpp)
  target_include_directories(test_vector_concurrency PRIVATE tests/vector)
  target_link_libraries(test_vector_concurrency PRIVATE elpis_vector elpis_embedding elpis_fms elpis_hash Threads::Threads)
  hacf_warnings(test_vector_concurrency)
  add_test(NAME vector_concurrency COMMAND test_vector_concurrency ${CMAKE_BINARY_DIR}/vector-conc-state)
  # Runtime is dominated by real cold I/O under deliberate shard thrashing and
  # scales linearly with ELPIS_R2_CONC_ITERS (default 60). See
  # R2_AUDIT_REMEDIATION_01.md for measured figures. The timeout is finite so a
  # genuine liveness defect fails instead of hanging; it is not a way to absorb
  # an unbounded wait.
  set_tests_properties(vector_concurrency PROPERTIES TIMEOUT 600)

  add_executable(test_vector_crosshost_fixture tests/vector/test_vector_crosshost_fixture.cpp)
  target_include_directories(test_vector_crosshost_fixture PRIVATE tests/vector)
  target_link_libraries(test_vector_crosshost_fixture PRIVATE elpis_vector elpis_embedding elpis_corpus elpis_fms elpis_hash Threads::Threads)
  target_compile_definitions(test_vector_crosshost_fixture PRIVATE
    HACF_FIXTURE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/tests/vector/fixture")
  hacf_warnings(test_vector_crosshost_fixture)
  add_test(NAME vector_crosshost_fixture COMMAND test_vector_crosshost_fixture ${CMAKE_BINARY_DIR}/vector-xhost-state)

  add_executable(test_vector_adversarial tests/vector/test_vector_adversarial.cpp)
  target_include_directories(test_vector_adversarial PRIVATE tests/vector)
  target_link_libraries(test_vector_adversarial PRIVATE elpis_vector elpis_embedding elpis_corpus elpis_fms elpis_hash Threads::Threads)
  hacf_warnings(test_vector_adversarial)
  add_test(NAME vector_adversarial COMMAND test_vector_adversarial ${CMAKE_BINARY_DIR}/vector-adv-state)

  add_executable(benchmark_vector_exact benchmarks/vector/benchmark_exact.cpp)
  target_include_directories(benchmark_vector_exact PRIVATE tests/vector)
  target_link_libraries(benchmark_vector_exact PRIVATE elpis_vector elpis_embedding elpis_fms elpis_hash Threads::Threads)
  hacf_warnings(benchmark_vector_exact)
endif()

# ---------------------------------------------------------------------------
# Gate R3: deterministic hybrid retrieval and frozen RetrievalBundle.
# ---------------------------------------------------------------------------
add_library(elpis_hybrid STATIC
  src/retrieval/hybrid/context_graph.cpp
  src/retrieval/hybrid/hybrid_retrieval.cpp
  src/retrieval/hybrid/retrieval_bundle.cpp)
target_include_directories(elpis_hybrid
  PUBLIC include
  PRIVATE src/retrieval/hybrid)
target_link_libraries(elpis_hybrid PUBLIC
  elpis_corpus elpis_vector elpis_cascade elpis_hash Threads::Threads)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(elpis_hybrid PRIVATE -ffp-contract=off)
endif()
hacf_warnings(elpis_hybrid)

add_executable(test_context_graph tests/hybrid/test_context_graph.cpp)
target_include_directories(test_context_graph PRIVATE tests/vector tests/hybrid)
target_link_libraries(test_context_graph PRIVATE elpis_hybrid elpis_hash)
hacf_warnings(test_context_graph)
add_test(NAME context_graph COMMAND test_context_graph)

if(HACF_BUILD_FMS)
  add_executable(test_hybrid_fusion tests/hybrid/test_hybrid_fusion.cpp)
  target_include_directories(test_hybrid_fusion PRIVATE tests/vector tests/hybrid)
  target_link_libraries(test_hybrid_fusion PRIVATE elpis_hybrid elpis_vector elpis_embedding elpis_corpus elpis_fms elpis_hash Threads::Threads)
  hacf_warnings(test_hybrid_fusion)
  add_test(NAME hybrid_fusion COMMAND test_hybrid_fusion ${CMAKE_BINARY_DIR}/hybrid-fusion-state)

  add_executable(test_retrieval_bundle tests/hybrid/test_retrieval_bundle.cpp)
  target_include_directories(test_retrieval_bundle PRIVATE tests/vector tests/hybrid)
  target_link_libraries(test_retrieval_bundle PRIVATE elpis_hybrid elpis_vector elpis_embedding elpis_corpus elpis_fms elpis_hash Threads::Threads)
  hacf_warnings(test_retrieval_bundle)
  add_test(NAME retrieval_bundle COMMAND test_retrieval_bundle ${CMAKE_BINARY_DIR}/retrieval-bundle-state)

  add_executable(test_hybrid_adversarial tests/hybrid/test_hybrid_adversarial.cpp)
  target_include_directories(test_hybrid_adversarial PRIVATE tests/vector tests/hybrid)
  target_link_libraries(test_hybrid_adversarial PRIVATE elpis_hybrid elpis_vector elpis_embedding elpis_corpus elpis_fms elpis_hash Threads::Threads)
  hacf_warnings(test_hybrid_adversarial)
  add_test(NAME hybrid_adversarial COMMAND test_hybrid_adversarial ${CMAKE_BINARY_DIR}/hybrid-adversarial-state)

  add_executable(test_hybrid_crosshost_fixture tests/hybrid/test_hybrid_crosshost_fixture.cpp)
  target_include_directories(test_hybrid_crosshost_fixture PRIVATE tests/vector tests/hybrid)
  target_link_libraries(test_hybrid_crosshost_fixture PRIVATE elpis_hybrid elpis_vector elpis_embedding elpis_corpus elpis_fms elpis_hash Threads::Threads)
  target_compile_definitions(test_hybrid_crosshost_fixture PRIVATE
    HACF_R3_FIXTURE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/tests/hybrid/fixture")
  hacf_warnings(test_hybrid_crosshost_fixture)
  add_test(NAME hybrid_crosshost_fixture COMMAND test_hybrid_crosshost_fixture ${CMAKE_BINARY_DIR}/hybrid-xhost-state)

  add_executable(benchmark_hybrid benchmarks/hybrid/benchmark_hybrid.cpp)
  target_include_directories(benchmark_hybrid PRIVATE tests/vector tests/hybrid)
  target_link_libraries(benchmark_hybrid PRIVATE elpis_hybrid elpis_vector elpis_embedding elpis_corpus elpis_fms elpis_hash Threads::Threads)
  hacf_warnings(benchmark_hybrid)
endif()

if(HACF_BUILD_FMS)
  add_executable(test_hybrid_concurrency tests/hybrid/test_hybrid_concurrency.cpp)
  target_include_directories(test_hybrid_concurrency PRIVATE tests/vector tests/hybrid)
  target_link_libraries(test_hybrid_concurrency PRIVATE elpis_hybrid elpis_vector elpis_embedding elpis_corpus elpis_fms elpis_hash Threads::Threads)
  hacf_warnings(test_hybrid_concurrency)
  add_test(NAME hybrid_concurrency COMMAND test_hybrid_concurrency ${CMAKE_BINARY_DIR}/hybrid-concurrency-state)
  set_tests_properties(hybrid_concurrency PROPERTIES TIMEOUT 180)
endif()
