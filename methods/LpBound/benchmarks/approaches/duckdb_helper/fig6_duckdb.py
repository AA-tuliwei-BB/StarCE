import os
from pathlib import Path
from tqdm import tqdm
import sys

import pandas as pd

# add parent directory to the sys path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lpbound.config.paths import LpBoundPaths

from benchmarks.approaches.duckdb_helper.duckdb_helper import (
    get_connection,
    get_duckdb_estimate,
    get_duckdb_estimate_with_time,
)


def estimation_experiment_duckdb():

    estimation_result_path = f"{LpBoundPaths.RESULTS_DIR}/accuracy_cyclic/duckdb_estimates.txt"
    os.makedirs(os.path.dirname(estimation_result_path), exist_ok=True)

    duckdb_conn = get_connection("subgraph_matching")

    # workload file
    workload_dir = Path(f"{LpBoundPaths.WORKLOADS_DIR}/subgraph_matching/dblp")
    # read the query from the workload file
    query_files: list[Path] = list(workload_dir.glob("*.sql"))
    queries: list[str] = [f.read_text() for f in query_files]

    estimates: list[float] = []
    this_query_ids: list[str] = []

    for i in tqdm(range(len(queries))):
        query_sql = queries[i]
        query_name = query_files[i].name.replace(".sql", "")

        this_query_ids.append(query_name)

        # estimation
        this_estimate, _ = get_duckdb_estimate_with_time(duckdb_conn, query_sql)

        estimates.append(this_estimate)

    result = pd.DataFrame(
        {
            "QueryID": this_query_ids,
            "Estimate": estimates,
        }
    )
    result.to_csv(estimation_result_path, index=False, header=False)


if __name__ == "__main__":

    estimation_experiment_duckdb()
