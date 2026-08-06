"""
Analyze the root cause of JOBLightRanges underestimation bias.
Quantify the impact of range predicates on estimation error from the data level.
"""
import os
import sys
import re
import numpy as np
from pathlib import Path
from collections import Counter, defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "experiment"))

# ---------- 1. Load checkpoint data ----------
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
    # Also load PAR0.0 as baseline (no adjustment)
    par00_est = read_txt(checkpoint_root / benchmark / f"card_{benchmark}_PAR0.0.txt")
    return real, pm1_est, par00_est

print("=" * 70)
print("1. Load data from each dataset")
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

# ---------- 2. Parse subqueries and classify predicate types ----------
def parse_predicates(sql):
    """Parse predicates from SQL, return (equality_count, range_count, predicates_detail)"""
    # Extract WHERE clause
    where_match = re.search(r'WHERE\s+(.+?)(?:;|$)', sql, re.IGNORECASE)
    if not where_match:
        return 0, 0, []

    where_clause = where_match.group(1)
    # Split by AND (simplified, not handling nested AND)
    parts = re.split(r'\s+AND\s+', where_clause, flags=re.IGNORECASE)

    eq_count = 0
    range_count = 0
    details = []

    for part in parts:
        part = part.strip()
        # Skip join conditions (containing .id= or .movie_id= etc.)
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
    """Parse subquery.sql file, count predicates for each subquery"""
    results = []
    with open(filepath) as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            eq_cnt, range_cnt, details = parse_predicates(line)
            # Count number of tables
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
print("2. Analyze predicate type distribution for each workload")
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

    # Table count distribution
    table_dist = Counter(p["table_count"] for p in parsed)
    print(f"    Table count distribution: {dict(sorted(table_dist.items()))}")

    if bm == "JOBLightRanges":
        jolr_parsed = parsed
    else:
        jol_parsed = parsed

# ---------- 3. JOBLightRanges internal analysis: range vs pure equality ----------
print("\n" + "=" * 70)
print("3. Within JOBLightRanges: range pred subqueries vs pure equality subqueries")
print("=" * 70)

jolr_real = all_data["JOBLightRanges"]["real"]
jolr_pm1 = all_data["JOBLightRanges"]["pm1"]

# Grouping
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

for label, errors in [("Has range pred", range_errors),
                        ("Pure equality pred", eq_only_errors),
                        ("No predicate", no_pred_errors)]:
    if errors:
        arr = np.array(errors)
        print(f"  {label}: n={len(arr)}, "
              f"median={np.median(arr):.3f}, mean={np.mean(arr):.3f}, "
              f"p25={np.percentile(arr, 25):.3f}, p75={np.percentile(arr, 75):.3f}")

# ---------- 4. Analyze: impact of filter_coeff count on error ----------
print("\n" + "=" * 70)
print("4. Relationship between predicate count and estimation error (JOBLightRanges)")
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

# ---------- 5. Analyze range and equality separately within the same workload ----------
print("\n" + "=" * 70)
print("5. Stratified analysis by range count (JOBLightRanges)")
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

# ---------- 6. Compare over/under distribution of JOBLight vs JOBLightRanges ----------
print("\n" + "=" * 70)
print("6. Error distribution shape comparison (JOBLight vs JOBLightRanges)")
print("=" * 70)

for bm in ["JOBLight", "JOBLightRanges"]:
    real = all_data[bm]["real"]
    pm1 = all_data[bm]["pm1"]
    errors = np.array([max(1.0, e) / max(1.0, t) for t, e in zip(real, pm1)])
    log_err = np.log10(errors)

    # By error segment
    severe_under = np.sum(log_err < -1.0)  # est < 0.1x true
    moderate_under = np.sum((log_err >= -1.0) & (log_err < -0.3))  # est 0.1-0.5x true
    mild_under = np.sum((log_err >= -0.3) & (log_err < 0))  # est 0.5-1x true
    mild_over = np.sum((log_err >= 0) & (log_err < 0.3))  # est 1-2x true
    moderate_over = np.sum((log_err >= 0.3) & (log_err < 1.0))  # est 2-10x true
    severe_over = np.sum(log_err >= 1.0)  # est > 10x true

    n = len(errors)
    print(f"\n  {bm}:")
    print(f"    Severe underestimate (<0.1x):  {severe_under:5d} ({severe_under/n:5.1%})")
    print(f"    Moderate underestimate (0.1-0.5x): {moderate_under:5d} ({moderate_under/n:5.1%})")
    print(f"    Mild underestimate (0.5-1x):   {mild_under:5d} ({mild_under/n:5.1%})")
    print(f"    Mild overestimate (1-2x):     {mild_over:5d} ({mild_over/n:5.1%})")
    print(f"    Moderate overestimate (2-10x):    {moderate_over:5d} ({moderate_over/n:5.1%})")
    print(f"    Severe overestimate (>10x):     {severe_over:5d} ({severe_over/n:5.1%})")
    print(f"    Total underestimate ratio:           {severe_under+moderate_under+mild_under:5d} ({(severe_under+moderate_under+mild_under)/n:.1%})")

# ---------- 7. Analyze error by range predicate column ----------
print("\n" + "=" * 70)
print("7. Analyze error by range predicate column (JOBLightRanges)")
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

# ---------- 8. Compare: mixed predicates in subqueries, range+eq vs pure range vs pure eq ----------
print("\n" + "=" * 70)
print("8. Analyze by predicate combination (JOBLightRanges 2-table join)")
print("=" * 70)

# Only look at 2-table join subqueries (most common)
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

# ---------- 9. Deepest analysis: PM0 vs PM1 difference in range scenarios ----------
print("\n" + "=" * 70)
print("9. PM1 vs PAR0.0 (PM0 without adjustment) difference analysis")
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

# For JOBLightRanges, deep-dive into cases where PM1 != PAR0.0
print("\n  JOBLightRanges: Analysis of cases where PM1 != PAR0.0:")
jolr_pm1 = np.array(all_data["JOBLightRanges"]["pm1"])
jolr_par00 = np.array(all_data["JOBLightRanges"]["par00"])
jolr_real_arr = np.array(all_data["JOBLightRanges"]["real"])
diff_mask = np.abs(jolr_pm1 - jolr_par00) > 1e-10
diff_indices = np.where(diff_mask)[0]
print(f"  Subqueries with different estimates: {len(diff_indices)}")
if len(diff_indices) > 0:
    print(f"  First 5 differing cases:")
    for idx in diff_indices[:5]:
        p = jolr_parsed[idx]
        pm1_err = max(1.0, jolr_pm1[idx]) / max(1.0, jolr_real_arr[idx])
        par00_err = max(1.0, jolr_par00[idx]) / max(1.0, jolr_real_arr[idx])
        print(f"    #{idx}: tables={p['table_count']}, preds={p['total_pred']} "
              f"(eq={p['eq_count']}, range={p['range_count']})")
        print(f"      true={jolr_real_arr[idx]:.1f}, pm1={jolr_pm1[idx]:.1f}, "
              f"par00={jolr_par00[idx]:.1f}")
        print(f"      SQL: {p['sql'][:150]}...")

print("\nAnalysis complete.")
