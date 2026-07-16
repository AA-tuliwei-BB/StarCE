#!/usr/bin/env python3
"""
TestLpBound — Build Time, Estimate Time, and Accuracy tests for the LpBound method

Connects LpBound's statistics build time, cardinality estimation time, and JOBLightRanges subquery accuracy
to the StarCE experiment system, results saved to experiment/checkpoint/LpBound/.

Usage:
    cd experiment/
    conda activate TestEnv          # current project environment (for running this script)
    python TestLpBound.py           # run all (Build + Estimate)
    python TestLpBound.py --build-only
    python TestLpBound.py --est-only
    python TestLpBound.py --accuracy           # additionally run JOBLightRanges subquery accuracy estimation
    python TestLpBound.py --accuracy --est-only  # only Estimate + accuracy estimation

Depends on: conda environment 'lpbound' must be created and configured (see methods/LpBound setup instructions)
"""

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ============================================================
# Path configuration
# ============================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
LPBOUND_DIR = PROJECT_ROOT / "methods" / "LpBound"
CHECKPOINT_DIR = SCRIPT_DIR / "checkpoint" / "LpBound"
RESULT_FILE = CHECKPOINT_DIR / "result.txt"

# LpBound → StarCE benchmark  name mapping
BENCHMARK_MAP = {
    "stats": "STATS",
    "joblight": "JOBLight",
    "jobrange": "JOBLightRanges",
    "jobjoin": "JobJoin",
    "subgraph_matching": "SubgraphMatching",
}

# Build Time  benchmark list (all 5 datasets)
BUILD_BENCHMARKS = ["stats", "joblight", "jobrange", "jobjoin", "subgraph_matching"]

# Estimate Time  benchmark list (3 supported by C++ binary)
EST_BENCHMARKS = ["stats", "joblight", "jobjoin"]

# JOBLightRanges subquery accuracy estimation
JOBLR_SUBQUERY_FILE = PROJECT_ROOT / "Benchmark" / "workloads" / "JOBLightRanges" / "subquery" / "subquery.sql"
JOBLR_OUTPUT_FILE = PROJECT_ROOT / "Benchmark" / "workloads" / "JOBLightRanges" / "subquery" / "result" / "lpbound.txt"


def ensure_lpbound_environment() -> bool:
    """
    Check and fix common LpBound environment issues.
    Returns True if environment is ready, False if manual intervention is needed.
    """
    all_ok = True

    # 1. Case-sensitive CSV symlinks
    for dir_name, csv_source in [
        ("stats", LPBOUND_DIR / "data" / "datasets" / "stats"),
        ("imdb", LPBOUND_DIR / "data" / "datasets" / "imdb"),
    ]:
        if not csv_source.is_dir():
            log(f"  [WARN] CSV directory does not exist: {csv_source}")
            all_ok = False
            continue
        created = []
        for f in csv_source.iterdir():
            if not f.suffix == ".csv":
                continue
            lower_name = f.name.lower()
            if f.name != lower_name:
                lower_path = f.with_name(lower_name)
                if not lower_path.exists():
                    lower_path.symlink_to(f.name)
                    created.append(f"  {f.name} -> {lower_name}")
        if created:
            log(f"  Created lowercase symlinks ({dir_name}):")
            for c in created:
                log(c)

    # 2. C++ binary
    cpp_bin = LPBOUND_DIR / "src/lpbound/cpp_solver/lpbound_parallel/build/lpbound_parallel"
    if not cpp_bin.exists():
        log(f"  [WARN] C++ binary not found: {cpp_bin}")
        log(f"  Build instructions: cd {LPBOUND_DIR}/src/lpbound/cpp_solver/lpbound_parallel && bash compile.sh")
        all_ok = False

    return all_ok


def ensure_dirs():
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


