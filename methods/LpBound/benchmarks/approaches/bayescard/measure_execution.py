import subprocess
import time
import os
import pandas as pd
import sys
sys.path.append("../../../")
sys.path.append("../../")

from src.lpbound.config.paths import LpBoundPaths

def run_and_measure(execution_part: str):
    
    if execution_part == "generate_hdf":
        command = [
            "python", "run_experiment.py",
            "--dataset", "imdb",
            "--generate_hdf",
            "--csv_path", "data/imdb",
            "--hdf_path", "hdf_files/imdb"
        ]
        execution_part = "generate_hdf"
    
    elif execution_part == "generate_models":
        command = [
            "python", "run_experiment.py",
            "--dataset", "imdb",
            "--generate_models",
            "--hdf_path", "hdf_files/imdb",
            "--model_path", "Benchmark/IMDB/job-light",
            "--learning_algo", "chow-liu",
            "--max_parents", "1",
            "--sample_size", "200000"
        ]
        execution_part = "generate_models"
        
    elif execution_part == "evaluate_cardinalities":
        command = [
            "python", "run_experiment.py",
            "--dataset", "imdb",
            "--evaluate_cardinalities",
            "--model_path", "Benchmark/IMDB/job-light",
            "--query_file_location", "Benchmark/IMDB/job-light.sql",
            "--learning_algo", "chow-liu",
            "--max_parents", "1",
            "--infer_algo", "exact-jit"
        ]
        execution_part = "evaluate_cardinalities"
        
    elif execution_part == "evaluate_cardinalities_subqueries":
        command = [
            "python", "run_experiment.py",
            "--dataset", "imdb",
            "--evaluate_cardinalities",
            "--model_path", "Benchmark/IMDB/job-light",
            "--query_file_location", "Benchmark/IMDB/job-light-all-subqueries.sql",
            "--learning_algo", "chow-liu",
            "--max_parents", "1",
            "--infer_algo", "exact-jit"
        ]
        execution_part = "evaluate_cardinalities_subqueries"
        
    else:
        raise ValueError(f"Invalid execution part: {execution_part}")
    start_time = time.time()
    
    try:
        # Execute the command and capture output
        process = subprocess.run(command, check=True, capture_output=False, text=True)
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        print(f"Command executed successfully!")
        print(f"Execution time: {execution_time:.2f} seconds")
        print(f"Output:\n{process.stdout}")
        
        # Write execution time to a file
        with open("execution_time.txt", "a") as file:
            file.write(f"Executed part: {execution_part} \t")
            file.write(f"Execution time: {execution_time:.6f} seconds\n")
        
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        print(f"Error output:\n{e.stderr}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    
    runs = 6
    
    run_and_measure("generate_hdf")
    run_and_measure("generate_models") 
    for r in range(runs):
        run_and_measure("evaluate_cardinalities")
        os.rename("runtimes_single_queries.txt", "runtimes_full_queries_" + str(r) + ".txt")
        os.rename("predictions.txt", "predictions_full_queries.txt")
        
    for r in range(runs):
        run_and_measure("evaluate_cardinalities_subqueries")
        os.rename("runtimes_single_queries.txt", "runtimes_subqueries_" + str(r) + ".txt")
        os.rename("predictions.txt", "predictions_subqueries.txt")

    # copy predictions_full_queries to results directory
    df_results_full_queries = pd.read_csv("predictions_full_queries.txt", header=None)
    
    # add the QueryID column
    df_results_full_queries.reset_index(inplace=True)
    df_results_full_queries.columns = ["QueryID", "bayescard_Estimate"]
    df_results_full_queries["QueryID"] = df_results_full_queries["QueryID"] + 1
    
    df_results_full_queries.to_csv(f"{LpBoundPaths.RESULTS_DIR}/accuracy_acyclic/joblight/bayescard_joblight_full_estimations.csv")
    