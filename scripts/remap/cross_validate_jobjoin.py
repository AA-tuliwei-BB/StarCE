#!/usr/bin/env python3
"""
Cross-validate LpBound jobjoin subquery true cardinalities against StarCE jobjoin subquery true cardinalities.

Phase 1 (fast, no DB): Parse both sides' SQL, normalize signatures, match
Phase 2 (sampled DB verification): Sample matched pairs, compute true cardinalities from both sides directly using DuckDB

Usage:
    conda activate TestEnv
    python scripts/remap/cross_validate_jobjoin.py
"""

import re
import sys
import random
from collections import defaultdict
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent.parent

# ─── LpBound table name abbreviations -> DuckDB real table names ───
LP_TABLE_MAP = {
    'MK': 'movie_keyword', 'MK1': 'movie_keyword', 'MK2': 'movie_keyword',
    'T': 'title', 'T1': 'title', 'T2': 'title',
    'MC': 'movie_companies', 'MC1': 'movie_companies', 'MC2': 'movie_companies',
    'MI': 'movie_info', 'MI1': 'movie_info', 'MI2': 'movie_info',
    'CC': 'complete_cast',
    'CI': 'cast_info', 'CI1': 'cast_info', 'CI2': 'cast_info',
    'MI_IDX': 'movie_info_idx', 'MI_IDX1': 'movie_info_idx', 'MI_IDX2': 'movie_info_idx',
    'MIIDX': 'movie_info_idx',
    'K': 'keyword', 'K1': 'keyword', 'K2': 'keyword',
    'ML': 'movie_link',
    'CN': 'company_name', 'CN1': 'company_name', 'CN2': 'company_name',
    'CCT1': 'comp_cast_type', 'CCT2': 'comp_cast_type', 'CCT': 'comp_cast_type',
    'IT1': 'info_type', 'IT2': 'info_type', 'IT': 'info_type',
    'CT': 'company_type', 'CT1': 'company_type', 'CT2': 'company_type',
    'N': 'name', 'N1': 'name', 'N2': 'name',
    'KT': 'kind_type', 'KT1': 'kind_type', 'KT2': 'kind_type',
    'LT': 'link_type',
    'CHN': 'char_name',
    'AN': 'aka_name', 'AN1': 'aka_name', 'AN2': 'aka_name',
    'RT': 'role_type',
    'AT': 'aka_title', 'AT1': 'aka_title', 'AT2': 'aka_title',
    'PI': 'person_info',
}


def lp_table_to_duckdb(abb):
    return LP_TABLE_MAP.get(abb.upper(), abb.lower())


def parse_sql_canonical(sql, table_map_fn=None):
    """
    Parse SQL and return canonical signature: (sorted_tables, canonical_joins)
    table_map_fn: optional function to map table aliases to real table names
    """
    sql = re.sub(r'\s+', ' ', sql).strip().rstrip(';').lower()
    fm = re.search(r'from (.+?)( where |$)', sql)
    if not fm:
        return None

    a2t = {}
    tables_set = set()
    for t_str in fm.group(1).split(","):
        p = t_str.strip().split()
        if len(p) >= 3 and p[1] == 'as':
            tbl_raw, als = p[0], p[2]
        elif len(p) >= 2:
            tbl_raw, als = p[0], p[1]
        else:
            tbl_raw = als = p[0]
        # strip numeric suffix for deduplication
        tbl = re.sub(r'\d+$', '', tbl_raw)
        if table_map_fn:
            tbl = table_map_fn(tbl)
        a2t[als] = tbl
        tables_set.add(tbl)

    tables = tuple(sorted(tables_set))

    wm = re.search(r'where (.+)$', sql)
    conds = [c.strip() for c in wm.group(1).split(" and ")] if wm else []

    joins_raw = []
    for c in conds:
        ps = re.split(r'(<=|>=|!=|<>|=|<|>)', c, maxsplit=1)
        if len(ps) >= 3 and '.' in ps[0] and '.' in ps[2]:
            joins_raw.append((ps[0].strip(), ps[1], ps[2].strip()))

    # Union-Find to normalize join conditions
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

    for l, op, r in joins_raw:
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

    return (tables, tuple(sorted(canonical_joins)))


