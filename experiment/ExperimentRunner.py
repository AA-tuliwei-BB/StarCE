#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StarCE experiment test script
Used for running and testing various performance metrics of StarCE
"""

import os
import json
import re
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class StarCEConfig:
    """StarCE configuration struct, for easy management and JSON serialization"""
    EnableStarCE: int = 1
    UseAssignedAdjustRate: int = 1
    UseSubqueryCard: int = 0
    UseSingleTableCard: int = 1
    RecordingSubquery: int = 0
    SubqueryOutputGroupByMain: int = 0
    RecordingSingleQuery: int = 0
    RefreshStatistics: int = 0
    EnableStarSplit: int = 0
    MaxStarSize: int = 3
    PredMethod: int = 1
    IsCollectingRelErr: int = 0
    CollectParallel: int = 8
    # CompressPrecision: float = 2.0
    CompressPrecision: float = 1.5
    SCHEMA_PATH: str = "xxx_schema.json" # change: db
    SUBQUERY_PATH: str = "dummy_query.sql"  # change: workload
    SUBQUERY_RESULT_PATH: str = "dummy_result.txt" # change: workload
    SINGLE_QUERY_PATH: str = "dummy_query.sql" # change: workload
    SINGLE_QUERY_RESULT_PATH: str = "dummy_result.txt" #change: workload
    DB_PATH: str = "xxx.db" # change: db
    STATS_PATH: str = "../checkpoint/StarCE/statistics.json" # change: db
    SQL_PATH: str = "dummy_query.sql" # change: workload
    REAL_CARD_PATH: str = "dummy_result.txt"
    REL_ERR_PATH: str = "dummy_result.txt"
    STATS_SIZE_PATH: str = "statistics_size.json"
    RecordEstimateTime: int = 0
    SUBQUERY_TIME_PATH: str = "subquery_time.txt"
    ADJUST_RATE: float = 1
    PREDICATE_ADJUST_RATE: float = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    def to_json_file(self, filepath: str) -> None:
        """Save as JSON file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=4, ensure_ascii=False)

    @classmethod
    def from_json_file(cls, filepath: str) -> 'StarCEConfig':
        """Load from JSON file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)

    def copy(self) -> 'StarCEConfig':
        """Create a copy of the configuration"""
        return StarCEConfig(**self.to_dict())

    def update(self, **kwargs) -> 'StarCEConfig':
        """Update config items, return new config object (does not modify original)"""
        new_config = self.copy()
        for key, value in kwargs.items():
            if hasattr(new_config, key):
                setattr(new_config, key, value)
            else:
                raise ValueError(f"Unknown config item: {key}")
        return new_config


class ExperimentRunner(ABC):
    """Experiment runner base class"""

    def __init__(self, project_root: Optional[str] = None):
        """Initialize the experiment runner"""
        # Get script directory
        self.script_dir = Path(__file__).parent.absolute()
        
        # Project root directory (defaults to parent of script_dir)
        if project_root:
            self.project_root = Path(project_root).absolute()
        else:
            self.project_root = self.script_dir.parent
        
        # running_space directory
        self.running_space = self.script_dir / "running_space"
        self.running_space.mkdir(exist_ok=True)
        
        # checkpoint directory (StarCE statistics storage location)
        self.checkpoint_dir = self.script_dir / "checkpoint"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Absolute path to Benchmark directory
        self.benchmark_dir = self.project_root / "Benchmark"
        
        # Log and result files
        self.log_file = self.running_space / "log.txt"
        self.result_file = self.running_space / "result.txt"
        
        # starce executable path
        self.starce_exec = self.running_space / "starce"
        
        # Configuration object
        self.config: Optional[StarCEConfig] = None

    def log(self, message: str, to_console: bool = True):
        """Log a message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message)
        
        if to_console:
            print(log_message.strip())

    def result(self, message: str):
        """Record a result"""
        with open(self.result_file, 'a', encoding='utf-8') as f:
            f.write(f"{message}\n")
        print(message)

    def save_config(self, config: StarCEConfig):
        """
        Save config to running_space/config.json (for starce executable use)
        
        Args:
            config: Configuration object to save
        """
        config_file = self.running_space / "config.json"
        config.to_json_file(str(config_file))
        self.log(f"Config file saved to: {config_file}")
        self.config = config

    def _filter_benchmark_specs(self, benchmark_specs, benchmarks=None):
        """
        Filter benchmark_specs by the given benchmark list.

        Args:
            benchmark_specs: [(benchmark, config_getter, queries_file), ...]
            benchmarks: List of benchmarks to keep; None means no filtering
        """
        if benchmarks is None:
            return benchmark_specs

        requested = list(benchmarks)
        available = {benchmark for benchmark, _, _ in benchmark_specs}
        invalid = [benchmark for benchmark in requested if benchmark not in available]
        if invalid:
            raise ValueError(f"Unsupported benchmark: {invalid}")

        requested_set = set(requested)
        return [
            spec
            for spec in benchmark_specs
            if spec[0] in requested_set
        ]

    def get_stats_db_config(self) -> StarCEConfig:
        """
        Get STATS database configuration
        
        Returns:
            STATS configuration object
        """
        config = StarCEConfig()
        config.DB_PATH = str(self.benchmark_dir / "duckdb" / "stats.db")
        config.SCHEMA_PATH = str(self.benchmark_dir / "STATS" / "schema_stats.json")
        config.STATS_PATH = str(self.checkpoint_dir / "StarCE" / "statistics_stats.json")
        return config

    def get_imdb_db_config(self) -> StarCEConfig:
        """
        Get IMDB database configuration

        Returns:
            IMDB configuration object
        """
        config = StarCEConfig()
        config.DB_PATH = str(self.benchmark_dir / "duckdb" / "imdb.db")
        config.SCHEMA_PATH = str(self.benchmark_dir / "IMDB" / "schema_imdb.json")
        config.STATS_PATH = str(self.checkpoint_dir / "StarCE" / "statistics_imdb.json")
        return config

    def get_imdb_light_db_config(self) -> StarCEConfig:
        """
        Get IMDB_LIGHT database configuration

        Returns:
            IMDB_LIGHT configuration object
        """
        config = StarCEConfig()
        config.DB_PATH = str(self.benchmark_dir / "duckdb" / "imdb.db")
        config.SCHEMA_PATH = str(self.benchmark_dir / "workloads" / "JOBLight" / "schema_joblight.json")
        config.STATS_PATH = str(self.checkpoint_dir / "StarCE" / "statistics_joblight.json")
        return config

    def get_imdb_light_ranges_db_config(self) -> StarCEConfig:
        """
        Get IMDB_LIGHT_RANGES database configuration

        Returns:
            IMDB_LIGHT_RANGES configuration object
        """
        config = StarCEConfig()
        config.DB_PATH = str(self.benchmark_dir / "duckdb" / "imdb.db")
        config.SCHEMA_PATH = str(self.benchmark_dir / "workloads" / "JOBLightRanges" / "schema_joblr.json")
        config.STATS_PATH = str(self.checkpoint_dir / "StarCE" / "statistics_joblr.json")
        return config

    def get_stats_config(self) -> StarCEConfig:
        """
        Get stats-ceb benchmark configuration
        Returns: based on STATS configuration modified for stats-ceb benchmark configuration object
        """
        config = self.get_stats_db_config()
        config.SQL_PATH = str(self.benchmark_dir / "workloads" / "STATS-CEB" / "queries.sql")
        config.SUBQUERY_PATH = str(self.benchmark_dir / "workloads" / "STATS-CEB" / "subquery" / "subquery.sql")
        # config.SUBQUERY_RESULT_PATH = str(self.running_space / "dummy_result.txt")
        config.SINGLE_QUERY_PATH = str(self.benchmark_dir / "workloads" / "STATS-CEB" / "single_query" / "single_query.sql")
        config.SINGLE_QUERY_RESULT_PATH = str(self.benchmark_dir / "workloads" / "STATS-CEB" / "single_query" / "pg_est.txt")
        return config

    def get_jobm_config(self) -> StarCEConfig:
        """
        Get jobm benchmark configuration
        Returns: based on IMDB configuration modified for jobm benchmark configuration object
        """
        config = self.get_imdb_db_config()
        config.SQL_PATH = str(self.benchmark_dir / "workloads" / "JOBM" / "queries.sql")
        config.SUBQUERY_PATH = str(self.benchmark_dir / "workloads" / "JOBM" / "subquery" / "subquery.sql")
        # config.SUBQUERY_RESULT_PATH = str(self.running_space / "dummy_result.txt")
        config.SINGLE_QUERY_PATH = str(self.benchmark_dir / "workloads" / "JOBM" / "single_query" / "single_query.sql")
        config.SINGLE_QUERY_RESULT_PATH = str(self.benchmark_dir / "workloads" / "JOBM" / "single_query" / "pg_est.txt")
        return config

    def get_jobjoin_config(self) -> StarCEConfig:
        """
        Get jobjoin benchmark configuration

        Returns: based on IMDB configuration modified for jobjoin benchmark configuration object
        """
        config = self.get_imdb_db_config()
        config.SCHEMA_PATH = str(self.benchmark_dir / "workloads" / "JobJoin" / "schema_jobjoin.json")
        config.STATS_PATH = str(self.checkpoint_dir / "StarCE" / "statistics_jobjoin.json")
        config.SQL_PATH = str(self.benchmark_dir / "workloads" / "JobJoin" / "queries.sql")
        config.SUBQUERY_PATH = str(self.benchmark_dir / "workloads" / "JobJoin" / "subquery" / "subquery.sql")
        config.SINGLE_QUERY_PATH = str(self.benchmark_dir / "workloads" / "JobJoin" / "single_query" / "single_query.sql")
        config.SINGLE_QUERY_RESULT_PATH = str(self.benchmark_dir / "workloads" / "JobJoin" / "single_query" / "pg_est.txt")
        return config

    def get_statsjoin_config(self) -> StarCEConfig:
        """
        Get statsjoin benchmark configuration

        Returns: based on STATS configuration modified for statsjoin benchmark configuration object
        """
        config = self.get_stats_db_config()
        config.SCHEMA_PATH = str(self.benchmark_dir / "workloads" / "StatsJoin" / "schema_statsjoin.json")
        config.STATS_PATH = str(self.checkpoint_dir / "StarCE" / "statistics_stats.json")
        config.SQL_PATH = str(self.benchmark_dir / "workloads" / "StatsJoin" / "queries.sql")
        config.SUBQUERY_PATH = str(self.benchmark_dir / "workloads" / "StatsJoin" / "subquery" / "subquery.sql")
        config.SINGLE_QUERY_PATH = str(self.benchmark_dir / "workloads" / "StatsJoin" / "single_query" / "single_query.sql")
        config.SINGLE_QUERY_RESULT_PATH = str(self.benchmark_dir / "workloads" / "StatsJoin" / "single_query" / "real.txt")
        return config

    def get_joblight_config(self) -> StarCEConfig:
        """
        Get joblight benchmark configuration
        Returns: based on IMDB configuration modified for joblight benchmark configuration object
        """
        config = self.get_imdb_light_db_config()
        config.SQL_PATH = str(self.benchmark_dir / "workloads" / "JOBLight" / "queries.sql")
        config.SUBQUERY_PATH = str(self.benchmark_dir / "workloads" / "JOBLight" / "subquery" / "subquery.sql")
        # config.SUBQUERY_RESULT_PATH = str(self.running_space / "dummy_result.txt")
        config.SINGLE_QUERY_PATH = str(self.benchmark_dir / "workloads" / "JOBLight" / "single_query" / "single_query.sql")
        config.SINGLE_QUERY_RESULT_PATH = str(self.benchmark_dir / "workloads" / "JOBLight" / "single_query" / "pg_est.txt")
        return config

    def get_joblight_ranges_config(self) -> StarCEConfig:
        config = self.get_imdb_light_ranges_db_config()
        config.SQL_PATH = str(self.benchmark_dir / "workloads" / "JOBLightRanges" / "queries.sql")
        config.SUBQUERY_PATH = str(self.benchmark_dir / "workloads" / "JOBLightRanges" / "subquery" / "subquery.sql")
        # config.SUBQUERY_RESULT_PATH = str(self.running_space / "dummy_result.txt")
        config.SINGLE_QUERY_PATH = str(self.benchmark_dir / "workloads" / "JOBLightRanges" / "single_query" / "single_query.sql")
        config.SINGLE_QUERY_RESULT_PATH = str(self.benchmark_dir / "workloads" / "JOBLightRanges" / "single_query" / "pg_est.txt")
        return config

    def record_paths(self):
        """Log important path information"""
        self.result("=" * 80)
        self.result(f"Experiment start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.result(f"Project root directory: {self.project_root}")
        self.result(f"Benchmark directory: {self.benchmark_dir}")
        self.result(f"Running space directory: {self.running_space}")
        self.result(f"starce executable: {self.starce_exec}")
        self.result("=" * 80)

    def run_starce(self, suppress_output: bool = False) -> Tuple[bool, float]:
        """
        Run starce and return (success flag, run time)
        
        Args:
            suppress_output: Whether to suppress logging of stdout/stderr to console (default False)
        """
        # Switch to running_space directory and run
        start_time = time.time()
        try:
            result = subprocess.run(
                [str(self.starce_exec)],
                cwd=str(self.running_space),
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            elapsed_time = time.time() - start_time
            
            if result.returncode == 0:
                self.log(f"starce ran successfully, elapsed: {elapsed_time:.2f}  seconds")
                # Log output (if suppressed, do not show on console but still write to log file)
                if result.stdout:
                    self.log(f"Standard output:\n{result.stdout}", to_console=not suppress_output)
                if result.stderr:
                    self.log(f"Standard error:\n{result.stderr}", to_console=not suppress_output)
                return True, elapsed_time
            else:
                self.log(f"starce run failed, return code: {result.returncode}", to_console=True)
                if result.stderr:
                    self.log(f"Error message:\n{result.stderr}", to_console=True)
                return False, elapsed_time
        except subprocess.TimeoutExpired:
            elapsed_time = time.time() - start_time
            self.log(f"starce run timed out (>{elapsed_time:.2f}  seconds)", to_console=True)
            return False, elapsed_time
        except Exception as e:
            elapsed_time = time.time() - start_time
            self.log(f"Exception occurred while running starce: {e}", to_console=True)
            return False, elapsed_time

    def run_starce_raw(self) -> Tuple[int, str, str, float]:
        """
        Run starce and return raw output

        Returns:
            (returncode, stdout, stderr, elapsed_time)
        """
        start_time = time.time()
        result = subprocess.run(
            [str(self.starce_exec)],
            cwd=str(self.running_space),
            capture_output=True,
            text=True,
            timeout=3600
        )
        elapsed_time = time.time() - start_time
        return result.returncode, result.stdout, result.stderr, elapsed_time

    def _prepare_input_sql_with_explain(self, queries_file: Path, output_file: Path) -> None:
        """
        Copy queries file to output_file, and add EXPLAIN before each SELECT statement
        
        Args:
            queries_file: Source queries.sql file path
            output_file: Output file path (running_space/input.sql)
        """
        if not queries_file.exists():
            raise FileNotFoundError(f"Cannot find queries file: {queries_file}")
        
        with open(queries_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Add EXPLAIN before each SELECT (case insensitive)
        # Use regex to match SELECT statements (case insensitive)
        # Match SELECT at line start (may have leading spaces)
        pattern = r'^(\s*)(select\s+)'
        replacement = r'\1EXPLAIN \2'
        new_content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.MULTILINE)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        self.log(f"Copied queries file to {output_file}  and added EXPLAIN")

    def _prepare_input_sql_without_explain(self, queries_file: Path, output_file: Path) -> None:
        """
        Copy queries file to output_file, without adding EXPLAIN (plain queries)
        
        Args:
            queries_file: Source queries.sql file path
            output_file: Output file path (running_space/input.sql)
        """
        if not queries_file.exists():
            raise FileNotFoundError(f"Cannot find queries file: {queries_file}")
        
        shutil.copy2(queries_file, output_file)
        self.log(f"Copied queries file to {output_file} (plain queries, no EXPLAIN")

    def inner_test_planning_time(self, config: StarCEConfig, db_name: str, queries_file: Path, num_runs: int = 3) -> Optional[float]:
        """
        Test planning time for a specific database
        
        Args:
            config: Test configuration
            db_name: Database name (for display, e.g. "STATS" or "JOBM")
            queries_file: queries.sql file path
            num_runs: Number of runs
        
        Returns:
            Optional[float]: Final planning time (seconds), None on failure
        """
        self.result(f"\n--- Test planning time ({db_name}) ---")
        self.log(f"Starting planning time test ({db_name}), run(s) {num_runs}")
        
        input_sql = self.running_space / "input.sql"
        
        # 1. Copy queries to input.sql and add EXPLAIN
        try:
            self._prepare_input_sql_with_explain(queries_file, input_sql)
        except Exception as e:
            self.result(f"Failed to prepare input.sql ({db_name}): {e}")
            return None
        
        # Test using input.sql
        config.SQL_PATH = "input.sql"
        self.save_config(config)
        
        times_input = []
        for i in range(num_runs):
            self.log(f"Using input.sql: run  {i+1}/{num_runs} run(s)...")
            success, elapsed = self.run_starce(suppress_output=True)
            if success:
                times_input.append(elapsed)
            else:
                self.log(f" {i+1} run(s) failed, skipped", to_console=True)
        
        # 2. Test using dummy_query.sql
        config.SQL_PATH = "dummy_query.sql"
        self.save_config(config)
        
        times_dummy = []
        for i in range(num_runs):
            self.log(f"using dummy_query.sql:  {i+1}/{num_runs} run(s)...")
            success, elapsed = self.run_starce(suppress_output=True)
            if success:
                times_dummy.append(elapsed)
            else:
                self.log(f" {i+1} run(s) failed, skipped", to_console=True)

        # Output results
        avg_time_input = None
        if times_input:
            avg_time_input = sum(times_input) / len(times_input)
            self.result(f"Planning time test results ({db_name}) - using input.sql:")
            self.result(f"  Successful runs: {len(times_input)}/{num_runs}")
            self.result(f"  Average planning time: {avg_time_input:.2f}  seconds")
            self.result(f"  Fastest: {min(times_input):.2f}  seconds")
            self.result(f"  Slowest: {max(times_input):.2f}  seconds")
        else:
            self.result(f"Planning time test failed ({db_name}) - using input.sql: all run(s) failed")

        avg_time_dummy = None
        if times_dummy:
            avg_time_dummy = sum(times_dummy) / len(times_dummy)
            self.result(f"Planning time test results ({db_name}) - using dummy_query.sql:")
            self.result(f"  Successful runs: {len(times_dummy)}/{num_runs}")
            self.result(f"  Average planning time: {avg_time_dummy:.2f}  seconds")
            self.result(f"  Fastest: {min(times_dummy):.2f}  seconds")
            self.result(f"  Slowest: {max(times_dummy):.2f}  seconds")
        else:
            self.result(f"Planning time test failed ({db_name}) - using dummy_query.sql: all run(s) failed")

        # Calculate final planning time: explain time - dummy time
        if avg_time_input is not None and avg_time_dummy is not None:
            final_planning_time = avg_time_input - avg_time_dummy
            self.result(f"Final planning time ({db_name}): {final_planning_time:.2f} seconds (explain time - dummy time)")
            return final_planning_time
        else:
            self.result(f"Cannot calculate final planning time ({db_name}): insufficient explain time or dummy time data")
            return None

    def inner_test_running_time(self, config: StarCEConfig, db_name: str, queries_file: Path, num_runs: int = 3) -> Optional[float]:
        """
        Test running time for a specific database
        
        Args:
            config: Test configuration
            db_name: Database name (for display, e.g. "STATS" or "JOBM")
            queries_file: queries.sql file path
            num_runs: Number of runs
        
        Returns:
            Optional[float]: Final running time (seconds), None on failure
        """
        self.result(f"\n--- Test running time ({db_name}) ---")
        self.log(f"Test running time ({db_name}), run(s) {num_runs}")
        
        input_sql = self.running_space / "input.sql"
        explain_sql = self.running_space / "explain.sql"
        
        # 1. Prepare plain input.sql (without EXPLAIN)
        try:
            self._prepare_input_sql_without_explain(queries_file, input_sql)
        except Exception as e:
            self.result(f"Failed to prepare input.sql ({db_name}): {e}")
            return None
        
        # Test using input.sql (plain queries)
        config.SQL_PATH = "input.sql"
        self.save_config(config)
        
        times_input = []
        for i in range(num_runs):
            self.log(f"using input.sql (plain queries):  {i+1}/{num_runs} run(s)...")
            success, elapsed = self.run_starce(suppress_output=True)
            if success:
                times_input.append(elapsed)
            else:
                self.log(f" {i+1} run(s) failed, skipped", to_console=True)
        
        # 2. Prepare explain.sql (with EXPLAIN)
        try:
            self._prepare_input_sql_with_explain(queries_file, explain_sql)
        except Exception as e:
            self.result(f"Failed to prepare explain.sql ({db_name}): {e}")
            return None
        
        # Test using explain.sql
        config.SQL_PATH = "explain.sql"
        self.save_config(config)
        
        times_explain = []
        for i in range(num_runs):
            self.log(f"using explain.sql (EXPLAIN queries):  {i+1}/{num_runs} run(s)...")
            success, elapsed = self.run_starce(suppress_output=True)
            if success:
                times_explain.append(elapsed)
            else:
                self.log(f" {i+1} run(s) failed, skipped", to_console=True)
        
        # Output results
        avg_time_input = None
        if times_input:
            avg_time_input = sum(times_input) / len(times_input)
            self.result(f"time test results ({db_name}) - using input.sql (plain queries):")
            self.result(f"  Successful runs: {len(times_input)}/{num_runs}")
            self.result(f"  Average running time: {avg_time_input:.2f}  seconds")
            self.result(f"  Fastest: {min(times_input):.2f}  seconds")
            self.result(f"  Slowest: {max(times_input):.2f}  seconds")
        else:
            self.result(f"running time test failed ({db_name}) - using input.sql: all run(s) failed")
        
        avg_time_explain = None
        if times_explain:
            avg_time_explain = sum(times_explain) / len(times_explain)
            self.result(f"time test results ({db_name}) - using explain.sql (EXPLAIN queries):")
            self.result(f"  Successful runs: {len(times_explain)}/{num_runs}")
            self.result(f"  Average running time: {avg_time_explain:.2f}  seconds")
            self.result(f"  Fastest: {min(times_explain):.2f}  seconds")
            self.result(f"  Slowest: {max(times_explain):.2f}  seconds")
        else:
            self.result(f"running time test failed ({db_name}) - Using explain.sql: all run(s) failed")
        
        # Calculate final running time: input.sql time - explain.sql time
        if avg_time_input is not None and avg_time_explain is not None:
            final_running_time = avg_time_input - avg_time_explain
            self.result(f"Final running time ({db_name}): {final_running_time:.2f} seconds (input.sql time - explain.sql time)")
            return final_running_time
        else:
            self.result(f"Cannot calculate final running time ({db_name}): insufficient input.sql time or explain.sql time data")
            return None

    def inner_test_per_query_running_time(
        self,
        config: StarCEConfig,
        queries_file: Path,
        num_runs: int = 1,
        injected_card_path: Optional[str] = None,
    ) -> list:
        """
        Test execution time of main queries one by one

        Args:
            config: Test configuration
            queries_file: queries.sql file path (one main query per line)
            num_runs: Number of runs per query, averaged
            injected_card_path: Injection-based methods pass full subquery cardinality file path;
                                 None means no injection (DuckDB / StarCE native mode)

        Returns:
            list[Optional[float]]，length = number of queries, each item is avg execution time (seconds), None on failure
        """
        if not queries_file.exists():
            raise FileNotFoundError(f"Cannot find queries file: {queries_file}")

        with open(queries_file, 'r', encoding='utf-8') as f:
            queries = [line.rstrip('\n') for line in f if line.strip() and not line.strip().startswith('--')]

        tmp_sql = self.running_space / "per_query_tmp.sql"
        results = []

        if injected_card_path is not None:
            injected_card_path_abs = str(Path(injected_card_path).absolute())

        for i, sql in enumerate(queries):
            with open(tmp_sql, 'w', encoding='utf-8') as f:
                f.write(sql + '\n')

            run_config = config.copy()
            run_config.SQL_PATH = "per_query_tmp.sql"
            if injected_card_path is not None:
                run_config.UseSubqueryCard = 1
                run_config.SUBQUERY_RESULT_PATH = injected_card_path_abs
            self.save_config(run_config)

            times = []
            for _ in range(num_runs):
                success, elapsed = self.run_starce(suppress_output=True)
                if success:
                    times.append(elapsed)

            avg = sum(times) / len(times) if times else None
            results.append(avg)

            if (i + 1) % 10 == 0 or (i + 1) == len(queries):
                self.log(f"per-query progress: {i + 1}/{len(queries)}")

        return results

    @abstractmethod
    def test_build_time(self, num_runs: int = 3) -> None:
        """
        Test build time (abstract method, subclass must implement)
        Results written directly to result file, no return value
        
        Args:
            num_runs: Number of runs
        """
        pass

    @abstractmethod
    def test_planning_time(self, num_runs: int = 3) -> None:
        """
        Test planning time (abstract method, subclass must implement)
        Results written directly to result file, no return value
        
        Args:
            num_runs: Number of runs
        """
        pass

    @abstractmethod
    def test_running_time(self, num_runs: int = 3) -> None:
        """
        Test running time (abstract method, subclass must implement)
        Results written directly to result file, no return value
        
        Args:
            num_runs: Number of runs
        """
        pass

    def run(self):
        """all tests"""
        self.log("=" * 80)
        self.log("Experiment tests start")
        self.log("=" * 80)
        
        # 1. Log path info
        self.record_paths()
        
        # 2. Run each sub-experiment (implemented by subclass)
        self.test_build_time(num_runs=3)
        self.test_planning_time(num_runs=3)
        self.test_running_time(num_runs=3)
        
        self.log("=" * 80)
        self.log("Experiment tests completed")
        self.log("=" * 80)


def setup_starce_executable(project_root: Path, running_space: Path):
    """
    Copy starce executable to running_space
    
    Args:
            project_root: Project root directory
                    running_space: Running space directory
    
    Report error and exit program on failure
    """
    import sys
    
    starce_source = project_root / "build" / "starce"
    starce_exec = running_space / "starce"
    
    if not starce_source.exists():
        print(f"Error: starce executable not found: {starce_source}", file=sys.stderr)
        sys.exit(1)
    
    try:
        shutil.copy2(starce_source, starce_exec)
        os.chmod(starce_exec, 0o755)
        print(f"Successfully copied starce executable to: {starce_exec}")
    except Exception as e:
        print(f"Error: failed to copy starce executable: {e}", file=sys.stderr)
        sys.exit(1)


class StarCETestRunner(ExperimentRunner):
    """StarCE test runner"""

    def __init__(self, project_root: Optional[str] = None):
        """Initialize StarCE test runner"""
        super().__init__(project_root)
        # Ensure StarCE subdirectory exists
        starce_subdir = self.checkpoint_dir / "StarCE"
        starce_subdir.mkdir(parents=True, exist_ok=True)

    def inner_test_build_time(self, config: StarCEConfig, db_name: str, num_runs: int = 3) -> Tuple[float, int]:
        """
        Internal build time test method (shared logic)
        Results written directly to result file, returns average build time and statistics file size
        
        Args:
            config: Test configuration
            db_name: Database name (for log display, e.g. "STATS" or "IMDB")
            num_runs: Number of runs
        
        Returns:
            tuple: (Average build time, statistics file size)
        """
        self.result(f"\n--- Test build time - StarCE - ({db_name}) ---")
        self.log(f"Starting build time test - StarCE - ({db_name}), run(s) {num_runs}")
        
        # Save config to running_space/config.json
        self.save_config(config)
        
        times = []
        for i in range(num_runs):
            self.log(f" {i+1}/{num_runs} run(s)...")
            success, elapsed = self.run_starce()
            if success:
                times.append(elapsed)
            else:
                self.log(f" {i+1} run(s) failed, skipped", to_console=True)
        
        if not times:
            msg = f"Build time test failed ({db_name}): all run(s) failed"
            self.result(msg)
            raise RuntimeError(msg)
        
        avg_time = sum(times) / len(times)
        self.result(f"Build time test results ({db_name}):")
        self.result(f"  Successful runs: {len(times)}/{num_runs}")
        self.result(f"  Average build time: {avg_time:.2f}  seconds")
        self.result(f"  Fastest: {min(times):.2f}  seconds")
        self.result(f"  Slowest: {max(times):.2f}  seconds")
        
        # Get statistics raw data size (data_only, aligned with LpBound baseline)
        stats_size_path = self.running_space / config.STATS_SIZE_PATH
        if not stats_size_path.exists():
            raise FileNotFoundError(f"Statistics size file not generated: {stats_size_path}")
        with open(stats_size_path, 'r') as f:
            size_report = json.load(f)
        size = size_report["data_only"]
        self.result(f"  Statistics size (data_only): {size} bytes ({size/1024/1024:.2f} MB)")
        
        return avg_time, size

    def test_build_time(self, num_runs: int = 3) -> Dict[str, Tuple[float, int]]:
        """
        Test build time (multiple runs averaged
        Test both STATS and IMDB databases
        Results written directly to result file, returns build time and file size
        
        Returns:
            dict: {'STATS': (time, size), 'IMDB': (time, size)}
        """
        self.result("\n=== Test build time - StarCE ===")
        
        # Test STATS database
        stats_config = self.get_stats_db_config()
        stats_config.RefreshStatistics = 1
        stats_time, stats_size = self.inner_test_build_time(stats_config, "STATS", num_runs)
        
        # Test IMDB database
        imdb_config = self.get_imdb_db_config()
        imdb_config.RefreshStatistics = 1
        imdb_time, imdb_size = self.inner_test_build_time(imdb_config, "IMDB", num_runs)
        
        return {'STATS': (stats_time, stats_size), 'IMDB': (imdb_time, imdb_size)}

    def test_planning_time(self, num_runs: int = 3, benchmarks=None) -> Dict[str, Optional[float]]:
        """
        Test planning time (multiple runs averaged
        
        Test STATS, JOBM, JOBLight, and JOBLightRanges databases by default,
        or test only specified benchmarks via the benchmarks parameter.
        1. Copy queries to running_space/input.sql, add EXPLAIN, measure time
        2. Same config, run with dummy_query.sql, measure time
        
        Returns:
            Dict[str, Optional[float]]: benchmark -> planning_time
        """
        self.result("\n=== Test planning time - StarCE ===")

        benchmark_specs = [
            ("STATS", self.get_stats_config, self.benchmark_dir / "workloads" / "STATS-CEB" / "queries.sql"),
            ("JOBM", self.get_jobm_config, self.benchmark_dir / "workloads" / "JOBM" / "queries.sql"),
            ("JOBLight", self.get_joblight_config, self.benchmark_dir / "workloads" / "JOBLight" / "queries.sql"),
            ("JOBLightRanges", self.get_joblight_ranges_config, self.benchmark_dir / "workloads" / "JOBLightRanges" / "filtered_queries.sql"),
            ("JobJoin", self.get_jobjoin_config, self.benchmark_dir / "workloads" / "JobJoin" / "queries.sql"),
            ("StatsJoin", self.get_statsjoin_config, self.benchmark_dir / "workloads" / "StatsJoin" / "queries.sql"),
        ]
        benchmark_specs = self._filter_benchmark_specs(benchmark_specs, benchmarks)

        results = {}
        for benchmark, config_getter, queries_file in benchmark_specs:
            config = config_getter()
            results[benchmark] = self.inner_test_planning_time(config, benchmark, queries_file, num_runs)

        return results

    def test_running_time(self, num_runs: int = 3, benchmarks=None) -> Dict[str, Optional[float]]:
        """
        Test running time (multiple runs averaged
        
        Test STATS, JOBM, JOBLight, and JOBLightRanges databases by default,
        or test only specified benchmarks via the benchmarks parameter.
        1. Use plain queries (input.sql) to measure time
        2. Use EXPLAIN queries (explain.sql) to measure time
        3. Final running time = input.sql time - explain.sql time
        
        Returns:
            Dict[str, Optional[float]]: benchmark -> running_time
        """
        self.result("\n=== Test running time - StarCE ===")

        benchmark_specs = [
            ("STATS", self.get_stats_config, self.benchmark_dir / "workloads" / "STATS-CEB" / "queries.sql"),
            ("JOBM", self.get_jobm_config, self.benchmark_dir / "workloads" / "JOBM" / "queries.sql"),
            ("JOBLight", self.get_joblight_config, self.benchmark_dir / "workloads" / "JOBLight" / "queries.sql"),
            ("JOBLightRanges", self.get_joblight_ranges_config, self.benchmark_dir / "workloads" / "JOBLightRanges" / "filtered_queries.sql"),
            ("JobJoin", self.get_jobjoin_config, self.benchmark_dir / "workloads" / "JobJoin" / "queries.sql"),
            ("StatsJoin", self.get_statsjoin_config, self.benchmark_dir / "workloads" / "StatsJoin" / "queries.sql"),
        ]
        benchmark_specs = self._filter_benchmark_specs(benchmark_specs, benchmarks)

        results = {}
        for benchmark, config_getter, queries_file in benchmark_specs:
            config = config_getter()
            results[benchmark] = self.inner_test_running_time(config, benchmark, queries_file, num_runs)

        return results

    def get_est_cards(self, benchmark: str = None) -> Dict[str, Any]:
        """
        Get estimated cardinalities
        
        Args:
            benchmark: benchmark name ('Stats', 'JOBM'), processes all databases if None
        
        Returns:
            dict: Dictionary containing evaluation results, including:
                - total_time: Total evaluation time (seconds)
                - output_file: Result output file path
        """
        if benchmark is None:
            raise ValueError(f"invalid benchmark: None")
        else:
            # Process single benchmark
            if benchmark == 'Stats':
                config = self.get_stats_config()
                queries_file = Path(config.SQL_PATH)
                result_path = self.checkpoint_dir / "StarCE" / "card_stats.txt"
            elif benchmark == 'JOBM':
                config = self.get_jobm_config()
                queries_file = Path(config.SQL_PATH)
                result_path = self.checkpoint_dir / "StarCE" / "card_jobm.txt"
            elif benchmark == 'JOBLight':
                config = self.get_joblight_config()
                queries_file = Path(config.SQL_PATH)
                result_path = self.checkpoint_dir / "StarCE" / "card_joblight.txt"
            elif benchmark == 'JOBLightRanges':
                config = self.get_joblight_ranges_config()
                queries_file = Path(config.SQL_PATH)
                result_path = self.checkpoint_dir / "StarCE" / "card_joblr.txt"
            elif benchmark == 'JobJoin':
                config = self.get_jobjoin_config()
                queries_file = Path(config.SQL_PATH)
                result_path = self.checkpoint_dir / "StarCE" / "card_jobjoin.txt"

                explain_sql = self.running_space / "explain.sql"
                self._prepare_input_sql_with_explain(queries_file, explain_sql)

                config.RecordingSubquery = 0
                config.SQL_PATH = "explain.sql"

                self.save_config(config)
                start_time = time.time()
                returncode, stdout, stderr, elapsed = self.run_starce_raw()
                total_time = time.time() - start_time

                if returncode != 0:
                    raise RuntimeError(f"StarCE query evaluation failed ({benchmark}): {stderr}")

                import sys as _sys
                _scripts_dir = str(self.project_root / "scripts")
                if _scripts_dir not in _sys.path:
                    _sys.path.insert(0, _scripts_dir)
                from extract_card_from_explain import process_data
                cardinalities = process_data(stdout)

                with open(result_path, 'w') as f:
                    for card in cardinalities:
                        f.write(f"{card}\n")

                return {
                    'benchmark': benchmark,
                    'total_time': total_time,
                    'output_file': str(result_path)
                }
            elif benchmark == 'StatsJoin':
                config = self.get_statsjoin_config()
                queries_file = Path(config.SUBQUERY_PATH)
                result_path = self.checkpoint_dir / "StarCE" / "card_statsjoin.txt"

                explain_sql = self.running_space / "explain.sql"
                self._prepare_input_sql_with_explain(queries_file, explain_sql)

                config.RecordingSubquery = 0
                config.SQL_PATH = "explain.sql"

                self.save_config(config)
                start_time = time.time()
                returncode, stdout, stderr, elapsed = self.run_starce_raw()
                total_time = time.time() - start_time

                if returncode != 0:
                    raise RuntimeError(f"StarCE query evaluation failed ({benchmark}): {stderr}")

                import sys as _sys
                _scripts_dir = str(self.project_root / "scripts")
                if _scripts_dir not in _sys.path:
                    _sys.path.insert(0, _scripts_dir)
                from extract_card_from_explain import process_data
                cardinalities = process_data(stdout)

                with open(result_path, 'w') as f:
                    for card in cardinalities:
                        f.write(f"{card}\n")

                return {
                    'benchmark': benchmark,
                    'total_time': total_time,
                    'output_file': str(result_path)
                }
            else:
                raise ValueError(f"Unsupported benchmark: {benchmark}")
            
            # Generate explain.sql file
            explain_sql = self.running_space / "explain.sql"
            self._prepare_input_sql_with_explain(queries_file, explain_sql)
            
            config.RecordingSubquery = 1
            config.RecordEstimateTime = 1
            config.SUBQUERY_PATH = "null.sql"
            config.SQL_PATH = "explain.sql"
            config.SUBQUERY_RESULT_PATH = str(result_path)
            bench_display = 'STATS' if benchmark == 'Stats' else benchmark
            time_file_name = f"estimate_time_{bench_display}.txt"
            config.SUBQUERY_TIME_PATH = str(Path(result_path).parent / time_file_name)

            self.save_config(config)
            start_time = time.time()
            success, elapsed = self.run_starce(True)
            total_time = time.time() - start_time

            if not success:
                raise RuntimeError(f"StarCE query evaluation failed ({benchmark})")

            return {
                'benchmark': benchmark,
                'total_time': total_time,
                'output_file': str(result_path),
                'time_file': config.SUBQUERY_TIME_PATH
            }

    def run(self):
        """all StarCE tests"""
        self.log("=" * 80)
        self.log("StarCE experiment tests start")
        self.log("=" * 80)
        
        # 1. Log path info
        self.record_paths()
        
        # 2. each sub-experiment
        # Note: main() entry is only for quick validation; regular experiments use ipynb to call methods individually
        # self.test_build_time(num_runs=3)
        # self.test_planning_time(num_runs=3)
        # self.test_running_time(num_runs=3)
        
        self.log("=" * 80)
        self.log("Experiment tests completed")
        self.log("=" * 80)


class DuckDBTestRunner(ExperimentRunner):
    """DuckDB test runner (EnableStarCE=0)"""

    def test_build_time(self, num_runs: int = 3) -> None:
        """
        Test build time (multiple runs averaged
        Test both STATS and IMDB databases
        Results written directly to result file, no return value
        """
        self.result("\n=== Test build time - DuckDB ===")
        self.result("DuckDB cannot directly test statistics build_time, skipping")
        self.log("DuckDB cannot directly test statistics build_time, skipping")

    def test_planning_time(self, num_runs: int = 3, benchmarks=None) -> Dict[str, Optional[float]]:
        """
        Test planning time (multiple runs averaged
        
        Test STATS, JOBM, JOBLight, and JOBLightRanges databases by default,
        or test only specified benchmarks via the benchmarks parameter.
        1. Copy queries to running_space/input.sql, add EXPLAIN, measure time
        2. Same config, run with dummy_query.sql, measure time
        
        Returns:
            Dict[str, Optional[float]]: benchmark -> planning_time
        """
        self.result("\n=== Test planning time - DuckDB ===")

        benchmark_specs = [
            ("STATS", self.get_stats_config, self.benchmark_dir / "workloads" / "STATS-CEB" / "queries.sql"),
            ("JOBM", self.get_jobm_config, self.benchmark_dir / "workloads" / "JOBM" / "queries.sql"),
            ("JOBLight", self.get_joblight_config, self.benchmark_dir / "workloads" / "JOBLight" / "queries.sql"),
            ("JOBLightRanges", self.get_joblight_ranges_config, self.benchmark_dir / "workloads" / "JOBLightRanges" / "filtered_queries.sql"),
            ("JobJoin", self.get_jobjoin_config, self.benchmark_dir / "workloads" / "JobJoin" / "queries.sql"),
            ("StatsJoin", self.get_statsjoin_config, self.benchmark_dir / "workloads" / "StatsJoin" / "queries.sql"),
        ]
        benchmark_specs = self._filter_benchmark_specs(benchmark_specs, benchmarks)

        results = {}
        for benchmark, config_getter, queries_file in benchmark_specs:
            config = config_getter()
            config.EnableStarCE = 0
            results[benchmark] = self.inner_test_planning_time(config, benchmark, queries_file, num_runs)

        return results

    def test_running_time(self, num_runs: int = 3, benchmarks=None) -> Dict[str, Optional[float]]:
        """
        Test running time (multiple runs averaged
        
        Test STATS, JOBM, JOBLight, and JOBLightRanges databases by default,
        or test only specified benchmarks via the benchmarks parameter.
        1. Use plain queries (input.sql) to measure time
        2. Use EXPLAIN queries (explain.sql) to measure time
        3. Final running time = input.sql time - explain.sql time
        
        Returns:
            Dict[str, Optional[float]]: benchmark -> running_time
        """
        self.result("\n=== Test running time - DuckDB ===")

        benchmark_specs = [
            ("STATS", self.get_stats_config, self.benchmark_dir / "workloads" / "STATS-CEB" / "queries.sql"),
            ("JOBM", self.get_jobm_config, self.benchmark_dir / "workloads" / "JOBM" / "queries.sql"),
            ("JOBLight", self.get_joblight_config, self.benchmark_dir / "workloads" / "JOBLight" / "queries.sql"),
            ("JOBLightRanges", self.get_joblight_ranges_config, self.benchmark_dir / "workloads" / "JOBLightRanges" / "filtered_queries.sql"),
            ("JobJoin", self.get_jobjoin_config, self.benchmark_dir / "workloads" / "JobJoin" / "queries.sql"),
            ("StatsJoin", self.get_statsjoin_config, self.benchmark_dir / "workloads" / "StatsJoin" / "queries.sql"),
        ]
        benchmark_specs = self._filter_benchmark_specs(benchmark_specs, benchmarks)

        results = {}
        for benchmark, config_getter, queries_file in benchmark_specs:
            config = config_getter()
            config.EnableStarCE = 0
            results[benchmark] = self.inner_test_running_time(config, benchmark, queries_file, num_runs)

        return results

    def run(self):
        """all DuckDB tests"""
        self.log("=" * 80)
        self.log("DuckDB experiment tests start")
        self.log("=" * 80)
        
        # 1. Log path info
        self.record_paths()
        
        # 2. Run each sub-experiment (each defines its own config)
        self.test_build_time(num_runs=3)
        self.test_planning_time(num_runs=3)
        self.test_running_time(num_runs=3)
        
        self.log("=" * 80)
        self.log("Experiment tests completed")
        self.log("=" * 80)


class InjectionTestRunner(ExperimentRunner):
    """Injection method test runner (using externally injected cardinalities)"""

    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize injection-type test runner
        
        Args:
            project_root: Project root directory
        """
        super().__init__(project_root)

    def inner_test_planning_time_with_injection(self, config: StarCEConfig, db_name: str, 
                                                queries_file: Path, 
                                                injected_card_path: str,
                                                card_est_time: float = 0.0,
                                                num_runs: int = 3) -> Optional[float]:
        """
        Test planning time for a specific database(using injected cardinality)
        
        Args:
            config: Test configuration
            db_name: Database name (for display, e.g. "STATS" or "JOBM")
            queries_file: queries.sql file path
            injected_card_path: Injected cardinality file path (SUBQUERY_RESULT_PATH)
            card_est_time: Pure cardinality estimation time (seconds), excluding SQL parsing time, added to planning time
            num_runs: Number of runs
        
        Returns:
            Optional[float]: Final planning time (seconds), None on failure

        Note:
            card_est_time only includes the estimator execution time, not SQL parsing time.
            SQL parsing is a one-time task and should not count towards per-query planning time.
            Formula: planning_time = explain_time - dummy_time + card_est_time
        """
        self.result(f"\n--- Test planning time(injected cardinality) ({db_name}) ---")
        self.log(f"Starting planning time test(injected cardinality) ({db_name}), run(s) {num_runs}")
        
        injected_card_path_obj = Path(injected_card_path).absolute()
        if not injected_card_path_obj.exists():
            self.result(f"Error ({db_name}): Injected cardinality file not found: {injected_card_path_obj}")
            return None
        
        input_sql = self.running_space / "input.sql"
        
        # 1. Copy queries to input.sql and add EXPLAIN
        try:
            self._prepare_input_sql_with_explain(queries_file, input_sql)
        except Exception as e:
            self.result(f"Failed to prepare input.sql ({db_name}): {e}")
            return None
        
        # Configure injected cardinality: set UseSubqueryCard=1 and set SUBQUERY_RESULT_PATH
        config.UseSubqueryCard = 1
        config.SUBQUERY_RESULT_PATH = str(injected_card_path_obj)
        # Test using input.sql
        config.SQL_PATH = "input.sql"
        self.save_config(config)
        
        times_input = []
        for i in range(num_runs):
            self.log(f"Using input.sql (injected cardinality):  {i+1}/{num_runs} run(s)...")
            success, elapsed = self.run_starce(suppress_output=True)
            if success:
                times_input.append(elapsed)
            else:
                self.log(f" {i+1} run(s) failed, skipped", to_console=True)
        
        # 2. Test using dummy_query.sql
        config.SQL_PATH = "dummy_query.sql"
        self.save_config(config)
        
        times_dummy = []
        for i in range(num_runs):
            self.log(f"using dummy_query.sql (injected cardinality):  {i+1}/{num_runs} run(s)...")
            success, elapsed = self.run_starce(suppress_output=True)
            if success:
                times_dummy.append(elapsed)
            else:
                self.log(f" {i+1} run(s) failed, skipped", to_console=True)
        
        # Output results
        avg_time_input = None
        if times_input:
            avg_time_input = sum(times_input) / len(times_input)
            self.result(f"Planning time test results ({db_name}) - Using input.sql (injected cardinality):")
            self.result(f"  Successful runs: {len(times_input)}/{num_runs}")
            self.result(f"  Average planning time: {avg_time_input:.2f}  seconds")
            self.result(f"  Fastest: {min(times_input):.2f}  seconds")
            self.result(f"  Slowest: {max(times_input):.2f}  seconds")
        else:
            self.result(f"Planning time test failed ({db_name}) - using input.sql: all run(s) failed")
        
        avg_time_dummy = None
        if times_dummy:
            avg_time_dummy = sum(times_dummy) / len(times_dummy)
            self.result(f"Planning time test results ({db_name}) - using dummy_query.sql (injected cardinality):")
            self.result(f"  Successful runs: {len(times_dummy)}/{num_runs}")
            self.result(f"  Average planning time: {avg_time_dummy:.2f}  seconds")
            self.result(f"  Fastest: {min(times_dummy):.2f}  seconds")
            self.result(f"  Slowest: {max(times_dummy):.2f}  seconds")
        else:
            self.result(f"Planning time test failed ({db_name}) - using dummy_query.sql: all run(s) failed")
        
        # Calculate final planning time: explain time - dummy time + cardinality estimation time
        if avg_time_input is not None and avg_time_dummy is not None:
            final_planning_time = avg_time_input - avg_time_dummy + card_est_time
            self.result(f"Final planning time ({db_name}): {final_planning_time:.2f} seconds (explain time - dummy time + cardinality estimation time {card_est_time:.2f}  seconds)")
            return final_planning_time
        else:
            self.result(f"Cannot calculate final planning time ({db_name}): insufficient explain time or dummy time data")
            return None

    def inner_test_running_time_with_injection(self, config: StarCEConfig, db_name: str,
                                               queries_file: Path,
                                               injected_card_path: str,
                                               num_runs: int = 3) -> Optional[float]:
        """
        Test running time for a specific database(using injected cardinality)
        
        Args:
            config: Test configuration
            db_name: Database name (for display, e.g. "STATS" or "JOBM")
            queries_file: queries.sql file path
            injected_card_path: Injected cardinality file path (SUBQUERY_RESULT_PATH)
            num_runs: Number of runs
        
        Returns:
            Optional[float]: Final running time (seconds), None on failure
        """
        self.result(f"\n--- Test running time(injected cardinality) ({db_name}) ---")
        self.log(f"Test running time (injected cardinality) ({db_name}), run(s) {num_runs}")
        
        injected_card_path_obj = Path(injected_card_path).absolute()
        if not injected_card_path_obj.exists():
            self.result(f"Error ({db_name}): Injected cardinality file not found: {injected_card_path_obj}")
            return None
        
        input_sql = self.running_space / "input.sql"
        explain_sql = self.running_space / "explain.sql"
        
        # 1. Prepare plain input.sql (without EXPLAIN)
        try:
            self._prepare_input_sql_without_explain(queries_file, input_sql)
        except Exception as e:
            self.result(f"Failed to prepare input.sql ({db_name}): {e}")
            return None
        
        # Configure injected cardinality: set UseSubqueryCard=1 and set SUBQUERY_RESULT_PATH
        config.UseSubqueryCard = 1
        config.SUBQUERY_RESULT_PATH = str(injected_card_path_obj)
        # Test using input.sql (plain queries)
        config.SQL_PATH = "input.sql"
        self.save_config(config)
        
        times_input = []
        for i in range(num_runs):
            self.log(f"Using input.sql (plain queries, injected cardinality):  {i+1}/{num_runs} run(s)...")
            success, elapsed = self.run_starce(suppress_output=True)
            if success:
                times_input.append(elapsed)
            else:
                self.log(f" {i+1} run(s) failed, skipped", to_console=True)
        
        # 2. Prepare explain.sql (with EXPLAIN)
        try:
            self._prepare_input_sql_with_explain(queries_file, explain_sql)
        except Exception as e:
            self.result(f"Failed to prepare explain.sql ({db_name}): {e}")
            return None
        
        # Test using explain.sql
        config.SQL_PATH = "explain.sql"
        self.save_config(config)
        
        times_explain = []
        for i in range(num_runs):
            self.log(f"using explain.sql (EXPLAIN queries, injected cardinality):  {i+1}/{num_runs} run(s)...")
            success, elapsed = self.run_starce(suppress_output=True)
            if success:
                times_explain.append(elapsed)
            else:
                self.log(f" {i+1} run(s) failed, skipped", to_console=True)
        
        # Output results
        avg_time_input = None
        if times_input:
            avg_time_input = sum(times_input) / len(times_input)
            self.result(f"time test results ({db_name}) - Using input.sql (plain queries, injected cardinality):")
            self.result(f"  Successful runs: {len(times_input)}/{num_runs}")
            self.result(f"  Average running time: {avg_time_input:.2f}  seconds")
            self.result(f"  Fastest: {min(times_input):.2f}  seconds")
            self.result(f"  Slowest: {max(times_input):.2f}  seconds")
        else:
            self.result(f"running time test failed ({db_name}) - using input.sql: all run(s) failed")
        
        avg_time_explain = None
        if times_explain:
            avg_time_explain = sum(times_explain) / len(times_explain)
            self.result(f"time test results ({db_name}) - using explain.sql (EXPLAIN queries, injected cardinality):")
            self.result(f"  Successful runs: {len(times_explain)}/{num_runs}")
            self.result(f"  Average running time: {avg_time_explain:.2f}  seconds")
            self.result(f"  Fastest: {min(times_explain):.2f}  seconds")
            self.result(f"  Slowest: {max(times_explain):.2f}  seconds")
        else:
            self.result(f"running time test failed ({db_name}) - Using explain.sql: all run(s) failed")
        
        # Calculate final running time: input.sql time - explain.sql time
        if avg_time_input is not None and avg_time_explain is not None:
            final_running_time = avg_time_input - avg_time_explain
            self.result(f"Final running time ({db_name}): {final_running_time:.2f} seconds (input.sql time - explain.sql time)")
            return final_running_time
        else:
            self.result(f"Cannot calculate final running time ({db_name}): insufficient input.sql time or explain.sql time data")
            return None

    def test_build_time(self, num_runs: int = 3) -> None:
        """
        Test build time (injection methods don't need statistics)
        Results written directly to result file, no return value
        """
        self.result("\n=== Test build time - Injection method ===")
        self.result("Injection-based methods do not need to build statistics, skipping")
        self.log("Injection-based methods do not need to build statistics, skipping")

    def _get_injection_benchmark_context(self, benchmark: str):
        if benchmark == 'STATS':
            return (
                self.get_stats_config(),
                self.benchmark_dir / "workloads" / "STATS-CEB" / "queries.sql",
                "STATS",
            )
        if benchmark == 'JOBM':
            return (
                self.get_jobm_config(),
                self.benchmark_dir / "workloads" / "JOBM" / "queries.sql",
                "JOBM",
            )
        if benchmark == 'JobJoin':
            return (
                self.get_jobjoin_config(),
                self.benchmark_dir / "workloads" / "JobJoin" / "queries.sql",
                "JobJoin",
            )
        if benchmark == 'StatsJoin':
            return (
                self.get_statsjoin_config(),
                self.benchmark_dir / "workloads" / "StatsJoin" / "queries.sql",
                "StatsJoin",
            )
        if benchmark == 'JOBLight':
            return (
                self.get_joblight_config(),
                self.benchmark_dir / "workloads" / "JOBLight" / "queries.sql",
                "JOBLight",
            )
        if benchmark == 'JOBLightRanges':
            return (
                self.get_joblight_ranges_config(),
                self.benchmark_dir / "workloads" / "JOBLightRanges" / "filtered_queries.sql",
                "JOBLightRanges",
            )
        raise ValueError(f"Unsupported benchmark: {benchmark}")

    def test_planning_time(self, benchmark: str, injected_card_path: str, 
                          card_est_time: float = 0.0, num_runs: int = 3) -> Optional[float]:
        """
        Test planning time(using injected cardinality)
        
        Args:
            benchmark: benchmark name ('STATS' / 'JOBM' / 'JOBLight' / 'JOBLightRanges')
            injected_card_path: Injected cardinality file path (SUBQUERY_RESULT_PATH)
            card_est_time: Pure cardinality estimation time (seconds), excluding SQL parsing time, added to planning time
            num_runs: Number of runs
        
        1. Copy queries to running_space/input.sql, add EXPLAIN, measure time
        2. Same config, run with dummy_query.sql, measure time
        3. Final planning time = explain time - dummy time + cardinality estimation time
        
        Returns:
            Optional[float]: Final planning time (seconds), None on failure
        """
        self.result(f"\n=== Test planning time - injection-based method ({benchmark}) ===")
        self.result(f"Injected cardinality file path: {injected_card_path}")
        self.result(f"Cardinality estimation time: {card_est_time:.2f} seconds")

        try:
            config, queries_file, db_name = self._get_injection_benchmark_context(benchmark)
        except ValueError as e:
            self.result(f"Error: {e}")
            return None

        return self.inner_test_planning_time_with_injection(
            config, db_name, queries_file, injected_card_path, card_est_time, num_runs
        )

    def test_running_time(self, benchmark: str, injected_card_path: str, 
                         num_runs: int = 3) -> Optional[float]:
        """
        Test running time(using injected cardinality)
        
        Args:
            benchmark: benchmark name ('STATS' / 'JOBM' / 'JOBLight' / 'JOBLightRanges')
            injected_card_path: Injected cardinality file path (SUBQUERY_RESULT_PATH)
            num_runs: Number of runs
        
        1. Use plain queries (input.sql) to measure time
        2. Use EXPLAIN queries (explain.sql) to measure time
        3. Final running time = input.sql time - explain.sql time
        
        Returns:
            Optional[float]: Final running time (seconds), None on failure
        """
        self.result(f"\n=== Test running time - injection-based method ({benchmark}) ===")
        self.result(f"Injected cardinality file path: {injected_card_path}")

        try:
            config, queries_file, db_name = self._get_injection_benchmark_context(benchmark)
        except ValueError as e:
            self.result(f"Error: {e}")
            return None

        return self.inner_test_running_time_with_injection(
            config, db_name, queries_file, injected_card_path, num_runs
        )

    def run(self, benchmark: str, injected_card_path: str, 
            card_est_time: float = 0.0, num_runs: int = 3):
        """
        injection-based method tests
        
        Args:
            benchmark: benchmark name ('STATS' or 'JOBM')
            injected_card_path: Injected cardinality file path (SUBQUERY_RESULT_PATH)
            card_est_time: Pure cardinality estimation time (seconds), excluding SQL parsing time, added to planning time
            num_runs: Number of runs
        """
        self.log("=" * 80)
        self.log(f"Injection-based method experiment tests start ({benchmark})")
        self.log("=" * 80)
        
        # 1. Log path info
        self.record_paths()
        
        self.result(f"Benchmark: {benchmark}")
        self.result(f"Injected cardinality file path: {injected_card_path}")
        self.result(f"Cardinality estimation time: {card_est_time:.2f} seconds")
        
        # 2. each sub-experiment
        self.test_build_time(num_runs=num_runs)
        self.test_planning_time(benchmark, injected_card_path, card_est_time, num_runs)
        self.test_running_time(benchmark, injected_card_path, num_runs)
        
        self.log("=" * 80)
        self.log("Experiment tests completed")
        self.log("=" * 80)


def main():
    """Main function"""
    import sys
    
    # Can accept project root directory as optional argument
    project_root_str = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Determine project root directory
    script_dir = Path(__file__).parent.absolute()
    if project_root_str:
        project_root = Path(project_root_str).absolute()
    else:
        project_root = script_dir.parent
    
    running_space = script_dir / "running_space"
    running_space.mkdir(exist_ok=True)
    
    # Copy starce executable (prerequisite step for all experiments, exits on failure)
    setup_starce_executable(project_root, running_space)
    
    # Create runner and experiments
    runner_starce = StarCETestRunner(str(project_root))
    runner_starce.run()
    runner_duckdb = DuckDBTestRunner(str(project_root))
    runner_duckdb.run()


if __name__ == "__main__":
    main()
