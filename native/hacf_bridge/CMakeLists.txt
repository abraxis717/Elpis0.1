cmake_minimum_required(VERSION 3.20)
project(elpis_hacf_bridge C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# HACF R3 dependencies (build from native/hacf first)
# Accept HACF_INCLUDE_DIR and HACF_LIB_DIR as cache variables from cmake command line
if(NOT DEFINED HACF_INCLUDE_DIR)
  set(HACF_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../hacf/include" CACHE PATH "HACF include directory")
endif()
if(NOT DEFINED HACF_LIB_DIR)
  set(HACF_LIB_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../hacf/build" CACHE PATH "HACF library directory")
endif()

find_path(HACF_INCLUDE_DIR NAMES elpis/cascade.h PATHS "${HACF_INCLUDE_DIR}" NO_DEFAULT_PATH)
find_library(HACF_CASCADE_LIB NAMES elpis_cascade PATHS "${HACF_LIB_DIR}" NO_DEFAULT_PATH)
find_library(HACF_HYBRID_LIB NAMES elpis_hybrid PATHS "${HACF_LIB_DIR}" NO_DEFAULT_PATH)
find_library(HACF_FMS_LIB NAMES elpis_fms PATHS "${HACF_LIB_DIR}" NO_DEFAULT_PATH)
find_library(HACF_VECTOR_LIB NAMES elpis_vector PATHS "${HACF_LIB_DIR}" NO_DEFAULT_PATH)
find_library(HACF_GRAPH_LIB NAMES elpis_graph PATHS "${HACF_LIB_DIR}" NO_DEFAULT_PATH)
find_library(HACF_HASH_LIB NAMES elpis_hash PATHS "${HACF_LIB_DIR}" NO_DEFAULT_PATH)
find_library(HACF_CHUNKING_LIB NAMES elpis_chunking PATHS "${HACF_LIB_DIR}" NO_DEFAULT_PATH)
find_library(HACF_CORPUS_LIB NAMES elpis_corpus PATHS "${HACF_LIB_DIR}" NO_DEFAULT_PATH)
find_library(HACF_EMBEDDING_LIB NAMES elpis_embedding PATHS "${HACF_LIB_DIR}" NO_DEFAULT_PATH)

if(NOT HACF_INCLUDE_DIR)
  message(FATAL_ERROR "HACF include directory not found. Build native/hacf first.")
endif()

# Python development headers
find_package(Python3 COMPONENTS Development REQUIRED)

set(HACF_STATIC_LIBS
  ${HACF_CASCADE_LIB}
  ${HACF_HYBRID_LIB}
  ${HACF_FMS_LIB}
  ${HACF_VECTOR_LIB}
  ${HACF_GRAPH_LIB}
  ${HACF_HASH_LIB}
  ${HACF_CHUNKING_LIB}
  ${HACF_CORPUS_LIB}
  ${HACF_EMBEDDING_LIB}
)

# Build wrapper shared library
# Use whole-archive to ensure all static lib symbols are exported
add_library(r1_hacf_wrapper SHARED python_r1_wrapper.c)
target_include_directories(r1_hacf_wrapper PRIVATE
  ${HACF_INCLUDE_DIR}
  ${Python3_INCLUDE_DIRS}
)
target_link_libraries(r1_hacf_wrapper PRIVATE
  ${Python3_LIBRARIES}
  stdc++
  sqlite3
  pthread
  m
)
# Link static libs with start-group/end-group to handle cross-dependencies
target_link_options(r1_hacf_wrapper PRIVATE
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
  "-Wl,--end-group"
)
set_target_properties(r1_hacf_wrapper PROPERTIES
  OUTPUT_NAME "r1_hacf_wrapper"
  PREFIX "lib"
)
