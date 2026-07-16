import subprocess
import time
from typing import List
import logging
import os
import shutil
import argparse
import sys

# PostgreSQL connection parameters (only needed for IMDB experiments)
global DBNAME
DBNAME = "DBNAME"

global DB_USER
DB_USER = "USER"

global DB_PASSWORD
DB_PASSWORD = "PASSWORD"

global DB_HOST
DB_HOST = "localhost"

global DB_PORT
DB_PORT = "5432"

# Data paths - relative to this script's directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))

# Use the current Python interpreter (set by conda environment activation)
PYTHON_EXEC = sys.executable

# STATS data location (from project's data directory)
STATS_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "datasets", "stats")
# Local copy for preprocessing (we copy to avoid modifying original)
STATS_LOCAL_DIR = os.path.join(SCRIPT_DIR, "datasets", "stats_simplified")

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


def setup_stats_data():
    """
    Set up STATS dataset by copying from project's data directory.
    We copy (not symlink) because preprocessing modifies the files in place.
    """
    if os.path.exists(STATS_LOCAL_DIR):
        logger.info(f"STATS data directory already exists at {STATS_LOCAL_DIR}")
        return True

    if not os.path.exists(STATS_DATA_DIR):
        logger.error(f"Source STATS data not found at {STATS_DATA_DIR}")
        logger.error("Please ensure the project's data/datasets/stats directory exists")
        return False

    logger.info(f"Copying STATS data from {STATS_DATA_DIR} to {STATS_LOCAL_DIR}")
    os.makedirs(os.path.dirname(STATS_LOCAL_DIR), exist_ok=True)
    shutil.copytree(STATS_DATA_DIR, STATS_LOCAL_DIR)
    logger.info("STATS data copied successfully")
    return True


import re

# Column name mapping: uppercase -> correct camelCase (as used in schema)
COLUMN_NAME_MAP = {
    'ID': 'Id',
    'USERID': 'UserId',
    'POSTID': 'PostId',
    'DATE': 'Date',
    'CREATIONDATE': 'CreationDate',
    'SCORE': 'Score',
    'VIEWCOUNT': 'ViewCount',
    'OWNERUSERID': 'OwnerUserId',
    'ANSWERCOUNT': 'AnswerCount',
    'COMMENTCOUNT': 'CommentCount',
    'FAVORITECOUNT': 'FavoriteCount',
    'LASTEDITORUSERID': 'LastEditorUserId',
    'REPUTATION': 'Reputation',
    'VIEWS': 'Views',
    'UPVOTES': 'UpVotes',
    'DOWNVOTES': 'DownVotes',
    'POSTTYPEID': 'PostTypeId',
    'VOTETYPEID': 'VoteTypeId',
    'BOUNTYAMOUNT': 'BountyAmount',
    'POSTHISTORYTYPEID': 'PostHistoryTypeId',
    'RELATEDPOSTID': 'RelatedPostId',
    'LINKTYPEID': 'LinkTypeId',
    'COUNT': 'Count',
    'EXCERPTPOSTID': 'ExcerptPostId',
}

# Table name mapping: uppercase -> lowercase (as used in schema)
TABLE_NAME_MAP = {
    'BADGES': 'badges',
    'USERS': 'users',
    'VOTES': 'votes',
    'POSTS': 'posts',
    'COMMENTS': 'comments',
    'POSTHISTORY': 'postHistory',
    'POSTLINKS': 'postLinks',
    'TAGS': 'tags',
}


