cmake_minimum_required(VERSION 3.20)
project(elpis_hacf_bridge C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# HACF R3 dependencies (build from native/hacf first)
# Accept HACF_INCLUDE_DIR and HACF_LIB_DIR as cache variables from cmake command line.
# Resolve to absolute paths relative to CMAKE_CURRENT_SOURCE_DIR so static archives are found.
if(NOT DEFINED HACF_INCLUDE_DIR)
  set(HACF_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../hacf/include" CACHE PATH "HACF include directory")
endif()
if(NOT DEFINED HACF_LIB_DIR)
  set(HACF_LIB_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../hacf/build" CACHE PATH "HACF library directory")
endif()

# Force absolute — if the value is relative, resolve against the bridge source dir
get_filename_component(_hacf_inc_abs "${HACF_INCLUDE_DIR}" ABSOLUTE BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
get_filename_component(_hacf_lib_abs "${HACF_LIB_DIR}" ABSOLUTE BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
set(HACF_INCLUDE_DIR "${_hacf_inc_abs}")
set(HACF_LIB_DIR "${_hacf_lib_abs}")

find_path(HACF_INCLUDE_DIR NAMES elpis/cascade.h PATHS "${HACF_INCLUDE_DIR}" NO_DEFAULT_PATH)

# Build full static-library paths directly — avoids find_library issues
set(HACF_HASH_LIB "${HACF_LIB_DIR}/libelpis_hash.a")
set(HACF_GRAPH_LIB "${HACF_LIB_DIR}/libelpis_graph.a")
set(HACF_FMS_LIB "${HACF_LIB_DIR}/libelpis_fms.a")
set(HACF_CASCADE_LIB "${HACF_LIB_DIR}/libelpis_cascade.a")
set(HACF_EMBEDDING_LIB "${HACF_LIB_DIR}/libelpis_embedding.a")
set(HACF_CHUNKING_LIB "${HACF_LIB_DIR}/libelpis_chunking.a")
set(HACF_CORPUS_LIB "${HACF_LIB_DIR}/libelpis_corpus.a")
set(HACF_VECTOR_LIB "${HACF_LIB_DIR}/libelpis_vector.a")
set(HACF_HYBRID_LIB "${HACF_LIB_DIR}/libelpis_hybrid.a")

if(NOT HACF_INCLUDE_DIR)
  message(FATAL_ERROR "HACF include directory not found. Build native/hacf first.")
endif()

# Python development headers
find_package(Python3 COMPONENTS Development REQUIRED)

# Build wrapper shared library
# Use whole-archive to ensure all static lib symbols are exported
add_library(r1_hacf_wrapper SHARED python_r1_wrapper.c)
target_include_directories(r1_hacf_wrapper PRIVATE
  ${HACF_INCLUDE_DIR}
  ${Python3_INCLUDE_DIRS}
)

# Link the wrapper against the HACF static libraries and system dependencies.
# The static libs are passed via target_link_libraries so CMake resolves
# transitive dependencies correctly.  On Linux we also add --no-undefined so
# any missing symbol fails at link time rather than load time.
target_link_libraries(r1_hacf_wrapper PRIVATE
  ${Python3_LIBRARIES}
  stdc++
  sqlite3
  pthread
  m
  # HACF static archives — order matters for the linker; hash -> graph -> fms
  # -> cascade -> embedding -> chunking -> corpus -> vector -> hybrid
  $<LINK_LIBRARY:WHOLE_ARCHIVE,${HACF_HASH_LIB}>
  $<LINK_LIBRARY:WHOLE_ARCHIVE,${HACF_GRAPH_LIB}>
  $<LINK_LIBRARY:WHOLE_ARCHIVE,${HACF_FMS_LIB}>
  $<LINK_LIBRARY:WHOLE_ARCHIVE,${HACF_CASCADE_LIB}>
  $<LINK_LIBRARY:WHOLE_ARCHIVE,${HACF_EMBEDDING_LIB}>
  $<LINK_LIBRARY:WHOLE_ARCHIVE,${HACF_CHUNKING_LIB}>
  $<LINK_LIBRARY:WHOLE_ARCHIVE,${HACF_CORPUS_LIB}>
  $<LINK_LIBRARY:WHOLE_ARCHIVE,${HACF_VECTOR_LIB}>
  $<LINK_LIBRARY:WHOLE_ARCHIVE,${HACF_HYBRID_LIB}>
)

# Reject unresolved symbols at link time (catches missing HACF symbols early).
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_link_options(r1_hacf_wrapper PRIVATE "-Wl,--no-undefined")
endif()

set_target_properties(r1_hacf_wrapper PROPERTIES
  OUTPUT_NAME "r1_hacf_wrapper"
  PREFIX "lib"
)
