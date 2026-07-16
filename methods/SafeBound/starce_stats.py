
import datetime
import pickle
import sys, os
import pandas as pd
import numpy as np
import re
sys.path.append('./Source')
from SafeBoundUtils import *
from JoinGraphUtils import *
from SQLParser import *

# path = 'single_query.sql'
path = 'subqueries-stats.sql'

def load_csv_to_dataframes(dir_path):
    df_dict = {}
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if file.endswith('.csv'):
                file_path = os.path.join(root, file)
                # 去除.csv后缀作为键名
                key = os.path.splitext(file)[0]
                df_dict[key] = pd.read_csv(file_path)
    return df_dict

def sql_to_joingraph(sql_query):
    """
    解析SQL查询并转换为JoinQueryGraph方法调用
    
    参数:
        sql_query: SQL查询字符串，格式如示例
        
    返回:
        JoinQueryGraph实例
    """
    
    # 初始化JoinQueryGraph
    query = JoinQueryGraph()
    
    # 解析FROM子句获取表别名
    from_match = re.search(r'FROM\s+(.+?)(?:\s+WHERE|$)', sql_query, re.IGNORECASE)
    if not from_match:
        raise ValueError("Invalid SQL query: missing FROM clause")
    
    # 解析表别名
    tables = [t.strip() for t in from_match.group(1).split(',')]
    for table in tables:
        if ' AS ' in table.upper():
            table_name, alias = re.split(r'\s+AS\s+', table, flags=re.IGNORECASE)
        else:
            table_name = alias = table.split()[-1]  # 如果没有AS，取最后一个单词作为别名
        query.addAlias(table_name.strip(), alias.strip())
    
    # 解析WHERE子句获取连接条件
    where_match = re.search(r'WHERE\s+(.+?)(?:\s*;|$)', sql_query, re.IGNORECASE)
    if where_match:
        join_conditions = [cond.strip() for cond in where_match.group(1).split('AND')]
        
        for condition in join_conditions:
            matched = False
            # 解析形如 table1.column1=table2.column2 的条件
            match = re.match(r'(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)', condition)
            if match:
                table1, col1, table2, col2 = match.groups()
                query.addJoin(table1, col1, table2, col2)
                matched = True
            # 解析形如
    
    return query


# 使用相对路径调用函数
# data_dict = load_csv_to_dataframes('Data/Stats')

# tableDFs = []
# tableNames = []
# tableJoinCols = []
# filterColumns = []

# for name, df in data_dict.items():
#     print(f"\n{name}:")
#     print(df.head())
#     tableDFs.append(df)
#     tableNames.append(name)
#     if name == 'users':
#         tableJoinCols.append(['Id'])
#         filterColumns.append([])
#     elif name == 'votes':
#         tableJoinCols.append(['PostId', 'UserId'])
#         filterColumns.append([])
#     elif name == 'posts':
#         tableJoinCols.append(['Id', 'OwnerUserId'])
#         filterColumns.append([])
#     elif name == 'postHistory':
#         tableJoinCols.append(['PostId', 'UserId'])
#         filterColumns.append([])
#     elif name == 'tags':
#         tableJoinCols.append(['ExcerptPostId'])
#         filterColumns.append([])
#     elif name == 'postLinks':
#         tableJoinCols.append(['PostId', 'RelatedPostId'])
#         filterColumns.append([])
#     elif name == 'badges':
#         tableJoinCols.append(['UserId'])
#         filterColumns.append([])
#     elif name == 'comments':
#         tableJoinCols.append(['PostId', 'UserId'])
#         filterColumns.append([])
#     else:
#         print('fuck')
#         tableJoinCols.append([])
#         filterColumns.append([])

# FKtoKDict = {
#     # "votes": [["UserId", "users", "Id"], ["PostId", "posts", "Id"]],
#     # "posts": [["OwnerUserId", "users", "Id"]],
#     # "postHistory": [["UserId", "users", "Id"], ["PostId", "posts", "Id"]],
#     # "tags": [["ExcerptPostId", "posts", "Id"]],
#     # "postLinks": [["PostId", "posts", "Id"], ["RelatedPostId", "posts", "Id"]],
#     # "badges": [["UserId", "users", "Id"]],
#     # "comments": [["UserId", "users", "Id"], ["PostId", "posts", "Id"]],
# }

# print('test')

# safeBound = SafeBound(tableDFs=tableDFs, tableNames=tableNames, tableJoinCols=tableJoinCols, relativeErrorPerSegment=.01, FKtoKDict=FKtoKDict)
# safeBound = SafeBound(tableDFs=tableDFs[:1], tableNames=tableNames[:1], tableJoinCols=tableJoinCols[:1], relativeErrorPerSegment=.01, trackNulls=False, trackTriGrams=False)

# print(os.path.getsize("./StatObjects/SafeBound_5_Stats.pkl"))
safeBound = pickle.load(open("./StatObjects/SafeBound_5_Stats.pkl", 'rb'))

# print('test')

# queries = SQLFileToJoinQueryGraphs('subqueries-stats.sql', True)
# for query in queries:
#     bound = safeBound.functionalFrequencyBound(query)
#     print(bound)

with open('subqueries-stats.sql') as f:
    line_id = 0
    sqls = f.readlines()
    for sql in sqls:
        line_id += 1
        query = sql_to_joingraph(sql)
        query.buildJoinGraph()
        # query.printJoinGraph()
        bound = safeBound.functionalFrequencyBound(query)
        print(bound)