#!/usr/bin/env python3
"""
Remap single-table cardinality results to match another single-table query order.

Use case (STATS-CEB in this repo):
- You extracted single-table queries from `benchmark/stats-ceb/queries.sql` and from
  `benchmark/stats-ceb/subquery/subquery.sql` (via StarCE RecordingSingleQuery).
- You already have a canonical single-table query list + result file (e.g. Postgres estimates)
  under `benchmark/stats-ceb/single_queries/`.
- This script builds a stable mapping by normalizing queries (order-insensitive for AND),
  then outputs a new result file whose line order matches the "subquery-extracted" single-table SQL.

Output format:
- One number per line (same as pg_est.txt / real.txt), aligned with the output query list.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, List, Optional, Tuple


def _read_nonempty_lines(path: Path) -> List[str]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: List[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("--"):
            continue
        out.append(s)
    return out


def _split_top_level_and(expr: str) -> List[str]:
    out: List[str] = []
    buf: List[str] = []
    depth = 0
    in_quote = False
    i = 0
    n = len(expr)

    def flush() -> None:
        s = "".join(buf).strip()
        if s:
            out.append(s)
        buf.clear()

    while i < n:
        ch = expr[i]
        if ch == "'" and (i == 0 or expr[i - 1] != "\\"):
            in_quote = not in_quote
            buf.append(ch)
            i += 1
            continue

        if not in_quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth > 0:
                    depth -= 1

            if depth == 0:
                tail = expr[i : i + 5]
                if tail.lower() == " and ":
                    flush()
                    i += 5
                    continue

        buf.append(ch)
        i += 1

    flush()
    return out


def _normalize_predicate(pred: str) -> str:
    s = " ".join(pred.strip().split())
    for op in ["<=", ">=", "!=", "=", "<", ">"]:
        s = s.replace(f" {op} ", op)
    return s


def normalize_single_table_sql(sql: str) -> str:
    s = sql.strip().rstrip(";").strip()
    s = " ".join(s.split())
    low = s.lower()

    if not low.startswith("select"):
        raise ValueError(f"not a SELECT statement: {sql}")

    marker = " from "
    idx = low.find(marker)
    if idx == -1:
        raise ValueError(f"missing FROM: {sql}")

    after_from = s[idx + len(marker) :]
    after_from_low = after_from.lower()

    where_marker = " where "
    widx = after_from_low.find(where_marker)
    if widx == -1:
        table_part = after_from.strip()
        where_part = ""
    else:
        table_part = after_from[:widx].strip()
        where_part = after_from[widx + len(where_marker) :].strip()

    table_part = " ".join(table_part.split()).lower()

    if not where_part:
        return f"from {table_part}"

    preds = [_normalize_predicate(p) for p in _split_top_level_and(where_part)]
    preds_sorted = sorted(preds)
    return f"from {table_part} where " + " and ".join(preds_sorted)


@dataclass(frozen=True)
class MappingReport:
    total: int
    missing: int
    ambiguous: int


def _build_multimap(norm_sqls: Iterable[str]) -> DefaultDict[str, List[str]]:
    mm: DefaultDict[str, List[str]] = defaultdict(list)
    for q in norm_sqls:
        mm[normalize_single_table_sql(q)].append(q)
    return mm


def _check_same_multiset(a: List[str], b: List[str], name_a: str, name_b: str) -> None:
    ca = Counter(normalize_single_table_sql(x) for x in a)
    cb = Counter(normalize_single_table_sql(x) for x in b)
    if ca == cb:
        return

    only_a = [(k, ca[k] - cb.get(k, 0)) for k in ca.keys() if ca[k] > cb.get(k, 0)]
    only_b = [(k, cb[k] - ca.get(k, 0)) for k in cb.keys() if cb[k] > ca.get(k, 0)]
    only_a.sort(key=lambda x: -x[1])
    only_b.sort(key=lambda x: -x[1])

    msg_lines = [
        f"multiset mismatch between {name_a} and {name_b}",
        f"  only in {name_a} (top 10):",
    ]
    for k, cnt in only_a[:10]:
        msg_lines.append(f"    +{cnt} {k}")
    msg_lines.append(f"  only in {name_b} (top 10):")
    for k, cnt in only_b[:10]:
        msg_lines.append(f"    +{cnt} {k}")
    raise RuntimeError("\n".join(msg_lines))


def remap_results(
    *,
    queries_single_sql: Path,
    subquery_single_sql: Path,
    canonical_single_sql: Path,
    canonical_result: Path,
    output_result: Path,
    mapping_tsv: Optional[Path],
) -> MappingReport:
    q_queries = _read_nonempty_lines(queries_single_sql)
    q_subq = _read_nonempty_lines(subquery_single_sql)

    _check_same_multiset(q_queries, q_subq, "queries-extracted", "subquery-extracted")

    canonical_q = _read_nonempty_lines(canonical_single_sql)
    canonical_r = _read_nonempty_lines(canonical_result)
    if len(canonical_q) != len(canonical_r):
        raise RuntimeError(
            "canonical query/result length mismatch: "
            f"{canonical_single_sql} has {len(canonical_q)} lines, "
            f"{canonical_result} has {len(canonical_r)} lines"
        )

    norm_to_result: Dict[str, str] = {}
    for sql, val in zip(canonical_q, canonical_r):
        key = normalize_single_table_sql(sql)
        if key in norm_to_result and norm_to_result[key] != val:
            raise RuntimeError(f"duplicate canonical key with different values: {key}")
        norm_to_result[key] = val

    mm_queries = _build_multimap(q_queries)

    out_vals: List[str] = []
    missing = 0
    ambiguous = 0
    map_rows: List[Tuple[int, str, str, str]] = []

    for i, sub_sql in enumerate(q_subq, start=1):
        key = normalize_single_table_sql(sub_sql)
        candidates = mm_queries.get(key, [])
        if not candidates:
            missing += 1
            out_vals.append("0")
            continue
        if len(candidates) > 1:
            ambiguous += 1

        if key not in norm_to_result:
            missing += 1
            out_vals.append("0")
            continue

        val = norm_to_result[key]
        out_vals.append(val)
        map_rows.append((i, candidates[0], sub_sql, val))

    output_result.write_text("\n".join(out_vals) + "\n", encoding="utf-8")

    if mapping_tsv is not None:
        header = "subquery_idx\tqueries_sql\tsubquery_sql\tvalue\n"
        body = "".join(f"{i}\t{a}\t{b}\t{v}\n" for i, a, b, v in map_rows)
        mapping_tsv.write_text(header + body, encoding="utf-8")

    return MappingReport(total=len(q_subq), missing=missing, ambiguous=ambiguous)


def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser(
        description="Remap canonical single-table results into subquery-extracted query order."
    )
    p.add_argument(
        "--queries-single-sql",
        default="experiment/running_space/single_query_from_queries.sql",
        help="Single-table SQL extracted from queries workload.",
    )
    p.add_argument(
        "--subquery-single-sql",
        default="experiment/running_space/single_query_from_subquery.sql",
        help="Single-table SQL extracted from subquery workload (target order).",
    )
    p.add_argument(
        "--canonical-single-sql",
        default="benchmark/stats-ceb/single_queries/single_query.sql",
        help="Canonical single-table SQL list aligned with canonical result file.",
    )
    p.add_argument(
        "--canonical-result",
        default="benchmark/stats-ceb/single_queries/pg_est.txt",
        help="Canonical result file (one value per line) aligned with canonical-single-sql.",
    )
    p.add_argument(
        "-o",
        "--output-result",
        default="experiment/running_space/pg_est_subquery_order.txt",
        help="Output remapped result file path.",
    )
    p.add_argument(
        "--mapping-tsv",
        default="",
        help="Optional: write a TSV with (idx, queries_sql, subquery_sql, value).",
    )

    args = p.parse_args(argv)
    mapping_tsv = Path(args.mapping_tsv) if args.mapping_tsv else None

    try:
        rpt = remap_results(
            queries_single_sql=Path(args.queries_single_sql),
            subquery_single_sql=Path(args.subquery_single_sql),
            canonical_single_sql=Path(args.canonical_single_sql),
            canonical_result=Path(args.canonical_result),
            output_result=Path(args.output_result),
            mapping_tsv=mapping_tsv,
        )
    except Exception as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2

    sys.stdout.write(
        f"OK: wrote {rpt.total} lines to {args.output_result}\n"
        f"missing={rpt.missing} ambiguous={rpt.ambiguous}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