def log(msg: str, to_console: bool = True):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    with open(RESULT_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    if to_console:
        print(line)


def run_lpbound_module(module_name: str, *extra_args) -> subprocess.CompletedProcess:
    """Run a Python module in the lpbound conda environment"""
    cmd = [
        "conda", "run", "-n", "lpbound", "python", "-c",
        f"import sys; sys.path.insert(0, 'src'); {module_name}",
    ]
    return subprocess.run(
        cmd,
        cwd=str(LPBOUND_DIR),
        capture_output=True,
        text=True,
        timeout=3600,
    )


# ============================================================
# Build Time
# ============================================================

def _run_build_benchmark(benchmark: str, p_max: int) -> Optional[float]:
    """Run a single build test, return overall time (seconds), None on failure."""
    import tempfile

    code = f"""
import sys, time, json
sys.path.insert(0, 'src')
from lpbound.config.lpbound_config import LpBoundConfig
from lpbound.acyclic.lpbound import build_lpbound_statistics
from lpbound.cyclic.stats_generator_by_duckdb import build_subgraph_matching_statistics
from lpbound.utils.sql_execution import get_overall_time

cfg = LpBoundConfig(
    benchmark_name='{benchmark}',
    num_mcvs=5000,
    num_buckets=128,
    p_max={p_max},
)
t0 = time.perf_counter()
time_dict = build_subgraph_matching_statistics(cfg) if '{benchmark}' == 'subgraph_matching' else build_lpbound_statistics(cfg)
elapsed = time.perf_counter() - t0
overall = get_overall_time(time_dict)
print(json.dumps({{"benchmark": "{benchmark}", "p_max": {p_max}, "overall": overall, "wall": elapsed}}))
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        tmp_path = f.name

    try:
        proc = subprocess.run(
            ["conda", "run", "-n", "lpbound", "python", tmp_path],
            cwd=str(LPBOUND_DIR),
            capture_output=True,
            text=True,
            timeout=3600,
        )

        if proc.returncode != 0:
            log(f"    [ERROR] failed: {proc.stderr[-300:] if proc.stderr else 'unknown'}")
            return None

        for line in proc.stdout.splitlines():
            if line.startswith('{"benchmark"'):
                data = json.loads(line)
                log(f"    -> overall={data['overall']:.1f}s (wall: {data['wall']:.1f}s)")
                return data["overall"]
        return None
    finally:
        os.unlink(tmp_path)


def run_build_time() -> dict:
    """
    Run Build Time experiments.
    For each benchmark, use p_max=1 (L1) and p_max=10 (all norms) configurations,
    call build_lpbound_statistics() to measure time.

    Returns: { l1: {benchmark: seconds}, all: {benchmark: seconds} }
    """
    log("=" * 60)
    log("  Build Time — Statistics build time")
    log("=" * 60)

    results_l1 = {}
    results_all = {}

    for p_max, label, results_dict in [
        (1, "L1 only", results_l1),
        (10, "All norms (L0-L10+Linf)", results_all),
    ]:
        log(f"\n--- {label} ---")
        for benchmark in BUILD_BENCHMARKS:
            display_name = BENCHMARK_MAP.get(benchmark, benchmark)
            log(f"  Building stats for {display_name} ({benchmark})...")
            result = _run_build_benchmark(benchmark, p_max)
            results_dict[benchmark] = result

    return {"l1": results_l1, "all": results_all}


# ============================================================
# Estimate Time
# ============================================================

def run_estimate_time() -> dict:
    """
    Run Estimate Time experiments.
    Call C++ lpbound_parallel binary, run sequential and parallel modes separately.

    Returns: { benchmark: { "sequential_ms": float, "parallel_ms": float,
                        "build_us": float, "solve_us": float,
                        "total_subqueries": int } }
    """
    log("\n" + "=" * 60)
    log("  Estimate Time — Cardinality estimation time")
    log("=" * 60)

    cpp_bin = LPBOUND_DIR / "src/lpbound/cpp_solver/lpbound_parallel/build/lpbound_parallel"
    input_dir = LPBOUND_DIR / "src/lpbound/cpp_solver/lpbound_parallel/input_data"
    raw_dir = LPBOUND_DIR / "results/estimation_time/raw_results"
    raw_dir.mkdir(parents=True, exist_ok=True)

    if not cpp_bin.exists():
        log(f"[ERROR] C++ binary not found: {cpp_bin}")
        log(f"  Build instructions: cd {LPBOUND_DIR}/src/lpbound/cpp_solver/lpbound_parallel && bash compile.sh")
        return {}

    # Check which benchmarks have input data
    available = [b for b in EST_BENCHMARKS if (input_dir / b).is_dir()]
    missing = [b for b in EST_BENCHMARKS if not (input_dir / b).is_dir()]
    if missing:
        log(f"  Benchmarks missing input data (will be skipped): {missing}")
        log(f"  Generation method: conda activate lpbound && python src/lpbound/cpp_solver/lpbound_parallel/create_input_files.py")
    if not available:
        log("[ERROR] No benchmarks have input data")
        return {}

    log(f"  Available benchmarks: {available}")

    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = "8"

    # --- Sequential ---
    log("\n  Running sequential mode (OMP_NUM_THREADS=8)...")
    log("  (processing all benchmarks may take a few minutes)")
    proc_seq = subprocess.run(
        [str(cpp_bin), "--sequential",
         "--input-dir", str(input_dir),
         "--output-dir", str(raw_dir)],
        cwd=str(LPBOUND_DIR),
        capture_output=True,
        text=True,
        timeout=1200,  # 20  minute timeout
        env=env,
    )
    if proc_seq.returncode != 0:
        log(f"  [ERROR] Sequential  mode failed (exit={proc_seq.returncode}): {proc_seq.stderr[-500:] if proc_seq.stderr else ''}")
    else:
        log("  Sequential  mode completed")

    # --- Parallel ---
    log("  Running parallel mode (OMP_NUM_THREADS=8)...")
    proc_par = subprocess.run(
        [str(cpp_bin), "--parallel",
         "--input-dir", str(input_dir),
         "--output-dir", str(raw_dir)],
        cwd=str(LPBOUND_DIR),
        capture_output=True,
        text=True,
        timeout=1200,
        env=env,
    )
    if proc_par.returncode != 0:
        log(f"  [ERROR] Parallel  mode failed (exit={proc_par.returncode}): {proc_par.stderr[-500:] if proc_par.stderr else ''}")
    else:
        log("  Parallel  mode completed")

    # --- Parse results ---
    results = {}
    for benchmark in available:
        seq_file = raw_dir / f"runtimes_{benchmark}_lpbound_optimized_full_lattice_sequential.txt"
        seq_detailed = raw_dir / f"runtimes_{benchmark}_lpbound_optimized_full_lattice_sequential_detailed.txt"
        par_file = raw_dir / f"runtimes_{benchmark}_lpbound_optimized_full_lattice_parallel.txt"

        if not seq_file.exists():
            log(f"  [WARN] {benchmark}: sequential result file not found, skipping")
            continue

        entry = {}

        # Sequential
        if seq_file.exists():
            with open(seq_file) as f:
                rows = list(csv.DictReader(f))
            if rows:
                runtimes_ns = [float(r["runtime"]) for r in rows]
                entry["sequential_ms"] = round(sum(runtimes_ns) / len(runtimes_ns) / 1_000_000, 4)
                entry["total_subqueries"] = len(rows) // 4  # 4 runs (remove warmup)

        # Sequential detailed (build_time / solve_time)
        if seq_detailed.exists():
            with open(seq_detailed) as f:
                rows = list(csv.DictReader(f))
            if rows:
                build_times = [float(r["build_time"]) for r in rows]
                solve_times = [float(r["solve_time"]) for r in rows]
                entry["build_us"] = round(sum(build_times) / len(build_times) / 1_000, 3)
                entry["solve_us"] = round(sum(solve_times) / len(solve_times) / 1_000, 3)

        # Parallel
        if par_file.exists():
            with open(par_file) as f:
                rows = list(csv.DictReader(f))
            if rows:
                total_times = [float(r["total_time"]) for r in rows]
                entry["parallel_ms"] = round(sum(total_times) / len(total_times) / 1_000_000, 4)
                # Total parallel estimation time: avg per query x num queries -> seconds
                unique_qids = set(r["query_id"] for r in rows)
                entry["num_queries"] = len(unique_qids)
                avg_ns = sum(total_times) / len(total_times)
                entry["total_parallel_s"] = round(avg_ns * len(unique_qids) / 1_000_000_000, 4)

        if entry:
            results[benchmark] = entry

        # Save per-LP estimation time to checkpoint
        if seq_detailed.exists():
            _save_per_lp_time(benchmark, seq_detailed)

    return results


def _save_per_lp_time(benchmark: str, detailed_file: Path) -> None:
    """
    Extract each LP's build+solve time from C++ detailed CSV, write to checkpoint.

    Each row = one LP solve = one cardinality estimation, time unit seconds.
    Multiple runs averaged (skip warmup run_id=1).
    """
    from collections import defaultdict

    with open(detailed_file) as f:
        rows = list(csv.DictReader(f))

    lp_times: dict[tuple[int, int], list[float]] = defaultdict(list)
    for r in rows:
        run = int(r["run_id"])
        if run == 1:  # warmup
            continue
        key = (int(r["query_id"]), int(r["lattice"]))
        total_ns = float(r["build_time"]) + float(r["solve_time"])
        lp_times[key].append(total_ns)

    display = BENCHMARK_MAP.get(benchmark, benchmark)
    output = CHECKPOINT_DIR / f"estimate_time_{display}.txt"
    with open(output, "w") as f:
        for key in sorted(lp_times.keys()):
            avg_ns = sum(lp_times[key]) / len(lp_times[key])
            f.write(f"{avg_ns / 1_000_000_000:.9f}\n")

    log(f"  Per-LP time saved to {output} ({len(lp_times)} LPs)")


# ============================================================
# Accuracy — JOBLightRanges subquery cardinality estimation
# ============================================================

def run_accuracy() -> dict:
    """
    Run LpBound estimation on each of JOBLightRanges's 8292 subqueries,
    write results to Benchmark/workloads/JOBLightRanges/subquery/result/lpbound.txt,
    also back up to checkpoint/LpBound/.

    Returns: { "subqueries": int, "success": int, "failed": int,
             "time_min": float, "output": str }
    """
    log("\n" + "=" * 60)
    log("  Accuracy — JOBLightRanges subquery cardinality estimation")
    log("=" * 60)

    script_path = LPBOUND_DIR / "benchmarks" / "experiments" / "estimate_subqueries.py"
    if not script_path.exists():
        log(f"[ERROR] Script not found: {script_path}")
        return {}

    JOBLR_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    proc = subprocess.run(
        [
            "conda", "run", "-n", "lpbound", "python",
            str(script_path),
            "--benchmark", "jobrange",
            "--subquery-file", str(JOBLR_SUBQUERY_FILE),
            "--output", str(JOBLR_OUTPUT_FILE),
            "--checkpoint-interval", "500",
        ],
        cwd=str(LPBOUND_DIR),
        capture_output=True,
        text=True,
        timeout=3600,
    )
    elapsed = time.perf_counter() - t0

    # Output the script's stdout
    for line in proc.stdout.splitlines():
        if line.strip():
            log(f"  {line.strip()}")

    result = {}
    if proc.returncode != 0:
        log(f"[ERROR] Accuracy estimation failed (exit={proc.returncode})")
        if proc.stderr:
            for line in proc.stderr.splitlines()[-10:]:
                log(f"  [stderr] {line.strip()}")
        return result

    # Parse final output for statistics
    for line in proc.stdout.splitlines():
        if "done!" in line:
            m = re.search(r'Total (\d+)  entries, took ([\d.]+) min', line)
            if m:
                result["subqueries"] = int(m.group(1))
                result["time_min"] = float(m.group(2))
        elif "Success:" in line:
            m = re.search(r'Success: (\d+).*failed: (\d+)', line)
            if m:
                result["success"] = int(m.group(1))
                result["failed"] = int(m.group(2))

    result["wall_time_min"] = round(elapsed / 60, 1)

    # Backup to checkpoint
    if JOBLR_OUTPUT_FILE.exists():
        ckpt_copy = CHECKPOINT_DIR / "lpbound_JOBLightRanges.txt"
        shutil.copy2(JOBLR_OUTPUT_FILE, ckpt_copy)
        log(f"  Backed up to: {ckpt_copy}")

    return result


# ============================================================
# Summary & Save
# ============================================================

def run_space_usage() -> dict:
    """
    Query DuckDB norms table row count, compute statistics space usage.
    Returns: { benchmark: bytes }
    """
    import tempfile

    log("\n" + "=" * 60)
    log("  Space Usage — Statistics space usage")
    log("=" * 60)

    code = """
import sys, json
sys.path.insert(0, 'src')
from lpbound.config.lpbound_config import LpBoundConfig
from lpbound.config.benchmark_schema import load_benchmark_schema
from lpbound.duckdb_adapter.duckdb_manager import DatabaseManager

results = {}
for benchmark in ['stats', 'joblight', 'jobrange', 'jobjoin']:
    cfg = LpBoundConfig(benchmark_name=benchmark)
    schema = load_benchmark_schema(cfg)
    con = DatabaseManager(schema).create_or_load_db(read_only=True)
    num_rows = con.execute('SELECT COUNT(*) FROM norms').fetchone()[0]
    num_bytes = num_rows * 12 * 8  # 12 lp-norms x 8 bytes each
    con.close()
    results[benchmark] = num_bytes
print(json.dumps(results))
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        tmp_path = f.name

    try:
        proc = subprocess.run(
            ["conda", "run", "-n", "lpbound", "python", tmp_path],
            cwd=str(LPBOUND_DIR),
            capture_output=True,
            text=True,
            timeout=300,
        )

        results = {}
        if proc.returncode != 0:
            log(f"  [ERROR] Space usage failed: {proc.stderr[-300:] if proc.stderr else 'unknown'}")
            return results

        # Take the last JSON line (preceding lines are build_lpbound_statistics progress output)
        for line in reversed(proc.stdout.splitlines()):
            line = line.strip()
            if line.startswith('{'):
                data = json.loads(line)
                for bm, num_bytes in data.items():
                    display = BENCHMARK_MAP.get(bm, bm)
                    mb = num_bytes / 1e6
                    results[bm] = num_bytes
                    log(f"  {display}: {mb:.2f} MB ({num_bytes:,} bytes)")
                break
        return results
    finally:
        os.unlink(tmp_path)


def save_results(build: dict, est: dict, space: dict = {}, accuracy: dict = {}):
    """Save results to checkpoint/LpBound/"""
    ensure_dirs()

    # --- result.txt ---
    # Clear and rewrite
    RESULT_FILE.write_text("")
    log("LpBound experiment results", to_console=True)
    log(f"Time: {datetime.now().isoformat()}", to_console=True)
    log("", to_console=True)

    # Build Time table
    log("--- Build Time (seconds) ---")
    log(f"  {'Benchmark':<20} {'L1 only':>10} {'All norms':>10}")
    log("  " + "-" * 40)
    for b in BUILD_BENCHMARKS:
        l1 = build["l1"].get(b)
        al = build["all"].get(b)
        l1_s = f"{l1:.1f}" if l1 is not None else "N/A"
        al_s = f"{al:.1f}" if al is not None else "N/A"
        log(f"  {BENCHMARK_MAP.get(b, b):<20} {l1_s:>10} {al_s:>10}")

    # Estimate Time table
    log("\n--- Estimate Time ---")
    log(f"  {'Benchmark':<20} {'Par avg(ms)':>12} {'Queries':>8} {'Total(s)':>10} {'#Subqueries':>12}")
    log("  " + "-" * 67)
    est_benchmarks = sorted(set(list(est.keys()) + [b for b in EST_BENCHMARKS if b not in est]))
    for b in est_benchmarks:
        e = est.get(b, {})
        if not e:
            log(f"  {BENCHMARK_MAP.get(b, b):<20} {'N/A':>12} {'N/A':>8} {'N/A':>10} {'N/A':>12}")
        else:
            log(
                f"  {BENCHMARK_MAP.get(b, b):<20} "
                f"{e.get('parallel_ms', 'N/A'):>12} "
                f"{e.get('num_queries', 'N/A'):>8} "
                f"{e.get('total_parallel_s', 'N/A'):>10} "
                f"{e.get('total_subqueries', 'N/A'):>12}"
            )

    log("\n  * Par avg = parallel mode average time per query (ms)")
    log("  * Total = Par avg × Queries, i.e., total estimation time (s)")

    # Accuracy table
    if accuracy and accuracy.get("subqueries"):
        log("\n--- JOBLightRanges subquery accuracy estimation ---")
        log(f"  Subquery count: {accuracy.get('subqueries', 'N/A')}")
        log(f"  Success: {accuracy.get('success', 'N/A')}")
        log(f"  failed: {accuracy.get('failed', 'N/A')}")
        log(f"  Time: {accuracy.get('time_min', 'N/A')} min")
        log(f"  Output: Benchmark/workloads/JOBLightRanges/subquery/result/lpbound.txt")

    # --- benchmark_times.csv ---
    # Keep CSV format consistent with existing experiment system
    # Read existing CSV first, avoid overwriting old values when new data is empty
    csv_path = CHECKPOINT_DIR / "benchmark_times.csv"
    old_rows: dict[str, dict[str, str]] = {}
    if csv_path.exists():
        with open(csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                old_rows[row["Benchmark"]] = row
        cols = list(old_rows[next(iter(old_rows))].keys()) if old_rows else []
        if "BuildTime_L1" not in cols or "BuildTime_All" not in cols:
            old_rows.clear()  # Old format, incompatible, regenerate

    # Use display name as key uniformly, avoid internal/display name duplicates
    display_names = set(old_rows.keys())
    for d in [build["l1"], build["all"], est, space]:
        for k in d:
            display_names.add(BENCHMARK_MAP.get(k, k))

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Benchmark", "BuildTime_L1", "BuildTime_All",
            "EstSeq_ms", "EstPar_ms", "EstBuild_us", "EstSolve_us", "NumSubqueries",
            "StatisticsSize",
        ])
        # internal -> display reverse mapping, for looking up internal data from display name
        display_to_internal = {v: k for k, v in BENCHMARK_MAP.items()}
        for display_name in sorted(display_names):
            internal = display_to_internal.get(display_name, display_name)
            l1 = build["l1"].get(internal)
            al = build["all"].get(internal)
            e = est.get(internal, {})
            sz = space.get(internal)
            old = old_rows.get(display_name, {})

            # New data first, fallback to old data if empty
            l1_s = f"{l1:.1f}" if l1 is not None else old.get("BuildTime_L1", "")
            al_s = f"{al:.1f}" if al is not None else old.get("BuildTime_All", "")

            writer.writerow([
                display_name,
                l1_s,
                al_s,
                e.get("sequential_ms", "") or old.get("EstSeq_ms", ""),
                e.get("parallel_ms", "") or old.get("EstPar_ms", ""),
                e.get("build_us", "") or old.get("EstBuild_us", ""),
                e.get("solve_us", "") or old.get("EstSolve_us", ""),
                e.get("total_subqueries", "") or old.get("NumSubqueries", ""),
                f"{sz:.0f}" if sz is not None else old.get("StatisticsSize", ""),
            ])
    log(f"\n  CSV saved: {csv_path}")

    # --- JSON details ---
    # Read existing JSON first, avoid overwriting old build_time when new data is empty
    json_path = CHECKPOINT_DIR / "timing_details.json"
    old_build_time = {}
    if json_path.exists():
        try:
            old_payload = json.loads(json_path.read_text())
            old_build_time = old_payload.get("build_time", {})
        except (json.JSONDecodeError, KeyError):
            pass

    merged_build = {}
    for b in BUILD_BENCHMARKS:
        new_l1 = build["l1"].get(b)
        new_all = build["all"].get(b)
        old = old_build_time.get(b, {})
        merged_build[b] = {
            "l1": new_l1 if new_l1 is not None else old.get("l1"),
            "all": new_all if new_all is not None else old.get("all"),
        }

    payload = {
        "timestamp": datetime.now().isoformat(),
        "build_time": merged_build,
        "estimate_time": est,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    log(f"  JSON saved: {json_path}")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="LpBound Build Time & Estimate Time test")
    parser.add_argument("--build-only", action="store_true", help="Run Build Time only")
    parser.add_argument("--est-only", action="store_true", help="Run Estimate Time only")
    parser.add_argument("--accuracy", action="store_true",
                        help="Run JOBLightRanges subquery accuracy estimation (about 10 minutes)")
    args = parser.parse_args()

    run_build = not args.est_only
    run_est = not args.build_only
    run_acc = args.accuracy

    ensure_dirs()

    log("Checking LpBound environment...")
    if not ensure_lpbound_environment():
        log("[WARN] Environment check found issues, some features may be unavailable")

    build_results = {"l1": {}, "all": {}}
    est_results = {}
    space_results = {}
    accuracy_results = {}

    t_start = time.perf_counter()

    if run_build:
        build_results = run_build_time()

    if run_est:
        est_results = run_estimate_time()

    space_results = run_space_usage()

    if run_acc:
        accuracy_results = run_accuracy()

    save_results(build_results, est_results, space_results, accuracy_results)

    elapsed = time.perf_counter() - t_start
    log(f"\nTotal elapsed: {elapsed:.0f}s")


if __name__ == "__main__":
    main()
