"""
将 factorjoin.txt（与 subquery_from_grouped.sql 行对齐，9472 行）
转换为与 subquery.sql 行对齐的格式（6424 行）。

subquery_from_grouped.sql 中同一条 SQL 可能在不同主查询分组中重复出现，
每次使用不同的物化样本，可能得到不同估计值。
本脚本对同一 SQL 的所有估计取均值，输出到 factorjoin_remapped.txt。

最后计算并输出 Q-Error 统计（与 real.txt 比较）。
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
    # 1. 读取 grouped SQL 和对应的 factorjoin 估计值
    with open(GROUPED_SQL) as f:
        grouped_sqls = [l.strip() for l in f if l.strip()]
    with open(INPUT_TXT) as f:
        grouped_preds = [float(l.strip()) for l in f if l.strip()]

    if len(grouped_sqls) != len(grouped_preds):
        print(f"行数不匹配: grouped_sqls={len(grouped_sqls)}, preds={len(grouped_preds)}", file=sys.stderr)
        sys.exit(1)

    # 2. 构建 sql -> [pred1, pred2, ...] 映射
    sql_to_preds = defaultdict(list)
    for sql, pred in zip(grouped_sqls, grouped_preds):
        sql_to_preds[sql].append(pred)

    print(f"grouped SQL 总行数:  {len(grouped_sqls)}")
    print(f"唯一 SQL 数:         {len(sql_to_preds)}")
    dup_count = sum(1 for v in sql_to_preds.values() if len(v) > 1)
    print(f"有重复出现的 SQL 数: {dup_count}")

    # 3. 读取目标 subquery.sql（6424 行，无重复）
    with open(SUBQUERY_SQL) as f:
        target_sqls = [l.strip() for l in f if l.strip()]

    print(f"\ntarget subquery.sql 行数: {len(target_sqls)}")

    # 4. 检查覆盖情况
    missing = [q for q in target_sqls if q not in sql_to_preds]
    print(f"在 grouped 中未找到的查询: {len(missing)}")
    if missing:
        for q in missing[:3]:
            print(f"  示例: {q[:100]}")

    # 5. 生成输出：同一 SQL 多个估计取均值
    remapped = []
    for sql in target_sqls:
        if sql in sql_to_preds:
            vals = sql_to_preds[sql]
            remapped.append(np.mean(vals))
        else:
            remapped.append(1.0)  # 未找到时用 1.0

    with open(OUTPUT_TXT, "w") as f:
        for v in remapped:
            f.write(str(v) + "\n")

    print(f"\n已写入 {len(remapped)} 行到 {OUTPUT_TXT}")

    # 6. 计算 Q-Error（与 real.txt 比较）
    if not os.path.exists(REAL_TXT):
        print("real.txt 不存在，跳过 Q-Error 计算")
        return

    with open(REAL_TXT) as f:
        reals = [float(l.strip()) for l in f if l.strip()]

    if len(reals) != len(remapped):
        print(f"警告：real.txt 行数 ({len(reals)}) != 输出行数 ({len(remapped)})")
        return

    qerrs = []
    for r, p in zip(reals, remapped):
        r = max(r, 1.0)
        p = max(p, 1.0)
        qerrs.append(max(r / p, p / r))

    qerrs = np.array(qerrs)
    print("\nQ-Error 统计（与 real.txt 比较）:")
    for pct in [50, 90, 95, 99, 100]:
        print(f"  p{pct:3d}: {np.percentile(qerrs, pct):.2f}")
    print(f"  mean: {np.mean(qerrs):.2f}")
    print(f"  总查询数: {len(qerrs)}")


if __name__ == "__main__":
    main()
