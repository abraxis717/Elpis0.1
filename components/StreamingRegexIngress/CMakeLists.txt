cmake_minimum_required(VERSION 3.20)
project(elpis_streaming_regex_ingress LANGUAGES C CXX)

find_package(PkgConfig REQUIRED)
pkg_check_modules(PCRE2 REQUIRED IMPORTED_TARGET libpcre2-8)

set(ELPIS_HACF_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../native/hacf")

add_library(elpis_streaming_regex_ingress SHARED
    src/native_regex_ingress.cpp
    ${ELPIS_HACF_ROOT}/src/hash/sha256.c
)

target_compile_definitions(elpis_streaming_regex_ingress
    PRIVATE ELPIS_STREAMING_REGEX_NO_MAIN=1
)

set_target_properties(elpis_streaming_regex_ingress PROPERTIES
    C_VISIBILITY_PRESET hidden
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN YES
)

target_include_directories(elpis_streaming_regex_ingress
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
    PRIVATE
        ${ELPIS_HACF_ROOT}/include
)

target_link_libraries(elpis_streaming_regex_ingress
    PRIVATE PkgConfig::PCRE2
)

target_compile_features(elpis_streaming_regex_ingress PRIVATE cxx_std_17)

add_executable(elpis_native_regex_ingress
    src/native_regex_ingress.cpp
    ${ELPIS_HACF_ROOT}/src/hash/sha256.c
)

target_include_directories(elpis_native_regex_ingress
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
        ${ELPIS_HACF_ROOT}/include
)

target_link_libraries(elpis_native_regex_ingress
    PRIVATE PkgConfig::PCRE2
)

target_compile_features(elpis_native_regex_ingress PRIVATE cxx_std_17)

# B01 bounded-profile regression.
#
# This is a focused successor regression target. It verifies that every
# successfully accepted v1 input remains wholly retained until lexical
# disposition and that out-of-profile input publishes no result.
add_executable(elpis_streaming_regex_b01_regression
    tests/test_b01_bounded_profile.cpp
)

target_link_libraries(elpis_streaming_regex_b01_regression
    PRIVATE elpis_streaming_regex_ingress
)

target_compile_features(
    elpis_streaming_regex_b01_regression
    PRIVATE cxx_std_17
)

# B01 Phase-2 EOF/read-state regression.
#
# Exercises the private staging state machine used by the standalone CLI,
# including deterministic first-read and after-prefix I/O failures.
add_executable(elpis_streaming_regex_b01_cli_io_regression
    tests/test_b01_cli_eof_gate.cpp
)

target_include_directories(
    elpis_streaming_regex_b01_cli_io_regression
    PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src
)

target_compile_features(
    elpis_streaming_regex_b01_cli_io_regression
    PRIVATE cxx_std_17
)
