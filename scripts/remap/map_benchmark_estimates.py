#!/usr/bin/env python3
"""
Map method estimation results from End-to-End-CardEst-Benchmark to the Benchmark/ directory.
Supports FLAT, BayesCard, DeepDB, and NeuroCard.

Normalization strategy:
  1. Sort table names lexicographically
  2. Run Union-Find on all equi-join conditions to establish equivalence classes
  3. Within each equivalence class, sort columns lexicographically, use the first column as anchor, generate minimal non-redundant joins
  4. Sort filters lexicographically
  5. Signature = (sorted_tables, canonical_joins, sorted_filters) exact match
"""

import re, sys
from collections import defaultdict
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent.parent


def parse_sql(sql: str) -> dict | None:
    sql = re.sub(r'\s+', ' ', sql).strip().lower().rstrip(';')
    fm = re.search(r'from (.+?)( where |$)', sql)
    if not fm: return None
    a2t = {}
    tables = []
    for t in fm.group(1).split(","):
        p = t.strip().split()
        if len(p) >= 3 and p[1] == 'as': tbl, als = p[0], p[2]
        elif len(p) >= 2: tbl, als = p[0], p[1]
        else: tbl = als = p[0]
        a2t[als] = tbl
        tables.append(tbl)
    wm = re.search(r'where (.+)$', sql)
    conds = [c.strip() for c in wm.group(1).split(" and ")] if wm else []
    joins, filts = [], []
    for c in conds:
        ps = re.split(r'(<=|>=|!=|<>|=|<|>)', c, maxsplit=1)
        if len(ps) >= 3 and '.' in ps[0] and '.' in ps[2]:
            joins.append((ps[0].strip(), ps[1], ps[2].strip()))
        else:
            filts.append(c)
    return {'tables': tables, 'a2t': a2t, 'joins': joins, 'filts': filts}


def canonicalize(parsed: dict) -> tuple | None:
    """
    Return canonical signature: (sorted_tables, canonical_joins, sorted_filters)
    """
    sig, _groups = _canonicalize_inner(parsed)
    return sig


def _canonicalize_inner(parsed: dict) -> tuple:
    """
    Return (signature, list of column equivalence classes).
    Column equivalence classes: [[table.column, ...], ...]  each group is all columns connected via equi-joins
    """
    a2t = parsed['a2t']
    tables = [re.sub(r'\d+$', '', t) for t in parsed['tables']]
    tables = tuple(sorted(set(tables)))

    joins = parsed['joins']
    filts = parsed['filts']

    def nc(c):
        a, cn = c.split('.')
        t = re.sub(r'\d+$', '', a2t.get(a, a))
        return f"{t}.{cn}"

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
            find(nc(l)); find(nc(r))

    groups = defaultdict(set)
    for n in parent:
        groups[find(n)].add(n)

    col_groups = []
    canonical_joins = []
    for g in sorted(groups.values(), key=lambda s: sorted(s)[0] if s else ''):
        if len(g) < 2:
            continue
        cols = sorted(g)
        col_groups.append(cols)
        anchor = cols[0]
        for other in cols[1:]:
            canonical_joins.append(f"{anchor} = {other}")

    canonical_joins = tuple(sorted(canonical_joins))

    def nf(f):
        for a, t in sorted(a2t.items(), key=lambda x: -len(x[0])):
            f = f.replace(f"{a}.", f"{t}.")
        return re.sub(r'\s+', ' ', f).strip()

    canonical_filts = tuple(sorted(nf(f) for f in filts))

    return (tables, canonical_joins, canonical_filts), col_groups


# ── Bridge table inference ──

# STATS: infer bridge table from equi-join column name
def stats_bridge_for_column(col: str) -> str | None:
    """Infer bridge table from column name: userid/owneruserid -> users, postid/relatedpostid -> posts"""
    col = col.lower()
    if col in ('userid', 'owneruserid', 'lasteditoruserid'):
        return 'users'
    if col in ('postid', 'relatedpostid'):
        return 'posts'
    return None

# JOBLight: movie_id -> title
def joblight_bridge_for_column(col: str) -> str | None:
    col = col.lower()
    if col == 'movie_id':
        return 'title'
    return None

# Primary keys of bridge tables
BRIDGE_KEY = {'users': 'users.id', 'posts': 'posts.id', 'title': 'title.id'}


