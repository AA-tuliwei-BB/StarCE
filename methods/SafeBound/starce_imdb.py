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
path = 'subqueries.sql'

def sql_to_joingraph(sql_query):
    """
    Parse SQL query and convert to JoinQueryGraph method call
    
    Parameters:
        sql_query: SQL query string, format as in example
        
    Returns:
        JoinQueryGraph instance
    """
    return SQLQueriesToJoinQueryGraphs(sql_query)

    # initialize JoinQueryGraph
    query = JoinQueryGraph()
    
    # parse FROM clause to get table aliases
    from_match = re.search(r'FROM\s+(.+?)(?:\s+WHERE|$)', sql_query, re.IGNORECASE)
    if not from_match:
        raise ValueError("Invalid SQL query: missing FROM clause")
    
    # parse table aliases
    tables = [t.strip() for t in from_match.group(1).split(',')]
    for table in tables:
        if ' AS ' in table.upper():
            table_name, alias = re.split(r'\s+AS\s+', table, flags=re.IGNORECASE)
        else:
            table_name = alias = table.split()[-1]  # if no AS, take last word as alias
        query.addAlias(table_name.strip(), alias.strip())
    
    # parse WHERE clause to get join conditions
    where_match = re.search(r'WHERE\s+(.+?)(?:\s*;|$)', sql_query, re.IGNORECASE)
    if where_match:
        join_conditions = [cond.strip() for cond in where_match.group(1).split('AND')]
        
        for condition in join_conditions:
            # parse conditions like table1.column1=table2.column2
            match = re.match(r'(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)', condition)
            if match:
                table1, col1, table2, col2 = match.groups()
                query.addJoin(table1, col1, table2, col2)
    
    return query

print(os.path.getsize("./StatObjects/SafeBound_2_JOBM.pkl"))
safeBound = pickle.load(open("./StatObjects/SafeBound_2_JOBM.pkl", 'rb'))

print('test')

with open(path) as f:
    line_id = 0
    sqls = f.readlines()
    for sql in sqls:
        line_id += 1
        # query = sql_to_joingraph(sql)[0]
        result = SQLQueriesToJoinQueryGraphs(sql)
        # print(line_id, len(result))
        query = result[0]
        query.buildJoinGraph()
        # query.printJoinGraph()
        bound = safeBound.functionalFrequencyBound(query)
        print(bound)
    # sqls = f.readlines()
    # id = 0
    # for sql in sqls:
    #     id = id + 1
    #     # print(id)
    #     query = sql_to_joingraph(sql)
    #     query.buildJoinGraph()
    #     # query.printJoinGraph()
    #     bound = safeBound.functionalFrequencyBound(query)
    #     print(bound)