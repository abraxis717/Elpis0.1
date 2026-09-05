cmake_minimum_required(VERSION 3.20)
project(elpis_query_local_proposal_ingress C)

add_library(elpis_query_local_proposal_ingress STATIC
    src/query_local_proposal.c
    src/query_local_proposal_batch.c
)

target_include_directories(elpis_query_local_proposal_ingress
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
        ${CMAKE_CURRENT_SOURCE_DIR}/../../native/semantic-spine/include
        ${CMAKE_CURRENT_SOURCE_DIR}/../../native/hacf/include
)

target_compile_features(elpis_query_local_proposal_ingress PUBLIC c_std_11)
