#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


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


def _split_top_level(expr: str, sep: str) -> List[str]:
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
                if sep == "," and ch == ",":
                    flush()
                    i += 1
                    continue
                if sep.lower() == "and":
                    tail = expr[i : i + 5]
                    if tail.lower() == " and ":
                        flush()
                        i += 5
                        continue

        buf.append(ch)
        i += 1

    flush()
    return out


def _normalize_space(s: str) -> str:
    return " ".join(s.strip().split())


def _strip_outer_parens(s: str) -> str:
    s2 = s.strip()
    while s2.startswith("(") and s2.endswith(")"):
        inner = s2[1:-1].strip()
        if not inner:
            break
        s2 = inner
    return s2


def _looks_like_column_ref(expr: str) -> bool:
    s = expr.strip()
    if " " in s or "(" in s or ")" in s:
        return False
    if s.startswith("'") or s.endswith("'"):
        return False
    if "::" in s:
        return False
    parts = s.split(".")
    if len(parts) != 2:
        return False
    a, b = parts
    if not a or not b:
        return False
    a_ok = a.replace("_", "").isalnum()
    b_ok = b.replace("_", "").isalnum()
    return a_ok and b_ok


class _UnionFind:
    def __init__(self) -> None:
        self.parent: Dict[str, str] = {}

    def find(self, x: str) -> str:
        if x not in self.parent:
            self.parent[x] = x
            return x
        p = self.parent[x]
        if p != x:
            self.parent[x] = self.find(p)
        return self.parent[x]

    def union(self, a: str, b: str) -> None:
        ra = self.find(a)
        rb = self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _split_predicate(pred: str) -> Tuple[str, str, str]:
    s = pred
    for op in ["<=", ">=", "!=", "<", ">", "="]:
        if op == "=":
            i = s.find("=")
            if i == -1:
                continue
            if i > 0 and s[i - 1] in ("<", ">", "!"):
                continue
        else:
            i = s.find(op)
            if i == -1:
                continue
        left = s[:i].strip()
        right = s[i + len(op) :].strip()
        return left, op, right
    return pred.strip(), "", ""


def _normalize_predicate(pred: str) -> str:
    s = _normalize_space(pred)
    left, op, right = _split_predicate(s)
    if not op:
        return s

    left_n = _normalize_space(left)
    right_n = _normalize_space(right)

    if op in ("=", "!="):
        if left_n > right_n:
            left_n, right_n = right_n, left_n

    return f"{left_n}{op}{right_n}"


def normalize_subquery_sql(sql: str) -> str:
    s = sql.strip().rstrip(";").strip()
    s = _normalize_space(s)
    low = s.lower()
    marker = " from "
    idx = low.find(marker)
    if idx == -1:
        raise ValueError(f"missing FROM: {sql}")

    after_from = s[idx + len(marker) :]
    after_from_low = after_from.lower()
    where_marker = " where "
    widx = after_from_low.find(where_marker)
    if widx == -1:
        from_part = after_from.strip()
        where_part = ""
    else:
        from_part = after_from[:widx].strip()
        where_part = after_from[widx + len(where_marker) :].strip()

    tables = [_normalize_space(x).lower() for x in _split_top_level(from_part, ",")]
    tables_sorted = ",".join(sorted(tables))

    if not where_part:
        return f"from {tables_sorted}"

    raw_preds = _split_top_level(where_part, "and")
    join_edges: List[Tuple[str, str]] = []
    other_preds: List[str] = []

    for p in raw_preds:
        p0 = _normalize_space(p)
        left, op, right = _split_predicate(p0)
        if op == "=":
            l = _strip_outer_parens(_normalize_space(left))
            r = _strip_outer_parens(_normalize_space(right))
            if _looks_like_column_ref(l) and _looks_like_column_ref(r):
                join_edges.append((l, r))
                continue
        other_preds.append(_normalize_predicate(p0))

    canonical_join_preds: List[str] = []
    if join_edges:
        uf = _UnionFind()
        for a, b in join_edges:
            uf.union(a, b)

        comps: Dict[str, List[str]] = {}
        for a, b in join_edges:
            for x in (a, b):
                r = uf.find(x)
                comps.setdefault(r, []).append(x)

        for nodes0 in comps.values():
            nodes = sorted(set(nodes0))
            if len(nodes) <= 1:
                continue
            rep = nodes[0]
            for x in nodes[1:]:
                canonical_join_preds.append(_normalize_predicate(f"{rep}={x}"))

    preds = canonical_join_preds + other_preds
    preds_sorted = " and ".join(sorted(set(preds)))
    return f"from {tables_sorted} where {preds_sorted}"


@dataclass(frozen=True)
class CompareRow:
    idx: int
    est: int
    real: int
    qerror: float
    sql: str


def _qerror(est: int, real: int) -> float:
    if est <= 0 or real <= 0:
        return math.inf if est != real else 1.0
    r = est / real
    return r if r >= 1.0 else 1.0 / r


