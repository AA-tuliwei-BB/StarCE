import os
from duckdb import DuckDBPyConnection
from tqdm import tqdm
import sys

import pandas as pd

# add parent directory to the sys path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lpbound.config.benchmark_schema import load_benchmark_schema
from lpbound.config.lpbound_config import LpBoundConfig
from lpbound.config.paths import LpBoundPaths
from lpbound.acyclic.lpbound import build_lpbound_statistics, estimate

from benchmarks.approaches.postgres.postgres import DatabaseConnection, get_dbConn
from benchmarks.approaches.duckdb_helper.duckdb_helper import (
    get_connection,
    get_duckdb_estimate,
    get_duckdb_estimate_with_time,
)


def estimation_experiment(config: LpBoundConfig, verbose: bool = False):

    benchmark = config.benchmark_name

    dump_lp_program_path = f"{LpBoundPaths.OUTPUT_DIR}/lp_programs/{benchmark}/"
    estimation_result_path = f"{LpBoundPaths.RESULTS_DIR}/accuracy_acyclic/{benchmark}/"
    os.makedirs(dump_lp_program_path, exist_ok=True)
    os.makedirs(estimation_result_path, exist_ok=True)

    # workload file
    workload_file = f"{LpBoundPaths.WORKLOADS_DIR}/{benchmark}/{benchmark}Queries.sql"
    # read the query from the workload file
    with open(workload_file, "r") as f:
        queries = f.readlines()
    query_ids = range(1, len(queries) + 1)
    # query_ids = [50]  # FIXME: for debugging

    estimates: list[float] = []
    this_query_ids: list[int] = []

    for i in tqdm(range(len(query_ids))):
        query_id = query_ids[i]

        this_query_ids.append(query_id)
        query_sql = queries[query_id - 1]

        # estimation
        this_estimate = estimate(
            input_query_sql=query_sql,
            config=config,
            dump_lp_program_file=f"{dump_lp_program_path}/{benchmark}_full_estimations_{query_id}.lp",
            verbose=verbose,
        )

        estimates.append(this_estimate)

    result = pd.DataFrame(
        {
            "QueryID": this_query_ids,
            "lpbound_Estimate": estimates,
        }
    )
    result.to_csv(f"{estimation_result_path}/lpbound_{benchmark}_full_estimations.csv", index=False)


def estimation_experiment_other_approaches(benchmark: str, approach: str):

    estimation_result_path = f"{LpBoundPaths.RESULTS_DIR}/accuracy_acyclic/{benchmark}/"
    os.makedirs(estimation_result_path, exist_ok=True)

    if approach not in {"postgres", "duckdb"}:
        raise ValueError(f"Approach {approach} not supported in the public repo")

    # initialize the approach-specific connection
    postgres_conn: DatabaseConnection | None = None
    duckdb_conn: DuckDBPyConnection | None = None
    if approach == "postgres":
        postgres_conn = get_dbConn(benchmark, groupby=False)
    elif approach == "duckdb":
        duckdb_conn = get_connection(benchmark)
    # END: initialize the approach-specific connection

    # workload file
    workload_file = f"{LpBoundPaths.WORKLOADS_DIR}/{benchmark}/{benchmark}Queries.sql"
    # read the query from the workload file
    with open(workload_file, "r") as f:
        queries = f.readlines()
    query_ids = range(1, len(queries) + 1)

    estimates: list[float] = []
    this_query_ids: list[int] = []
    inference_times: list[float] = []

    for i in tqdm(range(len(query_ids))):
        query_id = query_ids[i]

        this_query_ids.append(query_id)
        query_sql = queries[query_id - 1]
        this_inference_time = 0.0

        # estimation
        if approach == "postgres":
            assert postgres_conn is not None
            this_estimate, this_inference_time = postgres_conn.getSizeEstimateSQLWithTime(query_sql)
        elif approach == "duckdb":
            assert duckdb_conn is not None
            this_estimate, this_inference_time = get_duckdb_estimate_with_time(duckdb_conn, query_sql)
        else:
            raise ValueError(f"Approach {approach} not supported")

        estimates.append(this_estimate)
        inference_times.append(this_inference_time)

    result = pd.DataFrame(
        {
            "QueryID": this_query_ids,
            f"{approach}_Estimate": estimates,
            f"{approach}_InferenceTime": inference_times,
        }
    )
    result.to_csv(f"{estimation_result_path}/{approach}_{benchmark}_full_estimations.csv", index=False)


def build_benchmarks():

    for benchmark in ["stats", "joblight", "jobrange", "jobjoin", "statsjoin"]:
        lpbound_config = LpBoundConfig(
            benchmark_name=benchmark,
            num_mcvs=5000,
            num_buckets=128,
            p_max=10,
        )
        build_lpbound_statistics(lpbound_config)


def estimation_benchmarks():
    for benchmark in ["joblight", "stats", "jobrange", "jobjoin", "statsjoin"]:
        config = LpBoundConfig(
            benchmark_name=benchmark,
            p_max=10,
        )

        estimation_experiment(config)


if __name__ == "__main__":

    # get the approach name from the command line
    approach = sys.argv[1] if len(sys.argv) > 1 else "lpbound"
    assert approach in ["lpbound", "postgres", "duckdb"]

    if approach == "lpbound":
        # for lpbound
        build_benchmarks()
        estimation_benchmarks()
    else:
        # for other approaches
        for benchmark in ["joblight", "stats", "jobrange", "jobjoin", "statsjoin"]:
            estimation_experiment_other_approaches(benchmark, approach)
