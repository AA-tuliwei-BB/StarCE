"""
Additional validation: controlled variable analysis of JOBLightRanges underestimation root cause
- Verify "predicate count is the primary cause"
- Verify "getNDV returns total row count rather than NDV"
- Analyze the cumulative effect of PM1 filter_coeff
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

# ---------- Verification 1: Impact of predicate count on error while controlling table count ----------
print("=" * 70)
print("Verification 1: Predicate count vs error at same table count")
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

# Group by table count, examine relationship between predicate count and error
for nt in [2, 3, 4]:
    print(f"\n  {nt}-table join:")
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

# ---------- Verification 2: Impact of predicate count on error in STATS dataset ----------
print("\n" + "=" * 70)
print("Verification 2: Impact of predicate count on error in STATS dataset")
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

# ---------- Verification 3: Predicate count impact on error in JOBLight (controlled variable) ----------
print("\n" + "=" * 70)
print("Verification 3: Impact of predicate count on error in JOBLight")
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

# ---------- Verification 4: Key -- count how many subqueries severely underestimated due to product effect ----------
print("\n" + "=" * 70)
print("Verification 4: Theoretical analysis of PM1 product effect")
print("=" * 70)

# For JOBLightRanges, estimates in 2-table joins:
# If both tables have filters, typical filter_coeff values
# Get actual selectivity from PG's single_query estimates

# Read single_query files to get filtered cardinalities
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

# Get baseline row counts per table
# From statistics JSON
stats_path = PROJECT_ROOT / "experiment/checkpoint/StarCE/statistics_imdb.json"
with open(stats_path) as f:
    stats_json = json.load(f)

# Find single-table statistics (EqualSet with only one table)
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

print(f"  Found {len(table_base_cards)} tables with base cardinalities from statistics:")
for t, c in sorted(table_base_cards.items()):
    print(f"    {t}: {c:,.0f}")

# Analyze selectivity distribution of single_query
print(f"\n  single_query sample analysis (first 20):")
selectivities = []
for i, (sql, est) in enumerate(zip(sq_lines[:100], pg_ests[:100])):
    # extract table name
    table_match = re.search(r'FROM\s+(\w+)\s+', sql, re.IGNORECASE)
    if table_match:
        table = table_match.group(1).lower()
        # Map to schema table name
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
    print(f"\n  Selectivity distribution (n={len(sel_arr)}):")
    print(f"    median={np.median(sel_arr):.4f}, mean={np.mean(sel_arr):.4f}")
    print(f"    p25={np.percentile(sel_arr, 25):.4f}, p75={np.percentile(sel_arr, 75):.4f}")
    print(f"    min={np.min(sel_arr):.6f}, max={np.max(sel_arr):.4f}")

    # Simulate PM1 product effect
    print(f"\n  Simulated PM1 product effect (randomly sample 3 filter_coeff):")
    np.random.seed(42)
    products = []
    for _ in range(10000):
        sels = np.random.choice(sel_arr, size=3)
        products.append(np.prod(sels))
    prod_arr = np.array(products)
    print(f"    Product distribution of 3 filter_coeff:")
    print(f"    median={np.median(prod_arr):.6f}, mean={np.mean(prod_arr):.6f}")
    print(f"    p10={np.percentile(prod_arr, 10):.6f}, p25={np.percentile(prod_arr, 25):.6f}")

    # Compare with geometric mean
    geo_means = []
    for _ in range(10000):
        sels = np.random.choice(sel_arr, size=3)
        geo_means.append(np.prod(sels) ** (1/3))
    gm_arr = np.array(geo_means)
    print(f"\n    Geometric mean (original approach) distribution:")
    print(f"    median={np.median(gm_arr):.4f}, mean={np.mean(gm_arr):.4f}")

    print(f"\n    Direct product / Geometric mean = {np.median(prod_arr)/np.median(gm_arr):.4f}")
    print(f"    -> PM1 direct product makes coeff ~{np.median(gm_arr)/np.median(prod_arr):.1f}x smaller")

# ---------- Verification 5: GetNDV returns total row count rather than NDV ----------
print("\n" + "=" * 70)
print("Verification 5: GetNDV returns total row count (card) rather than NDV")
print("=" * 70)

print("""
  GetNDV code (starce.hpp:634-642):
    int64_t GetNDV(const std::string& table) {
        EqualSet eset;
        eset.Entries.insert({table, ""});
        return static_cast<int64_t>(statistics.at(eset)->card);
    }

  'card' is the cardinality field of DSStatistic,
  For single-table (table, "") EqualSet, card = total row count of the table

  filter_coeff = GetTableCard(rel_id) / GetNDV(tableName)
               = filtered_card / total_rows
               = selectivity

  Therefore filter_coeff is actually the predicate selectivity

  For a subquery with N filtering tables:
  - PM1 direct product: coeff = sel1 * sel2 * ... * selN
  - When each sel ~0.1-0.3, 3 tables -> coeff ~0.001-0.027
  - This is far smaller than the actual coefficient, causing severe underestimation
""")

print("\nAnalysis complete.")
