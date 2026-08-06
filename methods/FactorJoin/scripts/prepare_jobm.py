import os
import pickle
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

grouped_file = str(PROJECT_ROOT / "Benchmark/workloads/JOBM/subquery/subquery_grouped.sql")
subquery_file = str(PROJECT_ROOT / "Benchmark/workloads/JOBM/subquery/subquery.sql")
main_queries_dir = str(PROJECT_ROOT / "methods/FactorJoin/checkpoints/jobm_main_queries/")
output_pkl = str(PROJECT_ROOT / "methods/FactorJoin/checkpoints/jobm_sub_to_main.pkl")

os.makedirs(main_queries_dir, exist_ok=True)

# 1. Parse grouped file
sql_to_main_id = {}
main_id = None
with open(grouped_file, "r") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        if line.startswith("=== "):
            main_id = line.split(" ")[1]
        elif line.startswith("EXPLAIN "):
            main_sql = line.replace("EXPLAIN ", "").strip()
            # main queries are stored as 1.sql, 2.sql, ...
            with open(os.path.join(main_queries_dir, f"{main_id}.sql"), "w") as mf:
                mf.write(main_sql)
        elif line.startswith("SELECT "):
            sql_to_main_id[line] = main_id

# 2. Map subquery.sql
mapping = []
found_count = 0
with open(subquery_file, "r") as f:
    for i, line in enumerate(f):
        line = line.strip()
        if not line:
            continue
        
        # Exact match or with/without semicolon
        match_id = None
        if line in sql_to_main_id:
            match_id = sql_to_main_id[line]
        elif line.endswith(";") and line[:-1] in sql_to_main_id:
            match_id = sql_to_main_id[line[:-1]]
        elif not line.endswith(";") and (line + ";") in sql_to_main_id:
            match_id = sql_to_main_id[line + ";"]
        
        if match_id:
            mapping.append(match_id)
            found_count += 1
        else:
            print(f"Warning: subquery {i} not found in grouped file: {line[:100]}...")
            mapping.append(None)

with open(output_pkl, "wb") as f:
    pickle.dump(mapping, f)

print(f"Total subqueries in subquery.sql: {len(mapping)}")
print(f"Successfully mapped: {found_count}")
print(f"Main queries extracted: {len(os.listdir(main_queries_dir))}")
print(f"Mapping saved to {output_pkl}")
