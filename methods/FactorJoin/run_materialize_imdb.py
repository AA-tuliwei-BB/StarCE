#!/usr/bin/env python3
"""
IMDB-JOB pre-materialization script: extract main queries from derived_query_file.pkl, materialize binned cards, and record elapsed time.
Requires prior training and prepare_sample.
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

    # 1. Get equivalent_keys from schema (avoid circular import when loading model)
    schema = gen_imdb_schema(args.data_path)
    _, equivalent_keys = identify_key_values(schema)

    # 2. Extract main queries from derived_query_file to directory
    with open(args.derived_query_file, "rb") as f:
        all_queries, _ = pickle.load(f)
    os.makedirs(args.query_dir, exist_ok=True)
    for name, sql in all_queries.items():
        path = os.path.join(args.query_dir, f"{name}.sql")
        with open(path, "w") as f:
            f.write(sql.strip())
            if not sql.strip().endswith(";"):
                f.write(";")
    print(f"[INFO] Extracted {len(all_queries)} main queries to {args.query_dir}")

    # 3. Pre-materialize and record elapsed time
    t_start = time.time()
    get_query_binned_cards(
        args.query_dir,
        args.db_conn_kwargs,
        equivalent_keys,
        args.sampling_percentage,
        args.save_dir,
    )
    elapsed = time.time() - t_start
    print(f"\n[Pre-materialization complete] Total elapsed: {elapsed:.2f} sec ({elapsed/60:.2f} min)")


if __name__ == "__main__":
    main()
