#!/usr/bin/env python3
"""
TestLpBound — LpBound 方法的 Build Time、Estimate Time 和 Accuracy 测试

将 LpBound 的统计信息构建时间、基数估计时间和 JOBLightRanges 子查询精度
接入 StarCE 实验体系，结果保存到 experiment/checkpoint/LpBound/。

使用方法:
    cd experiment/
    conda activate TestEnv          # 当前项目环境（用于运行本脚本）
    python TestLpBound.py           # 运行全部（Build + Estimate）
    python TestLpBound.py --build-only
    python TestLpBound.py --est-only
    python TestLpBound.py --accuracy           # 额外运行 JOBLightRanges 子查询精度估计
    python TestLpBound.py --accuracy --est-only  # 仅 Estimate + 精度估计

依赖: conda 环境 'lpbound' 需已创建并配置好（见 methods/LpBound 的 setup 说明）
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
# 路径配置
# ============================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
LPBOUND_DIR = PROJECT_ROOT / "methods" / "LpBound"
CHECKPOINT_DIR = SCRIPT_DIR / "checkpoint" / "LpBound"
RESULT_FILE = CHECKPOINT_DIR / "result.txt"

# LpBound → StarCE benchmark 名称映射
BENCHMARK_MAP = {
    "stats": "STATS",
    "joblight": "JOBLight",
    "jobrange": "JOBLightRanges",
    "jobjoin": "JobJoin",
    "subgraph_matching": "SubgraphMatching",
}

# Build Time 的 benchmark 列表（全部 5 个数据集）
BUILD_BENCHMARKS = ["stats", "joblight", "jobrange", "jobjoin", "subgraph_matching"]

# Estimate Time 的 benchmark 列表（C++ 二进制支持的 3 个）
EST_BENCHMARKS = ["stats", "joblight", "jobjoin"]

# JOBLightRanges 子查询精度估计
JOBLR_SUBQUERY_FILE = PROJECT_ROOT / "Benchmark" / "workloads" / "JOBLightRanges" / "subquery" / "subquery.sql"
JOBLR_OUTPUT_FILE = PROJECT_ROOT / "Benchmark" / "workloads" / "JOBLightRanges" / "subquery" / "result" / "lpbound.txt"


def ensure_lpbound_environment() -> bool:
    """
    检查并修复 LpBound 环境的常见问题。
    返回 True 表示环境就绪，False 表示需要手动干预。
    """
    all_ok = True

    # 1. 大小写 CSV 符号链接
    for dir_name, csv_source in [
        ("stats", LPBOUND_DIR / "data" / "datasets" / "stats"),
        ("imdb", LPBOUND_DIR / "data" / "datasets" / "imdb"),
    ]:
        if not csv_source.is_dir():
            log(f"  [WARN] CSV 目录不存在: {csv_source}")
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
            log(f"  创建小写符号链接 ({dir_name}):")
            for c in created:
                log(c)

    # 2. C++ 二进制
    cpp_bin = LPBOUND_DIR / "src/lpbound/cpp_solver/lpbound_parallel/build/lpbound_parallel"
    if not cpp_bin.exists():
        log(f"  [WARN] C++ 二进制不存在: {cpp_bin}")
        log(f"  编译方法: cd {LPBOUND_DIR}/src/lpbound/cpp_solver/lpbound_parallel && bash compile.sh")
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
    """在 lpbound conda 环境中运行 Python 模块"""
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
    """运行单个 build 测试，返回 overall time（秒），失败返回 None。"""
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
            log(f"    [ERROR] 失败: {proc.stderr[-300:] if proc.stderr else 'unknown'}")
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
    运行 Build Time 实验。
    对每个 benchmark 分别用 p_max=1 (L1) 和 p_max=10 (all norms) 两种配置，
    调用 build_lpbound_statistics() 测量时间。

    返回: { l1: {benchmark: seconds}, all: {benchmark: seconds} }
    """
    log("=" * 60)
    log("  Build Time — 统计信息构建时间")
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
    运行 Estimate Time 实验。
    调用 C++ lpbound_parallel 二进制，分别运行 sequential 和 parallel 模式。

    返回: { benchmark: { "sequential_ms": float, "parallel_ms": float,
                        "build_us": float, "solve_us": float,
                        "total_subqueries": int } }
    """
    log("\n" + "=" * 60)
    log("  Estimate Time — 基数估计时间")
    log("=" * 60)

    cpp_bin = LPBOUND_DIR / "src/lpbound/cpp_solver/lpbound_parallel/build/lpbound_parallel"
    input_dir = LPBOUND_DIR / "src/lpbound/cpp_solver/lpbound_parallel/input_data"
    raw_dir = LPBOUND_DIR / "results/estimation_time/raw_results"
    raw_dir.mkdir(parents=True, exist_ok=True)

    if not cpp_bin.exists():
        log(f"[ERROR] C++ 二进制不存在: {cpp_bin}")
        log(f"  编译方法: cd {LPBOUND_DIR}/src/lpbound/cpp_solver/lpbound_parallel && bash compile.sh")
        return {}

    # 检查哪些 benchmark 的输入数据存在
    available = [b for b in EST_BENCHMARKS if (input_dir / b).is_dir()]
    missing = [b for b in EST_BENCHMARKS if not (input_dir / b).is_dir()]
    if missing:
        log(f"  缺少输入数据的 benchmark (将跳过): {missing}")
        log(f"  生成方法: conda activate lpbound && python src/lpbound/cpp_solver/lpbound_parallel/create_input_files.py")
    if not available:
        log("[ERROR] 没有任何 benchmark 的输入数据")
        return {}

    log(f"  可用 benchmark: {available}")

    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = "8"

    # --- Sequential ---
    log("\n  Running sequential mode (OMP_NUM_THREADS=8)...")
    log("  (处理所有 benchmark 可能需要几分钟)")
    proc_seq = subprocess.run(
        [str(cpp_bin), "--sequential",
         "--input-dir", str(input_dir),
         "--output-dir", str(raw_dir)],
        cwd=str(LPBOUND_DIR),
        capture_output=True,
        text=True,
        timeout=1200,  # 20 分钟超时
        env=env,
    )
    if proc_seq.returncode != 0:
        log(f"  [ERROR] Sequential 模式失败 (exit={proc_seq.returncode}): {proc_seq.stderr[-500:] if proc_seq.stderr else ''}")
    else:
        log("  Sequential 模式完成")

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
        log(f"  [ERROR] Parallel 模式失败 (exit={proc_par.returncode}): {proc_par.stderr[-500:] if proc_par.stderr else ''}")
    else:
        log("  Parallel 模式完成")

    # --- 解析结果 ---
    results = {}
    for benchmark in available:
        seq_file = raw_dir / f"runtimes_{benchmark}_lpbound_optimized_full_lattice_sequential.txt"
        seq_detailed = raw_dir / f"runtimes_{benchmark}_lpbound_optimized_full_lattice_sequential_detailed.txt"
        par_file = raw_dir / f"runtimes_{benchmark}_lpbound_optimized_full_lattice_parallel.txt"

        if not seq_file.exists():
            log(f"  [WARN] {benchmark}: 未找到 sequential 结果文件，跳过")
            continue

        entry = {}

        # Sequential
        if seq_file.exists():
            with open(seq_file) as f:
                rows = list(csv.DictReader(f))
            if rows:
                runtimes_ns = [float(r["runtime"]) for r in rows]
                entry["sequential_ms"] = round(sum(runtimes_ns) / len(runtimes_ns) / 1_000_000, 4)
                entry["total_subqueries"] = len(rows) // 4  # 4 runs (去除 warmup)

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
                # 总并行估计时间：每查询平均 × 查询数 → 秒
                unique_qids = set(r["query_id"] for r in rows)
                entry["num_queries"] = len(unique_qids)
                avg_ns = sum(total_times) / len(total_times)
                entry["total_parallel_s"] = round(avg_ns * len(unique_qids) / 1_000_000_000, 4)

        if entry:
            results[benchmark] = entry

        # 保存每 LP 估计时间到 checkpoint
        if seq_detailed.exists():
            _save_per_lp_time(benchmark, seq_detailed)

    return results


def _save_per_lp_time(benchmark: str, detailed_file: Path) -> None:
    """
    从 C++ detailed CSV 提取每个 LP 的 build+solve 时间，写入 checkpoint。

    每行 = 一个 LP 求解 = 一次基数估计，时间单位秒。
    对多次 run 取平均（跳过 warmup run_id=1）。
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
# Accuracy — JOBLightRanges 子查询基数估计
# ============================================================

