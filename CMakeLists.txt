cmake_minimum_required(VERSION 3.20)
project(elpis-canonical C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Root-level test registration is mandatory. Subproject-local
# enable_testing() is not sufficient for `ctest --test-dir <root-build>`.
enable_testing()

# HACF R3
add_subdirectory(native/hacf)

# Semantic spine: built and test-registered by default from the project root.
option(ELPIS_BUILD_SEMANTIC_SPINE
  "Build the native semantic spine and its qualification tests"
  ON)

if(ELPIS_BUILD_SEMANTIC_SPINE)
  set(ELPIS_HACF_ROOT
    "${CMAKE_CURRENT_SOURCE_DIR}/native/hacf"
    CACHE PATH "Path to HashAdressedCascadeFabric source root"
    FORCE)
  add_subdirectory(native/semantic-spine)
endif()

# R1 wrapper (optional, requires HACF built first)
# add_subdirectory(native/hacf_bridge)

# ---------------------------------------------------------------------------
# Qualified bounded Regex shipment R0.
#
# Build admission is not runtime admission. This compiles the authority-zero
# StreamingRegexIngress -> HACF -> QueryLocalProposalIngress path only.
# ---------------------------------------------------------------------------
option(ELPIS_BUILD_BASIC_REGEX
  "Build the qualified bounded Regex/HACF/query-local ingress stack"
  ON)

if(ELPIS_BUILD_BASIC_REGEX)
  add_subdirectory(components/StreamingRegexIngress)
  add_subdirectory(components/RegexHACFQueryIngress)
endif()
