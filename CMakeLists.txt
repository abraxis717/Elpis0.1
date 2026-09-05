cmake_minimum_required(VERSION 3.20)
project(elpis-canonical C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# HACF R3
add_subdirectory(native/hacf)

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
