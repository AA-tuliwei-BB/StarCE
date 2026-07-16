#!/usr/bin/env python3
"""
Compute true cardinality of join queries via GROUP BY pushdown.

Algorithm: For each base table, GROUP BY join key with COUNT(*); push single-table predicates into CTE WHERE;
then join the grouped results and SUM(product of cnt). Avoids generating huge intermediate results from direct joins.

Supports JOBM / JOBLight / JOBLightRanges / JobJoin / STATS benchmarks.

Usage:
    python scripts/compute_join_true_cards.py \
        --db Benchmark/duckdb/imdb.db \
        --queries benchmark/jobjoin/queries.sql \
        --output benchmark/jobjoin/subqueries/result/real.txt \
        --subquery-sql benchmark/jobjoin/subqueries/subquery.sql
"""

import argparse
import re
import sys
from collections import defaultdict


def qid(name):
    """Wrap identifier in double quotes to prevent keyword conflicts (e.g., DuckDB's AT)."""
    return f'"{name}"'


def parse_query(query):
    """
    Parse query, return (aliases_map, join_conditions, predicates).

    aliases_map: {alias: table_name}
    join_conditions: [(left_alias, left_col, right_alias, right_col)]
    predicates: {alias: [condition_string]}  -- single-table predicates, grouped by alias
    """
    from_match = re.search(
        r'FROM\s+(.*?)\s+WHERE\s+',
        query, re.IGNORECASE | re.DOTALL
    )
    if not from_match:
        raise ValueError(f"Cannot parse FROM clause: {query[:100]}")

    from_text = from_match.group(1)

    aliases_map = {}
    for m in re.finditer(r'(?i)(\w+)\s+AS\s+(\w+)', from_text):
        # Unified lowercase: SQL identifiers are case-insensitive
        aliases_map[m.group(2).lower()] = m.group(1).lower()

    where_match = re.search(
        r'WHERE\s+(.*?);?\s*$',
        query, re.IGNORECASE | re.DOTALL
    )
    if not where_match:
        raise ValueError(f"Cannot parse WHERE clause: {query[:100]}")

    where_text = where_match.group(1).rstrip(';')

    conditions = split_and(where_text)

    join_conditions = []
    cross_predicates = []
    predicates = defaultdict(list)

    for cond in conditions:
        jc = parse_join_condition(cond, aliases_map)
        if jc:
            join_conditions.append(jc)
        else:
            # Classify single-table predicates
            refs = find_alias_refs(cond, aliases_map)
            if len(refs) == 1:
                alias = refs[0]
                predicates[alias].append(cond)
            elif len(refs) > 1:
                # Cross-table predicates stay in outer WHERE
                cross_predicates.append(cond)
            # refs == 0: unclassifiable expressions stay in outer WHERE too (e.g., pure constants)

    return aliases_map, join_conditions, dict(predicates), cross_predicates


