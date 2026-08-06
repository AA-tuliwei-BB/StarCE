#!/usr/bin/env python3
"""
Collect LpBound EstimateTime and BuildTime on various datasets

Usage:
    cd methods/LpBound  # run from project root
    conda activate lpbound
    python collect_timings.py              # Run all
    python collect_timings.py --build-only # BuildTime only
    python collect_timings.py --est-only   # EstimateTime only
"""

import argparse
import subprocess
import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from lpbound.config.paths import LpBoundPaths
from lpbound.config.lpbound_config import LpBoundConfig
from lpbound.acyclic.lpbound import build_lpbound_statistics
from lpbound.cyclic.stats_generator_by_duckdb import build_subgraph_matching_statistics
from lpbound.utils.sql_execution import get_overall_time


# ============================================================
# Configuration
# ============================================================

BUILD_BENCHMARKS = ["stats", "joblight", "jobrange", "jobjoin", "subgraph_matching"]
EST_BENCHMARKS = ["stats", "joblight", "jobjoin"]  # The three supported by C++ binary

CPP_BINARY = LpBoundPaths.PROJ_ROOT_DIR / "src/lpbound/cpp_solver/lpbound_parallel/build/lpbound_parallel"
INPUT_DATA_DIR = LpBoundPaths.PROJ_ROOT_DIR / "src/lpbound/cpp_solver/lpbound_parallel/input_data"
RAW_RESULTS_DIR = LpBoundPaths.RESULTS_DIR / "estimation_time" / "raw_results"
OUTPUT_FILE = LpBoundPaths.PROJ_ROOT_DIR / "timing_results.json"

N_RUNS = 5  # Number of C++ binary runs (first is warmup)


# ============================================================
# BuildTime
# ============================================================

def run_build_time(benchmarks: list[str]) -> dict:
    """
    Run build time experiment, return { benchmark: { "l1": seconds, "all": seconds } }
    """
    print("=" * 60)
    print("  Build Time (statistics build time)")
    print("=" * 60)

    results = {}

    # --- p_max=1 (L1 only) ---
    print("\n--- LpBound L1 only ---")
    for benchmark in benchmarks:
        cfg = LpBoundConfig(
            benchmark_name=benchmark,
            num_mcvs=5000,
            num_buckets=128,
            p_max=1,
            include_l0=False,
            include_l_inf=False,
        )
        print(f"  Building stats for {benchmark} (L1 only)...")
        t0 = time.perf_counter()
        if benchmark == "subgraph_matching":
            time_dict = build_subgraph_matching_statistics(cfg)
        else:
            time_dict = build_lpbound_statistics(cfg)
        elapsed = time.perf_counter() - t0
        overall = get_overall_time(time_dict)
        print(f"    -> {overall:.1f}s (wall: {elapsed:.1f}s)")
        results.setdefault(benchmark, {})["l1"] = round(overall, 1)

    # --- p_max=10 (all lp-norms) ---
    print("\n--- LpBound all lp-norms (L0-L10 + Linf) ---")
    for benchmark in benchmarks:
        cfg = LpBoundConfig(
            benchmark_name=benchmark,
            num_mcvs=5000,
            num_buckets=128,
            p_max=10,
        )
        print(f"  Building stats for {benchmark} (all norms)...")
        t0 = time.perf_counter()
        if benchmark == "subgraph_matching":
            time_dict = build_subgraph_matching_statistics(cfg)
        else:
            time_dict = build_lpbound_statistics(cfg)
        elapsed = time.perf_counter() - t0
        overall = get_overall_time(time_dict)
        print(f"    -> {overall:.1f}s (wall: {elapsed:.1f}s)")
        results.setdefault(benchmark, {})["all"] = round(overall, 1)

    return results


# ============================================================
# EstimateTime
# ============================================================

def run_estimate_time(run_parallel: bool) -> None:
    """Run C++ estimate time experiment"""
    RAW_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    mode_flag = "--parallel" if run_parallel else "--sequential"
    mode_name = "parallel" if run_parallel else "sequential"

    cmd = [
        str(CPP_BINARY),
        mode_flag,
        "--input-dir", str(INPUT_DATA_DIR),
        "--output-dir", str(RAW_RESULTS_DIR),
    ]

    print(f"\n  Running C++ binary in {mode_name} mode (OMP_NUM_THREADS=8)...")
    print(f"  Command: {' '.join(cmd)}")

    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = "8"

    result = subprocess.run(
        cmd,
        cwd=str(LpBoundPaths.PROJ_ROOT_DIR),
        capture_output=True,
        text=True,
        env=env,
    )

    if result.returncode != 0:
        print(f"  [ERROR] C++ binary failed (exit {result.returncode})")
        print(f"  stdout: {result.stdout}")
        print(f"  stderr: {result.stderr}")
        return

    # Print key lines from C++ output
    for line in result.stdout.splitlines():
        if any(kw in line.lower() for kw in ["running", "query", "finished", "loaded"]):
            print(f"    {line.strip()}")


