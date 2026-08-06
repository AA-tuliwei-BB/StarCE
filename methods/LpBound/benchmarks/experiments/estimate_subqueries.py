"""
Invoke LpBound for each subquery in the specified benchmark's subquery file for cardinality estimation.

Purpose: generate subquery-level estimate results for benchmarks like JOBLightRanges (corresponding to LpBound's jobrange),
      supplementing into StarCE's Benchmark/workloads/ result set.

Usage:
    cd methods/LpBound/
    conda run -n lpbound python benchmarks/experiments/estimate_subqueries.py \
        --benchmark jobrange \
        --subquery-file /path/to/subquery.sql \
        --output /path/to/lpbound.txt \
        [--checkpoint-interval 500]

Output:
    One estimate value (float) per row, row count exactly aligned with subquery.sql.
    If a query fails, write -1 as placeholder and log to error file.
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

    # Read subqueries
    with open(subquery_path) as f:
        queries = [line.strip() for line in f if line.strip()]

    total = len(queries)
    print(f"Total {total} subqueries to estimate")

    # Initialize LpBound config
    cfg = LpBoundConfig(benchmark_name=args.benchmark, p_max=args.p_max)
    print(f"LpBound config: benchmark={args.benchmark}, p_max={args.p_max}")

    estimates = []
    errors = []
    start_time = time.perf_counter()

    for i, q in enumerate(queries):
        # LpBound native format is SELECT *; convert COUNT(*) to *
        q_mod = q.replace("SELECT COUNT(*)", "SELECT *")

        try:
            est = estimate(q_mod, cfg, verbose=False)
            estimates.append(est)
        except Exception as e:
            estimates.append(-1.0)
            errors.append((i, str(e)))

        # Progress report
        if (i + 1) % args.checkpoint_interval == 0:
            elapsed = time.perf_counter() - start_time
            avg = elapsed / (i + 1)
            eta = avg * (total - i - 1)
            print(f"  Progress: {i+1}/{total} ({100*(i+1)/total:.1f}%), "
                  f"avg {avg:.3f}s/q, ETA {eta/60:.1f} min")

            # Save intermediate results
            ckpt_path = output_path.with_suffix(".ckpt")
            with open(ckpt_path, "w") as f:
                for e in estimates:
                    f.write(f"{e}\n")
            print(f"  Checkpoint saved: {ckpt_path}")

    # Write final results
    with open(output_path, "w") as f:
        for e in estimates:
            f.write(f"{e}\n")

    elapsed = time.perf_counter() - start_time
    print(f"\nComplete! Total {total} queries, elapsed {elapsed/60:.1f} min")
    print(f"Succeeded: {total - len(errors)}, Failed: {len(errors)}")
    print(f"Output file: {output_path}")

    if errors:
        err_log = output_path.with_suffix(".errors.log")
        with open(err_log, "w") as f:
            for idx, msg in errors:
                f.write(f"Line {idx}: {msg}\n")
        print(f"Error log: {err_log}")

    # Clean up checkpoint
    ckpt_path = output_path.with_suffix(".ckpt")
    if ckpt_path.exists():
        ckpt_path.unlink()


if __name__ == "__main__":
    main()
