#!/usr/bin/env python3
"""
Build SafeBound for StatsJoin benchmark and generate subquery cardinality estimates.

Usage:
    cd methods/SafeBound
    python estimate_statsjoin.py
"""
import pickle
import sys
import os
import re
import pandas as pd

sys.path.append('./Source')
from SafeBoundUtils import *
from JoinGraphUtils import *
from SQLParser import *

# === Configuration ===
DATA_DIR = 'Data/Stats'
PKL_PATH = './StatObjects/SafeBound_StatsJoin.pkl'
SUBQUERY_FILE = '../../Benchmark/workloads/StatsJoin/subquery/subquery.sql'
OUTPUT_FILE = '../../Benchmark/workloads/StatsJoin/subquery/result/safebound.txt'

# STATS 8-table configuration
tableNames = ["badges", "comments", "postHistory", "postLinks",
              "posts", "tags", "users", "votes"]

joinColumns = [["Id", "UserId"],
               ["Id", "PostId", "UserId"],
               ["Id", "PostId", "UserId"],
               ["Id", "PostId", "RelatedPostId"],
               ["Id", "OwnerUserId", "LastEditorUserId"],
               ["Id", "ExcerptPostId"],
               ["Id"],
               ["Id", "PostId", "UserId"]]

# StatsJoin has no predicates, filterColumns are all empty
filterColumns = [[] for _ in tableNames]

FKtoKDict = {
    "badges": [["UserId", "Id", "users"]],
    "comments": [["PostId", "Id", "posts"], ["UserId", "Id", "users"]],
    "postHistory": [["PostId", "Id", "posts"], ["UserId", "Id", "users"]],
    "postLinks": [["PostId", "Id", "posts"]],
    "posts": [["OwnerUserId", "Id", "users"]],
    "tags": [["ExcerptPostId", "Id", "posts"]],
    "votes": [["UserId", "Id", "users"], ["PostId", "Id", "posts"]],
}


def sql_to_joingraph(sql_query):
    """Parse SQL query and convert to JoinQueryGraph"""
    query = JoinQueryGraph()

    from_match = re.search(r'FROM\s+(.+?)(?:\s+WHERE|$)', sql_query, re.IGNORECASE)
    if not from_match:
        raise ValueError(f"Invalid SQL: missing FROM clause: {sql_query[:100]}")

    tables = [t.strip() for t in from_match.group(1).split(',')]
    for table in tables:
        if ' AS ' in table.upper():
            table_name, alias = re.split(r'\s+AS\s+', table, flags=re.IGNORECASE)
        else:
            table_name = alias = table.split()[-1]
        query.addAlias(table_name.strip(), alias.strip())

    where_match = re.search(r'WHERE\s+(.+?)(?:\s*;|$)', sql_query, re.IGNORECASE)
    if where_match:
        join_conditions = [cond.strip() for cond in where_match.group(1).split('AND')]
        for condition in join_conditions:
            match = re.match(r'(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)', condition)
            if match:
                t1, c1, t2, c2 = match.groups()
                query.addJoin(t1, c1, t2, c2)

    return query


def main():
    # === Step 1: Build or load SafeBound ===
    if os.path.exists(PKL_PATH):
        print(f"Loading existing SafeBound: {PKL_PATH}")
        safeBound = pickle.load(open(PKL_PATH, 'rb'))
    else:
        print("Building SafeBound (StatsJoin, no predicates)...")
        # Load CSV data
        data = {}
        for table in tableNames:
            csv_path = os.path.join(DATA_DIR, f"{table}.csv")
            if os.path.exists(csv_path):
                data[table] = pd.read_csv(csv_path)
                print(f"  Loading {table}: {len(data[table])} rows")
            else:
                raise FileNotFoundError(f"CSV file does not exist: {csv_path}")

        # Select needed columns
        tables = [data[t][list(set(joinColumns[i] + filterColumns[i]))]
                  for i, t in enumerate(tableNames)]

        # Build SafeBound (filterColumns are all empty lists)
        safeBound = SafeBound(
            tableDFs=tables,
            tableNames=tableNames,
            tableJoinCols=joinColumns,
            originalFilterCols=filterColumns,
            relativeErrorPerSegment=0.01,
            FKtoKDict=FKtoKDict,
        )
        del data

        # Save
        os.makedirs(os.path.dirname(PKL_PATH), exist_ok=True)
        pickle.dump(safeBound, open(PKL_PATH, 'wb'))
        print(f"SafeBound saved: {PKL_PATH} ({os.path.getsize(PKL_PATH):,} bytes)")

    # === Step 2: Run estimation ===
    print(f"\nReading subqueries: {SUBQUERY_FILE}")
    with open(SUBQUERY_FILE) as f:
        sqls = [l.strip() for l in f if l.strip()]
    print(f"Total {len(sqls)} subqueries")

    estimates = []
    for i, sql in enumerate(sqls, 1):
        try:
            query = sql_to_joingraph(sql)
            query.buildJoinGraph()
            bound = safeBound.functionalFrequencyBound(query)
            estimates.append(int(bound))
        except Exception as e:
            print(f"  Q{i} error: {e}")
            estimates.append(-1)

        if i % 50 == 0:
            print(f"  Progress: {i}/{len(sqls)}")

    # === Step 3: Write results ===
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        for c in estimates:
            f.write(f"{c}\n")

    neg = sum(1 for e in estimates if e < 0)
    print(f"\nSafeBound complete: {len(estimates)} estimates -> {OUTPUT_FILE} ({neg} failed)")


if __name__ == '__main__':
    main()
