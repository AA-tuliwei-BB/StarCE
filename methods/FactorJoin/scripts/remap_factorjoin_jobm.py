"""
Convert factorjoin.txt (row-aligned with subquery_from_grouped.sql, 9472 rows)
to a format row-aligned with subquery.sql (6424 rows).

The same SQL in subquery_from_grouped.sql may appear repeatedly in different main query groups,
each time using different materialized samples, potentially yielding different estimate values.
This script averages all estimates for the same SQL and outputs to factorjoin_remapped.txt.

Finally compute and output Q-Error statistics (compared with real.txt).
"""

import os
import sys
import numpy as np
from collections import defaultdict

PROJ_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../.."))
SUBQUERY_DIR = os.path.join(PROJ_ROOT, "Benchmark/workloads/JOBM/subquery")
RESULT_DIR = os.path.join(SUBQUERY_DIR, "result")

GROUPED_SQL   = os.path.join(SUBQUERY_DIR, "subquery_from_grouped.sql")
SUBQUERY_SQL  = os.path.join(SUBQUERY_DIR, "subquery.sql")
INPUT_TXT     = os.path.join(RESULT_DIR, "factorjoin.txt")
OUTPUT_TXT    = os.path.join(RESULT_DIR, "factorjoin_remapped.txt")
REAL_TXT      = os.path.join(RESULT_DIR, "real.txt")


def main():
    # 1. Read grouped SQL and corresponding factorjoin estimates
    with open(GROUPED_SQL) as f:
        grouped_sqls = [l.strip() for l in f if l.strip()]
    with open(INPUT_TXT) as f:
        grouped_preds = [float(l.strip()) for l in f if l.strip()]

    if len(grouped_sqls) != len(grouped_preds):
        print(f"Row count mismatch: grouped_sqls={len(grouped_sqls)}, preds={len(grouped_preds)}", file=sys.stderr)
        sys.exit(1)

    # 2. Build sql -> [pred1, pred2, ...] mapping
    sql_to_preds = defaultdict(list)
    for sql, pred in zip(grouped_sqls, grouped_preds):
        sql_to_preds[sql].append(pred)

    print(f"Grouped SQL total rows:  {len(grouped_sqls)}")
    print(f"Unique SQL count:         {len(sql_to_preds)}")
    dup_count = sum(1 for v in sql_to_preds.values() if len(v) > 1)
    print(f"SQL with duplicates: {dup_count}")

    # 3. Read target subquery.sql (6424 rows, no duplicates)
    with open(SUBQUERY_SQL) as f:
        target_sqls = [l.strip() for l in f if l.strip()]

    print(f"\ntarget subquery.sql rows: {len(target_sqls)}")

    # 4. Check coverage
    missing = [q for q in target_sqls if q not in sql_to_preds]
    print(f"Queries not found in grouped: {len(missing)}")
    if missing:
        for q in missing[:3]:
            print(f"  Example: {q[:100]}")

    # 5. Generate output: average multiple estimates for the same SQL
    remapped = []
    for sql in target_sqls:
        if sql in sql_to_preds:
            vals = sql_to_preds[sql]
            remapped.append(np.mean(vals))
        else:
            remapped.append(1.0)  # Use 1.0 when not found

    with open(OUTPUT_TXT, "w") as f:
        for v in remapped:
            f.write(str(v) + "\n")

    print(f"\nWritten {len(remapped)} rows to {OUTPUT_TXT}")

    # 6. Compute Q-Error (compare with real.txt)
    if not os.path.exists(REAL_TXT):
        print("real.txt does not exist, skipping Q-Error computation")
        return

    with open(REAL_TXT) as f:
        reals = [float(l.strip()) for l in f if l.strip()]

    if len(reals) != len(remapped):
        print(f"Warning: real.txt rows ({len(reals)}) != output rows ({len(remapped)})")
        return

    qerrs = []
    for r, p in zip(reals, remapped):
        r = max(r, 1.0)
        p = max(p, 1.0)
        qerrs.append(max(r / p, p / r))

    qerrs = np.array(qerrs)
    print("\nQ-Error statistics (compared with real.txt):")
    for pct in [50, 90, 95, 99, 100]:
        print(f"  p{pct:3d}: {np.percentile(qerrs, pct):.2f}")
    print(f"  mean: {np.mean(qerrs):.2f}")
    print(f"  Total queries: {len(qerrs)}")


if __name__ == "__main__":
    main()
