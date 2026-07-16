import subprocess
import time

BASE_COMMAND = """python run_experiment.py --dataset imdb \
       --evaluate_cardinalities \
       --model_path Benchmark/IMDB/job-light \
       --query_file_location Benchmark/IMDB/job-range-all-subqueries.sql \
       --learning_algo chow-liu \
       --max_parents 1 \
       --infer_algo exact-jit"""

def run_query(query_num):
    command = BASE_COMMAND.format(query_num)
    subprocess.run(command, shell=True)

# Run each query 5 times
for i in range(1, 2):
    print(f"\n=== Running Query {i} ===")
    for run in range(1, 6):
        print(f"Run {run} for Query {i}")
        run_query(i)
        # Add a small delay between runs to avoid any potential issues
        time.sleep(1) 