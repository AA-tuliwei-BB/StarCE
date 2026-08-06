import os
from pathlib import Path
import time
from tqdm import tqdm
import sys

import pandas as pd

# add parent directory to the sys path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lpbound.config.paths import LpBoundPaths

from benchmarks.approaches.postgres.postgres import get_dbConn


def compute_subquery_cardinalities(benchmark: str):
    """
    Compute the lattics for the given queries and method
    Store the results in the statistics folder
    """

    assert benchmark.lower() in ["jobjoin", "joblight", "jobrange", "stats"]

    # read the subqueries for the benchmark
    subqueries_file = f"{LpBoundPaths.WORKLOADS_DIR}/{benchmark}/{benchmark}_subqueries.csv"
    df = pd.read_csv(subqueries_file, sep="|")

    postgres_conn = get_dbConn(benchmark, groupby=False)

    this_query_ids = []
    tables_list = []
    estimates = []
    inference_times = []

    for i in tqdm(range(len(df))):
        row = df.iloc[i]
        query_id = row["QueryID"]
        tables = row["Tables"].split()
        subquery_sql = row["SQL"]

        this_estimate, this_inference_time = postgres_conn.getSizeEstimateSQLWithTime(subquery_sql)

        # record the statistics
        this_query_ids.append(query_id)
        tables_list.append(" ".join(sorted(tables)))
        estimates.append(this_estimate)
        inference_times.append(this_inference_time)

        # output statistics
        subquery_estimate_results = pd.DataFrame()
        subquery_estimate_results["QueryID"] = this_query_ids
        subquery_estimate_results["Tables"] = tables_list
        subquery_estimate_results["postgres_Estimate"] = estimates
        subquery_estimate_results["postgres_InferenceTime"] = inference_times

        # write the statistics
        output_dir = f"{LpBoundPaths.RESULTS_DIR}/evaluation_time/subquery_estimations/{benchmark}"
        os.makedirs(
            output_dir,
            exist_ok=True,
        )
        subquery_estimate_results.to_csv(
            f"{output_dir}/postgres_subquery_estimations.csv",
            index=False,
        )


if __name__ == "__main__":

    benchmarks = ["jobjoin", "joblight", "jobrange", "stats"]
    for benchmark in benchmarks:
        compute_subquery_cardinalities(benchmark)