def translate_lp_sql_to_duckdb(sql):
    """
    Translate LpBound SQL to a DuckDB-executable COUNT(*) query
    """
    sql = sql.strip().rstrip(';')
    fm = re.search(r'from\s+(.+?)(\s+where\s+|$)', sql, re.IGNORECASE)
    if not fm:
        return None

    from_text = fm.group(1)
    wm = re.search(r'where\s+(.+)$', sql, re.IGNORECASE)
    where_text = wm.group(1) if wm else None

    table_parts = []
    for t_str in from_text.split(','):
        p = t_str.strip().split()
        if len(p) >= 3 and p[1].lower() == 'as':
            tbl_raw, als = p[0], p[2]
        elif len(p) >= 2:
            tbl_raw, als = p[0], p[1]
        else:
            tbl_raw = p[0]
            als = tbl_raw
        tbl = lp_table_to_duckdb(tbl_raw).lower()
        # DuckDB keyword handling
        if tbl == 'name':
            tbl = f'"{tbl}"'
        table_parts.append(f"{tbl} AS {als.lower()}")

    from_clause = ', '.join(table_parts)
    if where_text:
        sql_new = f"SELECT COUNT(*) FROM {from_clause} WHERE {where_text.lower()}"
    else:
        sql_new = f"SELECT COUNT(*) FROM {from_clause}"
    return sql_new


def translate_starce_sql_to_duckdb(sql):
    """
    Translate StarCE subquery SQL to a COUNT(*) query executable directly in DuckDB.
    StarCE uses `table_name AS table_name1` format aliases.
    """
    sql = sql.strip().rstrip(';').lower()
    # StarCE queries are already in COUNT(*) format, only need to handle table name quoting
    # check if FROM clause contains keyword table names
    for kw in ['name', 'key', 'order']:
        sql = re.sub(
            rf'\b{kw}\b(?=\s+AS\s+)',
            f'"{kw}"',
            sql,
            flags=re.IGNORECASE
        )
    return sql + ';'


