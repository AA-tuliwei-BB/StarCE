import re
import time

from lpbound.config.benchmark_schema import load_benchmark_schema
from lpbound.config.lpbound_config import LpBoundConfig
from lpbound.duckdb_adapter.duckdb_manager import DatabaseManager


def get_connection(benchmark: str, groupby: bool = False):
    lpbound_config = LpBoundConfig(benchmark_name=benchmark)
    schema_data = load_benchmark_schema(lpbound_config)
    db_manager = DatabaseManager(benchmark_schema=schema_data, groupby=groupby)
    con = db_manager.create_or_load_db(read_only=False)
    return con


def extract_number(string):
    """Extracts the number following "EC:" from a multi-line string, even if interrupted by "│ " or other characters.

    Args:
        string: The input string.

    Returns:
        The extracted number as a string, or None if no match is found.
    """

    pattern = r"│EC:\s*(\d+)\s*.*?\n│\s*(\d+)"
    match = re.search(pattern, string, re.MULTILINE)

    return match.group(1) + match.group(2)


def get_duckdb_estimate(con, query: str) -> int:
    duckdb_string = con.sql(query).explain()

    try:
        estimated_cardinalities = extract_number(duckdb_string)
    except:
        # get first occurence of EC: in the string
        estimated_cardinalities = re.findall(r"EC:\s(\d+)", duckdb_string)[0]

    if estimated_cardinalities is None:
        estimated_cardinalities = re.findall(r"EC:\s(\d+)", duckdb_string)[0]

    if len(estimated_cardinalities) > 0:
        total_estimated_cardinality = int(estimated_cardinalities)
    else:
        total_estimated_cardinality = 0

    return total_estimated_cardinality


def get_duckdb_estimate_with_time(con, query: str) -> tuple[int, float]:
    start_time = time.time()
    # print(query)
    duckdb_string = con.sql(query).explain()
    #print(duckdb_string)
    try:
        estimated_cardinalities = extract_number(duckdb_string)
    except:
        # get first occurence of EC: in the string
        estimated_cardinalities = re.findall(r"EC:\s(\d+)", duckdb_string)[0]

    if estimated_cardinalities is None:
        estimated_cardinalities = re.findall(r"EC:\s(\d+)", duckdb_string)[0]

    if len(estimated_cardinalities) > 0:
        total_estimated_cardinality = int(estimated_cardinalities)
    else:
        total_estimated_cardinality = 0
    
    end_time = time.time()
    time_taken = end_time - start_time  # in seconds
    return total_estimated_cardinality, time_taken * 1000  # in milliseconds
