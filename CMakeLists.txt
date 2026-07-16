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

#     # 启用 ASan
#     if (CMAKE_CXX_COMPILER_ID STREQUAL "GNU" OR CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
#         set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fsanitize=address")
#         set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -fsanitize=address")
#     endif()

#     # 添加子目录：starce 和 duckdb
#     add_subdirectory(duckdb)

#     # 添加头文件路径
#     include_directories(
#         ${CMAKE_SOURCE_DIR}/duckdb/src/include
#         ${CMAKE_SOURCE_DIR}/starce/include
#     )

#     # 添加可执行文件
#     add_executable(starce main.cpp)

#     # 链接库
#     target_link_libraries(starce duckdb)

#     # 显式链接 ASan 运行时库
#     if (CMAKE_CXX_COMPILER_ID STREQUAL "GNU" OR CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
#         target_link_libraries(starce -fsanitize=address)
#     endif()
# else()
#     include_directories(duckdb/src/include)
#     link_directories(duckdb/build/release/src)
#     add_executable(starce main.cpp)
#     target_link_libraries(starce duckdb)
# endif()