def _build_sql_to_real(subquery_sql: Path, real_txt: Path) -> Dict[str, int]:
    sqls = _read_nonempty_lines(subquery_sql)
    reals_s = _read_nonempty_lines(real_txt)
    if len(sqls) != len(reals_s):
        raise RuntimeError(
            "subquery.sql and real.txt length mismatch: "
            f"{subquery_sql} has {len(sqls)} lines, {real_txt} has {len(reals_s)} lines"
        )

    m: Dict[str, int] = {}
    for sql, val_s in zip(sqls, reals_s):
        key = normalize_subquery_sql(sql)
        val = int(val_s)
        if key in m and m[key] != val:
            raise RuntimeError(f"duplicate key with different real card: {key}")
        m[key] = val
    return m


def compare(
    *,
    recorded_sql: Path,
    recorded_est: Path,
    workload_subquery_sql: Path,
    workload_real: Path,
    out_tsv: Path,
    out_real: Path,
    topk: int,
) -> None:
    rec_sqls = _read_nonempty_lines(recorded_sql)
    rec_est_s = _read_nonempty_lines(recorded_est)
    if len(rec_sqls) != len(rec_est_s):
        raise RuntimeError(
            "recorded subquery sql and estimate length mismatch: "
            f"{recorded_sql} has {len(rec_sqls)} lines, {recorded_est} has {len(rec_est_s)} lines"
        )
    rec_est = [int(x) for x in rec_est_s]

    sql_to_real = _build_sql_to_real(workload_subquery_sql, workload_real)

    rows: List[CompareRow] = []
    out_real_lines: List[str] = []
    missing: List[int] = []

    for i, (sql, est) in enumerate(zip(rec_sqls, rec_est), start=1):
        key = normalize_subquery_sql(sql)
        real = sql_to_real.get(key)
        if real is None:
            missing.append(i)
            real = 0
        qe = _qerror(est, real)
        rows.append(CompareRow(idx=i, est=est, real=real, qerror=qe, sql=sql))
        out_real_lines.append(str(real))

    out_real.write_text("\n".join(out_real_lines) + "\n", encoding="utf-8")

    header = "idx\test\treal\tqerror\tsql"
    tsv_lines = [header]
    for r in rows:
        q = "inf" if math.isinf(r.qerror) else f"{r.qerror:.6g}"
        tsv_lines.append(f"{r.idx}\t{r.est}\t{r.real}\t{q}\t{r.sql}")
    out_tsv.write_text("\n".join(tsv_lines) + "\n", encoding="utf-8")

    rows_sorted = sorted(rows, key=lambda x: (math.isinf(x.qerror), x.qerror), reverse=True)
    print(f"total={len(rows)} matched={len(rows)-len(missing)} missing={len(missing)}", file=sys.stderr)
    if missing:
        print(f"missing idx (1-based): {missing}", file=sys.stderr)
    if topk > 0:
        print(f"top{topk} qerror:", file=sys.stderr)
        for r in rows_sorted[:topk]:
            q = "inf" if math.isinf(r.qerror) else f"{r.qerror:.6g}"
            print(f"  idx={r.idx} est={r.est} real={r.real} qerror={q}", file=sys.stderr)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Map recorded subqueries to real cards (STATS-CEB) and output comparison."
    )
    p.add_argument(
        "--recorded-subquery-sql",
        type=Path,
        default=Path("experiment/running_space/subquery_details_worst.sql"),
        help="Recorded subquery SQL file (one query per line).",
    )
    p.add_argument(
        "--recorded-est",
        type=Path,
        default=Path("experiment/running_space/subquery_results_worst.txt"),
        help="Recorded estimate file (one integer per line).",
    )
    p.add_argument(
        "--workload-subquery-sql",
        type=Path,
        default=Path("Benchmark/workloads/STATS-CEB/subquery/subquery.sql"),
        help="Workload subquery SQL file aligned with real.txt.",
    )
    p.add_argument(
        "--workload-real",
        type=Path,
        default=Path("Benchmark/workloads/STATS-CEB/subquery/result/real.txt"),
        help="Real cardinality file aligned with workload-subquery-sql (one int per line).",
    )
    p.add_argument(
        "--out-tsv",
        type=Path,
        default=Path("experiment/running_space/subquery_compare_worst.tsv"),
        help="Output TSV: idx, est, real, qerror, sql.",
    )
    p.add_argument(
        "--out-real",
        type=Path,
        default=Path("experiment/running_space/subquery_real_worst.txt"),
        help="Output real cards aligned with recorded-subquery-sql.",
    )
    p.add_argument(
        "--topk",
        type=int,
        default=10,
        help="Print top-k qerror rows to stderr.",
    )
    args = p.parse_args(argv)

    compare(
        recorded_sql=args.recorded_subquery_sql,
        recorded_est=args.recorded_est,
        workload_subquery_sql=args.workload_subquery_sql,
        workload_real=args.workload_real,
        out_tsv=args.out_tsv,
        out_real=args.out_real,
        topk=args.topk,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