def phase1_parse_and_match():
    """Phase 1: Parse both sides' data, normalize signatures, match."""
    print("=" * 70)
    print("Phase 1: Parse & signature matching (no DB operations)")
    print("=" * 70)

    # ─── Read StarCE subqueries ───
    sc_sql_path = PROJ / 'benchmark/jobjoin/subqueries/subquery.sql'
    sc_real_path = PROJ / 'benchmark/jobjoin/subqueries/result/real.txt'

    with open(sc_sql_path) as f:
        sc_sqls = [l.strip() for l in f if l.strip()]
    with open(sc_real_path) as f:
        sc_reals = [int(l.strip()) for l in f if l.strip()]

    assert len(sc_sqls) == len(sc_reals), \
        f"StarCE SQL/real count mismatch: {len(sc_sqls)} vs {len(sc_reals)}"

    sc_data = []
    sc_errors = 0
    for i, sql in enumerate(sc_sqls):
        sig = parse_sql_canonical(sql)
        if sig is None:
            sc_errors += 1
            continue
        sc_data.append({'idx': i, 'sql': sql, 'sig': sig, 'card': sc_reals[i]})

    print(f"StarCE: {len(sc_sqls)} subqueries, {len(sc_data)} parsed, {sc_errors} errors")

    # ─── Read LpBound CSV ───
    csv_path = PROJ / 'methods/LpBound/benchmarks/workloads/jobjoin/jobjoin_subqueries.csv'
    with open(csv_path) as f:
        lines = f.readlines()

    lp_data = []
    lp_errors = 0
    for line in lines[1:]:  # skip header
        parts = line.strip().split('|', 2)
        if len(parts) < 3:
            continue
        qid = int(parts[0])
        sql = parts[2]
        sig = parse_sql_canonical(sql, table_map_fn=lp_table_to_duckdb)
        if sig is None:
            lp_errors += 1
            continue
        lp_data.append({'qid': qid, 'sql': sql, 'sig': sig})

    print(f"LpBound: {len(lines)-1} entries, {len(lp_data)} parsed, {lp_errors} errors")

    # ─── Index LpBound by signature ───
    lp_by_sig = defaultdict(list)
    for entry in lp_data:
        lp_by_sig[entry['sig']].append(entry)

    # analyze LpBound signature duplicates
    sig_with_multi = [(sig, entries) for sig, entries in lp_by_sig.items() if len(entries) > 1]
    print(f"\nLpBound unique signatures: {len(lp_by_sig)}")
    print(f"LpBound duplicate signatures (same signature, multiple entries): {len(sig_with_multi)}")
    if sig_with_multi:
        for sig, entries in sorted(sig_with_multi, key=lambda x: -len(x[1]))[:5]:
            qids = sorted(set(e['qid'] for e in entries))
            print(f"  tables={sig[0]}, count={len(entries)}, qids={qids}")

    # ─── Match ───
    matched = []
    unmatched = []
    multi_match = []  # one StarCE signature matches multiple LpBound entries

    for sc_entry in sc_data:
        sig = sc_entry['sig']
        if sig in lp_by_sig:
            lp_entries = lp_by_sig[sig]
            matched.append((sc_entry, lp_entries))
            if len(lp_entries) > 1:
                multi_match.append((sc_entry, lp_entries))
        else:
            unmatched.append(sc_entry)

    print(f"\n── Match Results ──")
    print(f"Matched:    {len(matched)}/{len(sc_data)} ({100*len(matched)/len(sc_data):.1f}%)")
    print(f"Unmatched:  {len(unmatched)}/{len(sc_data)}")
    print(f"  of which one-to-many matches: {len(multi_match)}")

    # ─── Analyze by table count ───
    by_n = defaultdict(lambda: [0, 0])
    for sc_entry in sc_data:
        n = len(sc_entry['sig'][0])
        by_n[n][1] += 1
    for sc_entry, _ in matched:
        n = len(sc_entry['sig'][0])
        by_n[n][0] += 1

    print(f"\n── Match rate by table count ──")
    for n in sorted(by_n):
        ma, tot = by_n[n]
        print(f"  {n}-table: {ma}/{tot} ({100*ma/tot:.0f}%)")

    # ─── Unmatched reason analysis ───
    if unmatched:
        print(f"\n── Unmatched Reason Analysis ──")
        # check if it is a table name mapping issue
        unknown_tables = defaultdict(list)
        starce_only_tables = set()
        lp_only_tables = set()
        for sc_entry in unmatched:
            for t in sc_entry['sig'][0]:
                starce_only_tables.add(t)

        lp_all_tables = set()
        for entry in lp_data:
            for t in entry['sig'][0]:
                lp_all_tables.add(t)

        starce_all_tables = set()
        for sc_entry in sc_data:
            for t in sc_entry['sig'][0]:
                starce_all_tables.add(t)

        print(f"  StarCE all tables: {sorted(starce_all_tables)}")
        print(f"  LpBound all tables: {sorted(lp_all_tables)}")
        print(f"  StarCE-only tables: {sorted(starce_all_tables - lp_all_tables)}")
        print(f"  LpBound-only tables: {sorted(lp_all_tables - starce_all_tables)}")

        # for matched and unmatched, compare join structures
        # see if unmatched due to same table set but different joins
        sc_tables_to_lp = defaultdict(list)  # StarCE table_set -> list of LpBound entries
        for entry in lp_data:
            sc_tables_to_lp[entry['sig'][0]].append(entry)

        same_tbl_diff_join = 0
        no_same_tbl = 0
        for sc_entry in unmatched:
            if sc_entry['sig'][0] in sc_tables_to_lp:
                same_tbl_diff_join += 1
            else:
                no_same_tbl += 1

        print(f"\n  Among unmatched:")
        print(f"    same table set but different joins: {same_tbl_diff_join}")
        print(f"    no matching table set: {no_same_tbl}")

        if same_tbl_diff_join > 0:
            print(f"\n  ── Examples of same table set but different joins (first 3) ──")
            count = 0
            for sc_entry in unmatched:
                if sc_entry['sig'][0] in sc_tables_to_lp and count < 3:
                    count += 1
                    sc_tables, sc_joins = sc_entry['sig']
                    lp_entries = sc_tables_to_lp[sc_tables]
                    lp_tables, lp_joins = lp_entries[0]['sig']
                    print(f"\n  StarCE idx={sc_entry['idx']}:")
                    print(f"    tables: {sc_tables}")
                    print(f"    joins:  {list(sc_joins)}")
                    print(f"  LpBound (same table set):")
                    print(f"    joins:  {list(lp_joins)}")
                    # show specific differences
                    sc_joins_set = set(sc_joins)
                    lp_joins_set = set(lp_joins)
                    print(f"    SC-only joins: {sc_joins_set - lp_joins_set}")
                    print(f"    LP-only joins: {lp_joins_set - sc_joins_set}")

    return sc_data, lp_data, matched, unmatched, lp_by_sig


