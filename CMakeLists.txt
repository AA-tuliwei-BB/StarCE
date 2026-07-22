cmake_minimum_required(VERSION 2.8.12...3.29)
project(starce)

set(CMAKE_CXX_STANDARD 11)

if (NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE "Release")
endif()

message("Build type: ${CMAKE_BUILD_TYPE}")

include_directories(duckdb/src/include)

if (CMAKE_BUILD_TYPE STREQUAL "Debug")
  link_directories(${CMAKE_SOURCE_DIR}/duckdb/build/debug/src)
  message("link debug mode duckdb")
else()
  link_directories(${CMAKE_SOURCE_DIR}/duckdb/build/release/src)
  message("link release mode duckdb")
endif()

add_executable(starce main.cpp)
target_link_libraries(starce duckdb)