def add_bridges_and_match(our_sig, col_groups, sp_map, bridge_fn):
    """
    Try adding bridge tables for unmatched queries. For each equivalence class,
    infer bridge tables from column names, add bridge table primary key columns
    to the equivalence class, re-normalize, then match.
    Returns the matched estimate or None.
    """
    tables, joins, filts = our_sig
    if not col_groups:
        return None

    # infer bridge tables for each equivalence class
    bridge_tables = set()
    extra_joins = []  # additional join conditions to add (table.col = bridge.key)

    for group in col_groups:
        # infer bridges from column names in this group
        col_names = {c.split('.')[1] for c in group}
        bridges_for_group = set()
        for cn in col_names:
            b = bridge_fn(cn)
            if b:
                bridges_for_group.add(b)

        for bt in bridges_for_group:
            bridge_tables.add(bt)
            # connect all columns in this group to bridge table primary key
            bk = BRIDGE_KEY[bt]
            for col in group:
                extra_joins.append(f"{col} = {bk}")

    if not bridge_tables:
        return None

    # build new table set and join set
    new_tables = tuple(sorted(set(tables) | bridge_tables))
    # merge original joins and new bridge joins, re-run Union-Find
    all_joins = list(joins) + extra_joins

    # simulate parse_sql output structure to re-canonicalize
    # need a2t to normalize column names, but these are already normalized table.column
    # directly run Union-Find
    parent = {}
    def find(x):
        if x not in parent: parent[x] = x
        if parent[x] != x: parent[x] = find(parent[x])
        return parent[x]
    def union(x, y):
        parent[find(x)] = find(y)

    for j in all_joins:
        parts = j.split(' = ')
        if len(parts) == 2:
            union(parts[0], parts[1])
            find(parts[0]); find(parts[1])

    groups = defaultdict(set)
    for n in parent:
        groups[find(n)].add(n)

    new_joins = []
    for g in sorted(groups.values(), key=lambda s: sorted(s)[0] if s else ''):
        if len(g) < 2:
            continue
        cols = sorted(g)
        anchor = cols[0]
        for other in cols[1:]:
            new_joins.append(f"{anchor} = {other}")

    new_sig = (new_tables, tuple(sorted(new_joins)), filts)

    if new_sig in sp_map:
        return sp_map[new_sig]
    return None


