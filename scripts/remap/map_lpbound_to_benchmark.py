#!/usr/bin/env python3
"""
Map LpBound subquery-level cardinality estimates to the Benchmark/workloads/ directory.

Supported datasets: STATS-CEB, JOBLight
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent.parent

# ─── Dataset configuration ───────────────────────────────────────

DATASETS = {
    'STATS-CEB': {
        'lp_name': 'stats',
        'table_map': {
            'B': 'badges', 'U': 'users', 'C': 'comments', 'P': 'posts',
            'PH': 'posthistory', 'PL': 'postlinks', 'T': 'tags', 'V': 'votes',
        },
        'bridge_tables': {'users', 'posts'},
        'sc_subquery': 'Benchmark/workloads/STATS-CEB/subquery/subquery.sql',
        'sc_real': 'Benchmark/workloads/STATS-CEB/subquery/result/real.txt',
        'out_dir': 'Benchmark/workloads/STATS-CEB/subquery/result',
    },
    'JobJoin': {
        'lp_name': 'jobjoin',
        'table_map': {
            'CI': 'cast_info', 'MC': 'movie_companies', 'MI': 'movie_info',
            'MI_IDX': 'movie_info_idx', 'MK': 'movie_keyword', 'T': 'title',
            'CN': 'company_name', 'CT': 'company_type', 'K': 'keyword',
            'KT': 'kind_type', 'IT': 'info_type', 'LT': 'link_type',
            'CC': 'complete_cast', 'CCT': 'comp_cast_type', 'ML': 'movie_link',
            'AT': 'aka_title', 'N': 'name', 'CHN': 'char_name',
            'RT': 'role_type', 'AN': 'aka_name', 'PI': 'person_info',
        },
        'bridge_tables': {'title'},
        'sc_subquery': 'Benchmark/workloads/JobJoin/subquery/subquery.sql',
        'sc_real': 'Benchmark/workloads/JobJoin/subquery/result/real.txt',
        'out_dir': 'Benchmark/workloads/JobJoin/subquery/result',
    },
    'JOBLight': {
        'lp_name': 'joblight',
        'table_map': {
            'CI': 'cast_info', 'MC': 'movie_companies', 'MI': 'movie_info',
            'MI_IDX': 'movie_info_idx', 'MK': 'movie_keyword', 'T': 'title',
        },
        'bridge_tables': {'title'},
        'sc_subquery': 'Benchmark/workloads/JOBLight/subquery/subquery.sql',
        'sc_real': 'Benchmark/workloads/JOBLight/subquery/result/real.txt',
        'out_dir': 'Benchmark/workloads/JOBLight/subquery/result',
    },
}


# ─── SQL parsing and normalization ────────────────────────────────

def parse_sql(sql: str) -> dict | None:
    sql = re.sub(r'\s+', ' ', sql).strip().lower().rstrip(';')
    sql = re.sub(r'::timestamp', '', sql)
    fm = re.search(r'from (.+?)( where |$)', sql)
    if not fm:
        return None
    a2t = {}
    for t in fm.group(1).split(","):
        p = t.strip().split()
        if len(p) >= 3 and p[1] == 'as':
            tbl, als = p[0], p[2]
        elif len(p) >= 2:
            tbl, als = p[0], p[1]
        else:
            tbl = als = p[0]
        a2t[als] = re.sub(r'\d+$', '', tbl)

    wm = re.search(r'where (.+)$', sql)
    conds = [c.strip() for c in wm.group(1).split(" and ")] if wm else []
    joins, filts = [], []
    for c in conds:
        ps = re.split(r'(<=|>=|!=|<>|=|<|>)', c, maxsplit=1)
        if len(ps) >= 3 and '.' in ps[0] and '.' in ps[2]:
            joins.append((ps[0].strip(), ps[1], ps[2].strip()))
        else:
            filts.append(c)
    return {'a2t': a2t, 'joins': joins, 'filts': filts}


def canonicalize(parsed: dict) -> tuple:
    """Return (canonical_joins, canonical_filts, col_groups)"""
    a2t = parsed['a2t']
    joins = parsed['joins']
    filts = parsed['filts']

    def nc(c):
        a, cn = c.split('.', 1)
        return f"{a2t.get(a, a)}.{cn}"

    parent = {}
    def find(x):
        if x not in parent: parent[x] = x
        if parent[x] != x: parent[x] = find(parent[x])
        return parent[x]
    def union(x, y):
        parent[find(x)] = find(y)

    for l, op, r in joins:
        if op == '=':
            union(nc(l), nc(r))

    groups = defaultdict(set)
    for n in parent:
        groups[find(n)].add(n)

    canonical_joins = []
    for g in sorted(groups.values(), key=lambda s: sorted(s)[0] if s else ''):
        if len(g) < 2:
            continue
        cols = sorted(g)
        anchor = cols[0]
        for other in cols[1:]:
            canonical_joins.append(f"{anchor} = {other}")
    canonical_joins = tuple(sorted(canonical_joins))

    def nf(f):
        for a, t in sorted(a2t.items(), key=lambda x: -len(x[0])):
            f = f.replace(f"{a}.", f"{t}.")
        f = re.sub(r'(?<=\w)(<=|>=|!=|<>|[=<>])(?=\S)', r' \1 ', f)
        return re.sub(r'\s+', ' ', f).strip()

    canonical_filts = tuple(sorted(nf(f) for f in filts))
    col_groups = [sorted(g) for g in groups.values() if len(g) >= 2]
    return (canonical_joins, canonical_filts, col_groups)


def get_table_set(sql: str) -> tuple | None:
    sql = sql.strip().rstrip(';').lower()
    fm = re.search(r'from (.+?)( where |$)', sql)
    if not fm:
        return None
    tables = set()
    for t in fm.group(1).split(","):
        tbl = t.strip().split()[0]
        tables.add(re.sub(r'\d+$', '', tbl))
    return tuple(sorted(tables))


def normalize_lp_tables_str(tables_str: str) -> str:
    parts = tables_str.strip().split()
    return ' '.join(sorted(parts))


# ─── Core mapping ────────────────────────────────────────────────

def build_lpbound_mapping(lp_dir: Path, cfg: dict, method: str = 'lpbound') -> dict:
    """Build StarCE subquery -> estimate mapping. method can be lpbound / safebound / duckdb etc."""

    lp_name = cfg['lp_name']
    table_map = cfg['table_map']
    bridge_tables = cfg['bridge_tables']
    sc_subquery_path = PROJ / cfg['sc_subquery']
    sc_real_path = PROJ / cfg['sc_real']

    lp_est_dir = lp_dir / f'results/evaluation_time/subquery_estimations/{lp_name}'

    def lp_tables_to_normalized(tables_str: str) -> tuple:
        parts = tables_str.strip().split()
        return tuple(sorted(table_map.get(p, p.lower()) for p in parts))

    # ═══ Read LpBound subquery SQL ═══
    lp_sqls = {}
    subquery_csv = lp_dir / f'benchmarks/workloads/{lp_name}/{lp_name}_subqueries.csv'
    with open(subquery_csv) as f:
        f.readline()
        for line in f:
            parts = line.strip().split('|', 2)
            if len(parts) >= 3:
                qid = int(parts[0])
                nk = (qid, normalize_lp_tables_str(parts[1]))
                lp_sqls[nk] = parts[2]

    # ═══ Read LpBound estimates and true cardinalities ═══
    lp_estimates = {}
    for m in [method, 'truecardinality']:
        lp_estimates[m] = {}
        csv_path = lp_est_dir / f'{m}_subquery_estimations.csv'
        with open(csv_path) as f:
            f.readline()
            for line in f:
                parts = line.strip().split(',')
                qid = int(parts[0])
                nk = (qid, normalize_lp_tables_str(parts[1].strip()))
                lp_estimates[m][nk] = float(parts[2])
    lp_true = lp_estimates['truecardinality']

    # ═══ Build LpBound entry index ═══
    lp_entries = []
    for (qid, norm_ts_str), sql in lp_sqls.items():
        card_val = lp_true.get((qid, norm_ts_str))
        if card_val is None:
            continue
        card = int(card_val)
        normalized_ts = lp_tables_to_normalized(norm_ts_str)
        parsed = parse_sql(sql)
        sig = canonicalize(parsed) if parsed else ((), (), [])
        lp_entries.append((qid, norm_ts_str, normalized_ts, card, sig))

    lp_by_ts_card = defaultdict(list)
    for idx, e in enumerate(lp_entries):
        lp_by_ts_card[(e[2], e[3])].append(idx)

    # ═══ Read StarCE data ═══
    sc_sqls = []
    with open(sc_subquery_path) as f:
        for line in f:
            line = line.strip()
            if line:
                sc_sqls.append(line)

    sc_real = []
    with open(sc_real_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    sc_real.append(int(line))
                except ValueError:
                    sc_real.append(None)

    # ═══ Match ═══
    mapping = [None] * len(sc_sqls)
    stats = {'pass1_card': 0, 'pass2_sig': 0, 'pass3_bridge': 0, 'unmatched': 0}

    sc_data = []
    for i, sql in enumerate(sc_sqls):
        ts = get_table_set(sql)
        card = sc_real[i] if i < len(sc_real) else None
        parsed = parse_sql(sql)
        sig = canonicalize(parsed) if parsed else ((), (), [])
        sc_data.append((ts, card, sig))

    # Pass 1: exact match by (table_set, true_cardinality)
    for i, (ts, card, sig) in enumerate(sc_data):
        if ts is None or card is None:
            continue
        candidates = lp_by_ts_card.get((ts, card), [])
        if len(candidates) == 1:
            e = lp_entries[candidates[0]]
            mapping[i] = (e[0], e[1])
            stats['pass1_card'] += 1

    # Pass 2: disambiguate multiple candidates using signatures
    for i, (ts, card, sig) in enumerate(sc_data):
        if mapping[i] is not None or ts is None or card is None:
            continue
        candidates = lp_by_ts_card.get((ts, card), [])
        if len(candidates) >= 1:
            best = next((idx for idx in candidates
                        if lp_entries[idx][4] == sig), None)
            if best is not None:
                e = lp_entries[best]
                mapping[i] = (e[0], e[1])
            else:
                e = lp_entries[candidates[0]]
                mapping[i] = (e[0], e[1])
            stats['pass2_sig'] += 1

    # Pass 3: center-table bridge fallback
    for i, (ts, card, sig) in enumerate(sc_data):
        if mapping[i] is not None or ts is None:
            continue
        sc_filts = set(sig[1])
        sc_col_groups = sig[2]
        sc_tables = set(ts)

        best_idx = None
        best_extra_tables = 999
        best_extra_filts = 999

        for idx, e in enumerate(lp_entries):
            lp_ts = e[2]
            lp_sig = e[4]
            lp_filts = set(lp_sig[1])
            lp_col_groups = lp_sig[2]

            if not sc_tables.issubset(set(lp_ts)):
                continue
            extra = set(lp_ts) - sc_tables
            if len(extra) == 0:
                continue
            if not extra.issubset(bridge_tables):
                continue
            if not sc_filts.issubset(lp_filts):
                continue

            lp_col_to_group = {}
            for gid, cols in enumerate(lp_col_groups):
                for c in cols:
                    lp_col_to_group[c] = gid
            join_ok = True
            for sc_group in sc_col_groups:
                groups = {lp_col_to_group.get(c) for c in sc_group}
                if None in groups or len(groups) > 1:
                    join_ok = False
                    break
            if not join_ok:
                continue

            extra_filts = len(lp_filts) - len(sc_filts)
            if (extra_tables := len(extra)) < best_extra_tables or \
               (extra_tables == best_extra_tables and extra_filts < best_extra_filts):
                best_extra_tables = extra_tables
                best_extra_filts = extra_filts
                best_idx = idx

        if best_idx is not None:
            e = lp_entries[best_idx]
            mapping[i] = (e[0], e[1])
            stats['pass3_bridge'] += 1

    stats['unmatched'] = sum(1 for m in mapping if m is None)

    return {'mapping': mapping, 'estimates': lp_estimates, 'stats': stats,
            'sc_data': sc_data}


# ─── Output ──────────────────────────────────────────────────────

def write_and_report(result: dict, out_dir: Path, method: str = 'lpbound'):
    mapping = result['mapping']
    estimates = result['estimates']
    stats = result['stats']
    n = len(mapping)

    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f'{method}.txt'
    missing = 0
    with open(out_path, 'w') as f:
        for m in mapping:
            if m is not None:
                val = estimates[method].get(m)
                if val is not None:
                    f.write(f"{val}\n")
                    continue
            f.write("MISSING\n")
            missing += 1

    matched = n - missing
    print(f"  {method}.txt: {matched}/{n} ({100*matched/n:.1f}%), {missing} MISSING")


# ─── Main entry ──────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <dataset> [method]")
        print(f"Datasets: {list(DATASETS.keys())}")
        print(f"Methods: lpbound (default), safebound, duckdb")
        sys.exit(1)

    dataset = sys.argv[1]
    method = sys.argv[2] if len(sys.argv) > 2 else 'lpbound'

    if dataset not in DATASETS:
        print(f"Unknown dataset: {dataset}. Available: {list(DATASETS.keys())}")
        sys.exit(1)

    cfg = DATASETS[dataset]
    lp_dir = PROJ / 'methods/LpBound'
    out_dir = PROJ / cfg['out_dir']

    print("=" * 60)
    print(f"{method} -> {dataset} subquery cardinality estimate mapping")
    print("=" * 60)

    result = build_lpbound_mapping(lp_dir, cfg, method)
    stats = result['stats']
    n = len(result['mapping'])

    print(f"\nStarCE subquery total: {n}")
    print(f"  Pass 1 (ts+card exact):  {stats['pass1_card']}")
    print(f"  Pass 2 (signature disamb): {stats['pass2_sig']}")
    print(f"  Pass 3 (bridge table):    {stats['pass3_bridge']}")
    print(f"  MISSING:                  {stats['unmatched']}")

    print(f"\nWriting to {out_dir}:")
    write_and_report(result, out_dir, method)
    print("\nDone!")


if __name__ == '__main__':
    main()
