#!/bin/bash
set -euo pipefail

MODE="${1:-release}"
JOBS="${2:-}"

UNAME_S="$(uname -s 2>/dev/null || echo unknown)"
UNAME_M="$(uname -m 2>/dev/null || echo unknown)"
DUCKDB_PLATFORM=""
if [[ "${UNAME_S}" == "Linux" && "${UNAME_M}" == "x86_64" ]]; then
  DUCKDB_PLATFORM="linux_amd64"
elif [[ "${UNAME_S}" == "Linux" && ( "${UNAME_M}" == "aarch64" || "${UNAME_M}" == "arm64" ) ]]; then
  DUCKDB_PLATFORM="linux_arm64"
elif [[ "${UNAME_S}" == "Darwin" && "${UNAME_M}" == "x86_64" ]]; then
  DUCKDB_PLATFORM="osx_amd64"
elif [[ "${UNAME_S}" == "Darwin" && ( "${UNAME_M}" == "arm64" || "${UNAME_M}" == "aarch64" ) ]]; then
  DUCKDB_PLATFORM="osx_arm64"
fi

case "${MODE}" in
  debug)
    CMAKE_BUILD_TYPE="Debug"
    DUCKDB_BUILD_DIR="duckdb/build/debug"
    STARCE_BUILD_DIR="build-debug"
    DUCKDB_DEBUG_CMAKE_ARGS=(
      -DENABLE_SANITIZER=FALSE
      -DENABLE_UBSAN=FALSE
    )
    ;;
  release)
    CMAKE_BUILD_TYPE="Release"
    DUCKDB_BUILD_DIR="duckdb/build/release"
    STARCE_BUILD_DIR="build"
    DUCKDB_DEBUG_CMAKE_ARGS=()
    ;;
  *)
    echo "Usage: $0 [debug|release] [jobs]"
    echo "Example: $0 debug"
    echo "Example: $0 release 8"
    exit 2
    ;;
esac

if [[ -z "${JOBS}" ]]; then
  if command -v nproc >/dev/null 2>&1; then
    JOBS="$(nproc)"
  else
    JOBS="8"
  fi
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo "Build mode: ${MODE} (CMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}), parallelism: ${JOBS}"

# Build DuckDB library
echo "Building DuckDB library..."
mkdir -p "${DUCKDB_BUILD_DIR}"
DUCKDB_CMAKE_ARGS=(
  -DCMAKE_BUILD_TYPE="${CMAKE_BUILD_TYPE}"
  -DBUILD_UNITTESTS=FALSE
  -DBUILD_BENCHMARKS=FALSE
)
if [[ -n "${DUCKDB_PLATFORM}" ]]; then
  DUCKDB_CMAKE_ARGS+=(-DDUCKDB_EXPLICIT_PLATFORM="${DUCKDB_PLATFORM}")
fi
cmake -S duckdb -B "${DUCKDB_BUILD_DIR}" "${DUCKDB_CMAKE_ARGS[@]}" "${DUCKDB_DEBUG_CMAKE_ARGS[@]}"
cmake --build "${DUCKDB_BUILD_DIR}" -j "${JOBS}"

# Build StarCE
echo "Building StarCE..."
mkdir -p "${STARCE_BUILD_DIR}"
cmake -S . -B "${STARCE_BUILD_DIR}" -DCMAKE_BUILD_TYPE="${CMAKE_BUILD_TYPE}"
cmake --build "${STARCE_BUILD_DIR}" -j "${JOBS}"

# Copy to running_space for ExperimentRunner
cp "${STARCE_BUILD_DIR}/starce" experiment/running_space/starce

echo "Build complete!"
