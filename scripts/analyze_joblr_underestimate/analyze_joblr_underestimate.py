"""
分析 JOBLightRanges 偏低估的根因。
从数据层面量化 range predicate 对估计误差的影响。
"""
import os
import sys
import re
import numpy as np
from pathlib import Path
from collections import Counter, defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "experiment"))

# ---------- 1. 加载 checkpoint 数据 ----------
def read_txt(path):
    vals = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                vals.append(float(line))
    return vals

checkpoint_root = PROJECT_ROOT / "experiment/checkpoint/StarCE/pred_method"

BENCHMARK_DIRS = {
    "STATS": "STATS-CEB",
    "JOBM": "JOBM",
    "JOBLight": "JOBLight",
    "JOBLightRanges": "JOBLightRanges",
}

def load_data(benchmark):
    bm_dir = BENCHMARK_DIRS[benchmark]
    real = read_txt(PROJECT_ROOT / f"Benchmark/workloads/{bm_dir}/subquery/result/real.txt")
    pm1_est = read_txt(checkpoint_root / benchmark / f"card_{benchmark}_PM1.txt")
    # 同时加载 PAR0.0 作为 baseline（无调整）
    par00_est = read_txt(checkpoint_root / benchmark / f"card_{benchmark}_PAR0.0.txt")
    return real, pm1_est, par00_est

print("=" * 70)
print("1. 加载各数据集数据")
print("=" * 70)

all_data = {}
for bm in ["STATS", "JOBM", "JOBLight", "JOBLightRanges"]:
    real, pm1, par00 = load_data(bm)
    all_data[bm] = {"real": real, "pm1": pm1, "par00": par00}
    errors = [max(1.0, e) / max(1.0, t) for t, e in zip(real, pm1)]
    log_err = np.log10(errors)
    under_frac = np.mean(np.array(errors) < 1.0)
    print(f"  {bm}: {len(real)} queries, "
          f"log10_err median={np.median(log_err):.3f}, "
          f"mean={np.mean(log_err):.3f}, "
          f"under_est_frac={under_frac:.1%}")

# ---------- 2. 解析 subquery，分类 predicate 类型 ----------
def parse_predicates(sql):
    """解析 SQL 中的谓词，返回 (equality_count, range_count, predicates_detail)"""
    # 提取 WHERE 子句
    where_match = re.search(r'WHERE\s+(.+?)(?:;|$)', sql, re.IGNORECASE)
    if not where_match:
        return 0, 0, []

    where_clause = where_match.group(1)
    # 按 AND 分割（简化处理，不处理嵌套 AND）
    parts = re.split(r'\s+AND\s+', where_clause, flags=re.IGNORECASE)

    eq_count = 0
    range_count = 0
    details = []

    for part in parts:
        part = part.strip()
        # 跳过 join 条件（包含 .id= 或 .movie_id= 等）
        if re.search(r'\.\s*(id|movie_id|person_id|keyword_id|company_id)\s*=', part, re.IGNORECASE):
            continue

        # range predicate
        if re.search(r'(<=|>=|!=|<>|<|>|BETWEEN|LIKE)', part, re.IGNORECASE):
            range_count += 1
            details.append(("range", part))
        # equality predicate
        elif '=' in part:
            eq_count += 1
            details.append(("eq", part))

    return eq_count, range_count, details


def parse_subquery_file(filepath):
    """解析 subquery.sql 文件，统计每条 subquery 的谓词"""
    results = []
    with open(filepath) as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            eq_cnt, range_cnt, details = parse_predicates(line)
            # 统计表数量
            tables = re.findall(r'FROM\s+(.+?)\s+WHERE', line, re.IGNORECASE)
            if not tables:
                tables = re.findall(r'FROM\s+(.+?);', line, re.IGNORECASE)
            table_count = len(tables[0].split(',')) if tables else 0

            results.append({
                "line_idx": i,
                "sql": line,
                "eq_count": eq_cnt,
                "range_count": range_cnt,
                "total_pred": eq_cnt + range_cnt,
                "table_count": table_count,
                "details": details,
            })
    return results


print("\n" + "=" * 70)
print("2. 分析各 workload 的谓词类型分布")
print("=" * 70)

for bm in ["JOBLight", "JOBLightRanges"]:
    bm_dir = BENCHMARK_DIRS[bm]
    subquery_path = PROJECT_ROOT / f"Benchmark/workloads/{bm_dir}/subquery/subquery.sql"
    parsed = parse_subquery_file(subquery_path)

    total_eq = sum(p["eq_count"] for p in parsed)
    total_range = sum(p["range_count"] for p in parsed)
    total_pred = total_eq + total_range
    has_range = sum(1 for p in parsed if p["range_count"] > 0)
    has_eq_only = sum(1 for p in parsed if p["range_count"] == 0 and p["eq_count"] > 0)
    no_pred = sum(1 for p in parsed if p["total_pred"] == 0)

    print(f"\n  {bm} ({len(parsed)} subqueries):")
    print(f"    Total predicates: {total_pred} (eq={total_eq}, range={total_range})")
    print(f"    Per subquery: avg {total_pred/len(parsed):.1f} preds "
          f"(eq={total_eq/len(parsed):.1f}, range={total_range/len(parsed):.1f})")
    print(f"    Subqueries with range preds: {has_range} ({has_range/len(parsed):.1%})")
    print(f"    Subqueries with only eq preds: {has_eq_only} ({has_eq_only/len(parsed):.1%})")
    print(f"    Subqueries with no preds: {no_pred} ({no_pred/len(parsed):.1%})")

    # 表数量分布
    table_dist = Counter(p["table_count"] for p in parsed)
    print(f"    Table count distribution: {dict(sorted(table_dist.items()))}")

    if bm == "JOBLightRanges":
        jolr_parsed = parsed
    else:
        jol_parsed = parsed

