"""
额外验证：控制变量分析 JOBLightRanges 低估根因
- 验证"谓词数量是主因"
- 验证"getNDV 返回的是总行数而非 NDV"
- 分析 PM1 filter_coeff 的累积效应
"""
import os, sys, re, json
import numpy as np
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "experiment"))

def read_txt(path):
    vals = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                vals.append(float(line))
    return vals

BENCHMARK_DIRS = {
    "STATS": "STATS-CEB",
    "JOBM": "JOBM",
    "JOBLight": "JOBLight",
    "JOBLightRanges": "JOBLightRanges",
}

def load_data(benchmark):
    bm_dir = BENCHMARK_DIRS[benchmark]
    real = read_txt(PROJECT_ROOT / f"Benchmark/workloads/{bm_dir}/subquery/result/real.txt")
    pm1 = read_txt(PROJECT_ROOT / f"experiment/checkpoint/StarCE/pred_method/{benchmark}/card_{benchmark}_PM1.txt")
    return real, pm1

# ---------- 验证 1: 控制表数量的情况下，谓词数量对误差的影响 ----------
print("=" * 70)
print("验证 1: 同表数量下，谓词数 vs 误差")
print("=" * 70)

def parse_subqueries(filepath):
    results = []
    with open(filepath) as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            # count tables
            table_match = re.search(r'FROM\s+(.+?)\s+WHERE', line, re.IGNORECASE)
            if not table_match:
                table_match = re.search(r'FROM\s+(.+?);', line, re.IGNORECASE)
            table_count = len(table_match.group(1).split(',')) if table_match else 0

            # count non-join predicates
            where_match = re.search(r'WHERE\s+(.+?)(?:;|$)', line, re.IGNORECASE)
            preds = []
            if where_match:
                parts = re.split(r'\s+AND\s+', where_match.group(1), flags=re.IGNORECASE)
                for part in parts:
                    part = part.strip()
                    if re.search(r'\.\s*(id|movie_id|person_id|keyword_id|company_id)\s*=', part, re.IGNORECASE):
                        continue
                    preds.append(part)

            results.append({
                "line_idx": i,
                "sql": line,
                "pred_count": len(preds),
                "table_count": table_count,
                "preds": preds,
            })
    return results

jolr_parsed = parse_subqueries(PROJECT_ROOT / "Benchmark/workloads/JOBLightRanges/subquery/subquery.sql")
jol_real, jol_pm1 = load_data("JOBLightRanges")

# 按表数量分组，看谓词数量与误差的关系
for nt in [2, 3, 4]:
    print(f"\n  {nt}-表 join:")
    for npred in [0, 1, 2, 3, 4, 5]:
        indices = [i for i, p in enumerate(jolr_parsed)
                   if p["table_count"] == nt and p["pred_count"] == npred]
        if not indices:
            continue
        errors = []
        for i in indices:
            if i < len(jol_real):
                err = max(1.0, jol_pm1[i]) / max(1.0, jol_real[i])
                errors.append(np.log10(err))
        if errors:
            arr = np.array(errors)
            print(f"    {npred} preds: n={len(arr)}, median={np.median(arr):.3f}, "
                  f"mean={np.mean(arr):.3f}, under_frac={np.mean(arr<0):.1%}")

# ---------- 验证 2: 对比 STATS 数据中谓词数量的影响 ----------
print("\n" + "=" * 70)
print("验证 2: STATS 数据集中谓词数量对误差的影响")
print("=" * 70)

stats_parsed = parse_subqueries(PROJECT_ROOT / "Benchmark/workloads/STATS-CEB/subquery/subquery.sql")
stats_real, stats_pm1 = load_data("STATS")

for npred in [0, 1, 2, 3, 4, 5]:
    indices = [i for i, p in enumerate(stats_parsed) if p["pred_count"] == npred]
    if not indices:
        continue
    errors = []
    for i in indices:
        if i < len(stats_real):
            err = max(1.0, stats_pm1[i]) / max(1.0, stats_real[i])
            errors.append(np.log10(err))
    if errors:
        arr = np.array(errors)
        print(f"  {npred} preds: n={len(arr)}, median={np.median(arr):.3f}, "
              f"mean={np.mean(arr):.3f}, under_frac={np.mean(arr<0):.1%}")

# ---------- 验证 3: JOBLight中按谓词数量分析（控制变量） ----------
print("\n" + "=" * 70)
print("验证 3: JOBLight 中谓词数量对误差的影响")
print("=" * 70)

jol_parsed = parse_subqueries(PROJECT_ROOT / "Benchmark/workloads/JOBLight/subquery/subquery.sql")
jol_real_arr, jol_pm1_arr = load_data("JOBLight")

for npred in [0, 1, 2, 3, 4]:
    indices = [i for i, p in enumerate(jol_parsed) if p["pred_count"] == npred]
    if not indices:
        continue
    errors = []
    for i in indices:
        if i < len(jol_real_arr):
            err = max(1.0, jol_pm1_arr[i]) / max(1.0, jol_real_arr[i])
            errors.append(np.log10(err))
    if errors:
        arr = np.array(errors)
        print(f"  {npred} preds: n={len(arr)}, median={np.median(arr):.3f}, "
              f"mean={np.mean(arr):.3f}, under_frac={np.mean(arr<0):.1%}")

# ---------- 验证 4: 关键——统计有多少子查询会因乘积效应而严重低估 ----------
print("\n" + "=" * 70)
print("验证 4: PM1 乘积效应的理论分析")
print("=" * 70)