def run_accuracy() -> dict:
    """
    对 JOBLightRanges 的 8292 条子查询逐条运行 LpBound 估计，
    结果写入 Benchmark/workloads/JOBLightRanges/subquery/result/lpbound.txt，
    同时备份到 checkpoint/LpBound/。

    返回: { "subqueries": int, "success": int, "failed": int,
             "time_min": float, "output": str }
    """
    log("\n" + "=" * 60)
    log("  Accuracy — JOBLightRanges 子查询基数估计")
    log("=" * 60)

    script_path = LPBOUND_DIR / "benchmarks" / "experiments" / "estimate_subqueries.py"
    if not script_path.exists():
        log(f"[ERROR] 脚本不存在: {script_path}")
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

    # 输出脚本的 stdout
    for line in proc.stdout.splitlines():
        if line.strip():
            log(f"  {line.strip()}")

    result = {}
    if proc.returncode != 0:
        log(f"[ERROR] 精度估计失败 (exit={proc.returncode})")
        if proc.stderr:
            for line in proc.stderr.splitlines()[-10:]:
                log(f"  [stderr] {line.strip()}")
        return result

    # 解析最终输出获取统计信息
    for line in proc.stdout.splitlines():
        if "完成!" in line:
            m = re.search(r'共 (\d+) 条.*耗时 ([\d.]+) min', line)
            if m:
                result["subqueries"] = int(m.group(1))
                result["time_min"] = float(m.group(2))
        elif "成功:" in line:
            m = re.search(r'成功: (\d+).*失败: (\d+)', line)
            if m:
                result["success"] = int(m.group(1))
                result["failed"] = int(m.group(2))

    result["wall_time_min"] = round(elapsed / 60, 1)

    # 备份到 checkpoint
    if JOBLR_OUTPUT_FILE.exists():
        ckpt_copy = CHECKPOINT_DIR / "lpbound_JOBLightRanges.txt"
        shutil.copy2(JOBLR_OUTPUT_FILE, ckpt_copy)
        log(f"  已备份到: {ckpt_copy}")

    return result


