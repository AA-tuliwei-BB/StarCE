#!/usr/bin/env python3
"""
Generate StatsJoin benchmark (join-only, no filter predicates) from STATS-CEB workload.

Read STATS-CEB main queries, strip all non-join conditions, deduplicate, and write to StatsJoin.
Subqueries are generated via StarCE's RecordingSubquery feature (not handled in this script).
Also generate schema, single_query, config, and other supporting files.
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
    """Split conditions at top-level AND, correctly handling quotes and parentheses."""
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
    Determine whether this is a join condition (alias1.col1 = alias2.col2).
    If so, return (original_case_tuple, lowercase_key_tuple); otherwise return None.
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
    # Original case -> for output
    orig = (la_orig, lc_orig, ra_orig, rc_orig)
    # Lowercase sorted -> for dedup key
    if la_low < ra_low:
        key = (la_low, lc_low, ra_low, rc_low)
    else:
        key = (ra_low, rc_low, la_low, lc_low)
    return (orig, key)


def parse_query(query):
    """
    Parse query, return (from_text, aliases_map, join_conditions).

    aliases_map: {alias_lower: table_name_original_case}
    join_conditions: [(original_case_tuple, lowercase_key_tuple)]
    from_text: Original FROM clause text (preserving case)
    """
    from_match = re.search(
        r'FROM\s+(.*?)\s+WHERE\s+',
        query, re.IGNORECASE | re.DOTALL
    )
    if not from_match:
        return None, None, None

    from_text = from_match.group(1)

    # Parse aliases: preserve original case for table names, use lowercase alias as key
    aliases_map = {}
    for m in re.finditer(r'(\w+)\s+(?:AS|as)\s+(\w+)', from_text):
        aliases_map[m.group(2).lower()] = m.group(1)  # table name preserves original case

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
    Strip non-join predicates from query, keeping only join conditions.
    Return (normalized_query, unique_key).

    Output preserves original case (compatible with StarCE statistics),
    unique_key uses lowercase for dedup.
    """
    from_text, aliases_map, join_conditions = parse_query(query)
    if aliases_map is None:
        return None, None
    if not join_conditions:
        return None, None

    # Reconstruct query with original case
    sorted_tables = sorted(f"{v} AS {k}" for k, v in aliases_map.items())

    # Reconstruct join conditions with original case
    join_strs = []
    for (la, lc, ra, rc), _ in join_conditions:
        join_strs.append(f"{la}.{lc}={ra}.{rc}")
    join_strs.sort()

    normalized = f"SELECT COUNT(*) FROM {', '.join(sorted_tables)} WHERE {' AND '.join(join_strs)};"

    # unique_key uses lowercase table names + lowercase join conditions for dedup
    table_set = frozenset(v.lower() for v in aliases_map.values())
    join_set = frozenset(key for _, key in join_conditions)
    unique_key = (table_set, join_set)

    return normalized, unique_key


def read_stat_ceb_queries(filepath):
    """
    Read STATS-CEB query file, supports two formats:
    - Main queries: N<TAB>sql
    - Subqueries: direct sql
    Return parsed query list.
    """
    queries = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Strip leading line number (e.g., "1\tselect ...")
            line = re.sub(r'^\d+\t', '', line)
            queries.append(line)
    return queries


def main():
    print("=" * 60)
    print("StatsJoin Benchmark Generator")
    print("=" * 60)

    # ============================================================
    # 1. Process main queries
    # ============================================================
    main_queries = read_stat_ceb_queries(str(STATS_CEB / "queries.sql"))
    print(f"\nOriginal main queries: {len(main_queries)} entries")

    main_stripped = []
    main_seen = set()
    for q in main_queries:
        norm, key = strip_query(q)
        if norm and key not in main_seen:
            main_seen.add(key)
            main_stripped.append(norm)

    print(f"After stripping predicates and dedup: {len(main_stripped)} entries (retention {len(main_stripped)/len(main_queries):.1%})")

    # ============================================================
    # 2. Subqueries -- generated via StarCE RecordingSubquery (not handled in this script)
    #    Steps:
    #    a. Copy queries.sql to experiment/running_space/statsjoin_queries.sql
    #    b. Add EXPLAIN prefix: sed 's/^/EXPLAIN /' statsjoin_queries.sql > statsjoin_queries_explain.sql
    #    c. Modify running_space/config.json:
    #       - RecordingSubquery=1, SQL_PATH=statsjoin_queries_explain.sql
    #       - SUBQUERY_PATH=statsjoin_subqueries.sql
    #       - SCHEMA_PATH/DB_PATH/STATS_PATH point to STATS corresponding paths
    #    d. cd experiment/running_space && ./starce
    #    e. Copy generated statsjoin_subqueries.sql to Benchmark/workloads/StatsJoin/subquery/subquery.sql
    # ============================================================

    # ============================================================
    # 3. Write queries.sql
    # ============================================================
    os.makedirs(str(STATS_JOIN), exist_ok=True)
    with open(str(STATS_JOIN / "queries.sql"), "w") as f:
        for q in main_stripped:
            f.write(q + "\n")
    print(f"\n✓ Main queries -> {STATS_JOIN / 'queries.sql'} ({len(main_stripped)} entries)")

    # ============================================================
    # 4. Generate schema_statsjoin.json
    # ============================================================
    # Copy EqualSets from STATS-CEB schema.json
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
    # 5. Generate single_query.sql (COUNT(*) for 8 base tables without predicates)
    # ============================================================
    tables = ["badges", "comments", "postHistory", "postLinks",
              "posts", "tags", "users", "votes"]
    os.makedirs(str(STATS_JOIN / "single_query"), exist_ok=True)
    with open(str(STATS_JOIN / "single_query/single_query.sql"), "w") as f:
        for t in tables:
            f.write(f"SELECT COUNT(*) FROM {t};\n")
    print(f"✓ single_query -> {STATS_JOIN / 'single_query/single_query.sql'} ({len(tables)} entries)")

    # ============================================================
    # 6. Generate config.json
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
    # 7. Statistics summary
    # ============================================================
    # Table count distribution
    table_counts = defaultdict(int)
    for q in main_stripped:
        nt = len(re.findall(r'\b(?:AS|as)\s+(\w+)', q))
        table_counts[nt] += 1

    print(f"\nMain query table count distribution: {dict(sorted(table_counts.items()))}")
    print(f"\n{'='*60}")
    print("StatsJoin benchmark generation complete!")
    print(f"Next step: compute TrueCard with compute_join_true_cards.py")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