def parse_estimate_results() -> dict:
    """
    Parse CSV files in raw_results, return:
    { benchmark: {"sequential_ms": float, "parallel_ms": float, "build_us": float, "solve_us": float} }
    """
    import csv

    results = {}

    for benchmark in EST_BENCHMARKS:
        results[benchmark] = {}

        # --- sequential ---
        seq_file = RAW_RESULTS_DIR / f"runtimes_{benchmark}_lpbound_optimized_full_lattice_sequential.txt"
        seq_detailed = RAW_RESULTS_DIR / f"runtimes_{benchmark}_lpbound_optimized_full_lattice_sequential_detailed.txt"

        if seq_file.exists():
            with open(seq_file) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            if rows:
                # runtime column is nanoseconds, convert to milliseconds
                runtimes = [float(r["runtime"]) for r in rows]
                avg_ns = sum(runtimes) / len(runtimes)
                results[benchmark]["sequential_ms"] = round(avg_ns / 1_000_000, 4)
                results[benchmark]["sequential_count"] = len(rows)

        if seq_detailed.exists():
            with open(seq_detailed) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            if rows:
                build_times = [float(r["build_time"]) for r in rows]
                solve_times = [float(r["solve_time"]) for r in rows]
                results[benchmark]["build_us"] = round(
                    sum(build_times) / len(build_times) / 1_000, 3
                )
                results[benchmark]["solve_us"] = round(
                    sum(solve_times) / len(solve_times) / 1_000, 3
                )

        # --- parallel ---
        par_file = RAW_RESULTS_DIR / f"runtimes_{benchmark}_lpbound_optimized_full_lattice_parallel.txt"

        if par_file.exists():
            with open(par_file) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            if rows:
                total_times = [float(r["total_time"]) for r in rows]
                avg_ns = sum(total_times) / len(total_times)
                results[benchmark]["parallel_ms"] = round(avg_ns / 1_000_000, 4)
                results[benchmark]["parallel_count"] = len(rows)

                # Total parallel estimation time: per-query avg * query count -> seconds
                unique_qids = set(r["query_id"] for r in rows)
                num_queries = len(unique_qids)
                results[benchmark]["num_queries"] = num_queries
                results[benchmark]["total_parallel_s"] = round(
                    avg_ns * num_queries / 1_000_000_000, 4
                )

    return results


# ============================================================
# Summary output
# ============================================================

def print_summary(build_results: dict, est_results: dict) -> None:
    """Print summary table"""
    print("\n")
    print("=" * 60)
    print("  Results summary")
    print("=" * 60)

    # Build Time
    print("\n📦 Build Time (seconds)")
    print("-" * 45)
    print(f"  {'Benchmark':<20} {'L1 only':>10} {'All norms':>10}")
    print("  " + "-" * 40)
    for b in BUILD_BENCHMARKS:
        if b in build_results:
            d = build_results[b]
            print(f"  {b:<20} {d.get('l1', 'N/A'):>10} {d.get('all', 'N/A'):>10}")
        else:
            print(f"  {b:<20} {'N/A':>10} {'N/A':>10}")

    # Estimate Time
    print(f"\n⚡ Estimate Time (per query avg / total, averaged over {N_RUNS - 1} runs)")
    print("-" * 80)
    print(f"  {'Benchmark':<12} {'Par avg(ms)':>12} {'Queries':>8} {'Total(s)':>10} {'Build(us)':>10} {'Solve(us)':>10}")
    print("  " + "-" * 67)
    for b in EST_BENCHMARKS:
        if b in est_results:
            d = est_results[b]
            print(
                f"  {b:<12} "
                f"{d.get('parallel_ms', 'N/A'):>12} "
                f"{d.get('num_queries', 'N/A'):>8} "
                f"{d.get('total_parallel_s', 'N/A'):>10} "
                f"{d.get('build_us', 'N/A'):>10} "
                f"{d.get('solve_us', 'N/A'):>10}"
            )

    print("\n  * Par avg = parallel mode per-query average time (ms)")
    print("  * Total = Par avg x Queries, i.e., full estimation total time (s)")
    print("  * Build/Solve from sequential detailed file (us/unit)")


def save_results(build_results: dict, est_results: dict, output_path: Path) -> None:
    """Save results to JSON file"""
    payload = {
        "timestamp": datetime.now().isoformat(),
        "build_time": build_results,
        "estimate_time": est_results,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"\nResults saved to: {output_path}")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Collect LpBound EstimateTime and BuildTime")
    parser.add_argument("--build-only", action="store_true", help="Run BuildTime only")
    parser.add_argument("--est-only", action="store_true", help="Run EstimateTime only")
    args = parser.parse_args()

    run_build = not args.est_only
    run_est = not args.build_only

    # Check C++ binary
    if run_est and not CPP_BINARY.exists():
        print(f"[ERROR] C++ binary does not exist: {CPP_BINARY}")
        print("  Please compile first: cd src/lpbound/cpp_solver/lpbound_parallel && bash compile.sh")
        sys.exit(1)

    build_results = {}
    est_results = {}

    t_start = time.perf_counter()

    if run_build:
        build_results = run_build_time(BUILD_BENCHMARKS)

    if run_est:
        print("\n" + "=" * 60)
        print("  Estimate Time (estimation time)")
        print("=" * 60)
        print("\n  Running sequential mode...")
        run_estimate_time(run_parallel=False)
        print("\n  Running parallel mode...")
        run_estimate_time(run_parallel=True)

        est_results = parse_estimate_results()

    # Summary output
    if build_results or est_results:
        print_summary(build_results, est_results)
        save_results(build_results, est_results, OUTPUT_FILE)

    elapsed = time.perf_counter() - t_start
    print(f"\nTotal time: {elapsed:.0f}s")


if __name__ == "__main__":
    main()
