#!/usr/bin/env python3
"""
从 STATS-CEB workload 生成 StatsJoin benchmark（join-only, 无过滤谓词）。

读取 STATS-CEB 的主查询，剥离所有非 join 条件，去重后写入 StatsJoin。
子查询通过 StarCE 的 RecordingSubquery 功能生成（不在此脚本中处理）。
同时生成 schema、single_query、config 等配套文件。
"""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATS_CEB = PROJECT_ROOT / "Benchmark/workloads/STATS-CEB"
STATS_JOIN = PROJECT_ROOT / "Benchmark/workloads/StatsJoin"


def split_and(text):
    """按顶层 AND 拆分条件，正确处理引号和括号。"""
    parts = []
    current = []
    depth = 0
    i = 0
    in_string = False
    quote_char = None

    while i < len(text):
        ch = text[i]
        if in_string:
            current.append(ch)
            if ch == '\\' and i + 1 < len(text):
                i += 1
                current.append(text[i])
            elif ch == quote_char:
                in_string = False
        elif ch in ("'", '"'):
            in_string = True
            quote_char = ch
            current.append(ch)
        elif ch == '(':
            depth += 1
            current.append(ch)
        elif ch == ')':
            depth -= 1
            current.append(ch)
        elif depth == 0 and text[i:i+5].upper() == ' AND ':
            parts.append(''.join(current).strip())
            current = []
            i += 4
        else:
            current.append(ch)
        i += 1

    if current:
        parts.append(''.join(current).strip())
    return parts


def parse_join_condition(cond, aliases_map):
    """
    判断是否是 join 条件（alias1.col1 = alias2.col2）。
    如果是则返回 (原始大小写元组, 小写key元组)，否则返回 None。
    """
    m = re.match(
        r'^\s*(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)\s*$',
        cond
    )
    if not m:
        return None
    la_orig, lc_orig = m.group(1), m.group(2)
    ra_orig, rc_orig = m.group(3), m.group(4)
    la_low, lc_low = la_orig.lower(), lc_orig.lower()
    ra_low, rc_low = ra_orig.lower(), rc_orig.lower()
    if la_low not in aliases_map or ra_low not in aliases_map:
        return None
    # 原始大小写 -> 用于输出
    orig = (la_orig, lc_orig, ra_orig, rc_orig)
    # 小写排序 -> 用于去重key
    if la_low < ra_low:
        key = (la_low, lc_low, ra_low, rc_low)
    else:
        key = (ra_low, rc_low, la_low, lc_low)
    return (orig, key)


def parse_query(query):
    """
    解析查询，返回 (from_text, aliases_map, join_conditions)。

    aliases_map: {alias_lower: table_name_original_case}
    join_conditions: [(原始大小写元组, 小写key元组)]
    from_text: 原始 FROM 子句文本（保留大小写）
    """
    from_match = re.search(
        r'FROM\s+(.*?)\s+WHERE\s+',
        query, re.IGNORECASE | re.DOTALL
    )
    if not from_match:
        return None, None, None

    from_text = from_match.group(1)

    # 解析别名：保留原始大小写的表名，alias 用小写作 key
    aliases_map = {}
    for m in re.finditer(r'(\w+)\s+(?:AS|as)\s+(\w+)', from_text):
        aliases_map[m.group(2).lower()] = m.group(1)  # table name 保留原始大小写

    where_match = re.search(
        r'WHERE\s+(.*?);?\s*$',
        query, re.IGNORECASE | re.DOTALL
    )
    if not where_match:
        return from_text, aliases_map, []

    where_text = where_match.group(1).rstrip(';').strip()
    conditions = split_and(where_text)

    join_conditions = []
    for cond in conditions:
        jc = parse_join_condition(cond, aliases_map)
        if jc:
            join_conditions.append(jc)

    return from_text, aliases_map, join_conditions


def strip_query(query):
    """
    从查询中剥离非 join 谓词，只保留 join 条件。
    返回 (normalized_query, unique_key)。

    输出保留原始大小写（兼容 StarCE 统计信息），
    unique_key 用小写去重。
    """
    from_text, aliases_map, join_conditions = parse_query(query)
    if aliases_map is None:
        return None, None
    if not join_conditions:
        return None, None

    # 用原始大小写重建查询
    sorted_tables = sorted(f"{v} AS {k}" for k, v in aliases_map.items())

    # 用原始大小写重建 join 条件
    join_strs = []
    for (la, lc, ra, rc), _ in join_conditions:
        join_strs.append(f"{la}.{lc}={ra}.{rc}")
    join_strs.sort()

    normalized = f"SELECT COUNT(*) FROM {', '.join(sorted_tables)} WHERE {' AND '.join(join_strs)};"

    # unique_key 用小写表名+小写join条件去重
    table_set = frozenset(v.lower() for v in aliases_map.values())
    join_set = frozenset(key for _, key in join_conditions)
    unique_key = (table_set, join_set)

    return normalized, unique_key


def read_stat_ceb_queries(filepath):
    """
    读取 STATS-CEB 查询文件，支持两种格式：
    - 主查询：N<TAB>sql
    - 子查询：直接 sql
    返回解析后的查询列表。
    """
    queries = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # 剥离行首编号（如 "1\tselect ..."）
            line = re.sub(r'^\d+\t', '', line)
            queries.append(line)
    return queries