def convert_query_for_factorjoin(sql):
    """
    Convert a SQL query to FactorJoin-compatible format:
    1. Convert table names to lowercase
    2. Convert column names to camelCase (as expected by schema)
    3. Add ::timestamp to date string literals for PostgreSQL compatibility
    """
    # Replace table names (case-insensitive)
    for upper_name, correct_name in TABLE_NAME_MAP.items():
        # Match table name followed by space or AS or comma or dot
        sql = re.sub(rf'\b{upper_name}\b', correct_name, sql, flags=re.IGNORECASE)

    # Replace column names (case-insensitive) - be careful with word boundaries
    for upper_name, correct_name in COLUMN_NAME_MAP.items():
        # Match column name that follows a dot (table.column pattern)
        sql = re.sub(rf'\.{upper_name}\b', f'.{correct_name}', sql, flags=re.IGNORECASE)

    # Lowercase SQL keywords
    keywords = ['SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'AS', 'IN', 'BETWEEN', 'LIKE', 'NOT', 'NULL', 'IS']
    for kw in keywords:
        sql = re.sub(rf'\b{kw}\b', kw.lower(), sql, flags=re.IGNORECASE)

    # Find date strings like '2014-09-11 14:33:06' and add ::timestamp
    # Pattern matches 'YYYY-MM-DD HH:MM:SS' format
    date_pattern = r"'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})'"
    sql = re.sub(date_pattern, r"'\1'::timestamp", sql)

    return sql


def convert_subqueries_csv_to_sql(csv_path, output_sql_path):
    """
    Convert stats_subqueries.csv (format: QueryID|Tables|SQL) to plain SQL file.
    FactorJoin expects one SQL query per line.
    Creates a NEW file - does not modify the original.
    """
    if os.path.exists(output_sql_path):
        logger.info(f"Converted subqueries file already exists at {output_sql_path}")
        return True

    if not os.path.exists(csv_path):
        logger.error(f"Subqueries CSV not found at {csv_path}")
        return False

    logger.info(f"Converting {csv_path} to {output_sql_path}")
    with open(csv_path, 'r') as infile, open(output_sql_path, 'w') as outfile:
        header = infile.readline()  # Skip header
        for line in infile:
            parts = line.strip().split('|')
            if len(parts) >= 3:
                sql = parts[2]  # SQL is the third column
                sql = convert_query_for_factorjoin(sql)
                outfile.write(sql + '\n')

    logger.info(f"Created new SQL file at {output_sql_path}")
    return True


def convert_sql_file_for_factorjoin(input_sql_path, output_sql_path):
    """
    Convert a SQL file (one query per line) to FactorJoin-compatible format.
    Creates a NEW file - does not modify the original.
    """
    if os.path.exists(output_sql_path):
        logger.info(f"Converted SQL file already exists at {output_sql_path}")
        return True

    if not os.path.exists(input_sql_path):
        logger.error(f"SQL file not found at {input_sql_path}")
        return False

    logger.info(f"Converting {input_sql_path} to {output_sql_path}")
    with open(input_sql_path, 'r') as infile, open(output_sql_path, 'w') as outfile:
        for line in infile:
            sql = line.strip()
            if sql:
                sql = convert_query_for_factorjoin(sql)
                outfile.write(sql + '\n')

    logger.info(f"Created new SQL file at {output_sql_path}")
    return True

def run_and_measure(execution_part: str, command: List[str]) -> bool:
    """
    Execute a command and measure its execution time.
    
    Args:
        execution_part: Name/description of the execution part
        command: Command to execute as list of strings
        
    Returns:
        bool: True if execution was successful, False otherwise
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
        
        return True
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing {execution_part}: {e}")
        logger.error(f"Error output:\n{e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during {execution_part}: {e}")
        return False

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run FactorJoin experiments")
    parser.add_argument("--stats-only", action="store_true",
                        help="Run only STATS experiments (no PostgreSQL required)")
    parser.add_argument("--imdb-only", action="store_true",
                        help="Run only IMDB experiments (requires PostgreSQL)")
    parser.add_argument("--skip-preprocess", action="store_true",
                        help="Skip data preprocessing (use if data already preprocessed)")
    args = parser.parse_args()

    # Data path for STATS (use local copy that gets preprocessed)
    stats_data_path = os.path.join(STATS_LOCAL_DIR, "{}.csv")

    # Query file paths (from project's workloads directory)
    WORKLOADS_DIR = os.path.join(PROJECT_ROOT, "benchmarks", "workloads")
    stats_queries_file = os.path.join(WORKLOADS_DIR, "stats", "statsQueries.sql")
    stats_subqueries_csv = os.path.join(WORKLOADS_DIR, "stats", "stats_subqueries.csv")
    # Output paths for converted queries (in factorjoin checkpoints dir)
    stats_subqueries_sql = os.path.join(SCRIPT_DIR, "checkpoints", "stats_subqueries.sql")
    stats_queries_converted = os.path.join(SCRIPT_DIR, "checkpoints", "statsQueries_converted.sql")

    # Define STATS commands (no PostgreSQL required)
    stats_commands = {
        "preprocess_stats": [
            PYTHON_EXEC, "run_experiment.py", "--dataset", "stats",
            "--preprocess_data", "--data_folder", STATS_LOCAL_DIR + "/"
        ],
        "train_stats_model": [
            PYTHON_EXEC, "run_experiment.py", "--dataset", "stats",
            "--generate_models", "--data_path", stats_data_path,
            "--model_path", "checkpoints/",
            "--n_dim_dist", "2",
            "--n_bins", "200",
            "--bucket_method", "greedy"
        ],
        "run_subqueries_stats": [
            PYTHON_EXEC, "run_experiment.py", "--dataset", "stats",
            "--evaluate", "--model_path", "checkpoints/model_stats_greedy_200.pkl",
            "--query_file_location", stats_subqueries_sql,
            "--save_folder", "checkpoints/"
        ],
        "run_full_queries_stats": [
            PYTHON_EXEC, "run_experiment.py", "--dataset", "stats",
            "--evaluate", "--model_path", "checkpoints/model_stats_greedy_200.pkl",
            "--query_file_location", stats_queries_converted,
            "--save_folder", "checkpoints/"
        ],
    }

    # Define IMDB commands (PostgreSQL required)
    imdb_commands = {
        "train_imdb_model": [
            PYTHON_EXEC, "run_experiment.py", "--dataset", "imdb",
            "--generate_models",
            "--data_path", "End-to-End-CardEst-Benchmark/datasets/imdb/{}.csv",
            "--model_path", "checkpoints/",
            "--n_dim_dist", "1",
            "--bucket_method", "fixed_start_key",
            "--db_conn_kwargs", f"dbname={DBNAME} user={DB_USER} password={DB_PASSWORD} host={DB_HOST} port={DB_PORT}"
        ],
        "run_queries_joblightrange": [
            PYTHON_EXEC, "run_experiment.py", "--dataset", "imdb",
            "--evaluate",
            "--model_path", "checkpoints/model_imdb_default.pkl",
            "--derived_query_file", "imdb/dict_sql_imdb_joblightranges.pkl",
            "--save_folder", "checkpoints/",
            "--db_conn_kwargs", f"dbname={DBNAME} user={DB_USER} password={DB_PASSWORD} host={DB_HOST} port={DB_PORT}"
        ],
        "run_queries_jobjoin": [
            PYTHON_EXEC, "run_experiment.py", "--dataset", "imdb",
            "--evaluate",
            "--model_path", "checkpoints/model_imdb_default.pkl",
            "--derived_query_file", "imdb/dict_sql_imdb_jobjoin.pkl",
            "--save_folder", "checkpoints/",
            "--db_conn_kwargs", f"dbname={DBNAME} user={DB_USER} password={DB_PASSWORD} host={DB_HOST} port={DB_PORT}"
        ],
        "run_queries_joblight": [
            PYTHON_EXEC, "run_experiment.py", "--dataset", "imdb",
            "--evaluate",
            "--model_path", "checkpoints/model_imdb_default.pkl",
            "--derived_query_file", "imdb/dict_sql_imdb.pkl",
            "--save_folder", "checkpoints/",
            "--db_conn_kwargs", f"dbname={DBNAME} user={DB_USER} password={DB_PASSWORD} host={DB_HOST} port={DB_PORT}"
        ],
    }

    # Select which commands to run based on arguments
    commands = {}
    if args.imdb_only:
        commands = imdb_commands
    elif args.stats_only:
        commands = stats_commands
    else:
        # Run both (default behavior)
        commands = {**stats_commands, **imdb_commands}
        

    # Set up data if running STATS experiments
    if not args.imdb_only:
        logger.info("=" * 80)
        logger.info("Setting up STATS data...")
        if not setup_stats_data():
            logger.error("Failed to set up STATS data. Exiting.")
            exit(1)
        logger.info("=" * 80 + "\n")

        # Convert subqueries CSV to SQL format for FactorJoin
        logger.info("=" * 80)
        logger.info("Converting subqueries CSV to SQL format...")
        if not convert_subqueries_csv_to_sql(stats_subqueries_csv, stats_subqueries_sql):
            logger.error("Failed to convert subqueries. Exiting.")
            exit(1)
        logger.info("=" * 80 + "\n")

        # Convert full queries SQL file for FactorJoin
        logger.info("=" * 80)
        logger.info("Converting full queries SQL file...")
        if not convert_sql_file_for_factorjoin(stats_queries_file, stats_queries_converted):
            logger.error("Failed to convert full queries. Exiting.")
            exit(1)
        logger.info("=" * 80 + "\n")

    # Execute each command in sequence
    for part, command in commands.items():
        # Skip preprocessing if requested
        if args.skip_preprocess and part == "preprocess_stats":
            logger.info("=" * 80)
            logger.info(f"Skipping {part} (--skip-preprocess flag set)")
            logger.info("=" * 80 + "\n")
            continue

        logger.info("=" * 80)
        logger.info(f"Starting new command: {part}")
        success = run_and_measure(part, command)
        logger.info("=" * 80 + "\n")
        
        # Only attempt to rename files if the command succeeded
        if success:
            source_file = 'checkpoints/imdb_JOB_sub_queries_model_imdb_default.txt'
            
            if part == "run_subqueries_stats":
                timing_file = 'checkpoints/stats_timing.txt'
            
            if part == "run_queries_joblightrange":
                target_file = 'checkpoints/imdb_JOB_sub_queries_model_imdb_default_joblightrange.txt'
                target_file_plots = '../../../results/accuracy_acyclic/jobrange/factorjoin_jobrange_full_estimations.csv'
                timing_file = 'checkpoints/imdb_JOB_sub_queries_model_imdb_default_joblightrange_timing.txt'
            elif part == "run_queries_jobjoin":
                target_file = 'checkpoints/imdb_JOB_sub_queries_model_imdb_default_jobjoin.txt'
                target_file_plots = '../../../results/accuracy_acyclic/jobjoin/factorjoin_jobjoin_full_estimations.csv'
                timing_file = 'checkpoints/imdb_JOB_sub_queries_model_imdb_default_jobjoin_timing.txt'
            elif part == "run_queries_joblight":
                target_file = 'checkpoints/imdb_JOB_sub_queries_model_imdb_default_joblight.txt'
                target_file_plots = '../../../results/accuracy_acyclic/joblight/factorjoin_joblight_full_estimations.csv'
                timing_file = 'checkpoints/imdb_JOB_sub_queries_model_imdb_default_joblight_timing.txt'
            else:
                target_file = None
                timing_file = None
            
            if target_file:
                try:
                    if os.path.exists("timing.txt"):
                        os.rename("timing.txt", timing_file)
                    if os.path.exists(source_file):
                        shutil.copy(source_file, target_file_plots)
                        
                        try:
                            with open(target_file, 'r') as f:
                                lines = f.readlines()

                            # Modify the first row
                            lines[0] = "QueryID,factorjoin_Estimate,runtime\n"

                            # Write back the modified content
                            with open(target_file, 'w') as f:
                                f.writelines(lines)
                        except:
                            print("Failed to rename column headers.")
                        
                        os.rename(source_file, target_file)
                        logger.info(f"Renamed {source_file} to {target_file}")
                    else:
                        logger.warning(f"Source file {source_file} does not exist, skipping rename")
                except Exception as e:
                    logger.error(f"Error renaming file: {e}")
        else:
            logger.warning(f"Skipping file rename for {part} due to execution failure")            
            
    
    # run evaluate_cardinalities 6 times
    # for i in range(6):
    #    run_and_measure("generate_hdf", commands["generate_hdf"])
