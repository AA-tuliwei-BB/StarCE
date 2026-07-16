#!/usr/bin/env python3
"""
IMDB-JOB 预物化脚本：从 derived_query_file.pkl 提取主查询，物化 binned cards 并记录耗时。
需先完成训练和 prepare_sample。
"""
import argparse
import os
import pickle
import time
from pathlib import Path

from Join_scheme.binning import identify_key_values
from Schemas.imdb.schema import gen_imdb_schema
from Sampling.get_query_binned_cards import get_query_binned_cards

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_path", default=str(PROJECT_ROOT / "methods/SafeBound/Data/IMDB/{}.csv"))
    parser.add_argument("--derived_query_file", default="checkpoints/derived_query_file.pkl")
    parser.add_argument("--query_dir", default="checkpoints/imdb_job_queries")
    parser.add_argument("--save_dir", default="checkpoints/")
    parser.add_argument("--sampling_percentage", type=float, default=1.0)
    parser.add_argument("--db_conn_kwargs", default="dbname=imdb user=postgres password=postgres host=127.0.0.1 port=5432")
    args = parser.parse_args()

    # 1. 从 schema 获取 equivalent_keys（避免加载模型时的循环导入）
    schema = gen_imdb_schema(args.data_path)
    _, equivalent_keys = identify_key_values(schema)

    # 2. 从 derived_query_file 提取主查询到目录
    with open(args.derived_query_file, "rb") as f:
        all_queries, _ = pickle.load(f)
    os.makedirs(args.query_dir, exist_ok=True)
    for name, sql in all_queries.items():
        path = os.path.join(args.query_dir, f"{name}.sql")
        with open(path, "w") as f:
            f.write(sql.strip())
            if not sql.strip().endswith(";"):
                f.write(";")
    print(f"[INFO] 已提取 {len(all_queries)} 条主查询到 {args.query_dir}")

    # 3. 预物化并记录耗时
    t_start = time.time()
    get_query_binned_cards(
        args.query_dir,
        args.db_conn_kwargs,
        equivalent_keys,
        args.sampling_percentage,
        args.save_dir,
    )
    elapsed = time.time() - t_start
    print(f"\n[预物化完成] 总耗时: {elapsed:.2f} 秒 ({elapsed/60:.2f} 分钟)")


if __name__ == "__main__":
    main()
