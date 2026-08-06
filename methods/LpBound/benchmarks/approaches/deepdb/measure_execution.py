import subprocess
import time
from typing import List
import logging
import os
import sys
import shutil
import pandas as pd
sys.path.append(".")
#from lpbound.config.paths import LpBoundPaths
sys.path.append("../../../")
sys.path.append("../../")

from src.lpbound.config.paths import LpBoundPaths

#sys.path.append(f"{LpBoundPaths.PROJ_ROOT_DIR}/benchmarks/approaches/deepdb")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5.5s] %(message)s",
    handlers=[
        logging.FileHandler("execution_times.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_and_measure(execution_part: str, command: List[str]) -> None:
    """
    Execute a command and measure its execution time.
    
    Args:
        execution_part: Name/description of the execution part
        command: Command to execute as list of strings
    """
    logger.info(f"Starting execution of: {execution_part}")
    start_time = time.time()
    
    try:
        # Execute the command
        process = subprocess.run(command, check=True, capture_output=True, text=True)
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        logger.info(f"Successfully completed: {execution_part}")
        logger.info(f"Execution time: {execution_time:.2f} seconds")
        
        # Write execution time to a separate file
        with open("execution_time.txt", "a") as file:
            file.write(f"Executed part: {execution_part}\n")
            file.write(f"Execution time: {execution_time:.6f} seconds\n")
            file.write("-" * 80 + "\n")
        
        # Log stdout if there is any
        if process.stdout:
            logger.debug(f"Command output:\n{process.stdout}")
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing {execution_part}: {e}")
        logger.error(f"Error output:\n{e.stderr}")
    except Exception as e:
        logger.error(f"Unexpected error during {execution_part}: {e}")

if __name__ == "__main__":
    # Define the three commands
    commands = {
        "generate_hdf": [
            "python3", "maqp.py", "--generate_hdf",
            "--dataset", "imdb-light",
            "--csv_seperator", ",",
            "--csv_path", "data/imdb_data",
            "--hdf_path", "data/imdb_hdf",
            "--max_rows_per_hdf_file", "100000000"
        ],
        
        "generate_ensemble": [
            "python3", "maqp.py", "--generate_ensemble",
            "--dataset", "imdb-light",
            "--samples_per_spn", "1000000", "1000000", "1000000", "1000000", "1000000",
            "--ensemble_strategy", "relationship",
            "--hdf_path", "data/imdb_hdf",
            "--ensemble_path", "data/imdb_spn_ensembles",
            "--max_rows_per_hdf_file", "100000000",
            "--post_sampling_factor", "10", "10", "5", "1", "1"
        ],
        
        "evaluate_cardinalities": [
            "python3", "maqp.py", "--evaluate_cardinalities",
            "--rdc_spn_selection",
            "--max_variants", "1",
            "--pairwise_rdc_path", "data/pairwise_rdc.pkl",
            "--dataset", "imdb-light",
            "--target_path", "data/imdb_cardinality_estimation/results/deepDB/imdb_light_model_based_budget_5.csv",
            "--ensemble_location", "data/imdb_spn_ensembles/ensemble_relationships_imdb-light_1000000.pkl",
            "--query_file_location", "./benchmarks/job-light/sql/job_light_queries.sql",
            "--ground_truth_file_location", "./benchmarks/job-light/sql/job_light_true_cardinalities.csv"
        ],
        
        "evaluate_subquery_cardinalities": [
            "python3", "maqp.py", "--evaluate_cardinalities",
            "--rdc_spn_selection",
            "--max_variants", "1",
            "--pairwise_rdc_path", "data/pairwise_rdc.pkl",
            "--dataset", "imdb-light",
            "--target_path", "data/imdb_cardinality_estimation/results/deepDB/imdb_light_model_based_budget_5.csv",
            "--ensemble_location", "data/imdb_spn_ensembles/ensemble_relationships_imdb-light_1000000.pkl",
            "--query_file_location", "./benchmarks/job-light/sql/job-light-all-subqueries-deepdb.sql",
            "--ground_truth_file_location", "./benchmarks/job-light/sql/true_cardinality_mock.csv"
        ]
        
    }

    runs = 6
    
    # Execute each command in sequence
    for part, command in commands.items():
        if part == "generate_hdf" or (part == "generate_ensemble"):
            logger.info("=" * 80)
            logger.info(f"Starting new command: {part}")
            run_and_measure(part, command)
            logger.info("=" * 80 + "\n")  
            
        if part == "evaluate_cardinalities":
            logger.info(f"Starting new command: {part}")
            for r in range(runs):
                run_and_measure(part, command)
                # rename runtime_log.txt to runtime_log_full_queries.txt
                os.rename('runtime_log.txt', "runtime_log_full_queries_" + str(r) + ".txt")
                os.rename('predictions.txt', "predictions_log_full_queries_" + str(r) + ".txt")
            
            logger.info("=" * 80 + "\n")  
            
        if part == "evaluate_subquery_cardinalities":
            logger.info(f"Starting new command: {part}")
            for r in range(runs):
                run_and_measure(part, command)
                # rename runtime_log.txt to runtime_log_full_queries.txt
                os.rename('runtime_log.txt', "runtime_log_subqueries_queries_" + str(r) + ".txt")
                os.rename('predictions.txt', "predictions_log_subqueries_queries_" + str(r) + ".txt")
            logger.info("=" * 80 + "\n")  
    # run evaluate_cardinalities 6 times
    #for i in range(6):
    #    run_and_measure("generate_hdf", commands["generate_hdf"])
    
    df_results_full_queries = pd.read_csv("predictions_log_full_queries_0.txt", header=None)
    
    # add the QueryID column
    df_results_full_queries.reset_index(inplace=True)
    df_results_full_queries.columns = ["QueryID", "deepdb_Estimate"]
    df_results_full_queries["QueryID"] = df_results_full_queries["QueryID"] + 1
    
    df_results_full_queries.to_csv(f"{LpBoundPaths.RESULTS_DIR}/accuracy_acyclic/joblight/deepdb_joblight_full_estimations.csv")
    
