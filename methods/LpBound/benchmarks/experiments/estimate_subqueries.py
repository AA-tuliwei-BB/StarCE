"""
对指定 benchmark 的子查询文件逐条调用 LpBound 进行基数估计。

用途：为 JOBLightRanges（对应 LpBound 的 jobrange）等 benchmark 生成
      子查询级别的估计结果，补充到 StarCE 的 Benchmark/workloads/ 结果集中。

用法:
    cd methods/LpBound/
    conda run -n lpbound python benchmarks/experiments/estimate_subqueries.py \
        --benchmark jobrange \
        --subquery-file /path/to/subquery.sql \
        --output /path/to/lpbound.txt \
        [--checkpoint-interval 500]

输出:
    每行一个估计值（浮点数），行数与 subquery.sql 完全对齐。
    如果某条查询失败，写入 -1 占位并记录到错误日志。
"""

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from lpbound.config.lpbound_config import LpBoundConfig
from lpbound.acyclic.lpbound import estimate


def main():
    parser = argparse.ArgumentParser(description="LpBound subquery-level cardinality estimation")
    parser.add_argument("--benchmark", required=True, help="LpBound benchmark name (e.g., jobrange)")
    parser.add_argument("--subquery-file", required=True, help="Path to subquery.sql file")
    parser.add_argument("--output", required=True, help="Path to output estimates file")
    parser.add_argument("--p-max", type=int, default=10, help="Max p-norm (default: 10)")
    parser.add_argument("--checkpoint-interval", type=int, default=500,
                        help="Save intermediate results every N queries (default: 500)")
    args = parser.parse_args()

    subquery_path = Path(args.subquery_file)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 读取子查询
    with open(subquery_path) as f:
        queries = [line.strip() for line in f if line.strip()]

    total = len(queries)
    print(f"共 {total} 条子查询待估计")

    # 初始化 LpBound 配置
    cfg = LpBoundConfig(benchmark_name=args.benchmark, p_max=args.p_max)
    print(f"LpBound config: benchmark={args.benchmark}, p_max={args.p_max}")

    estimates = []
    errors = []
    start_time = time.perf_counter()

    for i, q in enumerate(queries):
        # LpBound 原生格式为 SELECT *，将 COUNT(*) 转为 *
        q_mod = q.replace("SELECT COUNT(*)", "SELECT *")

        try:
            est = estimate(q_mod, cfg, verbose=False)
            estimates.append(est)
        except Exception as e:
            estimates.append(-1.0)
            errors.append((i, str(e)))

        # 进度报告
        if (i + 1) % args.checkpoint_interval == 0:
            elapsed = time.perf_counter() - start_time
            avg = elapsed / (i + 1)
            eta = avg * (total - i - 1)
            print(f"  进度: {i+1}/{total} ({100*(i+1)/total:.1f}%), "
                  f"平均 {avg:.3f}s/条, 预计剩余 {eta/60:.1f} min")

            # 保存中间结果
            ckpt_path = output_path.with_suffix(".ckpt")
            with open(ckpt_path, "w") as f:
                for e in estimates:
                    f.write(f"{e}\n")
            print(f"  检查点已保存: {ckpt_path}")

    # 写入最终结果
    with open(output_path, "w") as f:
        for e in estimates:
            f.write(f"{e}\n")

    elapsed = time.perf_counter() - start_time
    print(f"\n完成! 共 {total} 条, 耗时 {elapsed/60:.1f} min")
    print(f"成功: {total - len(errors)}, 失败: {len(errors)}")
    print(f"输出文件: {output_path}")

    if errors:
        err_log = output_path.with_suffix(".errors.log")
        with open(err_log, "w") as f:
            for idx, msg in errors:
                f.write(f"Line {idx}: {msg}\n")
        print(f"错误日志: {err_log}")

    # 清理检查点
    ckpt_path = output_path.with_suffix(".ckpt")
    if ckpt_path.exists():
        ckpt_path.unlink()


if __name__ == "__main__":
    main()