# ============================================================
# 汇总 & 保存
# ============================================================

def run_space_usage() -> dict:
    """
    查询 DuckDB norms 表行数，计算统计信息占用空间。
    返回: { benchmark: bytes }
    """
    import tempfile

    log("\n" + "=" * 60)
    log("  Space Usage — 统计信息占用空间")
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
            log(f"  [ERROR] Space usage 失败: {proc.stderr[-300:] if proc.stderr else 'unknown'}")
            return results

        # 取最后一行 JSON（前面的行是 build_lpbound_statistics 的进度输出）
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
    """保存结果到 checkpoint/LpBound/"""
    ensure_dirs()

    # --- result.txt ---
    # 清空重写
    RESULT_FILE.write_text("")
    log("LpBound 实验结果", to_console=True)
    log(f"时间: {datetime.now().isoformat()}", to_console=True)
    log("", to_console=True)

    # Build Time 表格
    log("--- Build Time (seconds) ---")
    log(f"  {'Benchmark':<20} {'L1 only':>10} {'All norms':>10}")
    log("  " + "-" * 40)
    for b in BUILD_BENCHMARKS:
        l1 = build["l1"].get(b)
        al = build["all"].get(b)
        l1_s = f"{l1:.1f}" if l1 is not None else "N/A"
        al_s = f"{al:.1f}" if al is not None else "N/A"
        log(f"  {BENCHMARK_MAP.get(b, b):<20} {l1_s:>10} {al_s:>10}")

    # Estimate Time 表格
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

    log("\n  * Par avg = parallel 模式每查询平均时间（ms）")
    log("  * Total = Par avg × Queries，即全量估计总时间（s）")

    # Accuracy 表格
    if accuracy and accuracy.get("subqueries"):
        log("\n--- JOBLightRanges 子查询精度估计 ---")
        log(f"  子查询数: {accuracy.get('subqueries', 'N/A')}")
        log(f"  成功: {accuracy.get('success', 'N/A')}")
        log(f"  失败: {accuracy.get('failed', 'N/A')}")
        log(f"  耗时: {accuracy.get('time_min', 'N/A')} min")
        log(f"  输出: Benchmark/workloads/JOBLightRanges/subquery/result/lpbound.txt")

    # --- benchmark_times.csv ---
    # 与现有实验体系保持一致的 CSV 格式
    # 先读取已有 CSV，避免新数据为空时覆盖旧值
    csv_path = CHECKPOINT_DIR / "benchmark_times.csv"
    old_rows: dict[str, dict[str, str]] = {}
    if csv_path.exists():
        with open(csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                old_rows[row["Benchmark"]] = row
        cols = list(old_rows[next(iter(old_rows))].keys()) if old_rows else []
        if "BuildTime_L1" not in cols or "BuildTime_All" not in cols:
            old_rows.clear()  # 旧格式，不兼容，重新生成

    # 统一用显示名作为 key，避免内部名/显示名重复
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
        # internal -> display 反向映射，便于从显示名查内部数据
        display_to_internal = {v: k for k, v in BENCHMARK_MAP.items()}
        for display_name in sorted(display_names):
            internal = display_to_internal.get(display_name, display_name)
            l1 = build["l1"].get(internal)
            al = build["all"].get(internal)
            e = est.get(internal, {})
            sz = space.get(internal)
            old = old_rows.get(display_name, {})

            # 新数据优先，为空则回退到旧数据
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
    log(f"\n  CSV 已保存: {csv_path}")

    # --- JSON 详情 ---
    # 先读取已有 JSON，避免新数据为空时覆盖旧 build_time
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
    log(f"  JSON 已保存: {json_path}")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="LpBound Build Time & Estimate Time 测试")
    parser.add_argument("--build-only", action="store_true", help="仅运行 Build Time")
    parser.add_argument("--est-only", action="store_true", help="仅运行 Estimate Time")
    parser.add_argument("--accuracy", action="store_true",
                        help="运行 JOBLightRanges 子查询精度估计（约需 10 分钟）")
    args = parser.parse_args()

    run_build = not args.est_only
    run_est = not args.build_only
    run_acc = args.accuracy

    ensure_dirs()

    log("检查 LpBound 环境...")
    if not ensure_lpbound_environment():
        log("[WARN] 环境检查发现问题，部分功能可能不可用")

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
    log(f"\n总耗时: {elapsed:.0f}s")


if __name__ == "__main__":
    main()