# ---------- 3. JOBLightRanges 内部分析：range vs 纯 equality ----------
print("\n" + "=" * 70)
print("3. JOBLightRanges 内部：range pred 子查询 vs 纯 equality 子查询")
print("=" * 70)

jolr_real = all_data["JOBLightRanges"]["real"]
jolr_pm1 = all_data["JOBLightRanges"]["pm1"]

# 分组
range_errors = []
eq_only_errors = []
no_pred_errors = []

for i, p in enumerate(jolr_parsed):
    if i >= len(jolr_real):
        break
    err = max(1.0, jolr_pm1[i]) / max(1.0, jolr_real[i])
    log_err = np.log10(err)
    if p["range_count"] > 0:
        range_errors.append(log_err)
    elif p["eq_count"] > 0:
        eq_only_errors.append(log_err)
    else:
        no_pred_errors.append(log_err)

for label, errors in [("有 range pred", range_errors),
                        ("纯 equality pred", eq_only_errors),
                        ("无谓词", no_pred_errors)]:
    if errors:
        arr = np.array(errors)
        print(f"  {label}: n={len(arr)}, "
              f"median={np.median(arr):.3f}, mean={np.mean(arr):.3f}, "
              f"p25={np.percentile(arr, 25):.3f}, p75={np.percentile(arr, 75):.3f}")

# ---------- 4. 分析：filter_coeff 数量对误差的影响 ----------
print("\n" + "=" * 70)
print("4. 谓词数量与估计误差的关系（JOBLightRanges）")
print("=" * 70)

pred_count_errors = defaultdict(list)
for i, p in enumerate(jolr_parsed):
    if i >= len(jolr_real):
        break
    err = max(1.0, jolr_pm1[i]) / max(1.0, jolr_real[i])
    log_err = np.log10(err)
    pred_count_errors[p["total_pred"]].append(log_err)

for cnt in sorted(pred_count_errors.keys()):
    arr = np.array(pred_count_errors[cnt])
    print(f"  {cnt} preds: n={len(arr)}, median={np.median(arr):.3f}, mean={np.mean(arr):.3f}")

# ---------- 5. 同一个 workload，range 和 equality 分别看 ----------
print("\n" + "=" * 70)
print("5. range count 分层分析（JOBLightRanges）")
print("=" * 70)

rc_errors = defaultdict(list)
for i, p in enumerate(jolr_parsed):
    if i >= len(jolr_real):
        break
    err = max(1.0, jolr_pm1[i]) / max(1.0, jolr_real[i])
    log_err = np.log10(err)
    rc_errors[p["range_count"]].append(log_err)

for rc in sorted(rc_errors.keys()):
    arr = np.array(rc_errors[rc])
    print(f"  {rc} range preds: n={len(arr)}, median={np.median(arr):.3f}, mean={np.mean(arr):.3f}")

# ---------- 6. 对比 JOBLight vs JOBLightRanges 的 over/under 分布 ----------
print("\n" + "=" * 70)
print("6. 误差分布形态对比（JOBLight vs JOBLightRanges）")
print("=" * 70)

for bm in ["JOBLight", "JOBLightRanges"]:
    real = all_data[bm]["real"]
    pm1 = all_data[bm]["pm1"]
    errors = np.array([max(1.0, e) / max(1.0, t) for t, e in zip(real, pm1)])
    log_err = np.log10(errors)

    # 按误差分段
    severe_under = np.sum(log_err < -1.0)  # est < 0.1x true
    moderate_under = np.sum((log_err >= -1.0) & (log_err < -0.3))  # est 0.1-0.5x true
    mild_under = np.sum((log_err >= -0.3) & (log_err < 0))  # est 0.5-1x true
    mild_over = np.sum((log_err >= 0) & (log_err < 0.3))  # est 1-2x true
    moderate_over = np.sum((log_err >= 0.3) & (log_err < 1.0))  # est 2-10x true
    severe_over = np.sum(log_err >= 1.0)  # est > 10x true

    n = len(errors)
    print(f"\n  {bm}:")
    print(f"    严重低估 (<0.1x):  {severe_under:5d} ({severe_under/n:5.1%})")
    print(f"    中度低估 (0.1-0.5x): {moderate_under:5d} ({moderate_under/n:5.1%})")
    print(f"    轻度低估 (0.5-1x):   {mild_under:5d} ({mild_under/n:5.1%})")
    print(f"    轻度高估 (1-2x):     {mild_over:5d} ({mild_over/n:5.1%})")
    print(f"    中度高估 (2-10x):    {moderate_over:5d} ({moderate_over/n:5.1%})")
    print(f"    严重高估 (>10x):     {severe_over:5d} ({severe_over/n:5.1%})")
    print(f"    低估总比例:           {severe_under+moderate_under+mild_under:5d} ({(severe_under+moderate_under+mild_under)/n:.1%})")

