"""
JobJoin 子查询级 FactorJoin 评估脚本。
读取 subquery.sql（9565 条），逐条调用 get_cardinality_bound_one，
产出 Benchmark/workloads/JobJoin/subquery/result/factorjoin.txt。

用法:
  cd methods/FactorJoin
  python scripts/evaluate_jobjoin_subqueries.py
"""
import sys, os, time, pickle, re

# 确保 FactorJoin 目录在 path 中
_factorjoin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _factorjoin_dir)

# 先导入 data_prepare 打破 bound.py ↔ data_prepare.py 循环导入
from Join_scheme.data_prepare import identify_key_values  # noqa: F401
from Join_scheme.bound import Bound_ensemble  # noqa: E402


def normalize_table_names(sql):
    """规范化 subquery.sql 中的表名、别名和列名大小写：
    1. 表名转小写（修复 MOVIE_keyword/AKA_name 等问题）
    2. 别名转小写（修复 CT/MC 等大写别名）
    3. WHERE 子句中 alias.column 的列名转小写（修复 ID/company_type_ID 等）
    4. WHERE 子句中 alias.column 引用别名同步转小写"""
    match = re.search(r'\bFROM\b\s+(.*?)\s+\bWHERE\b', sql, re.IGNORECASE)
    if not match:
        return sql
    from_clause = match.group(1)
    alias_map = {}  # 原始别名 -> 小写别名
    parts = []
    for part in from_clause.split(','):
        part = part.strip()
        m = re.match(r'(\S+)\s+AS\s+(\S+)', part, re.IGNORECASE)
        if m:
            table_name = m.group(1).lower()
            alias_orig = m.group(2)
            alias_lower = alias_orig.lower()
            alias_map[alias_orig] = alias_lower
            parts.append(f'{table_name} AS {alias_lower}')
        else:
            parts.append(part)
    new_from = ', '.join(parts)

    # 替换 WHERE 子句（及之后）中的别名引用和列名
    rest = sql[match.end(1):]
    # 按别名长度降序排列，避免短别名误替换
    for orig, lower in sorted(alias_map.items(), key=lambda x: -len(x[0])):
        # 替换 alias.column → lower.column_lower
        # 匹配 alias.ColumnName 模式，对大写开头/全大写的列名转小写
        rest = re.sub(
            r'\b' + re.escape(orig) + r'\.(\w+)',
            lambda m, lo=lower: lo + '.' + m.group(1).lower(),
            rest
        )
    return sql[:match.start(1)] + new_from + rest


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    factorjoin_dir = os.path.dirname(script_dir)
    proj_root = os.path.normpath(os.path.join(factorjoin_dir, "../.."))

    model_path = os.path.join(factorjoin_dir, "checkpoints/model_imdb_default.pkl")
    query_file = os.path.join(proj_root, "Benchmark/workloads/JobJoin/subquery/subquery.sql")
    mapping_file = os.path.join(factorjoin_dir, "checkpoints/jobjoin_subquery_to_main.pkl")
    sample_loc = os.path.join(factorjoin_dir, "checkpoints/binned_cards_{}/")
    save_file = os.path.join(proj_root, "Benchmark/workloads/JobJoin/subquery/result/factorjoin.txt")

    print(f"模型: {model_path}")
    print(f"查询文件: {query_file}")
    print(f"映射文件: {mapping_file}")
    print(f"采样目录: {sample_loc}")
    print(f"输出文件: {save_file}")

    # 加载模型
    print("加载模型...")
    with open(model_path, "rb") as f:
        be = pickle.load(f)
    print(f"  bns: {be.bns}, n_dim_dist: {be.n_dim_dist}")
    print(f"  ground_truth_factors_no_filter 表数: {len(be.ground_truth_factors_no_filter)}")

    # 设置采样参数
    be.SPERCENTAGE = 1.0
    be.query_sample_location = sample_loc

    # 加载映射
    with open(mapping_file, "rb") as f:
        mapping = pickle.load(f)

    # 加载子查询
    with open(query_file, "r") as f:
        queries = [line.strip() for line in f.readlines() if line.strip()]

    assert len(queries) == len(mapping), \
        f"查询数 ({len(queries)}) != 映射数 ({len(mapping)})"

    print(f"共 {len(queries)} 条子查询")

    preds = []
    failed = []
    t_start = time.time()

    for i, sql in enumerate(queries):
        main_id = mapping[i]
        try:
            sql_norm = normalize_table_names(sql)
            res = be.get_cardinality_bound_one(sql_norm, query_name=f"{main_id}.pkl")
            preds.append(res)
        except Exception as e:
            preds.append("MISSING")
            failed.append((i + 1, type(e).__name__, str(e)))

        if (i + 1) % 500 == 0:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed
            eta = (len(queries) - (i + 1)) / rate if rate > 0 else 0
            print(f"  已估计 {i+1}/{len(queries)} ({100*(i+1)/len(queries):.1f}%), "
                  f"耗时 {elapsed:.0f}s, 速率 {rate:.1f} q/s, ETA {eta:.0f}s")

    elapsed = time.time() - t_start
    print(f"总耗时: {elapsed:.1f}s, 平均 {elapsed/len(queries):.3f}s/q")

    if failed:
        print(f"{len(failed)} 条查询失败 (MISSING):")
        for qid, etype, emsg in failed[:20]:
            print(f"  行 {qid}: {etype}: {emsg[:120]}")
        if len(failed) > 20:
            print(f"  ... 及其他 {len(failed)-20} 条")

    # 确保输出目录存在
    os.makedirs(os.path.dirname(save_file), exist_ok=True)

    # 保存结果
    with open(save_file, "w") as f:
        for p in preds:
            f.write(str(p) + "\n")

    print(f"结果已保存: {save_file}")
    print(f"行数: {len(preds)} (有效: {sum(1 for p in preds if p != 'MISSING')}, "
          f"MISSING: {sum(1 for p in preds if p == 'MISSING')})")


if __name__ == "__main__":
    main()
