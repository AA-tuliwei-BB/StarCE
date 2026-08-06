#!/usr/bin/env python3
"""
Parse subquery_grouped.sql to extract main queries, flat subqueries, and sub-to-main mapping.
Single source of truth: subquery_grouped.sql only (no dependency on subquery.sql).
"""
import argparse
import os
import pickle
import re

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base = os.path.normpath(os.path.join(script_dir, ".."))
    proj_root = os.path.normpath(os.path.join(base, "../.."))

    parser = argparse.ArgumentParser()
    parser.add_argument("--grouped_file", default=os.path.join(proj_root, "Benchmark/workloads/JOBM/subquery/subquery_grouped.sql"))
    parser.add_argument("--main_queries_dir", default=os.path.join(base, "checkpoints/jobm_main_queries"))
    parser.add_argument("--subquery_output", default=os.path.join(proj_root, "Benchmark/workloads/JOBM/subquery/subquery_from_grouped.sql"))
    parser.add_argument("--mapping_output", default=os.path.join(base, "checkpoints/jobm_sub_to_main.pkl"))
    args = parser.parse_args()

    grouped_file = args.grouped_file
    main_queries_dir = args.main_queries_dir
    subquery_output = args.subquery_output
    mapping_output = args.mapping_output

    os.makedirs(main_queries_dir, exist_ok=True)
    os.makedirs(os.path.dirname(subquery_output), exist_ok=True)
    os.makedirs(os.path.dirname(mapping_output), exist_ok=True)

    main_queries = {}
    subqueries = []
    sub_to_main = []
    current_main_id = None

    with open(grouped_file, "r") as f:
        for line in f:
            line = line.rstrip()
            if not line:
                continue
            if line.startswith("==="):
                m = re.match(r"===\s*(\d+)\s*===", line)
                if m:
                    current_main_id = int(m.group(1))
            elif line.startswith("EXPLAIN "):
                main_sql = line.replace("EXPLAIN ", "", 1).strip()
                if not main_sql.endswith(";"):
                    main_sql += ";"
                if current_main_id is not None:
                    main_queries[current_main_id] = main_sql
                    path = os.path.join(main_queries_dir, f"{current_main_id}.sql")
                    with open(path, "w") as mf:
                        mf.write(main_sql)
            elif line.startswith("SELECT COUNT"):
                sql = line.strip()
                if not sql.endswith(";"):
                    sql += ";"
                subqueries.append(sql)
                if current_main_id is not None:
                    sub_to_main.append(current_main_id)
                else:
                    sub_to_main.append(None)

    with open(subquery_output, "w") as f:
        for sql in subqueries:
            f.write(sql + "\n")

    with open(mapping_output, "wb") as f:
        pickle.dump(sub_to_main, f)

    print(f"[INFO] Main queries: {len(main_queries)} -> {main_queries_dir}")
    print(f"[INFO] Subqueries: {len(subqueries)} -> {subquery_output}")
    print(f"[INFO] Mapping: {len(sub_to_main)} -> {mapping_output}")


if __name__ == "__main__":
    main()
