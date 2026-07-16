import os
import pickle
from pathlib import Path

# JobJoin input preparation for predicate-free, main-query-level evaluation.
# From Benchmark/workloads/JobJoin/queries.sql (31 rows, each a pure join SELECT COUNT(*)) produce:
#   1. checkpoints/jobjoin_main_queries/{1..31}.sql -- one query per file, for get_query_binned_cards directory-based materialization
#   2. checkpoints/jobjoin_queries_clean.sql        -- 31 clean SELECT rows, for test_on_jobjoin per-row evaluation
#   3. checkpoints/jobjoin_sub_to_main.pkl          -- identity mapping ["1",...,"31"], concatenate {main_id}.pkl during evaluation

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

queries_file = str(PROJECT_ROOT / "Benchmark/workloads/JobJoin/queries.sql")
main_queries_dir = str(PROJECT_ROOT / "methods/FactorJoin/checkpoints/jobjoin_main_queries/")
clean_queries_file = str(PROJECT_ROOT / "methods/FactorJoin/checkpoints/jobjoin_queries_clean.sql")
output_pkl = str(PROJECT_ROOT / "methods/FactorJoin/checkpoints/jobjoin_sub_to_main.pkl")

os.makedirs(main_queries_dir, exist_ok=True)

with open(queries_file, "r") as f:
    queries = [line.strip() for line in f if line.strip()]

mapping = []
with open(clean_queries_file, "w") as cf:
    for i, sql in enumerate(queries, start=1):
        main_id = str(i)
        with open(os.path.join(main_queries_dir, f"{main_id}.sql"), "w") as mf:
            mf.write(sql)
        cf.write(sql + "\n")
        mapping.append(main_id)

with open(output_pkl, "wb") as f:
    pickle.dump(mapping, f)

print(f"Main queries: {len(queries)}")
print(f"Per-query .sql written to {main_queries_dir}")
print(f"Clean query file: {clean_queries_file}")
print(f"Mapping saved to {output_pkl}")
