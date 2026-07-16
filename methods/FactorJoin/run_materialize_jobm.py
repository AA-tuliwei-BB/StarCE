#!/usr/bin/env python3
"""
JOBM pre-materialization script: materialize binned cards for main queries in jobm_main_queries/ and record elapsed time.
Requires prior training and prepare_sample. Run parse_subquery_grouped.py to generate jobm_main_queries/.
"""
import argparse
import os
import time
from pathlib import Path

from Join_scheme.binning import identify_key_values
from Schemas.imdb.schema import gen_jobm_schema
from Sampling.get_query_binned_cards import get_query_binned_cards

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_path", default=str(PROJECT_ROOT / "methods/SafeBound/Data/IMDB/{}.csv"))
    parser.add_argument("--query_dir", default="checkpoints/jobm_main_queries")
    parser.add_argument("--save_dir", default="checkpoints/")
    parser.add_argument("--sampling_percentage", type=float, default=1.0)
    parser.add_argument("--db_conn_kwargs", default="dbname=imdbm user=liwei host=localhost port=5432")
    args = parser.parse_args()

    schema = gen_jobm_schema(args.data_path)
    _, equivalent_keys = identify_key_values(schema)

    t_start = time.time()
    get_query_binned_cards(
        args.query_dir,
        args.db_conn_kwargs,
        equivalent_keys,
        args.sampling_percentage,
        args.save_dir,
    )
    elapsed = time.time() - t_start
    print(f"\n[JOBM pre-materialization complete] Total elapsed: {elapsed:.2f} sec ({elapsed/60:.2f} min)")


if __name__ == "__main__":
    main()
