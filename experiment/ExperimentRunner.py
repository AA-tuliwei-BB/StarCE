#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StarCE 实验测试脚本
用于运行和测试 StarCE 的各种性能指标
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
    """StarCE 配置结构体，便于管理和序列化为 JSON"""
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
        """转换为字典"""
        return asdict(self)

    def to_json_file(self, filepath: str) -> None:
        """保存为 JSON 文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=4, ensure_ascii=False)

    @classmethod
    def from_json_file(cls, filepath: str) -> 'StarCEConfig':
        """从 JSON 文件加载"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)

    def copy(self) -> 'StarCEConfig':
        """创建配置的副本"""
        return StarCEConfig(**self.to_dict())

    def update(self, **kwargs) -> 'StarCEConfig':
        """更新配置项，返回新的配置对象（不修改原对象）"""
        new_config = self.copy()
        for key, value in kwargs.items():
            if hasattr(new_config, key):
                setattr(new_config, key, value)
            else:
                raise ValueError(f"未知的配置项: {key}")
        return new_config


class ExperimentRunner(ABC):
    """实验运行器基类"""

    def __init__(self, project_root: Optional[str] = None):
        """初始化实验运行器"""
        # 获取脚本所在目录
        self.script_dir = Path(__file__).parent.absolute()
        
        # 项目根目录（默认在 script_dir 的上一级）
        if project_root:
            self.project_root = Path(project_root).absolute()
        else:
            self.project_root = self.script_dir.parent
        
        # running_space 目录
        self.running_space = self.script_dir / "running_space"
        self.running_space.mkdir(exist_ok=True)
        
        # checkpoint 目录（StarCE统计信息存储位置）
        self.checkpoint_dir = self.script_dir / "checkpoint"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Benchmark 目录的绝对路径
        self.benchmark_dir = self.project_root / "Benchmark"
        
        # 日志和结果文件
        self.log_file = self.running_space / "log.txt"
        self.result_file = self.running_space / "result.txt"
        
        # starce 可执行文件路径
        self.starce_exec = self.running_space / "starce"
        
        # 配置对象
        self.config: Optional[StarCEConfig] = None

    def log(self, message: str, to_console: bool = True):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message)
        
        if to_console:
            print(log_message.strip())

    def result(self, message: str):
        """记录结果"""
        with open(self.result_file, 'a', encoding='utf-8') as f:
            f.write(f"{message}\n")
        print(message)

    def save_config(self, config: StarCEConfig):
        """
        保存配置到 running_space/config.json（供starce可执行文件使用）
        
        参数:
            config: 要保存的配置对象
        """
        config_file = self.running_space / "config.json"
        config.to_json_file(str(config_file))
        self.log(f"配置文件已保存到: {config_file}")
        self.config = config

    def _filter_benchmark_specs(self, benchmark_specs, benchmarks=None):
        """
        按给定 benchmark 列表过滤 benchmark_specs。

        参数:
            benchmark_specs: [(benchmark, config_getter, queries_file), ...]
            benchmarks: 需要保留的 benchmark 列表；None 表示不过滤
        """
        if benchmarks is None:
            return benchmark_specs

        requested = list(benchmarks)
        available = {benchmark for benchmark, _, _ in benchmark_specs}
        invalid = [benchmark for benchmark in requested if benchmark not in available]
        if invalid:
            raise ValueError(f"不支持的benchmark: {invalid}")

        requested_set = set(requested)
        return [
            spec
            for spec in benchmark_specs
            if spec[0] in requested_set
        ]

    def get_stats_db_config(self) -> StarCEConfig:
        """
        获取STATS数据库的配置
        
        返回:
            基于默认配置修改后的STATS配置对象
        """
        config = StarCEConfig()
        config.DB_PATH = str(self.benchmark_dir / "duckdb" / "stats.db")
        config.SCHEMA_PATH = str(self.benchmark_dir / "STATS" / "schema_stats.json")
        config.STATS_PATH = str(self.checkpoint_dir / "StarCE" / "statistics_stats.json")
        return config

    def get_imdb_db_config(self) -> StarCEConfig:
        """
        获取IMDB数据库的配置

        返回:
            基于默认配置修改后的IMDB配置对象
        """
        config = StarCEConfig()
        config.DB_PATH = str(self.benchmark_dir / "duckdb" / "imdb.db")
        config.SCHEMA_PATH = str(self.benchmark_dir / "IMDB" / "schema_imdb.json")
        config.STATS_PATH = str(self.checkpoint_dir / "StarCE" / "statistics_imdb.json")
        return config

    def get_imdb_light_db_config(self) -> StarCEConfig:
        """
        获取IMDB_LIGHT数据库的配置

        返回:
            基于默认配置修改后的IMDB_LIGHT配置对象
        """
        config = StarCEConfig()
        config.DB_PATH = str(self.benchmark_dir / "duckdb" / "imdb.db")
        config.SCHEMA_PATH = str(self.benchmark_dir / "workloads" / "JOBLight" / "schema_joblight.json")
        config.STATS_PATH = str(self.checkpoint_dir / "StarCE" / "statistics_joblight.json")
        return config

    def get_imdb_light_ranges_db_config(self) -> StarCEConfig:
        """
        获取IMDB_LIGHT_RANGES数据库的配置

        返回:
            基于默认配置修改后的IMDB_LIGHT_RANGES配置对象
        """
        config = StarCEConfig()
        config.DB_PATH = str(self.benchmark_dir / "duckdb" / "imdb.db")
        config.SCHEMA_PATH = str(self.benchmark_dir / "workloads" / "JOBLightRanges" / "schema_joblr.json")
        config.STATS_PATH = str(self.checkpoint_dir / "StarCE" / "statistics_joblr.json")
        return config

    def get_stats_config(self) -> StarCEConfig:
        """
        获取stats-ceb benchmark的配置
        返回: 基于STATS数据库配置修改后的stats-ceb benchmark配置对象
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
        获取jobm benchmark的配置
        返回: 基于IMDB数据库配置修改后的jobm benchmark配置对象
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
        获取jobjoin benchmark的配置

        返回: 基于IMDB数据库配置修改后的jobjoin benchmark配置对象
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
        获取statsjoin benchmark的配置

        返回: 基于STATS数据库配置修改后的statsjoin benchmark配置对象
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
        获取joblight benchmark的配置
        返回: 基于IMDB数据库配置修改后的joblight benchmark配置对象
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
        """记录重要路径信息"""
        self.result("=" * 80)
        self.result(f"实验开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.result(f"项目根目录: {self.project_root}")
        self.result(f"Benchmark 目录: {self.benchmark_dir}")
        self.result(f"运行空间目录: {self.running_space}")
        self.result(f"starce 可执行文件: {self.starce_exec}")
        self.result("=" * 80)

    def run_starce(self, suppress_output: bool = False) -> Tuple[bool, float]:
        """
        运行 starce 并返回 (成功标志, 运行时间)
        
        参数:
            suppress_output: 是否抑制标准输出和标准错误的日志记录到控制台（默认False）
        """
        # 切换到 running_space 目录运行
        start_time = time.time()
        try:
            result = subprocess.run(
                [str(self.starce_exec)],
                cwd=str(self.running_space),
                capture_output=True,
                text=True,
                timeout=3600  # 1小时超时
            )
            elapsed_time = time.time() - start_time
            
            if result.returncode == 0:
                self.log(f"starce 运行成功，耗时: {elapsed_time:.2f} 秒")
                # 记录输出（如果抑制输出，则不显示到console，但仍写入日志文件）
                if result.stdout:
                    self.log(f"标准输出:\n{result.stdout}", to_console=not suppress_output)
                if result.stderr:
                    self.log(f"标准错误:\n{result.stderr}", to_console=not suppress_output)
                return True, elapsed_time
            else:
                self.log(f"starce 运行失败，返回码: {result.returncode}", to_console=True)
                if result.stderr:
                    self.log(f"错误信息:\n{result.stderr}", to_console=True)
                return False, elapsed_time
        except subprocess.TimeoutExpired:
            elapsed_time = time.time() - start_time
            self.log(f"starce 运行超时（>{elapsed_time:.2f} 秒）", to_console=True)
            return False, elapsed_time
        except Exception as e:
            elapsed_time = time.time() - start_time
            self.log(f"运行 starce 时发生异常: {e}", to_console=True)
            return False, elapsed_time

    def run_starce_raw(self) -> Tuple[int, str, str, float]:
        """
        运行 starce 并返回原始输出

        返回:
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
        复制queries文件到output_file，并在每个SELECT语句前添加EXPLAIN
        
        参数:
            queries_file: 源queries.sql文件路径
            output_file: 输出文件路径（running_space/input.sql）
        """
        if not queries_file.exists():
            raise FileNotFoundError(f"找不到queries文件: {queries_file}")
        
        with open(queries_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 在每个SELECT（大小写不敏感）前添加EXPLAIN
        # 使用正则表达式匹配SELECT语句（忽略大小写）
        # 匹配行首的SELECT（可能有前导空格）
        pattern = r'^(\s*)(select\s+)'
        replacement = r'\1EXPLAIN \2'
        new_content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.MULTILINE)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        self.log(f"已复制queries文件到 {output_file} 并添加EXPLAIN")

    def _prepare_input_sql_without_explain(self, queries_file: Path, output_file: Path) -> None:
        """
        复制queries文件到output_file，不添加EXPLAIN（普通查询）
        
        参数:
            queries_file: 源queries.sql文件路径
            output_file: 输出文件路径（running_space/input.sql）
        """
        if not queries_file.exists():
            raise FileNotFoundError(f"找不到queries文件: {queries_file}")
        
        shutil.copy2(queries_file, output_file)
        self.log(f"已复制queries文件到 {output_file}（普通查询，无EXPLAIN）")

    def inner_test_planning_time(self, config: StarCEConfig, db_name: str, queries_file: Path, num_runs: int = 3) -> Optional[float]:
        """
        为特定数据库测试计划时间
        
        参数:
            config: 测试配置
            db_name: 数据库名称（用于显示，如 "STATS" 或 "JOBM"）
            queries_file: queries.sql文件路径
            num_runs: 运行次数
        
        返回:
            Optional[float]: 最终计划时间（秒），失败则返回 None
        """
        self.result(f"\n--- 测试计划时间 ({db_name}) ---")
        self.log(f"开始测试计划时间 ({db_name})，运行 {num_runs} 次")
        
        input_sql = self.running_space / "input.sql"
        
        # 1. 复制queries为input.sql并添加EXPLAIN
        try:
            self._prepare_input_sql_with_explain(queries_file, input_sql)
        except Exception as e:
            self.result(f"准备input.sql失败 ({db_name}): {e}")
            return None
        
        # 使用input.sql进行测试
        config.SQL_PATH = "input.sql"
        self.save_config(config)
        
        times_input = []
        for i in range(num_runs):
            self.log(f"使用input.sql: 第 {i+1}/{num_runs} 次运行...")
            success, elapsed = self.run_starce(suppress_output=True)
            if success:
                times_input.append(elapsed)
            else:
                self.log(f"第 {i+1} 次运行失败，跳过", to_console=True)
        
        # 2. 使用dummy_query.sql进行测试
        config.SQL_PATH = "dummy_query.sql"
        self.save_config(config)
        
        times_dummy = []
        for i in range(num_runs):
            self.log(f"使用dummy_query.sql: 第 {i+1}/{num_runs} 次运行...")
            success, elapsed = self.run_starce(suppress_output=True)
            if success:
                times_dummy.append(elapsed)
            else:
                self.log(f"第 {i+1} 次运行失败，跳过", to_console=True)

        # 输出结果
        avg_time_input = None
        if times_input:
            avg_time_input = sum(times_input) / len(times_input)
            self.result(f"计划时间测试结果 ({db_name}) - 使用input.sql:")
            self.result(f"  成功运行次数: {len(times_input)}/{num_runs}")
            self.result(f"  平均计划时间: {avg_time_input:.2f} 秒")
            self.result(f"  最快: {min(times_input):.2f} 秒")
            self.result(f"  最慢: {max(times_input):.2f} 秒")
        else:
            self.result(f"计划时间测试失败 ({db_name}) - 使用input.sql: 所有运行都失败")

        avg_time_dummy = None
        if times_dummy:
            avg_time_dummy = sum(times_dummy) / len(times_dummy)
            self.result(f"计划时间测试结果 ({db_name}) - 使用dummy_query.sql:")
            self.result(f"  成功运行次数: {len(times_dummy)}/{num_runs}")
            self.result(f"  平均计划时间: {avg_time_dummy:.2f} 秒")
            self.result(f"  最快: {min(times_dummy):.2f} 秒")
            self.result(f"  最慢: {max(times_dummy):.2f} 秒")
        else:
            self.result(f"计划时间测试失败 ({db_name}) - 使用dummy_query.sql: 所有运行都失败")

        # 计算最终的planning time: explain time - dummy time
        if avg_time_input is not None and avg_time_dummy is not None:
            final_planning_time = avg_time_input - avg_time_dummy
            self.result(f"最终计划时间 ({db_name}): {final_planning_time:.2f} 秒 (explain time - dummy time)")
            return final_planning_time
        else:
            self.result(f"无法计算最终计划时间 ({db_name}): explain time 或 dummy time 数据不足")
            return None

    def inner_test_running_time(self, config: StarCEConfig, db_name: str, queries_file: Path, num_runs: int = 3) -> Optional[float]:
        """
        为特定数据库测试运行时间
        
        参数:
            config: 测试配置
            db_name: 数据库名称（用于显示，如 "STATS" 或 "JOBM"）
            queries_file: queries.sql文件路径
            num_runs: 运行次数
        
        返回:
            Optional[float]: 最终运行时间（秒），失败则返回 None
        """
        self.result(f"\n--- 测试运行时间 ({db_name}) ---")
        self.log(f"开始测试运行时间 ({db_name})，运行 {num_runs} 次")
        
        input_sql = self.running_space / "input.sql"
        explain_sql = self.running_space / "explain.sql"
        
        # 1. 准备普通的input.sql（不带EXPLAIN）
        try:
            self._prepare_input_sql_without_explain(queries_file, input_sql)
        except Exception as e:
            self.result(f"准备input.sql失败 ({db_name}): {e}")
            return None
        
        # 使用input.sql（普通查询）进行测试
        config.SQL_PATH = "input.sql"
        self.save_config(config)
        
        times_input = []
        for i in range(num_runs):
            self.log(f"使用input.sql（普通查询）: 第 {i+1}/{num_runs} 次运行...")
            success, elapsed = self.run_starce(suppress_output=True)
            if success:
                times_input.append(elapsed)
            else:
                self.log(f"第 {i+1} 次运行失败，跳过", to_console=True)
        
        # 2. 准备explain.sql（带EXPLAIN）
        try:
            self._prepare_input_sql_with_explain(queries_file, explain_sql)
        except Exception as e:
            self.result(f"准备explain.sql失败 ({db_name}): {e}")
            return None
        
        # 使用explain.sql进行测试
        config.SQL_PATH = "explain.sql"
        self.save_config(config)
        
        times_explain = []
        for i in range(num_runs):
            self.log(f"使用explain.sql（EXPLAIN查询）: 第 {i+1}/{num_runs} 次运行...")
            success, elapsed = self.run_starce(suppress_output=True)
            if success:
                times_explain.append(elapsed)
            else:
                self.log(f"第 {i+1} 次运行失败，跳过", to_console=True)
        
        # 输出结果
        avg_time_input = None
        if times_input:
            avg_time_input = sum(times_input) / len(times_input)
            self.result(f"运行时间测试结果 ({db_name}) - 使用input.sql（普通查询）:")
            self.result(f"  成功运行次数: {len(times_input)}/{num_runs}")
            self.result(f"  平均运行时间: {avg_time_input:.2f} 秒")
            self.result(f"  最快: {min(times_input):.2f} 秒")
            self.result(f"  最慢: {max(times_input):.2f} 秒")
        else:
            self.result(f"运行时间测试失败 ({db_name}) - 使用input.sql: 所有运行都失败")
        
        avg_time_explain = None
        if times_explain:
            avg_time_explain = sum(times_explain) / len(times_explain)
            self.result(f"运行时间测试结果 ({db_name}) - 使用explain.sql（EXPLAIN查询）:")
            self.result(f"  成功运行次数: {len(times_explain)}/{num_runs}")
            self.result(f"  平均运行时间: {avg_time_explain:.2f} 秒")
            self.result(f"  最快: {min(times_explain):.2f} 秒")
            self.result(f"  最慢: {max(times_explain):.2f} 秒")
        else:
            self.result(f"运行时间测试失败 ({db_name}) - 使用explain.sql: 所有运行都失败")
        
        # 计算最终的running time: input.sql时间 - explain.sql时间
        if avg_time_input is not None and avg_time_explain is not None:
            final_running_time = avg_time_input - avg_time_explain
            self.result(f"最终运行时间 ({db_name}): {final_running_time:.2f} 秒 (input.sql时间 - explain.sql时间)")
            return final_running_time
        else:
            self.result(f"无法计算最终运行时间 ({db_name}): input.sql时间 或 explain.sql时间 数据不足")
            return None

    def inner_test_per_query_running_time(
        self,
        config: StarCEConfig,
        queries_file: Path,
        num_runs: int = 1,
        injected_card_path: Optional[str] = None,
    ) -> list:
        """
        逐条测试主查询的执行时间

        参数:
            config: 测试配置
            queries_file: queries.sql 文件路径（每行一条主查询）
            num_runs: 每条查询运行次数，取平均
            injected_card_path: 注入型方法传入完整子查询基数文件路径；
                                 None 表示不注入（DuckDB / StarCE 原生模式）

        返回:
            list[Optional[float]]，长度 = 查询数，每项为该查询的平均执行时间（秒），失败为 None
        """
        if not queries_file.exists():
            raise FileNotFoundError(f"找不到 queries 文件: {queries_file}")

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
                self.log(f"per-query 进度: {i + 1}/{len(queries)}")

        return results

    @abstractmethod
    def test_build_time(self, num_runs: int = 3) -> None:
        """
        测试构建时间（抽象方法，子类需实现）
        结果会直接写入result文件，不返回
        
        参数:
            num_runs: 运行次数
        """
        pass

    @abstractmethod
    def test_planning_time(self, num_runs: int = 3) -> None:
        """
        测试计划时间（抽象方法，子类需实现）
        结果会直接写入result文件，不返回
        
        参数:
            num_runs: 运行次数
        """
        pass

    @abstractmethod
    def test_running_time(self, num_runs: int = 3) -> None:
        """
        测试运行时间（抽象方法，子类需实现）
        结果会直接写入result文件，不返回
        
        参数:
            num_runs: 运行次数
        """
        pass

    def run(self):
        """运行所有测试"""
        self.log("=" * 80)
        self.log("实验测试开始")
        self.log("=" * 80)
        
        # 1. 记录路径信息
        self.record_paths()
        
        # 2. 运行各个子实验（由子类实现具体的测试方法）
        self.test_build_time(num_runs=3)
        self.test_planning_time(num_runs=3)
        self.test_running_time(num_runs=3)
        
        self.log("=" * 80)
        self.log("实验测试完成")
        self.log("=" * 80)


def setup_starce_executable(project_root: Path, running_space: Path):
    """
    复制 starce 可执行文件到 running_space
    
    参数:
        project_root: 项目根目录
        running_space: 运行空间目录
    
    失败时直接报错并退出程序
    """
    import sys
    
    starce_source = project_root / "build" / "starce"
    starce_exec = running_space / "starce"
    
    if not starce_source.exists():
        print(f"错误: 找不到 starce 可执行文件: {starce_source}", file=sys.stderr)
        sys.exit(1)
    
    try:
        shutil.copy2(starce_source, starce_exec)
        os.chmod(starce_exec, 0o755)
        print(f"成功复制 starce 可执行文件到: {starce_exec}")
    except Exception as e:
        print(f"错误: 复制 starce 可执行文件失败: {e}", file=sys.stderr)
        sys.exit(1)


class StarCETestRunner(ExperimentRunner):
    """StarCE 测试运行器"""

    def __init__(self, project_root: Optional[str] = None):
        """初始化 StarCE 测试运行器"""
        super().__init__(project_root)
        # 确保 StarCE 子目录存在
        starce_subdir = self.checkpoint_dir / "StarCE"
        starce_subdir.mkdir(parents=True, exist_ok=True)

    def inner_test_build_time(self, config: StarCEConfig, db_name: str, num_runs: int = 3) -> Tuple[float, int]:
        """
        内部测试构建时间方法（公共逻辑）
        结果会直接写入result文件，并返回平均构建时间和统计文件大小
        
        参数:
            config: 测试配置
            db_name: 数据库名称（用于日志显示，如 "STATS" 或 "IMDB"）
            num_runs: 运行次数
        
        返回:
            tuple: (平均构建时间, 统计文件大小)
        """
        self.result(f"\n--- 测试构建时间 - StarCE - ({db_name}) ---")
        self.log(f"开始测试构建时间 - StarCE - ({db_name})，运行 {num_runs} 次")
        
        # 保存配置到 running_space/config.json
        self.save_config(config)
        
        times = []
        for i in range(num_runs):
            self.log(f"第 {i+1}/{num_runs} 次运行...")
            success, elapsed = self.run_starce()
            if success:
                times.append(elapsed)
            else:
                self.log(f"第 {i+1} 次运行失败，跳过", to_console=True)
        
        if not times:
            msg = f"构建时间测试失败 ({db_name}): 所有运行都失败"
            self.result(msg)
            raise RuntimeError(msg)
        
        avg_time = sum(times) / len(times)
        self.result(f"构建时间测试结果 ({db_name}):")
        self.result(f"  成功运行次数: {len(times)}/{num_runs}")
        self.result(f"  平均构建时间: {avg_time:.2f} 秒")
        self.result(f"  最快: {min(times):.2f} 秒")
        self.result(f"  最慢: {max(times):.2f} 秒")
        
        # 获取统计信息纯数据大小 (data_only, 对齐 LpBound 口径)
        stats_size_path = self.running_space / config.STATS_SIZE_PATH
        if not stats_size_path.exists():
            raise FileNotFoundError(f"统计大小文件未生成: {stats_size_path}")
        with open(stats_size_path, 'r') as f:
            size_report = json.load(f)
        size = size_report["data_only"]
        self.result(f"  统计信息大小 (data_only): {size} 字节 ({size/1024/1024:.2f} MB)")
        
        return avg_time, size

    def test_build_time(self, num_runs: int = 3) -> Dict[str, Tuple[float, int]]:
        """
        测试构建时间（运行多次取平均）
        对STATS和IMDB数据库都进行测试
        结果会直接写入result文件，并返回构建时间和文件大小
        
        返回:
            dict: {'STATS': (时间, 大小), 'IMDB': (时间, 大小)}
        """
        self.result("\n=== 测试构建时间 - StarCE ===")
        
        # 测试STATS数据库
        stats_config = self.get_stats_db_config()
        stats_config.RefreshStatistics = 1
        stats_time, stats_size = self.inner_test_build_time(stats_config, "STATS", num_runs)
        
        # 测试IMDB数据库
        imdb_config = self.get_imdb_db_config()
        imdb_config.RefreshStatistics = 1
        imdb_time, imdb_size = self.inner_test_build_time(imdb_config, "IMDB", num_runs)
        
        return {'STATS': (stats_time, stats_size), 'IMDB': (imdb_time, imdb_size)}

    def test_planning_time(self, num_runs: int = 3, benchmarks=None) -> Dict[str, Optional[float]]:
        """
        测试计划时间（运行多次取平均）
        
        默认对 STATS、JOBM、JOBLight 和 JOBLightRanges 数据库都进行测试，
        也可以通过 benchmarks 参数只测试指定 benchmark。
        1. 复制queries为running_space/input.sql，添加EXPLAIN，计算时间
        2. 相同config，使用dummy_query.sql运行，计算时间
        
        返回:
            Dict[str, Optional[float]]: benchmark -> planning_time
        """
        self.result("\n=== 测试计划时间 - StarCE ===")

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
        测试运行时间（运行多次取平均）
        
        默认对 STATS、JOBM、JOBLight 和 JOBLightRanges 数据库都进行测试，
        也可以通过 benchmarks 参数只测试指定 benchmark。
        1. 使用普通查询（input.sql）计算时间
        2. 使用EXPLAIN查询（explain.sql）计算时间
        3. 最终运行时间 = input.sql时间 - explain.sql时间
        
        返回:
            Dict[str, Optional[float]]: benchmark -> running_time
        """
        self.result("\n=== 测试运行时间 - StarCE ===")

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
        获取估计出的基数
        
        参数:
            benchmark: benchmark名称 ('Stats', 'JOBM')，如果为None则处理所有数据库
        
        返回:
            dict: 包含评估结果的字典，包括：
                - total_time: 总评估时间（秒）
                - output_file: 结果输出文件路径
        """
        if benchmark is None:
            raise ValueError(f"invalid benchmark: None")
        else:
            # 处理单个benchmark
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
                    raise RuntimeError(f"StarCE 查询评估失败 ({benchmark}): {stderr}")

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
                    raise RuntimeError(f"StarCE 查询评估失败 ({benchmark}): {stderr}")

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
                raise ValueError(f"不支持的benchmark: {benchmark}")
            
            # 生成explain.sql文件
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
                raise RuntimeError(f"StarCE 查询评估失败 ({benchmark})")

            return {
                'benchmark': benchmark,
                'total_time': total_time,
                'output_file': str(result_path),
                'time_file': config.SUBQUERY_TIME_PATH
            }

    def run(self):
        """运行所有 StarCE 测试"""
        self.log("=" * 80)
        self.log("StarCE 实验测试开始")
        self.log("=" * 80)
        
        # 1. 记录路径信息
        self.record_paths()
        
        # 2. 运行各个子实验
        # 注: main() 入口仅用于快速验证，常规实验通过 ipynb 逐个调用以下方法
        # self.test_build_time(num_runs=3)
        # self.test_planning_time(num_runs=3)
        # self.test_running_time(num_runs=3)
        
        self.log("=" * 80)
        self.log("实验测试完成")
        self.log("=" * 80)


class DuckDBTestRunner(ExperimentRunner):
    """DuckDB 测试运行器（EnableStarCE=0）"""

    def test_build_time(self, num_runs: int = 3) -> None:
        """
        测试构建时间（运行多次取平均）
        对STATS和IMDB数据库都进行测试
        结果会直接写入result文件，不返回
        """
        self.result("\n=== 测试构建时间 - DuckDB ===")
        self.result("DuckDB无法直接测试统计信息 build_time，跳过")
        self.log("DuckDB无法直接测试统计信息 build_time，跳过")

    def test_planning_time(self, num_runs: int = 3, benchmarks=None) -> Dict[str, Optional[float]]:
        """
        测试计划时间（运行多次取平均）
        
        默认对 STATS、JOBM、JOBLight 和 JOBLightRanges 数据库都进行测试，
        也可以通过 benchmarks 参数只测试指定 benchmark。
        1. 复制queries为running_space/input.sql，添加EXPLAIN，计算时间
        2. 相同config，使用dummy_query.sql运行，计算时间
        
        返回:
            Dict[str, Optional[float]]: benchmark -> planning_time
        """
        self.result("\n=== 测试计划时间 - DuckDB ===")

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
        测试运行时间（运行多次取平均）
        
        默认对 STATS、JOBM、JOBLight 和 JOBLightRanges 数据库都进行测试，
        也可以通过 benchmarks 参数只测试指定 benchmark。
        1. 使用普通查询（input.sql）计算时间
        2. 使用EXPLAIN查询（explain.sql）计算时间
        3. 最终运行时间 = input.sql时间 - explain.sql时间
        
        返回:
            Dict[str, Optional[float]]: benchmark -> running_time
        """
        self.result("\n=== 测试运行时间 - DuckDB ===")

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
        """运行所有 DuckDB 测试"""
        self.log("=" * 80)
        self.log("DuckDB 实验测试开始")
        self.log("=" * 80)
        
        # 1. 记录路径信息
        self.record_paths()
        
        # 2. 运行各个子实验（每个子实验会自行定义和保存配置）
        self.test_build_time(num_runs=3)
        self.test_planning_time(num_runs=3)
        self.test_running_time(num_runs=3)
        
        self.log("=" * 80)
        self.log("实验测试完成")
        self.log("=" * 80)