# 对于 JOBLightRanges，估计在 2 表 join 中，
# 如果 2 个表都有filter，filter_coeff 的典型值
# 从 PG 的 single_query 估计中获取实际 selectivity

# 读取 single_query 文件获取过滤后基数
sq_path = PROJECT_ROOT / "Benchmark/workloads/JOBLightRanges/single_query/single_query.sql"
pg_path = PROJECT_ROOT / "Benchmark/workloads/JOBLightRanges/single_query/pg_est.txt"

sq_lines = []
with open(sq_path) as f:
    for line in f:
        line = line.strip()
        if line:
            sq_lines.append(line)

pg_ests = []
with open(pg_path) as f:
    for line in f:
        line = line.strip()
        if line:
            pg_ests.append(float(line))

# 获取各表的基准行数
# 从 statistics JSON 中获取
stats_path = PROJECT_ROOT / "experiment/checkpoint/StarCE/statistics_imdb.json"
with open(stats_path) as f:
    stats_json = json.load(f)

# 找单表统计（EqualSet 只有一张表）
table_base_cards = {}
for item in stats_json.get("Statistics", []):
    ds_stat = item.get("DSStatistic", {})
    eset = item.get("EqualSet", {})
    entries = eset.get("Entries", [])
    if len(entries) == 1:
        table_name = entries[0].get("TableName", "")
        card = ds_stat.get("Cardinality", 0)
        if table_name and card > 0:
            table_base_cards[table_name] = float(card)

print(f"  从 statistics 中找到 {len(table_base_cards)} 张表的基准基数:")
for t, c in sorted(table_base_cards.items()):
    print(f"    {t}: {c:,.0f}")

# 分析 single_query 的 selectivity 分布
print(f"\n  single_query 样本分析 (前20个):")
selectivities = []
for i, (sql, est) in enumerate(zip(sq_lines[:100], pg_ests[:100])):
    # 提取表名
    table_match = re.search(r'FROM\s+(\w+)\s+', sql, re.IGNORECASE)
    if table_match:
        table = table_match.group(1).lower()
        # 映射到 schema 表名
        for t in table_base_cards:
            if t.lower() == table or table.startswith(t.lower()):
                base_card = table_base_cards[t]
                sel = est / base_card if base_card > 0 else 0
                selectivities.append(sel)
                if i < 20:
                    print(f"    {table}: pg_est={est:,.0f}, base={base_card:,.0f}, sel={sel:.4f}")
                break

if selectivities:
    sel_arr = np.array(selectivities)
    print(f"\n  Selectivity 分布 (n={len(sel_arr)}):")
    print(f"    median={np.median(sel_arr):.4f}, mean={np.mean(sel_arr):.4f}")
    print(f"    p25={np.percentile(sel_arr, 25):.4f}, p75={np.percentile(sel_arr, 75):.4f}")
    print(f"    min={np.min(sel_arr):.6f}, max={np.max(sel_arr):.4f}")

    # 模拟 PM1 乘积效应
    print(f"\n  模拟 PM1 乘积效应（随机抽取 3 个 filter_coeff）:")
    np.random.seed(42)
    products = []
    for _ in range(10000):
        sels = np.random.choice(sel_arr, size=3)
        products.append(np.prod(sels))
    prod_arr = np.array(products)
    print(f"    3 个 filter_coeff 的乘积分布:")
    print(f"    median={np.median(prod_arr):.6f}, mean={np.mean(prod_arr):.6f}")
    print(f"    p10={np.percentile(prod_arr, 10):.6f}, p25={np.percentile(prod_arr, 25):.6f}")

    # 与 geometric mean 对比
    geo_means = []
    for _ in range(10000):
        sels = np.random.choice(sel_arr, size=3)
        geo_means.append(np.prod(sels) ** (1/3))
    gm_arr = np.array(geo_means)
    print(f"\n    Geometric mean (原方案) 分布:")
    print(f"    median={np.median(gm_arr):.4f}, mean={np.mean(gm_arr):.4f}")

    print(f"\n    直接乘积 / Geometric mean = {np.median(prod_arr)/np.median(gm_arr):.4f}")
    print(f"    → PM1 直接乘积使 coeff 额外缩小了约 {np.median(gm_arr)/np.median(prod_arr):.1f}x")

# ---------- 验证 5: GetNDV 返回的是总行数而非 NDV ----------
print("\n" + "=" * 70)
print("验证 5: GetNDV 返回的是总行数 (card) 而非 NDV")
print("=" * 70)

print("""
  GetNDV 代码 (starce.hpp:634-642):
    int64_t GetNDV(const std::string& table) {
        EqualSet eset;
        eset.Entries.insert({table, ""});
        return static_cast<int64_t>(statistics.at(eset)->card);
    }

  'card' 是 DSStatistic 的 cardinality 字段,
  对于单表 (table, "") EqualSet，card = 表的总行数

  filter_coeff = GetTableCard(rel_id) / GetNDV(tableName)
               = filtered_card / total_rows
               = selectivity

  因此 filter_coeff 实际上就是谓词的选择率 (selectivity)

  对于有 N 个过滤表的子查询:
  - PM1 直接乘积: coeff = sel1 × sel2 × ... × selN
  - 当每个 sel ≈ 0.1-0.3 时, 3 个表 → coeff ≈ 0.001-0.027
  - 这是远小于实际情况的系数, 导致严重低估
""")

print("\n分析完成。")
