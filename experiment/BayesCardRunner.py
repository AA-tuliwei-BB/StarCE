#!/usr/bin/env python3
"""
BayesCard experiment orchestration module (pure BayesCard path).

Training and inference reuse the corresponding BayesCard components from methods/SafeBound/test_benchmark.py.
"""

from __future__ import annotations

import os
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BenchmarkConfig:
    benchmark: str
    sb_benchmark: str
    data_path_pattern: str
    query_file: Path
    checkpoint_output: Path
    model_dir: Path
    hdf_dir: Path
    preprocessed_dir: Path | None = None
    preprocessed_query_file: Path | None = None


class BayesCardRunner:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.experiment_dir = Path(__file__).resolve().parent
        self.project_root = Path(project_root).resolve() if project_root else self.experiment_dir.parent
        self.checkpoint_dir = self.experiment_dir / "checkpoint" / "BayesCard"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.summary_csv_path = self.checkpoint_dir / "benchmark_times.csv"
        self.workload_dir = self.project_root / "Benchmark" / "workloads"

        self.stats_data_pattern = str(self.project_root / "methods" / "SafeBound" / "Data" / "Stats" / "{}.csv")
        self.imdb_data_pattern = str(self.project_root / "methods" / "SafeBound" / "Data" / "IMDB" / "{}.csv")

        self.safebound_dir = self.project_root / "methods" / "SafeBound"
        self._sb = self._load_safebound_bayescard_module()
        from DeepDBUtils.evaluation.utils import timestamp_transorform  # type: ignore

        self._timestamp_transform = timestamp_transorform

    def _load_safebound_bayescard_module(self) -> Any:
        safebound_dir_str = str(self.safebound_dir)
        if safebound_dir_str not in sys.path:
            sys.path.insert(0, safebound_dir_str)
        import test_benchmark as sb  # type: ignore

        return sb

    @staticmethod
    def _normalize_benchmark_name(benchmark: str) -> str:
        token = benchmark.strip().lower()
        mapping = {
            "stats": "STATS",
            "stats-ceb": "STATS",
            "joblight": "JOBLight",
            "joblightranges": "JOBLightRanges",
            "joblr": "JOBLightRanges",
            "jobm": "JOBM",
            "statsjoin": "STATSJOIN",
        }
        if token not in mapping:
            raise ValueError(f"Unknown benchmark: {benchmark}")
        return mapping[token]

    @staticmethod
    def evaluate_benchmark_capability(benchmark: str) -> tuple[bool, str]:
        normalized = BayesCardRunner._normalize_benchmark_name(benchmark)
        if normalized == "JOBM":
            reason = (
                "Does not support pure BayesCard: JOBM's reliable path in the current repo depends on sampling/extra processing,"
                "not pure BayesCard BN inference."
            )
            return False, reason
        if normalized == "STATSJOIN":
            return True, "Supported: reuses STATS BN model, inference only, no training needed."
        if normalized in {"STATS", "JOBLight", "JOBLightRanges"}:
            return True, "Supported: can follow the pure BayesCard training and inference path under methods/SafeBound/bayescard."
        raise ValueError(f"Unhandled benchmark: {benchmark}")

    def _build_config(self, benchmark: str) -> BenchmarkConfig:
        normalized = self._normalize_benchmark_name(benchmark)
        supported, reason = self.evaluate_benchmark_capability(normalized)
        if not supported:
            raise ValueError(f"{normalized} Not runnable. Reason: {reason}")

        if normalized == "STATS":
            return BenchmarkConfig(
                benchmark="STATS",
                sb_benchmark="stats",
                data_path_pattern=self.stats_data_pattern,
                query_file=self.workload_dir / "STATS-CEB" / "subquery" / "subquery.sql",
                checkpoint_output=self.checkpoint_dir / "card_stats.txt",
                model_dir=self.checkpoint_dir / "models" / "stats",
                hdf_dir=self.checkpoint_dir / "hdf" / "stats",
            )

        if normalized == "STATSJOIN":
            return BenchmarkConfig(
                benchmark="STATSJOIN",
                sb_benchmark="stats",
                data_path_pattern=self.stats_data_pattern,
                query_file=self.workload_dir / "StatsJoin" / "subquery" / "subquery.sql",
                checkpoint_output=self.checkpoint_dir / "card_statsjoin.txt",
                model_dir=self.checkpoint_dir / "models" / "stats",
                hdf_dir=self.checkpoint_dir / "hdf" / "stats",
            )

        if normalized == "JOBLight":
            return BenchmarkConfig(
                benchmark="JOBLight",
                sb_benchmark="joblight",
                data_path_pattern=self.imdb_data_pattern,
                query_file=self.workload_dir / "JOBLight" / "subquery" / "subquery.sql",
                checkpoint_output=self.checkpoint_dir / "card_joblight.txt",
                model_dir=self.checkpoint_dir / "models" / "joblight",
                hdf_dir=self.checkpoint_dir / "hdf" / "joblight",
            )

        preprocessed_dir = self.checkpoint_dir / "preprocessed" / "joblightranges"
        return BenchmarkConfig(
            benchmark="JOBLightRanges",
            sb_benchmark="joblightranges",
            data_path_pattern=self.imdb_data_pattern,
            query_file=self.workload_dir / "JOBLightRanges" / "subquery" / "subquery.sql",
            checkpoint_output=self.checkpoint_dir / "card_joblr.txt",
            model_dir=self.checkpoint_dir / "models" / "joblightranges",
            hdf_dir=self.checkpoint_dir / "hdf" / "joblightranges",
            preprocessed_dir=preprocessed_dir,
            preprocessed_query_file=self.checkpoint_dir / "preprocessed" / "joblightranges_subquery.sql",
        )

    @staticmethod
    def _require_file(path: Path) -> None:
        if not path.is_file():
            raise FileNotFoundError(f"Missing file: {path}")

    @staticmethod
    def _read_non_empty_lines(path: Path) -> list[str]:
        with open(path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]

    def _train_pure_bayescard(self, config: BenchmarkConfig, csv_path_pattern: str) -> None:
        config.model_dir.mkdir(parents=True, exist_ok=True)
        config.hdf_dir.mkdir(parents=True, exist_ok=True)
        schema = self._sb.get_schema(config.sb_benchmark, csv_path_pattern)
        stats_flag = self._sb.is_stats_benchmark(config.sb_benchmark)

        self._sb.prepare_all_tables(
            schema,
            str(config.hdf_dir),
            max_table_data=20_000_000,
            stats=stats_flag,
        )

        prep = self._sb.JoinDataPreparator(
            str(config.hdf_dir / "meta_data.pkl"),
            schema,
            max_table_data=20_000_000,
        )

        for i, relationship_obj in enumerate(schema.relationships):
            relation = [relationship_obj.identifier]
            df, meta_types, null_values, full_join_est = prep.generate_n_samples(
                10_000_000,
                relationship_list=relation,
                post_sampling_factor=10,
            )
            columns = list(df.columns)
            meta_info = self._sb.build_meta_info(df.columns, null_values)
            bn = self._sb.Bayescard_BN(
                schema,
                relation,
                column_names=columns,
                full_join_size=full_join_est,
                table_meta_data=prep.table_meta_data,
                meta_types=meta_types,
                null_values=null_values,
                meta_info=meta_info,
            )
            bn.build_from_data(
                df,
                algorithm="chow-liu",
                max_parents=1,
                ignore_cols=["id", "Id"],
                sample_size=200000,
            )
            model_path = config.model_dir / f"{i}_chow-liu_1.pkl"
            with open(model_path, "wb") as f:
                self._sb.pickle.dump(bn, f, self._sb.pickle.HIGHEST_PROTOCOL)

    def _estimate_one_query_strict(self, bn_ensemble: Any, schema: Any, query: str, parsed: Any = None) -> float:
        if parsed is None:
            parsed = self._sb.parse_query(query, schema)
        first_bn, next_mergeable_relationships, next_mergeable_tables = (
            bn_ensemble._greedily_select_first_cardinality_bn(
                parsed,
                rdc_spn_selection=True,
                rdc_attribute_dict={},
            )
        )
        factors = self._sb.generate_factors(
            bn_ensemble,
            parsed,
            first_bn,
            next_mergeable_relationships,
            next_mergeable_tables,
            rdc_bn_selection=True,
            rdc_attribute_dict={},
            merge_indicator_exp=True,
            exploit_incoming_multipliers=True,
            prefer_disjunct=False,
        )
        factors = self._sb.factor_refine(factors)

        parse_result = []
        for factor in factors:
            if isinstance(factor, self._sb.IndicatorExpectation):
                range_conditions = factor.spn._parse_conditions(
                    factor.conditions,
                    group_by_columns=None,
                    group_by_tuples=None,
                )
                actual_query, fanout = self._sb.prepare_single_query(range_conditions, factor)
                parse_result.append(
                    {
                        "bn_index": bn_ensemble.bns.index(factor.spn),
                        "inverse": factor.inverse,
                        "query": actual_query,
                        "expectation": fanout,
                    }
                )
            elif isinstance(factor, self._sb.Expectation):
                raise NotImplementedError("Expectation factors not supported")
            else:
                parse_result.append(factor)

        processed = bn_ensemble.parse_query_all([parse_result])
        estimate = bn_ensemble.cardinality(processed[0])
        if isinstance(estimate, np.ndarray):
            estimate = float(estimate[0])
        if estimate is None or float(estimate) <= 0:
            raise ValueError(f"Invalid estimate: {estimate}")
        return float(estimate)

    def _infer_pure_bayescard(
        self,
        config: BenchmarkConfig,
        schema_csv_path_pattern: str,
        query_file: Path,
        output_file: Path,
    ) -> dict[str, Any]:
        schema = self._sb.get_schema(config.sb_benchmark, schema_csv_path_pattern)
        bn_ensemble = self._sb.load_ensemble_sorted(schema, str(config.model_dir))
        queries = self._read_non_empty_lines(query_file)

        results: list[float] = []
        latencies: list[float] = []
        errors: list[str] = []

        # Pre-parse all queries (not counted towards estimation time)
        pre_parsed = []
        for idx, query in enumerate(queries):
            sql = query.split("||")[0].rstrip(";").strip()
            pre_parsed.append(self._sb.parse_query(sql, schema))

        for idx, query in enumerate(queries):
            sql = query.split("||")[0].rstrip(";").strip()
            t0 = time.time()
            try:
                estimate = self._estimate_one_query_strict(bn_ensemble, schema, sql, parsed=pre_parsed[idx])
                results.append(estimate)
            except Exception as e:
                errors.append(f"idx={idx} err={e} sql={sql[:160]}")
            latencies.append(time.time() - t0)

        if errors:
            preview = "\n".join(errors[:10])
            raise RuntimeError(
                f"BayesCard inference failed on {len(errors)} queries (total {len(queries)}).\n{preview}"
            )

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            for r in results:
                f.write(f"{r}\n")

        bench_name = output_file.stem.replace('card_', '')  # stats, joblight, joblr
        bench_display = {'stats': 'STATS', 'joblight': 'JOBLight', 'joblr': 'JOBLightRanges'}.get(bench_name, bench_name.upper())
        time_file = output_file.parent / f"estimate_time_{bench_display}.txt"
        with open(time_file, "w", encoding="utf-8") as f:
            for lat in latencies:
                f.write(f"{lat}\n")

        return {
            "query_count": len(results),
            "avg_latency_sec": (sum(latencies) / len(latencies)) if latencies else 0.0,
            "time_file": str(time_file),
        }

    def _assert_line_alignment(self, sql_path: Path, result_path: Path) -> None:
        sql_count = len(self._read_non_empty_lines(sql_path))
        result_count = len(self._read_non_empty_lines(result_path))
        if sql_count != result_count:
            raise RuntimeError(f"Line count mismatch: {sql_path}={sql_count}, {result_path}={result_count}")

    def _preprocess_stats_queries(self, src_sql: Path, dst_sql: Path) -> Path:
        self._require_file(src_sql)
        with open(src_sql, "r", encoding="utf-8") as f:
            sql_lines = f.readlines()

        pattern = r"'([^']+)'::timestamp"
        converted: list[str] = []
        for line in sql_lines:
            def replace_one(match: re.Match[str]) -> str:
                ts = match.group(1)
                return str(self._timestamp_transform(f"'{ts}'"))

            converted.append(re.sub(pattern, replace_one, line))

        dst_sql.parent.mkdir(parents=True, exist_ok=True)
        with open(dst_sql, "w", encoding="utf-8") as f:
            for line in converted:
                f.write(line)
        return dst_sql

    def _preprocess_stats_csv(self, src_csv_pattern: str, dst_dir: Path) -> str:
        """
        Convert time columns in STATS CSVs to integers relative to start time.
        This way BayesCard treats time columns as continuous values for range predicates.
        """
        src_dir = Path(src_csv_pattern.replace("{}.csv", "")).resolve()
        if not src_dir.is_dir():
            raise FileNotFoundError(f"STATS source directory not found: {src_dir}")

        dst_dir.mkdir(parents=True, exist_ok=True)
        for src_file in src_dir.glob("*.csv"):
            df = pd.read_csv(src_file)
            for col in df.columns:
                if "Date" not in col:
                    continue
                if df[col].dtype == object:
                    df[col] = df[col].apply(
                        lambda x: self._timestamp_transform(f"'{str(x)}'") if pd.notna(x) else x
                    )
            df.to_csv(dst_dir / src_file.name, index=False)

        return str(dst_dir / "{}.csv")

    def _total_model_size_bytes(self, model_dir: Path) -> int:
        total = 0
        found = False
        for p in model_dir.glob("*.pkl"):
            total += int(p.stat().st_size)
            found = True
        if not found:
            raise FileNotFoundError(f"Model directory empty or no .pkl files: {model_dir}")
        return total

    def _upsert_summary_row(self, row: dict[str, Any]) -> pd.DataFrame:
        if self.summary_csv_path.exists():
            df = pd.read_csv(self.summary_csv_path)
            if "benchmark" in df.columns:
                # Delete rows with same name
                df = df[df["benchmark"] != row["benchmark"]]
                # Also delete alias rows that normalize to the same (e.g. STATS-CEB -> STATS)
                try:
                    target = BayesCardRunner._normalize_benchmark_name(row["benchmark"])
                    mask = df["benchmark"].apply(
                        lambda x: BayesCardRunner._normalize_benchmark_name(str(x)) == target
                    )
                    df = df[~mask]
                except (ValueError, KeyError):
                    pass
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        else:
            df = pd.DataFrame([row])

        preferred = [
            "benchmark",
            "total_eval_like_time_sec",
            "checkpoint_output",
            "train_time_sec",
            "total_build_like_time_sec",
            "preprocess_time_sec",
            "query_count",
            "avg_latency_sec",
            "model_dir",
            "statistics_size_bytes",
            "seed",
        ]
        # Drop legacy model_path columns
        df = df[[c for c in preferred if c in df.columns]]
        df.to_csv(self.summary_csv_path, index=False)
        return df

    def run_benchmark(self, benchmark: str, seed: int = 0,
                      force_retrain: bool = False) -> dict[str, Any]:
        random.seed(seed)
        np.random.seed(seed)
        config = self._build_config(benchmark)
        self._require_file(config.query_file)

        # STATSJOIN reuses STATS model, does not train itself
        if config.benchmark == "STATSJOIN":
            force_retrain = False

        # force_retrain: delete existing model files, force training from scratch
        if force_retrain and config.model_dir.exists():
            import shutil
            for pkl in config.model_dir.glob("*.pkl"):
                pkl.unlink()
            if config.hdf_dir.exists():
                shutil.rmtree(config.hdf_dir)
            print(f"  force_retrain: cleaned up {config.model_dir} and {config.hdf_dir}")

        preprocess_time_sec = 0.0
        data_path_for_schema = config.data_path_pattern
        query_for_eval = config.query_file

        if config.benchmark == "STATS":
            stats_preprocessed_query = self.checkpoint_dir / "preprocessed" / "stats_subquery.sql"
            stats_preprocessed_csv_dir = self.checkpoint_dir / "preprocessed" / "stats_csv"
            t0 = time.time()
            data_path_for_schema = self._preprocess_stats_csv(config.data_path_pattern, stats_preprocessed_csv_dir)
            query_for_eval = self._preprocess_stats_queries(config.query_file, stats_preprocessed_query)
            preprocess_time_sec = time.time() - t0
        elif config.benchmark == "JOBLightRanges":
            if config.preprocessed_dir is None or config.preprocessed_query_file is None:
                raise ValueError("JOBLightRanges missing preprocessing config")
            config.preprocessed_dir.mkdir(parents=True, exist_ok=True)
            t0 = time.time()
            data_path_for_schema = self._sb.preprocess_joblr_csv(
                config.data_path_pattern,
                str(config.preprocessed_dir),
            )
            self._sb.preprocess_joblr_subquery_sql(
                str(config.query_file),
                str(config.preprocessed_query_file),
            )
            preprocess_time_sec = time.time() - t0
            query_for_eval = config.preprocessed_query_file
            self._require_file(query_for_eval)

        # Training (skip if model exists and not force_retrain; STATSJOIN also skips as it reuses STATS model)
        train_time_sec = 0.0
        if not any(config.model_dir.glob("*.pkl")):
            t0 = time.time()
            self._train_pure_bayescard(
                BenchmarkConfig(
                    benchmark=config.benchmark,
                    sb_benchmark=config.sb_benchmark,
                    data_path_pattern=data_path_for_schema,
                    query_file=config.query_file,
                    checkpoint_output=config.checkpoint_output,
                    model_dir=config.model_dir,
                    hdf_dir=config.hdf_dir,
                    preprocessed_dir=config.preprocessed_dir,
                    preprocessed_query_file=config.preprocessed_query_file,
                ),
                data_path_for_schema,
            )
            train_time_sec = time.time() - t0

        t0 = time.time()
        infer_meta = self._infer_pure_bayescard(
            config,
            data_path_for_schema,
            query_for_eval,
            config.checkpoint_output,
        )
        eval_time_sec = time.time() - t0

        self._assert_line_alignment(query_for_eval, config.checkpoint_output)
        model_size = self._total_model_size_bytes(config.model_dir)

        row = {
            "benchmark": config.benchmark,
            "seed": seed,
            "preprocess_time_sec": preprocess_time_sec,
            "train_time_sec": train_time_sec,
            "total_build_like_time_sec": preprocess_time_sec + train_time_sec,
            "total_eval_like_time_sec": eval_time_sec,
            "query_count": infer_meta["query_count"],
            "avg_latency_sec": infer_meta["avg_latency_sec"],
            "checkpoint_output": str(config.checkpoint_output),
            "model_dir": str(config.model_dir),
            "statistics_size_bytes": model_size,
        }
        self._upsert_summary_row(row)
        return row

    def run_all(self, benchmarks: list[str], seed: int = 0,
                force_retrain: bool = False) -> pd.DataFrame:
        rows = []
        for benchmark in benchmarks:
            rows.append(self.run_benchmark(benchmark, seed=seed,
                                           force_retrain=force_retrain))
        return pd.DataFrame(rows)


def evaluate_benchmark_capability(benchmark: str) -> tuple[bool, str]:
    return BayesCardRunner.evaluate_benchmark_capability(benchmark)


def run_benchmark(benchmark: str, seed: int = 0) -> dict[str, Any]:
    return BayesCardRunner().run_benchmark(benchmark, seed=seed)


def run_all(benchmarks: list[str], seed: int = 0) -> pd.DataFrame:
    return BayesCardRunner().run_all(benchmarks=benchmarks, seed=seed)