# ---------- 7. 分析每个 range predicate 列的误差 ----------
print("\n" + "=" * 70)
print("7. 按 range predicate 列分析误差（JOBLightRanges）")
print("=" * 70)

col_errors = defaultdict(list)
col_names = ['nr_order', 'production_year', 'episode_nr', 'season_nr',
             'phonetic_code', 'series_years', 'info', 'note']

for i, p in enumerate(jolr_parsed):
    if i >= len(jolr_real):
        break
    err = max(1.0, jolr_pm1[i]) / max(1.0, jolr_real[i])
    log_err = np.log10(err)
    for pred_type, pred_text in p["details"]:
        if pred_type == "range":
            for col in col_names:
                if col in pred_text.lower():
                    col_errors[col].append(log_err)
                    break

for col in sorted(col_errors.keys()):
    arr = np.array(col_errors[col])
    print(f"  {col}: n={len(arr)}, median={np.median(arr):.3f}, mean={np.mean(arr):.3f}")

# ---------- 8. 对比：混合谓词的 subquery 中，range+eq vs 纯 range vs 纯 eq ----------
print("\n" + "=" * 70)
print("8. 按谓词组合分析（JOBLightRanges 2-table join）")
print("=" * 70)

# 只看 2 表 join 的 subquery（最常见）
two_table_mask = [i for i, p in enumerate(jolr_parsed) if p["table_count"] == 2]

groups = {"only_eq": [], "only_range": [], "mixed": []}
for i in two_table_mask:
    p = jolr_parsed[i]
    err = max(1.0, jolr_pm1[i]) / max(1.0, jolr_real[i])
    log_err = np.log10(err)
    if p["range_count"] > 0 and p["eq_count"] > 0:
        groups["mixed"].append(log_err)
    elif p["range_count"] > 0:
        groups["only_range"].append(log_err)
    elif p["eq_count"] > 0:
        groups["only_eq"].append(log_err)

for label, errors in groups.items():
    if errors:
        arr = np.array(errors)
        print(f"  {label}: n={len(arr)}, median={np.median(arr):.3f}, mean={np.mean(arr):.3f}")

# ---------- 9. 最深层次分析：PM0 vs PM1 在 range 场景下的差异 ----------
print("\n" + "=" * 70)
print("9. PM1 vs PAR0.0 (PM0无调整) 差异分析")
print("=" * 70)

for bm in ["JOBLight", "JOBLightRanges", "STATS", "JOBM"]:
    pm1 = np.array(all_data[bm]["pm1"])
    par00 = np.array(all_data[bm]["par00"])
    real = np.array(all_data[bm]["real"])

    pm1_err = np.array([max(1.0, e) / max(1.0, t) for t, e in zip(real, pm1)])
    par00_err = np.array([max(1.0, e) / max(1.0, t) for t, e in zip(real, par00)])

    diff = np.abs(pm1_err - par00_err)
    same = np.sum(diff < 1e-10)
    print(f"  {bm}: PM1==PAR0.0 in {same}/{len(diff)} ({same/len(diff):.1%}) cases")

# 对 JOBLightRanges，深入看 PM1 != PAR0.0 的 case
print("\n  JOBLightRanges: PM1 != PAR0.0 的案例分析:")
jolr_pm1 = np.array(all_data["JOBLightRanges"]["pm1"])
jolr_par00 = np.array(all_data["JOBLightRanges"]["par00"])
jolr_real_arr = np.array(all_data["JOBLightRanges"]["real"])
diff_mask = np.abs(jolr_pm1 - jolr_par00) > 1e-10
diff_indices = np.where(diff_mask)[0]
print(f"  不同估计值的子查询数: {len(diff_indices)}")
if len(diff_indices) > 0:
    print(f"  前5个差异case:")
    for idx in diff_indices[:5]:
        p = jolr_parsed[idx]
        pm1_err = max(1.0, jolr_pm1[idx]) / max(1.0, jolr_real_arr[idx])
        par00_err = max(1.0, jolr_par00[idx]) / max(1.0, jolr_real_arr[idx])
        print(f"    #{idx}: tables={p['table_count']}, preds={p['total_pred']} "
              f"(eq={p['eq_count']}, range={p['range_count']})")
        print(f"      true={jolr_real_arr[idx]:.1f}, pm1={jolr_pm1[idx]:.1f}, "
              f"par00={jolr_par00[idx]:.1f}")
        print(f"      SQL: {p['sql'][:150]}...")

print("\n分析完成。")