def phase2_verify_sample(sc_data, lp_data, matched, unmatched, lp_by_sig, sample_n=20):
    """Phase 2: Sample matched pairs, compute true cardinalities from both sides directly using DuckDB."""
    print(f"\n{'=' * 70}")
    print(f"Phase 2: DuckDB cardinality verification (sample {sample_n} entries)")
    print("=" * 70)

    import duckdb

    DB_PATH = PROJ / 'Benchmark/duckdb/imdb.db'
    con = duckdb.connect(str(DB_PATH))

    # randomly sample from matched
    random.seed(42)
    if len(matched) >= sample_n:
        matched_sample = random.sample(matched, sample_n)
    else:
        matched_sample = matched

    # sample from unmatched for verification (cardinalities should differ, or sides use different joins)
    unmatched_sample = []
    if len(unmatched) >= 5:
        unmatched_sample = random.sample(unmatched, 5)

    results = []
    sc_self_verify_errors = 0
    lp_compute_errors = 0

    for sc_entry, lp_entries in matched_sample:
        # directly run StarCE query to verify true cardinality in real.txt
        sc_sql = translate_starce_sql_to_duckdb(sc_entry['sql'])
        try:
            sc_computed = int(con.execute(sc_sql).fetchone()[0])
        except Exception as e:
            sc_computed = None
            sc_self_verify_errors += 1

        # run the corresponding LpBound query to compute true cardinality
        lp_entry = lp_entries[0]
        lp_sql = translate_lp_sql_to_duckdb(lp_entry['sql'])
        try:
            lp_computed = int(con.execute(lp_sql).fetchone()[0])
        except Exception as e:
            lp_computed = None
            lp_compute_errors += 1

        results.append({
            'type': 'matched',
            'sc_idx': sc_entry['idx'],
            'sc_tables': sc_entry['sig'][0],
            'sc_real_file': sc_entry['card'],
            'sc_computed': sc_computed,
            'lp_qid': lp_entry['qid'],
            'lp_computed': lp_computed,
        })

    # also spot-check some unmatched
    for sc_entry in unmatched_sample:
        sc_sql = translate_starce_sql_to_duckdb(sc_entry['sql'])
        try:
            sc_computed = int(con.execute(sc_sql).fetchone()[0])
        except:
            sc_computed = None

        # find LpBound entries with same table set for comparison
        tables = sc_entry['sig'][0]
        lp_same_tables = [v for k, v in lp_by_sig.items() if k[0] == tables]
        lp_compared = None
        if lp_same_tables:
            lp_entry = lp_same_tables[0][0]
            lp_sql = translate_lp_sql_to_duckdb(lp_entry['sql'])
            try:
                lp_compared = int(con.execute(lp_sql).fetchone()[0])
            except:
                pass

        results.append({
            'type': 'unmatched',
            'sc_idx': sc_entry['idx'],
            'sc_tables': sc_entry['sig'][0],
            'sc_real_file': sc_entry['card'],
            'sc_computed': sc_computed,
            'lp_compared': lp_compared,
        })

    con.close()

    # ─── Output results ───
    print(f"\nStarCE real.txt self-verification: {sc_self_verify_errors}/{len(matched_sample)} compute failures")
    print(f"LpBound compute failures: {lp_compute_errors}/{len(matched_sample)}")

    print(f"\n── Matched Pair Verification Results ──")
    verified = [r for r in results if r['type'] == 'matched']

    sc_real_vs_computed_match = 0
    sc_real_vs_computed_diff = 0
    sc_real_vs_lp_diff = 0

    for r in verified:
        print(f"\n  StarCE idx={r['sc_idx']}, LpBound Q={r['lp_qid']}, tables={r['sc_tables']}")
        print(f"    StarCE real.txt : {r['sc_real_file']:,}")
        print(f"    StarCE computed : {r['sc_computed']:,}" if r['sc_computed'] else f"    StarCE computed : ERROR")
        print(f"    LpBound computed: {r['lp_computed']:,}" if r['lp_computed'] else f"    LpBound computed: ERROR")

        if r['sc_computed'] and r['sc_real_file'] == r['sc_computed']:
            sc_real_vs_computed_match += 1
        elif r['sc_computed']:
            sc_real_vs_computed_diff += 1
            rel_err = r['sc_real_file'] / r['sc_computed'] if r['sc_computed'] != 0 else float('inf')
            print(f"    ⚠ StarCE real vs computed MISMATCH! rel_err={rel_err:.6f}")

        if r['sc_computed'] and r['lp_computed'] and r['sc_computed'] != r['lp_computed']:
            sc_real_vs_lp_diff += 1
            rel_err = r['sc_computed'] / r['lp_computed'] if r['lp_computed'] != 0 else float('inf')
            print(f"    ⚠ SC vs LP cardinality DIFFERS! rel_err={rel_err:.6f}")

    # ─── Unmatched pair verification results ───
    unverified = [r for r in results if r['type'] == 'unmatched']
    if unverified:
        print(f"\n── Unmatched Pair Spot-check Results ──")
        for r in unverified:
            print(f"\n  StarCE idx={r['sc_idx']}, tables={r['sc_tables']}")
            print(f"    StarCE real.txt : {r['sc_real_file']:,}")
            print(f"    StarCE computed : {r['sc_computed']:,}" if r['sc_computed'] else f"    StarCE computed : ERROR")
            if r['lp_compared']:
                print(f"    LpBound (same table set): {r['lp_compared']:,}")
                if r['sc_computed'] and r['sc_computed'] != r['lp_compared']:
                    rel_err = r['sc_computed'] / r['lp_compared'] if r['lp_compared'] != 0 else float('inf')
                    print(f"    ⚠ cardinality differs (different join structure): rel_err={rel_err:.6f}")

    # ─── Final summary ───
    print(f"\n{'=' * 70}")
    print("Final Summary")
    print("=" * 70)
    print(f"\n  StarCE real.txt self-verification: {sc_real_vs_computed_match} match / {sc_real_vs_computed_diff} mismatch")
    print(f"  SC vs LP cardinality mismatch: {sc_real_vs_lp_diff} (should be 0, same tables and joins)")
    print(f"  Sample size: {len(verified)} matched pairs")

    return results


