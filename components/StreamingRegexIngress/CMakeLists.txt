cmake_minimum_required(VERSION 3.20)
project(elpis_streaming_regex_ingress LANGUAGES C CXX)

find_package(PkgConfig REQUIRED)
pkg_check_modules(PCRE2 REQUIRED IMPORTED_TARGET libpcre2-8)

add_executable(elpis_native_regex_ingress
    src/native_regex_ingress.cpp
    ../../native/hacf/src/hash/sha256.c
)

target_include_directories(elpis_native_regex_ingress
    PRIVATE
        ../../native/hacf/include
)

target_link_libraries(elpis_native_regex_ingress
    PRIVATE
        PkgConfig::PCRE2
)

target_compile_features(elpis_native_regex_ingress PRIVATE cxx_std_17)
