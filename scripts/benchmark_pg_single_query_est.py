#!/usr/bin/env python3
"""测 PostgreSQL 单表基数估计耗时（StarCE UseSingleTableCard 依赖的 pg_est 来源）。

两种口径：
  1. 会话内 \\timing：一条 psql 会话跑完全部 EXPLAIN，测每条纯估计耗时
  2. --per-query 逐条 psql 调用：含进程启动+连接开销，接近在线调用一次的成本
"""
import argparse
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_DIR = PROJECT_ROOT / "Benchmark" / "workloads"

BENCHMARKS = {
    "STATS": ("stats", BENCHMARK_DIR / "STATS-CEB" / "single_query" / "single_query.sql"),
    "JOBM": ("imdbm", BENCHMARK_DIR / "JOBM" / "single_query" / "single_query.sql"),
    "JOBLight": ("imdblight", BENCHMARK_DIR / "JOBLight" / "single_query" / "single_query.sql"),
    "JOBLightRanges": ("imdblightranges", BENCHMARK_DIR / "JOBLightRanges" / "single_query" / "single_query.sql"),
}

TIMING_RE = re.compile(r"Time:\s*([0-9.]+)\s*ms")


def find_psql():
    found = shutil.which("psql")
    if found:
        return found
    for c in ["/usr/local/pgsql/13.1/bin/psql", "/usr/local/pgsql/16/bin/psql"]:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    raise FileNotFoundError("找不到 psql")


def split_sqls(path):
    text = path.read_text(encoding="utf-8")
    return [s.strip() for s in re.split(r";\s*", text) if s.strip()]


def make_explain_sql(sql):
    sql = re.sub(r"count\s*\(\s*\*\s*\)", "*", sql, flags=re.IGNORECASE)
    if not re.match(r"^\s*explain\b", sql, flags=re.IGNORECASE):
        sql = "EXPLAIN " + sql
    return sql


def run_in_session(psql, conn, sqls):
    content = "\\timing on\n" + "".join(make_explain_sql(s) + ";\n" for s in sqls)
    start = time.perf_counter()
    proc = subprocess.run([psql, conn, "-v", "ON_ERROR_STOP=1", "-f", "-"],
                          input=content, capture_output=True, text=True)
    total = time.perf_counter() - start
    if proc.returncode != 0:
        raise RuntimeError(f"psql 失败: {proc.stderr.strip()[-500:]}")
    timings = [float(m) for m in TIMING_RE.findall(proc.stdout)]
    return total, timings


def run_per_query(psql, conn, sqls):
    times = []
    for sql in sqls:
        start = time.perf_counter()
        proc = subprocess.run([psql, conn, "-t", "-A", "-c", make_explain_sql(sql)],
                              capture_output=True, text=True)
        times.append((time.perf_counter() - start) * 1000)
        if proc.returncode != 0:
            raise RuntimeError(f"psql 失败: {proc.stderr.strip()[-500:]}")
    return times


def summarize(times_ms):
    n = len(times_ms)
    if n == 0:
        return 0.0, 0.0, 0.0, 0.0
    s = sorted(times_ms)
    mean = sum(s) / n
    median = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    return mean, median, s[0], s[-1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", choices=list(BENCHMARKS), action="append",
                        help="只测指定 benchmark，可多次指定，默认全部")
    parser.add_argument("--per-query", action="store_true",
                        help="追加逐条 psql 调用测试（含进程启动+连接开销）")
    parser.add_argument("--user", default="postgres", help="PG 用户，默认 postgres")
    args = parser.parse_args()

    psql = find_psql()
    names = args.benchmark or list(BENCHMARKS)

    rows = []
    for name in names:
        db, sql_path = BENCHMARKS[name]
        sqls = split_sqls(sql_path)
        conn = f"host=127.0.0.1 port=5432 user={args.user} dbname={db}"
        print(f"\n=== {name} ({db}, {len(sqls)} 条单表查询) ===")
        total, timings = run_in_session(psql, conn, sqls)
        mean, median, lo, hi = summarize(timings)
        extra = "" if len(timings) == len(sqls) else f" | 解析 {len(timings)}/{len(sqls)}"
        print(f"  会话内纯估计: 总耗时 {total:.3f}s | 平均 {mean:.2f}ms | 中位数 {median:.2f}ms"
              f" | 最小 {lo:.2f}ms | 最大 {hi:.2f}ms{extra}")
        per_query_total = None
        if args.per_query:
            times = run_per_query(psql, conn, sqls)
            pm, pmed, _, _ = summarize(times)
            per_query_total = sum(times) / 1000
            print(f"  逐条调用(含进程+连接): 总耗时 {per_query_total:.3f}s | 平均 {pm:.2f}ms | 中位数 {pmed:.2f}ms")
        rows.append((name, len(sqls), total, mean, median, per_query_total))

    print("\n汇总:")
    header = f"{'Benchmark':<14}{'条数':>6}{'总耗时(s)':>12}{'平均(ms)':>10}{'中位数(ms)':>12}{'逐条总(s)':>12}"
    print(header)
    for name, n, total, mean, median, per_query_total in rows:
        pq = f"{per_query_total:.3f}" if per_query_total is not None else "-"
        print(f"{name:<14}{n:>6}{total:>12.3f}{mean:>10.2f}{median:>12.2f}{pq:>12}")


if __name__ == "__main__":
    main()
