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
