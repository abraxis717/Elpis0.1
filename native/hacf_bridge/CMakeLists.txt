cmake_minimum_required(VERSION 3.20)
project(elpis_hacf_bridge C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT DEFINED HACF_INCLUDE_DIR)
  set(HACF_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../hacf/include" CACHE PATH "HACF include directory")
endif()

if(NOT DEFINED HACF_LIB_DIR)
  set(HACF_LIB_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../hacf/build" CACHE PATH "HACF library directory")
endif()

get_filename_component(_hacf_inc_abs "${HACF_INCLUDE_DIR}" ABSOLUTE BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
get_filename_component(_hacf_lib_abs "${HACF_LIB_DIR}" ABSOLUTE BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

set(HACF_INCLUDE_DIR "${_hacf_inc_abs}")
set(HACF_LIB_DIR "${_hacf_lib_abs}")

find_path(HACF_INCLUDE_DIR NAMES elpis/cascade.h PATHS "${HACF_INCLUDE_DIR}" NO_DEFAULT_PATH)

if(NOT HACF_INCLUDE_DIR)
  message(FATAL_ERROR "HACF include directory not found. Build native/hacf first.")
endif()

set(HACF_HASH_LIB "${HACF_LIB_DIR}/libelpis_hash.a")
set(HACF_GRAPH_LIB "${HACF_LIB_DIR}/libelpis_graph.a")
set(HACF_FMS_LIB "${HACF_LIB_DIR}/libelpis_fms.a")
set(HACF_CASCADE_LIB "${HACF_LIB_DIR}/libelpis_cascade.a")
set(HACF_EMBEDDING_LIB "${HACF_LIB_DIR}/libelpis_embedding.a")
set(HACF_CHUNKING_LIB "${HACF_LIB_DIR}/libelpis_chunking.a")
set(HACF_CORPUS_LIB "${HACF_LIB_DIR}/libelpis_corpus.a")
set(HACF_VECTOR_LIB "${HACF_LIB_DIR}/libelpis_vector.a")
set(HACF_HYBRID_LIB "${HACF_LIB_DIR}/libelpis_hybrid.a")

set(HACF_STATIC_LIBS
  ${HACF_HASH_LIB}
  ${HACF_GRAPH_LIB}
  ${HACF_FMS_LIB}
  ${HACF_CASCADE_LIB}
  ${HACF_EMBEDDING_LIB}
  ${HACF_CHUNKING_LIB}
  ${HACF_CORPUS_LIB}
  ${HACF_VECTOR_LIB}
  ${HACF_HYBRID_LIB}
)

foreach(ELPIS_HACF_ARCHIVE IN LISTS HACF_STATIC_LIBS)
  if(NOT EXISTS "${ELPIS_HACF_ARCHIVE}")
    message(FATAL_ERROR "Required HACF archive missing: ${ELPIS_HACF_ARCHIVE}")
  endif()
endforeach()

find_package(Threads REQUIRED)
find_package(SQLite3 REQUIRED)

add_library(r1_hacf_wrapper SHARED python_r1_wrapper.c)

target_include_directories(r1_hacf_wrapper PRIVATE
  ${HACF_INCLUDE_DIR}
)

set_target_properties(r1_hacf_wrapper PROPERTIES
  OUTPUT_NAME "r1_hacf_wrapper"
  PREFIX "lib"
  LINKER_LANGUAGE CXX
)

if(APPLE)
  target_link_libraries(r1_hacf_wrapper PRIVATE
    SQLite::SQLite3
    Threads::Threads
  )

  foreach(ELPIS_HACF_ARCHIVE IN LISTS HACF_STATIC_LIBS)
    target_link_options(r1_hacf_wrapper PRIVATE
      "-Wl,-force_load,${ELPIS_HACF_ARCHIVE}"
    )
  endforeach()
else()
  target_link_libraries(r1_hacf_wrapper PRIVATE
    "-Wl,--start-group"
    ${HACF_STATIC_LIBS}
    "-Wl,--end-group"
    SQLite::SQLite3
    Threads::Threads
    m
  )
endif()