def map_dataset(name, sp_sqls, estimates, our_sqls, out_path, bridge_fn=None):
    print(f"\n{'='*60}")
    print(f"{name}")
    print(f"{'='*60}")

    # build SP mapping: signature -> [(line_no, estimate)]
    sp_sig_to_list = defaultdict(list)
    sp_err = 0
    for i, sql in enumerate(sp_sqls):
        p = parse_sql(sql)
        if not p: sp_err += 1; continue
        sig = canonicalize(p)
        if not sig: sp_err += 1; continue
        sp_sig_to_list[sig].append((i, estimates[i]))

    sp_map = {sig: lst[0][1] for sig, lst in sp_sig_to_list.items()}

    sp_conflicts = sum(1 for sig, lst in sp_sig_to_list.items()
                       if len(set(e for _, e in lst)) > 1)

    print(f"  SP: {len(sp_sqls)} entries -> {len(sp_map)} unique signatures, "
          f"intra-signature conflicts:{sp_conflicts}, parse failures:{sp_err}")

    # match
    out = [None] * len(our_sqls)
    unmatched = []
    bridge_matched = 0
    match_count_per_sp = defaultdict(int)

    for i, sql in enumerate(our_sqls):
        p = parse_sql(sql)
        if not p: unmatched.append((i, "parse", sql[:120])); continue
        sig, col_groups = _canonicalize_inner(p)
        if not sig: unmatched.append((i, "sig", sql[:120])); continue

        if sig in sp_map:
            out[i] = sp_map[sig]
            match_count_per_sp[sig] += 1
        elif bridge_fn is not None:
            est = add_bridges_and_match(sig, col_groups, sp_map, bridge_fn)
            if est is not None:
                out[i] = est
                bridge_matched += 1
            else:
                unmatched.append((i, sig))
        else:
            unmatched.append((i, sig))

    m = sum(1 for e in out if e is not None)
    u = len(unmatched)
    print(f"  direct matches: {m - bridge_matched}, bridge matches: {bridge_matched}")
    print(f"  total: {m}/{len(our_sqls)} ({100*m/len(our_sqls):.1f}%)")
    print(f"  unmatched: {u}")

    # duplicate usage detection
    sp_multi_use = [(sig, cnt) for sig, cnt in match_count_per_sp.items() if cnt > 1]
    if sp_multi_use:
        sp_multi_use.sort(key=lambda x: -x[1])
        print(f"  SP signatures matched by multiple our queries: {len(sp_multi_use)} signatures, involving {sum(cnt for _,cnt in sp_multi_use)} our entries")

    # distribution by table count
    by_n = defaultdict(lambda: [0, 0])
    for i, sql in enumerate(our_sqls):
        p = parse_sql(sql)
        if not p: continue
        sig, _ = _canonicalize_inner(p)
        if not sig: continue
        n = len(sig[0])
        if out[i] is not None: by_n[n][0] += 1
        else: by_n[n][1] += 1
    for n in sorted(by_n):
        ma, um = by_n[n]
        if ma + um > 0:
            print(f"    {n}-table: {ma} matched, {um} unmatched ({100*ma/(ma+um):.0f}%)")

    # classify by reason
    tbl_diff = 0; join_diff = 0; filt_diff = 0
    for item in unmatched:
        if isinstance(item[1], str): continue
        sig = item[1]
        same_tbl_join = [s for s in sp_map if s[0] == sig[0] and s[1] == sig[1]]
        same_tbl = [s for s in sp_map if s[0] == sig[0]]
        if same_tbl_join: filt_diff += 1
        elif same_tbl: join_diff += 1
        else: tbl_diff += 1
    print(f"    table_mismatch: {tbl_diff}, join_mismatch: {join_diff}, filter_mismatch: {filt_diff}")

    if unmatched:
        print(f"\n  ── Unmatched examples (first 10) ──")
        for idx, sig in unmatched[:10]:
            if isinstance(sig, str): print(f"    [{idx}] {sig}"); continue
            t, j, f = sig
            print(f"    [{idx}] tables={t}, joins={j[:2]}, filters={f[:2]}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        for e in out:
            f.write(f"{e}\n" if e is not None else "MISSING\n")
    ok = (u == 0)
    print(f"\n  result: {'OK' if ok else f'MISSING={u}'} -> {out_path}")
    return ok


def main():
    all_ok = True

    # ═══ STATS-CEB ═══
    sp_raw = [l.strip() for l in (PROJ / "Stats-CEB/End-to-End-CardEst-Benchmark/workloads/stats_CEB/sub_plan_queries/stats_CEB_sub_queries.sql").read_text().splitlines() if l.strip()]
    sp_sqls = []
    for l in sp_raw:
        parts = l.split("||")
        sp_sqls.append(parts[0].strip().rstrip(';'))
    our_stats = [l.strip().rstrip(';') for l in (PROJ / "Benchmark/workloads/STATS-CEB/subquery/subquery.sql").read_text().splitlines() if l.strip()]

    stats_est_dir = PROJ / "Stats-CEB/End-to-End-CardEst-Benchmark/workloads/stats_CEB/sub_plan_queries/estimates"
    for method in ['flat', 'bayescard', 'deepdb', 'neurocard']:
        est_file = stats_est_dir / f"stats_CEB_sub_queries_{method}.txt"
        ests = [float(l) for l in est_file.read_text().splitlines() if l.strip()]
        assert len(sp_sqls) == len(ests), f"{method}: {len(sp_sqls)} vs {len(ests)}"
        all_ok &= map_dataset(f"STATS-CEB/{method}", sp_sqls, ests, our_stats,
                              PROJ / f"Benchmark/workloads/STATS-CEB/subquery/result/{method}.txt",
                              bridge_fn=stats_bridge_for_column)

    # ═══ JOBLight ═══
    jl_sp = PROJ / "Stats-CEB/End-to-End-CardEst-Benchmark/workloads/job-light/sub_plan_queries/job_light_sub_query.sql"
    our_jl_path = PROJ / "Benchmark/workloads/JOBLight/subquery/subquery.sql"
    if our_jl_path.exists():
        jl_sp_lines = [l.strip().rstrip(';') for l in jl_sp.read_text().splitlines() if l.strip()]
        our_jl_lines = [l.strip().rstrip(';') for l in our_jl_path.read_text().splitlines() if l.strip()]

        jl_est_dir = PROJ / "Stats-CEB/End-to-End-CardEst-Benchmark/workloads/job-light/sub_plan_queries/estimates"
        for method in ['flat', 'bayescard', 'deepdb', 'neurocard']:
            est_file = jl_est_dir / f"job_light_sub_queries_{method}.txt"
            jl_ests = [float(l) for l in est_file.read_text().splitlines() if l.strip()]
            assert len(jl_sp_lines) == len(jl_ests), f"JOBLight {method}: {len(jl_sp_lines)} vs {len(jl_ests)}"
            all_ok &= map_dataset(f"JOBLight/{method}", jl_sp_lines, jl_ests, our_jl_lines,
                                  PROJ / f"Benchmark/workloads/JOBLight/subquery/result/{method}.txt",
                                  bridge_fn=joblight_bridge_for_column)

    if not all_ok:
        print("\n" + "=" * 60)
        print("There are queries that could not be matched.")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
