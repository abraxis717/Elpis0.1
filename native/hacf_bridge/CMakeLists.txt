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
# The static libs contain C++ objects that need libstdc++ and libm available
# during their resolution.  Use --start-group/--end-group linker flags (Linux)
# so the linker handles circular dependencies among the static archives.
target_link_libraries(r1_hacf_wrapper PRIVATE
  ${Python3_LIBRARIES}
  sqlite3
  pthread
  # HACF static archives inside a link group so C++ symbols resolve properly
  "-Wl,--start-group"
  ${HACF_HASH_LIB}
  ${HACF_GRAPH_LIB}
  ${HACF_FMS_LIB}
  ${HACF_CASCADE_LIB}
  ${HACF_EMBEDDING_LIB}
  ${HACF_CHUNKING_LIB}
  ${HACF_CORPUS_LIB}
  ${HACF_VECTOR_LIB}
  ${HACF_HYBRID_LIB}
  stdc++
  m
  "-Wl,--end-group"
)

set_target_properties(r1_hacf_wrapper PROPERTIES
  OUTPUT_NAME "r1_hacf_wrapper"
  PREFIX "lib"
)