def main():
    print("=" * 60)
    print("StatsJoin Benchmark 生成器")
    print("=" * 60)

    # ============================================================
    # 1. 处理主查询
    # ============================================================
    main_queries = read_stat_ceb_queries(str(STATS_CEB / "queries.sql"))
    print(f"\n原始主查询: {len(main_queries)} 条")

    main_stripped = []
    main_seen = set()
    for q in main_queries:
        norm, key = strip_query(q)
        if norm and key not in main_seen:
            main_seen.add(key)
            main_stripped.append(norm)

    print(f"去谓词去重后: {len(main_stripped)} 条 (留存率 {len(main_stripped)/len(main_queries):.1%})")

    # ============================================================
    # 2. 子查询 — 通过 StarCE RecordingSubquery 生成（不在此脚本处理）
    #    步骤：
    #    a. 将 queries.sql 复制到 experiment/running_space/statsjoin_queries.sql
    #    b. 加 EXPLAIN 前缀：sed 's/^/EXPLAIN /' statsjoin_queries.sql > statsjoin_queries_explain.sql
    #    c. 修改 running_space/config.json：
    #       - RecordingSubquery=1, SQL_PATH=statsjoin_queries_explain.sql
    #       - SUBQUERY_PATH=statsjoin_subqueries.sql
    #       - SCHEMA_PATH/DB_PATH/STATS_PATH 指向 STATS 对应路径
    #    d. cd experiment/running_space && ./starce
    #    e. 将生成的 statsjoin_subqueries.sql 复制到 Benchmark/workloads/StatsJoin/subquery/subquery.sql
    # ============================================================

    # ============================================================
    # 3. 写入 queries.sql
    # ============================================================
    os.makedirs(str(STATS_JOIN), exist_ok=True)
    with open(str(STATS_JOIN / "queries.sql"), "w") as f:
        for q in main_stripped:
            f.write(q + "\n")
    print(f"\n✓ 主查询 → {STATS_JOIN / 'queries.sql'} ({len(main_stripped)} 条)")

    # ============================================================
    # 4. 生成 schema_statsjoin.json
    # ============================================================
    # 从 STATS-CEB schema.json 复制 EqualSets
    stats_schema = PROJECT_ROOT / "benchmark/stats-ceb/schema.json"
    with open(str(stats_schema)) as f:
        schema_data = json.load(f)

    statsjoin_schema = {
        "PredColumns": [],
        "EqualSets": schema_data["EqualSets"]
    }
    with open(str(STATS_JOIN / "schema_statsjoin.json"), "w") as f:
        json.dump(statsjoin_schema, f, indent=2)
    print(f"✓ Schema → {STATS_JOIN / 'schema_statsjoin.json'}")

    # ============================================================
    # 5. 生成 single_query.sql（8 张基表的 COUNT(*) 不含谓词）
    # ============================================================
    tables = ["badges", "comments", "postHistory", "postLinks",
              "posts", "tags", "users", "votes"]
    os.makedirs(str(STATS_JOIN / "single_query"), exist_ok=True)
    with open(str(STATS_JOIN / "single_query/single_query.sql"), "w") as f:
        for t in tables:
            f.write(f"SELECT COUNT(*) FROM {t};\n")
    print(f"✓ single_query → {STATS_JOIN / 'single_query/single_query.sql'} ({len(tables)} 条)")

    # ============================================================
    # 6. 生成 config.json
    # ============================================================
    config = {
        "UseAssignedAdjustRate": 0,
        "UseSubqueryCard": 0,
        "UseSingleTableCard": 1,
        "RecordingSubquery": 0,
        "RecordingSingleQuery": 1,
        "RefreshStatistics": 0,
        "EnableStarSplit": 0,
        "PredMethod": 0,
        "IsCollectingRelErr": 1,
        "CollectParallel": 8,
        "CompressPrecision": 2,
        "SCHEMA_PATH": "../../../benchmark/stats-ceb/schema.json",
        "SUBQUERY_PATH": "subquery.sql",
        "SUBQUERY_RESULT_PATH": "subquery_result.txt",
        "SINGLE_QUERY_PATH": "single_query/single_query.sql",
        "SINGLE_QUERY_RESULT_PATH": "single_query_result.txt",
        "DB_PATH": "../../duckdb/stats.db",
        "STATS_PATH": "statistics.json",
        "SQL_PATH": "queries.sql",
        "REAL_CARD_PATH": "subquery/result/real.txt",
        "REL_ERR_PATH": "rel_err.txt",
        "ADJUST_RATE": 0,
        "PREDICATE_ADJUST_RATE": 0
    }
    with open(str(STATS_JOIN / "config.json"), "w") as f:
        json.dump(config, f, indent=4)
    print(f"✓ Config → {STATS_JOIN / 'config.json'}")

    # ============================================================
    # 7. 统计摘要
    # ============================================================
    # 表数分布
    table_counts = defaultdict(int)
    for q in main_stripped:
        nt = len(re.findall(r'\b(?:AS|as)\s+(\w+)', q))
        table_counts[nt] += 1

    print(f"\n主查询表数分布: {dict(sorted(table_counts.items()))}")
    print(f"\n{'='*60}")
    print("StatsJoin benchmark 生成完成！")
    print(f"下一步: 用 compute_join_true_cards.py 计算 TrueCard")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