class InjectionTestRunner(ExperimentRunner):
    """注入型方法测试运行器（使用外部注入的基数）"""

    def __init__(self, project_root: Optional[str] = None):
        """
        初始化注入型测试运行器
        
        参数:
            project_root: 项目根目录
        """
        super().__init__(project_root)

    def inner_test_planning_time_with_injection(self, config: StarCEConfig, db_name: str, 
                                                queries_file: Path, 
                                                injected_card_path: str,
                                                card_est_time: float = 0.0,
                                                num_runs: int = 3) -> Optional[float]:
        """
        为特定数据库测试计划时间（使用注入基数）
        
        参数:
            config: 测试配置
            db_name: 数据库名称（用于显示，如 "STATS" 或 "JOBM"）
            queries_file: queries.sql文件路径
            injected_card_path: 注入的基数文件路径（SUBQUERY_RESULT_PATH）
            card_est_time: 纯基数估计时间（秒），不含 SQL 解析时间，用于加到 planning time 中
            num_runs: 运行次数
        
        返回:
            Optional[float]: 最终计划时间（秒），失败则返回 None

        注意:
            card_est_time 只包含估计器执行估计的时间，不包含 SQL 解析时间。
            SQL 解析是一次性工作，不应计入各查询的 planning time。
            计算公式: planning_time = explain_time - dummy_time + card_est_time
        """
        self.result(f"\n--- 测试计划时间（注入基数） ({db_name}) ---")
        self.log(f"开始测试计划时间（注入基数） ({db_name})，运行 {num_runs} 次")
        
        injected_card_path_obj = Path(injected_card_path).absolute()
        if not injected_card_path_obj.exists():
            self.result(f"错误 ({db_name}): 注入基数文件不存在: {injected_card_path_obj}")
            return None
        
        input_sql = self.running_space / "input.sql"
        
        # 1. 复制queries为input.sql并添加EXPLAIN
        try:
            self._prepare_input_sql_with_explain(queries_file, input_sql)
        except Exception as e:
            self.result(f"准备input.sql失败 ({db_name}): {e}")
            return None
        
        # 配置注入基数：设置UseSubqueryCard=1，并设置SUBQUERY_RESULT_PATH
        config.UseSubqueryCard = 1
        config.SUBQUERY_RESULT_PATH = str(injected_card_path_obj)
        # 使用input.sql进行测试
        config.SQL_PATH = "input.sql"
        self.save_config(config)
        
        times_input = []
        for i in range(num_runs):
            self.log(f"使用input.sql（注入基数）: 第 {i+1}/{num_runs} 次运行...")
            success, elapsed = self.run_starce(suppress_output=True)
            if success:
                times_input.append(elapsed)
            else:
                self.log(f"第 {i+1} 次运行失败，跳过", to_console=True)
        
        # 2. 使用dummy_query.sql进行测试
        config.SQL_PATH = "dummy_query.sql"
        self.save_config(config)
        
        times_dummy = []
        for i in range(num_runs):
            self.log(f"使用dummy_query.sql（注入基数）: 第 {i+1}/{num_runs} 次运行...")
            success, elapsed = self.run_starce(suppress_output=True)
            if success:
                times_dummy.append(elapsed)
            else:
                self.log(f"第 {i+1} 次运行失败，跳过", to_console=True)
        
        # 输出结果
        avg_time_input = None
        if times_input:
            avg_time_input = sum(times_input) / len(times_input)
            self.result(f"计划时间测试结果 ({db_name}) - 使用input.sql（注入基数）:")
            self.result(f"  成功运行次数: {len(times_input)}/{num_runs}")
            self.result(f"  平均计划时间: {avg_time_input:.2f} 秒")
            self.result(f"  最快: {min(times_input):.2f} 秒")
            self.result(f"  最慢: {max(times_input):.2f} 秒")
        else:
            self.result(f"计划时间测试失败 ({db_name}) - 使用input.sql: 所有运行都失败")
        
        avg_time_dummy = None
        if times_dummy:
            avg_time_dummy = sum(times_dummy) / len(times_dummy)
            self.result(f"计划时间测试结果 ({db_name}) - 使用dummy_query.sql（注入基数）:")
            self.result(f"  成功运行次数: {len(times_dummy)}/{num_runs}")
            self.result(f"  平均计划时间: {avg_time_dummy:.2f} 秒")
            self.result(f"  最快: {min(times_dummy):.2f} 秒")
            self.result(f"  最慢: {max(times_dummy):.2f} 秒")
        else:
            self.result(f"计划时间测试失败 ({db_name}) - 使用dummy_query.sql: 所有运行都失败")
        
        # 计算最终的planning time: explain time - dummy time + 基数估计时间
        if avg_time_input is not None and avg_time_dummy is not None:
            final_planning_time = avg_time_input - avg_time_dummy + card_est_time
            self.result(f"最终计划时间 ({db_name}): {final_planning_time:.2f} 秒 (explain time - dummy time + 基数估计时间 {card_est_time:.2f} 秒)")
            return final_planning_time
        else:
            self.result(f"无法计算最终计划时间 ({db_name}): explain time 或 dummy time 数据不足")
            return None

    def inner_test_running_time_with_injection(self, config: StarCEConfig, db_name: str,
                                               queries_file: Path,
                                               injected_card_path: str,
                                               num_runs: int = 3) -> Optional[float]:
        """
        为特定数据库测试运行时间（使用注入基数）
        
        参数:
            config: 测试配置
            db_name: 数据库名称（用于显示，如 "STATS" 或 "JOBM"）
            queries_file: queries.sql文件路径
            injected_card_path: 注入的基数文件路径（SUBQUERY_RESULT_PATH）
            num_runs: 运行次数
        
        返回:
            Optional[float]: 最终运行时间（秒），失败则返回 None
        """
        self.result(f"\n--- 测试运行时间（注入基数） ({db_name}) ---")
        self.log(f"开始测试运行时间（注入基数） ({db_name})，运行 {num_runs} 次")
        
        injected_card_path_obj = Path(injected_card_path).absolute()
        if not injected_card_path_obj.exists():
            self.result(f"错误 ({db_name}): 注入基数文件不存在: {injected_card_path_obj}")
            return None
        
        input_sql = self.running_space / "input.sql"
        explain_sql = self.running_space / "explain.sql"
        
        # 1. 准备普通的input.sql（不带EXPLAIN）
        try:
            self._prepare_input_sql_without_explain(queries_file, input_sql)
        except Exception as e:
            self.result(f"准备input.sql失败 ({db_name}): {e}")
            return None
        
        # 配置注入基数：设置UseSubqueryCard=1，并设置SUBQUERY_RESULT_PATH
        config.UseSubqueryCard = 1
        config.SUBQUERY_RESULT_PATH = str(injected_card_path_obj)
        # 使用input.sql（普通查询）进行测试
        config.SQL_PATH = "input.sql"
        self.save_config(config)
        
        times_input = []
        for i in range(num_runs):
            self.log(f"使用input.sql（普通查询，注入基数）: 第 {i+1}/{num_runs} 次运行...")
            success, elapsed = self.run_starce(suppress_output=True)
            if success:
                times_input.append(elapsed)
            else:
                self.log(f"第 {i+1} 次运行失败，跳过", to_console=True)
        
        # 2. 准备explain.sql（带EXPLAIN）
        try:
            self._prepare_input_sql_with_explain(queries_file, explain_sql)
        except Exception as e:
            self.result(f"准备explain.sql失败 ({db_name}): {e}")
            return None
        
        # 使用explain.sql进行测试
        config.SQL_PATH = "explain.sql"
        self.save_config(config)
        
        times_explain = []
        for i in range(num_runs):
            self.log(f"使用explain.sql（EXPLAIN查询，注入基数）: 第 {i+1}/{num_runs} 次运行...")
            success, elapsed = self.run_starce(suppress_output=True)
            if success:
                times_explain.append(elapsed)
            else:
                self.log(f"第 {i+1} 次运行失败，跳过", to_console=True)
        
        # 输出结果
        avg_time_input = None
        if times_input:
            avg_time_input = sum(times_input) / len(times_input)
            self.result(f"运行时间测试结果 ({db_name}) - 使用input.sql（普通查询，注入基数）:")
            self.result(f"  成功运行次数: {len(times_input)}/{num_runs}")
            self.result(f"  平均运行时间: {avg_time_input:.2f} 秒")
            self.result(f"  最快: {min(times_input):.2f} 秒")
            self.result(f"  最慢: {max(times_input):.2f} 秒")
        else:
            self.result(f"运行时间测试失败 ({db_name}) - 使用input.sql: 所有运行都失败")
        
        avg_time_explain = None
        if times_explain:
            avg_time_explain = sum(times_explain) / len(times_explain)
            self.result(f"运行时间测试结果 ({db_name}) - 使用explain.sql（EXPLAIN查询，注入基数）:")
            self.result(f"  成功运行次数: {len(times_explain)}/{num_runs}")
            self.result(f"  平均运行时间: {avg_time_explain:.2f} 秒")
            self.result(f"  最快: {min(times_explain):.2f} 秒")
            self.result(f"  最慢: {max(times_explain):.2f} 秒")
        else:
            self.result(f"运行时间测试失败 ({db_name}) - 使用explain.sql: 所有运行都失败")
        
        # 计算最终的running time: input.sql时间 - explain.sql时间
        if avg_time_input is not None and avg_time_explain is not None:
            final_running_time = avg_time_input - avg_time_explain
            self.result(f"最终运行时间 ({db_name}): {final_running_time:.2f} 秒 (input.sql时间 - explain.sql时间)")
            return final_running_time
        else:
            self.result(f"无法计算最终运行时间 ({db_name}): input.sql时间 或 explain.sql时间 数据不足")
            return None

    def test_build_time(self, num_runs: int = 3) -> None:
        """
        测试构建时间（注入型方法不需要构建统计信息）
        结果会直接写入result文件，不返回
        """
        self.result("\n=== 测试构建时间 - 注入型方法 ===")
        self.result("注入型方法不需要构建统计信息，跳过")
        self.log("注入型方法不需要构建统计信息，跳过")

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
        raise ValueError(f"不支持的benchmark: {benchmark}")

    def test_planning_time(self, benchmark: str, injected_card_path: str, 
                          card_est_time: float = 0.0, num_runs: int = 3) -> Optional[float]:
        """
        测试计划时间（使用注入基数）
        
        参数:
            benchmark: benchmark名称 ('STATS' / 'JOBM' / 'JOBLight' / 'JOBLightRanges')
            injected_card_path: 注入的基数文件路径（SUBQUERY_RESULT_PATH）
            card_est_time: 纯基数估计时间（秒），不含 SQL 解析时间，用于加到 planning time 中
            num_runs: 运行次数
        
        1. 复制queries为running_space/input.sql，添加EXPLAIN，计算时间
        2. 相同config，使用dummy_query.sql运行，计算时间
        3. 最终计划时间 = explain time - dummy time + 基数估计时间
        
        返回:
            Optional[float]: 最终计划时间（秒），失败则返回 None
        """
        self.result(f"\n=== 测试计划时间 - 注入型方法 ({benchmark}) ===")
        self.result(f"注入基数文件路径: {injected_card_path}")
        self.result(f"基数估计时间: {card_est_time:.2f} 秒")

        try:
            config, queries_file, db_name = self._get_injection_benchmark_context(benchmark)
        except ValueError as e:
            self.result(f"错误: {e}")
            return None

        return self.inner_test_planning_time_with_injection(
            config, db_name, queries_file, injected_card_path, card_est_time, num_runs
        )

    def test_running_time(self, benchmark: str, injected_card_path: str, 
                         num_runs: int = 3) -> Optional[float]:
        """
        测试运行时间（使用注入基数）
        
        参数:
            benchmark: benchmark名称 ('STATS' / 'JOBM' / 'JOBLight' / 'JOBLightRanges')
            injected_card_path: 注入的基数文件路径（SUBQUERY_RESULT_PATH）
            num_runs: 运行次数
        
        1. 使用普通查询（input.sql）计算时间
        2. 使用EXPLAIN查询（explain.sql）计算时间
        3. 最终运行时间 = input.sql时间 - explain.sql时间
        
        返回:
            Optional[float]: 最终运行时间（秒），失败则返回 None
        """
        self.result(f"\n=== 测试运行时间 - 注入型方法 ({benchmark}) ===")
        self.result(f"注入基数文件路径: {injected_card_path}")

        try:
            config, queries_file, db_name = self._get_injection_benchmark_context(benchmark)
        except ValueError as e:
            self.result(f"错误: {e}")
            return None

        return self.inner_test_running_time_with_injection(
            config, db_name, queries_file, injected_card_path, num_runs
        )

    def run(self, benchmark: str, injected_card_path: str, 
            card_est_time: float = 0.0, num_runs: int = 3):
        """
        运行注入型方法测试
        
        参数:
            benchmark: benchmark名称 ('STATS' 或 'JOBM')
            injected_card_path: 注入的基数文件路径（SUBQUERY_RESULT_PATH）
            card_est_time: 纯基数估计时间（秒），不含 SQL 解析时间，用于加到 planning time 中
            num_runs: 运行次数
        """
        self.log("=" * 80)
        self.log(f"注入型方法实验测试开始 ({benchmark})")
        self.log("=" * 80)
        
        # 1. 记录路径信息
        self.record_paths()
        
        self.result(f"Benchmark: {benchmark}")
        self.result(f"注入基数文件路径: {injected_card_path}")
        self.result(f"基数估计时间: {card_est_time:.2f} 秒")
        
        # 2. 运行各个子实验
        self.test_build_time(num_runs=num_runs)
        self.test_planning_time(benchmark, injected_card_path, card_est_time, num_runs)
        self.test_running_time(benchmark, injected_card_path, num_runs)
        
        self.log("=" * 80)
        self.log("实验测试完成")
        self.log("=" * 80)


def main():
    """主函数"""
    import sys
    
    # 可以接受项目根目录作为可选参数
    project_root_str = sys.argv[1] if len(sys.argv) > 1 else None
    
    # 确定项目根目录
    script_dir = Path(__file__).parent.absolute()
    if project_root_str:
        project_root = Path(project_root_str).absolute()
    else:
        project_root = script_dir.parent
    
    running_space = script_dir / "running_space"
    running_space.mkdir(exist_ok=True)
    
    # 复制 starce 可执行文件（所有实验的前置步骤，失败会直接退出）
    setup_starce_executable(project_root, running_space)
    
    # 创建 runner 并运行实验
    runner_starce = StarCETestRunner(str(project_root))
    runner_starce.run()
    runner_duckdb = DuckDBTestRunner(str(project_root))
    runner_duckdb.run()


if __name__ == "__main__":
    main()
