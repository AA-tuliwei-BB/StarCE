#!/usr/bin/env python3
"""
过滤 JOBLightRanges 中注入真实基数后执行时间超过 60 秒的主查询。
方法：对每条主查询单独运行 starce（UseSubqueryCard=1 注入 real.txt），外部计时，超时则 kill。
输出：filtered_queries.sql（不含超时查询，SQL 内容不变）
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parent.parent
RUNNING_SPACE = REPO / "experiment/running_space"
WORKLOAD = REPO / "Benchmark/workloads/JOBLightRanges"

QUERIES_FILE   = WORKLOAD / "queries.sql"
SUBQUERY_FILE  = WORKLOAD / "subquery/subquery.sql"
REAL_CARD_FILE = WORKLOAD / "subquery/result/real.txt"
SCHEMA_FILE    = WORKLOAD / "schema_joblr.json"
STATS_FILE     = RUNNING_SPACE / "statistics_JOBLightRanges_cp1.5.json"
DB_FILE        = REPO / "Benchmark" / "duckdb" / "imdb.db"
STARCE_BIN     = RUNNING_SPACE / "starce"

OUTPUT_FILE = WORKLOAD / "filtered_queries.sql"

TIMEOUT_SEC = 60
# ─────────────────────────────────────────────────────────────────────────────


def make_config(sql_path: Path, tmp_dir: Path) -> Path:
    cfg = {
        "EnableStarCE": 1,
        "UseAssignedAdjustRate": 0,
        "UseSubqueryCard": 1,
        "UseSingleTableCard": 0,
        "RecordingSubquery": 0,
        "SubqueryOutputGroupByMain": 0,
        "RecordingSingleQuery": 0,
        "RefreshStatistics": 0,
        "EnableStarSplit": 0,
        "PredMethod": 1,
        "IsCollectingRelErr": 0,
        "CollectParallel": 8,
        "CompressPrecision": 1.5,
        "SCHEMA_PATH": str(SCHEMA_FILE),
        "DB_PATH": str(DB_FILE),
        "STATS_PATH": str(STATS_FILE),
        "SQL_PATH": str(sql_path),
        "SUBQUERY_PATH": str(SUBQUERY_FILE),
        "SUBQUERY_RESULT_PATH": str(REAL_CARD_FILE),
        "SINGLE_QUERY_PATH": str(tmp_dir / "dummy.sql"),
        "SINGLE_QUERY_RESULT_PATH": str(tmp_dir / "dummy.txt"),
        "REAL_CARD_PATH": str(tmp_dir / "dummy.txt"),
        "REL_ERR_PATH": str(tmp_dir / "dummy.txt"),
        "ADJUST_RATE": 0,
        "PREDICATE_ADJUST_RATE": 1
    }
    cfg_path = tmp_dir / "config.json"
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, indent=4)
    return cfg_path


def run_query(sql: str, tmp_dir: Path) -> tuple[bool, float]:
    """返回 (timed_out, elapsed_sec)"""
    sql_path = tmp_dir / "query.sql"
    sql_path.write_text(sql + "\n")

    # dummy 文件（starce 可能要求路径存在）
    (tmp_dir / "dummy.sql").touch()
    (tmp_dir / "dummy.txt").touch()

    cfg_path = make_config(sql_path, tmp_dir)

    # starce 必须在 running_space 目录下运行（读取同目录的 config.json）
    # 但我们把 config.json 放在 tmp_dir，通过软链接覆盖
    # 更简单：直接把 config.json 写到 running_space，每次覆盖
    shutil.copy(cfg_path, RUNNING_SPACE / "config.json")

    t0 = time.time()
    proc = subprocess.Popen(
        [str(STARCE_BIN)],
        cwd=str(RUNNING_SPACE),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    timed_out = False
    try:
        proc.wait(timeout=TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL) if False else proc.kill()
        proc.wait()

    elapsed = time.time() - t0
    return timed_out, elapsed


def main():
    queries = []
    with open(QUERIES_FILE) as f:
        for line in f:
            line = line.rstrip("\n")
            if line.strip():
                queries.append(line)

    print(f"共 {len(queries)} 条查询，逐条执行（超时阈值 {TIMEOUT_SEC}s）...")

    kept = []
    removed = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        for i, sql in enumerate(queries, 1):
            timed_out, elapsed = run_query(sql, tmp_dir)

            if timed_out:
                print(f"  [REMOVE] #{i:4d}  TIMEOUT (>{TIMEOUT_SEC}s)")
                removed.append((i, sql))
            else:
                kept.append(sql)

            if i % 50 == 0:
                print(f"  进度: {i}/{len(queries)}，保留 {len(kept)}，剔除 {len(removed)}")

    with open(OUTPUT_FILE, "w") as f:
        for sql in kept:
            f.write(sql + "\n")

    print(f"\n完成：保留 {len(kept)} 条，剔除 {len(removed)} 条")
    print(f"输出：{OUTPUT_FILE}")
    if removed:
        print("\n被剔除的查询（原始行号）：")
        for idx, sql in removed:
            print(f"  #{idx:4d}  {sql[:100]}")


if __name__ == "__main__":
    main()
