#!/usr/bin/env python3
"""
通过 GROUP BY 下推计算 join 查询的真实基数。

算法：对每个基表按 join key 做 GROUP BY COUNT(*)，单表谓词下推到 CTE 的 WHERE 中，
然后连接分组结果，最后 SUM(cnt 的乘积)。避免直接 join 产生巨大的中间结果。

支持 JOBM / JOBLight / JOBLightRanges / JobJoin / STATS 等 benchmark。

用法：
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
    """双引号包裹标识符，防止关键字冲突（如 DuckDB 的 AT）。"""
    return f'"{name}"'


def parse_query(query):
    """
    解析查询，返回 (aliases_map, join_conditions, predicates)。

    aliases_map: {alias: table_name}
    join_conditions: [(left_alias, left_col, right_alias, right_col)]
    predicates: {alias: [condition_string]}  — 单表谓词，已按 alias 归类
    """
    from_match = re.search(
        r'FROM\s+(.*?)\s+WHERE\s+',
        query, re.IGNORECASE | re.DOTALL
    )
    if not from_match:
        raise ValueError(f"无法解析 FROM 子句: {query[:100]}")

    from_text = from_match.group(1)

    aliases_map = {}
    for m in re.finditer(r'(?i)(\w+)\s+AS\s+(\w+)', from_text):
        # 统一小写：SQL 标识符大小写不敏感
        aliases_map[m.group(2).lower()] = m.group(1).lower()

    where_match = re.search(
        r'WHERE\s+(.*?);?\s*$',
        query, re.IGNORECASE | re.DOTALL
    )
    if not where_match:
        raise ValueError(f"无法解析 WHERE 子句: {query[:100]}")

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
            # 归类单表谓词
            refs = find_alias_refs(cond, aliases_map)
            if len(refs) == 1:
                alias = refs[0]
                predicates[alias].append(cond)
            elif len(refs) > 1:
                # 跨表谓词留在外层 WHERE
                cross_predicates.append(cond)
            # refs == 0: 无法归类的表达式也留在外层（如纯常量）

    return aliases_map, join_conditions, dict(predicates), cross_predicates


def find_alias_refs(cond, aliases_map):
    """返回条件中引用的表别名列表（去重），大小写不敏感。"""
    refs = set()
    for alias in aliases_map:
        if re.search(rf'\b{re.escape(alias)}\.\w+', cond, re.IGNORECASE):
            refs.add(alias)
    return list(refs)


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
    如果是 join 条件 (alias.col = alias.col)，返回 (left_alias, left_col, right_alias, right_col)。
    否则返回 None。
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
    """返回 {alias: [join_key_columns]}。"""
    keys = defaultdict(set)
    for left_alias, left_col, right_alias, right_col in join_conditions:
        keys[left_alias].add(left_col)
        keys[right_alias].add(right_col)
    return {alias: sorted(cols) for alias, cols in keys.items()}


def build_grouped_query(aliases_map, join_conditions, predicates, cross_predicates):
    """
    构建使用 GROUP BY 下推的计数查询。
    predicates: {alias: [cond_str]}  — 单表谓词
    cross_predicates: [cond_str]     — 跨表谓词，留在外层 WHERE
    """
    join_keys = get_join_keys(aliases_map, join_conditions)

    # 构建 CTE：每个表按 join key GROUP BY，带单表谓词
    ctes = []
    for alias in sorted(aliases_map):
        table_name = aliases_map[alias]
        cols = join_keys.get(alias, [])
        col_list = ', '.join(qid(c) for c in cols)

        # 单表谓词：去掉 alias. 前缀（CTE 内部只有基表，不需要别名限定）
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

    # JOIN 条件
    join_clauses = []
    for left_alias, left_col, right_alias, right_col in join_conditions:
        join_clauses.append(
            f"{qid(left_alias)}.{qid(left_col)} = {qid(right_alias)}.{qid(right_col)}"
        )

    # 跨表谓词
    all_outer_conds = join_clauses + cross_predicates

    # SELECT: SUM(cnt 乘积)
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
    """解析查询并返回真实基数。"""
    aliases_map, join_conditions, predicates, cross_predicates = parse_query(query)
    gq = build_grouped_query(aliases_map, join_conditions, predicates, cross_predicates)
    result = con.execute(gq).fetchone()
    return int(result[0])


def process_queries(con, queries, label):
    """处理一组查询，返回基数列表。"""
    cards = []
    for i, q in enumerate(queries, 1):
        if not q.strip():
            continue
        try:
            card = compute_query(con, q)
            cards.append(card)
            n_tables = len(re.findall(r'(?i)\bAS\s+(\w+)', q))
            if i <= 5 or i % 200 == 0 or i == len(queries):
                print(f"  {label} Q{i:<4d} ({n_tables}表): {card:,}")
        except Exception as e:
            print(f"  {label} Q{i:<4d}: ERROR - {e}", file=sys.stderr)
            cards.append(-1)
    return cards


def main():
    parser = argparse.ArgumentParser(
        description='通过 GROUP BY 下推计算 join 查询真实基数'
    )
    parser.add_argument('--db', required=True, help='DuckDB 数据库路径')
    parser.add_argument('--queries', required=True, help='主查询文件路径')
    parser.add_argument('--output', required=True, help='主查询真实基数输出文件')
    parser.add_argument('--subquery-sql', default=None,
                        help='subquery.sql 路径（同时计算子查询真实基数）')
    parser.add_argument('--subquery-output', default=None,
                        help='子查询真实基数输出文件（默认与 --subquery-sql 同目录 result/real.txt）')
    args = parser.parse_args()

    import duckdb

    con = duckdb.connect(args.db)

    # 主查询
    with open(args.queries) as f:
        queries = [l.strip() for l in f if l.strip()]
    print(f"主查询: {len(queries)} 条")
    cards = process_queries(con, queries, "主")

    with open(args.output, 'w') as f:
        for c in cards:
            f.write(f"{c}\n")
    print(f"主查询真实基数 → {args.output}")

    # 子查询
    if args.subquery_sql:
        import os
        with open(args.subquery_sql) as f:
            sub_queries = [l.strip() for l in f if l.strip()]
        print(f"\n子查询: {len(sub_queries)} 条")
        sub_cards = process_queries(con, sub_queries, "子")

        if args.subquery_output:
            sub_out = args.subquery_output
        else:
            sub_out = os.path.join(os.path.dirname(args.subquery_sql),
                                   'result', 'real.txt')
        os.makedirs(os.path.dirname(sub_out), exist_ok=True)
        with open(sub_out, 'w') as f:
            for c in sub_cards:
                f.write(f"{c}\n")
        print(f"子查询真实基数 → {sub_out}")

    con.close()
    print("\n完成。")


if __name__ == '__main__':
    main()