def main():
    # Phase 1: Parse and match
    sc_data, lp_data, matched, unmatched, lp_by_sig = phase1_parse_and_match()

    # Phase 2: Sample DuckDB verification
    if matched:
        phase2_verify_sample(sc_data, lp_data, matched, unmatched, lp_by_sig, sample_n=30)
    else:
        print("\n⚠ No matching pairs found, skipping Phase 2")
        print("\nPossible root cause analysis:")
        sc_all_tables = set()
        for entry in sc_data:
            sc_all_tables.update(entry['sig'][0])
        lp_all_tables = set()
        for entry in lp_data:
            lp_all_tables.update(entry['sig'][0])
        print(f"  StarCE all tables: {sorted(sc_all_tables)}")
        print(f"  LpBound all tables: {sorted(lp_all_tables)}")

        # check if table name mapping is correct
        print("\n  Sample StarCE SQL:")
        for sc_entry in sc_data[:3]:
            print(f"    [{sc_entry['idx']}] tables={sc_entry['sig'][0]}, joins={sc_entry['sig'][1][:2]}")
        print("\n  Sample LpBound SQL:")
        for lp_entry in lp_data[:3]:
            print(f"    [Q{lp_entry['qid']}] tables={lp_entry['sig'][0]}, joins={lp_entry['sig'][1][:2]}")


if __name__ == '__main__':
    main()
