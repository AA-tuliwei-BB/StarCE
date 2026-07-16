#!/usr/bin/env python3
"""
为 StatsJoin benchmark 构建 SafeBound 并生成子查询基数估计。

用法:
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

# === 配置 ===
DATA_DIR = 'Data/Stats'
PKL_PATH = './StatObjects/SafeBound_StatsJoin.pkl'
SUBQUERY_FILE = '../../Benchmark/workloads/StatsJoin/subquery/subquery.sql'
OUTPUT_FILE = '../../Benchmark/workloads/StatsJoin/subquery/result/safebound.txt'

# STATS 8 表配置
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

# StatsJoin 无谓词，filterColumns 全为空
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
    """解析 SQL 查询并转换为 JoinQueryGraph"""
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
    # === 步骤1: 构建或加载 SafeBound ===
    if os.path.exists(PKL_PATH):
        print(f"加载已有 SafeBound: {PKL_PATH}")
        safeBound = pickle.load(open(PKL_PATH, 'rb'))
    else:
        print("构建 SafeBound (StatsJoin, 无谓词)...")
        # 加载 CSV 数据
        data = {}
        for table in tableNames:
            csv_path = os.path.join(DATA_DIR, f"{table}.csv")
            if os.path.exists(csv_path):
                data[table] = pd.read_csv(csv_path)
                print(f"  加载 {table}: {len(data[table])} 行")
            else:
                raise FileNotFoundError(f"CSV 文件不存在: {csv_path}")

        # 选择需要的列
        tables = [data[t][list(set(joinColumns[i] + filterColumns[i]))]
                  for i, t in enumerate(tableNames)]

        # 构建 SafeBound (filterColumns 全部为空列表)
        safeBound = SafeBound(
            tableDFs=tables,
            tableNames=tableNames,
            tableJoinCols=joinColumns,
            originalFilterCols=filterColumns,
            relativeErrorPerSegment=0.01,
            FKtoKDict=FKtoKDict,
        )
        del data

        # 保存
        os.makedirs(os.path.dirname(PKL_PATH), exist_ok=True)
        pickle.dump(safeBound, open(PKL_PATH, 'wb'))
        print(f"SafeBound 已保存: {PKL_PATH} ({os.path.getsize(PKL_PATH):,} bytes)")

    # === 步骤2: 运行估计 ===
    print(f"\n读取子查询: {SUBQUERY_FILE}")
    with open(SUBQUERY_FILE) as f:
        sqls = [l.strip() for l in f if l.strip()]
    print(f"共 {len(sqls)} 条子查询")

    estimates = []
    for i, sql in enumerate(sqls, 1):
        try:
            query = sql_to_joingraph(sql)
            query.buildJoinGraph()
            bound = safeBound.functionalFrequencyBound(query)
            estimates.append(int(bound))
        except Exception as e:
            print(f"  Q{i} 错误: {e}")
            estimates.append(-1)

        if i % 50 == 0:
            print(f"  进度: {i}/{len(sqls)}")

    # === 步骤3: 写入结果 ===
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        for c in estimates:
            f.write(f"{c}\n")

    neg = sum(1 for e in estimates if e < 0)
    print(f"\nSafeBound 完成: {len(estimates)} 条 -> {OUTPUT_FILE} ({neg} 条失败)")


if __name__ == '__main__':
    main()
