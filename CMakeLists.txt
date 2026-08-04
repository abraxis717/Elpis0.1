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