def find_alias_refs(cond, aliases_map):
    """Return deduplicated list of table aliases referenced in the condition (case-insensitive)."""
    refs = set()
    for alias in aliases_map:
        if re.search(rf'\b{re.escape(alias)}\.\w+', cond, re.IGNORECASE):
            refs.add(alias)
    return list(refs)


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
    If it is a join condition (alias.col = alias.col), return (left_alias, left_col, right_alias, right_col).
    Otherwise return None.
    """
    m = re.match(
        r'^\s*(\w+)\.(\w+)\s*(=|!=|<>)\s*(\w+)\.(\w+)\s*$',
        cond
    )
    if not m:
        return None

    left_alias = m.group(1).lower()
    left_col = m.group(2).lower()
    op = m.group(3)
    right_alias = m.group(4).lower()
    right_col = m.group(5).lower()

    if op != '=':
        return None

    if left_alias not in aliases_map or right_alias not in aliases_map:
        return None

    return (left_alias, left_col, right_alias, right_col)


def get_join_keys(aliases_map, join_conditions):
    """Return {alias: [join_key_columns]}."""
    keys = defaultdict(set)
    for left_alias, left_col, right_alias, right_col in join_conditions:
        keys[left_alias].add(left_col)
        keys[right_alias].add(right_col)
    return {alias: sorted(cols) for alias, cols in keys.items()}


def build_grouped_query(aliases_map, join_conditions, predicates, cross_predicates):
    """
    Build a count query using GROUP BY pushdown.
    predicates: {alias: [cond_str]}  -- single-table predicates
    cross_predicates: [cond_str]     -- cross-table predicates, stay in outer WHERE
    """
    join_keys = get_join_keys(aliases_map, join_conditions)

    # Build CTEs: each table GROUP BY join key, with single-table predicates
    ctes = []
    for alias in sorted(aliases_map):
        table_name = aliases_map[alias]
        cols = join_keys.get(alias, [])
        col_list = ', '.join(qid(c) for c in cols)

        # Single-table predicates: strip alias. prefix (CTE body only has base table, no alias qualification needed)
        preds = predicates.get(alias, [])
        fixed_preds = []
        for pred in preds:
            fixed_pred = re.sub(
                rf'\b{re.escape(alias)}\.(\w+)',
                r'\1', pred, flags=re.IGNORECASE
            )
            fixed_preds.append(fixed_pred)
        where_clause = ''
        if fixed_preds:
            where_clause = f"\n        WHERE {' AND '.join(fixed_preds)}"

        if cols:
            ctes.append(
                f"    {qid(alias)} AS (\n"
                f"        SELECT {col_list}, COUNT(*) AS cnt\n"
                f"        FROM {qid(table_name)}{where_clause}\n"
                f"        GROUP BY {col_list}\n"
                f"    )"
            )
        else:
            ctes.append(
                f"    {qid(alias)} AS (\n"
                f"        SELECT COUNT(*) AS cnt\n"
                f"        FROM {qid(table_name)}{where_clause}\n"
                f"    )"
            )

    # JOIN conditions
    join_clauses = []
    for left_alias, left_col, right_alias, right_col in join_conditions:
        join_clauses.append(
            f"{qid(left_alias)}.{qid(left_col)} = {qid(right_alias)}.{qid(right_col)}"
        )

    # Cross-table predicates
    all_outer_conds = join_clauses + cross_predicates

    # SELECT: SUM(product of cnt)
    cnt_product = ' * '.join(
        f"{qid(alias)}.cnt" for alias in sorted(aliases_map)
    )

    from_list = ', '.join(qid(a) for a in sorted(aliases_map))

    if all_outer_conds:
        where_str = ' AND '.join(all_outer_conds)
        sql = (
            f"WITH\n"
            + ',\n'.join(ctes) + '\n'
            f"SELECT COALESCE(SUM({cnt_product}), 0)\n"
            f"FROM {from_list}\n"
            f"WHERE {where_str};"
        )
    else:
        sql = (
            f"WITH\n"
            + ',\n'.join(ctes) + '\n'
            f"SELECT COALESCE(SUM({cnt_product}), 0)\n"
            f"FROM {from_list};"
        )

    return sql


def compute_query(con, query):
    """Parse query and return true cardinality."""
    aliases_map, join_conditions, predicates, cross_predicates = parse_query(query)
    gq = build_grouped_query(aliases_map, join_conditions, predicates, cross_predicates)
    result = con.execute(gq).fetchone()
    return int(result[0])


def process_queries(con, queries, label):
    """Process a set of queries, return cardinality list."""
    cards = []
    for i, q in enumerate(queries, 1):
        if not q.strip():
            continue
        try:
            card = compute_query(con, q)
            cards.append(card)
            n_tables = len(re.findall(r'(?i)\bAS\s+(\w+)', q))
            if i <= 5 or i % 200 == 0 or i == len(queries):
                print(f"  {label} Q{i:<4d} ({n_tables} tables): {card:,}")
        except Exception as e:
            print(f"  {label} Q{i:<4d}: ERROR - {e}", file=sys.stderr)
            cards.append(-1)
    return cards


def main():
    parser = argparse.ArgumentParser(
        description='Compute join query true cardinality via GROUP BY pushdown'
    )
    parser.add_argument('--db', required=True, help='DuckDB database path')
    parser.add_argument('--queries', required=True, help='Main query file path')
    parser.add_argument('--output', required=True, help='Main query true cardinality output file')
    parser.add_argument('--subquery-sql', default=None,
                        help='subquery.sql path (also compute subquery true cardinalities)')
    parser.add_argument('--subquery-output', default=None,
                        help='Subquery true cardinality output file (default: result/real.txt in same dir as --subquery-sql)')
    args = parser.parse_args()

    import duckdb

    con = duckdb.connect(args.db)

    # Main queries
    with open(args.queries) as f:
        queries = [l.strip() for l in f if l.strip()]
    print(f"Main queries: {len(queries)} entries")
    cards = process_queries(con, queries, "Main")

    with open(args.output, 'w') as f:
        for c in cards:
            f.write(f"{c}\n")
    print(f"Main query true cardinalities -> {args.output}")

    # Subqueries
    if args.subquery_sql:
        import os
        with open(args.subquery_sql) as f:
            sub_queries = [l.strip() for l in f if l.strip()]
        print(f"\nSubqueries: {len(sub_queries)} entries")
        sub_cards = process_queries(con, sub_queries, "Sub")

        if args.subquery_output:
            sub_out = args.subquery_output
        else:
            sub_out = os.path.join(os.path.dirname(args.subquery_sql),
                                   'result', 'real.txt')
        os.makedirs(os.path.dirname(sub_out), exist_ok=True)
        with open(sub_out, 'w') as f:
            for c in sub_cards:
                f.write(f"{c}\n")
        print(f"Subquery true cardinalities -> {sub_out}")

    con.close()
    print("\nDone.")


if __name__ == '__main__':
    main()
