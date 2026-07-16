#!/usr/bin/env python
"""
BayesCard Benchmark Wrapper
============================
Unified script for training and inference on STATS-CEB, JOBLight, JOBLightRanges, JOBM.

Subcommands:
  train         Train BayesCard BN ensemble models for a specific benchmark.
  infer         Run cardinality estimation on a subquery file using trained models.

Examples
--------
# STATS-CEB – train then infer
python test_benchmark.py train --benchmark stats \
    --csv_path Data/Stats/{}.csv \
    --hdf_path checkpoints/stats_hdf \
    --model_dir checkpoints/stats_models

python test_benchmark.py infer --benchmark stats \
    --csv_path Data/Stats/{}.csv \
    --model_dir checkpoints/stats_models \
    --query_file ../../Benchmark/workloads/STATS-CEB/subquery/subquery.sql \
    --output_file ../../Benchmark/workloads/STATS-CEB/subquery/result/bayescard.txt

# JOBLight – train then infer
python test_benchmark.py train --benchmark joblight \
    --csv_path Data/IMDB/{}.csv \
    --hdf_path checkpoints/imdb_light_hdf \
    --model_dir checkpoints/joblight_models

python test_benchmark.py infer --benchmark joblight \
    --csv_path Data/IMDB/{}.csv \
    --model_dir checkpoints/joblight_models \
    --query_file ../../Benchmark/workloads/JOBLight/subquery/subquery.sql \
    --output_file ../../Benchmark/workloads/JOBLight/subquery/result/bayescard.txt

# JOBLightRanges – train (includes data preprocessing) then infer
python test_benchmark.py train --benchmark joblightranges \
    --csv_path Data/IMDB/{}.csv \
    --hdf_path checkpoints/joblr_hdf \
    --model_dir checkpoints/joblr_models \
    --preprocessed_dir checkpoints/joblr_preprocessed

python test_benchmark.py infer --benchmark joblightranges \
    --csv_path Data/IMDB/{}.csv \
    --model_dir checkpoints/joblr_models \
    --query_file ../../Benchmark/workloads/JOBLightRanges/subquery/subquery.sql \
    --output_file ../../Benchmark/workloads/JOBLightRanges/subquery/result/bayescard.txt

# JOBM – train then infer
python test_benchmark.py train --benchmark jobm \
    --csv_path Data/IMDB/{}.csv \
    --hdf_path checkpoints/imdb_full_hdf \
    --model_dir checkpoints/jobm_models

python test_benchmark.py infer --benchmark jobm \
    --csv_path Data/IMDB/{}.csv \
    --model_dir checkpoints/jobm_models \
    --query_file ../../Benchmark/workloads/JOBM/subquery/subquery.sql \
    --output_file ../../Benchmark/workloads/JOBM/subquery/result/bayescard.txt
"""

import argparse
import logging
import os
import pickle
import re
import shutil
import sys
import time

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Path setup – add bayescard/ to sys.path so its internal imports work
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BAYESCARD_DIR = os.path.join(_SCRIPT_DIR, "bayescard")
sys.path.insert(0, _BAYESCARD_DIR)

from Schemas.stats.schema import gen_stats_light_schema
from Schemas.imdb.schema import (
    gen_job_light_imdb_schema,
    gen_job_light_ranges_schema,
    gen_imdb_schema,
)
from DataPrepare.prepare_single_tables import prepare_all_tables
from DataPrepare.join_data_preparation import JoinDataPreparator
from Models.Bayescard_BN import Bayescard_BN, build_meta_info
from Models.BN_ensemble_model import BN_ensemble

# DeepDBUtils compatibility shims (needed for pickle loading)
from DeepDBUtils import ensemble_compilation, aqp_spn, rspn

sys.modules["ensemble_compilation"] = ensemble_compilation
sys.modules["aqp_spn"] = aqp_spn
sys.modules["rspn"] = rspn

from bayescard.Evaluation.utils import parse_query
from DeepDBUtils.ensemble_compilation.probabilistic_query import (
    IndicatorExpectation,
    Expectation,
)
from DataPrepare.query_prepare_BayesCard import (
    generate_factors,
    factor_refine,
    prepare_single_query,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5.5s]  %(message)s",
    handlers=[
        logging.FileHandler(
            "logs/bayescard_{}.log".format(time.strftime("%Y%m%d-%H%M%S"))
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ===================================================================
#  Schema helpers
# ===================================================================

def get_schema(benchmark, csv_path):
    """Return the BayesCard SchemaGraph for the given benchmark."""
    bm = benchmark.lower()
    if bm == "stats":
        return gen_stats_light_schema(csv_path)
    elif bm == "joblight":
        return gen_job_light_imdb_schema(csv_path)
    elif bm == "joblightranges":
        return gen_job_light_ranges_schema(csv_path)
    elif bm == "jobm":
        return gen_imdb_schema(csv_path)
    else:
        raise ValueError(f"Unknown benchmark: {benchmark}")


def is_stats_benchmark(benchmark):
    """Return True if the benchmark uses Stats CSV data (has headers)."""
    return benchmark.lower() == "stats"


# ===================================================================
#  JOBLightRanges preprocessing helpers
# ===================================================================

def _convert_phonetic_code_to_int(code):
    """Convert a phonetic code like 'A1234' to an integer representation."""
    if not code or not isinstance(code, str):
        return code
    try:
        letter_val = (ord(code[0].upper()) - ord("A")) * 100000
        digits = int(code[1:]) if len(code) > 1 else 0
        return letter_val + digits
    except (ValueError, IndexError):
        return code


def _roman_to_int(s):
    """Convert a Roman numeral string to an integer."""
    roman_map = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    result = 0
    prev = 0
    for ch in reversed(s.upper()):
        val = roman_map.get(ch, 0)
        if val < prev:
            result -= val
        else:
            result += val
        prev = val
    return result


def preprocess_joblr_csv(src_csv_path_template, dst_dir):
    """
    Copy IMDB CSV files to *dst_dir* and convert the title table's
    phonetic_code / series_years / imdb_index columns from strings to integers.

    Returns the csv_path template pointing to the preprocessed directory.
    """
    os.makedirs(dst_dir, exist_ok=True)
    src_dir = os.path.dirname(src_csv_path_template.replace("{}.csv", ""))
    if not src_dir:
        src_dir = "."

    # Copy all csv files
    for fname in os.listdir(src_dir):
        if fname.endswith(".csv"):
            src = os.path.join(src_dir, fname)
            dst = os.path.join(dst_dir, fname)
            if not os.path.exists(dst):
                shutil.copy2(src, dst)

    # Preprocess title.csv
    title_path = os.path.join(dst_dir, "title.csv")
    logger.info("Preprocessing title.csv for JOBLightRanges -> %s", title_path)
    # IMDB CSV has no header
    df = pd.read_csv(
        title_path, header=None, escapechar="\\", encoding="utf-8",
        quotechar='"', sep=",", low_memory=False,
    )
    # title table columns: id, title, imdb_index, kind_id, production_year, imdb_id,
    #                       phonetic_code, episode_of_id, season_nr, episode_nr,
    #                       series_years, md5sum
    col_phonetic = 6   # phonetic_code
    col_imdb_idx = 2   # imdb_index
    col_series = 10    # series_years

    # phonetic_code -> int
    df[col_phonetic] = df[col_phonetic].apply(
        lambda x: _convert_phonetic_code_to_int(str(x)) if pd.notna(x) else x
    )

    # imdb_index (Roman numeral) -> int
    df[col_imdb_idx] = df[col_imdb_idx].apply(
        lambda x: _roman_to_int(str(x)) if pd.notna(x) and str(x).strip() else x
    )

    # series_years 'YYYY-YYYY' -> start year int
    def _parse_series_years(val):
        if pd.isna(val):
            return val
        s = str(val).strip()
        if not s:
            return val
        m = re.match(r"(\d{4}|\?{4})", s)
        if m:
            year_str = m.group(1)
            if year_str == "????":
                return 0
            return int(year_str)
        return val

    df[col_series] = df[col_series].apply(_parse_series_years)

    df.to_csv(title_path, header=False, index=False)
    logger.info("title.csv preprocessed with %d rows", len(df))
    return os.path.join(dst_dir, "{}.csv")


def preprocess_joblr_subquery_sql(src_sql_path, dst_sql_path):
    """
    Apply string-to-int conversions for JOBLightRanges subquery SQL
    (phonetic_code, series_years, imdb_index).
    """
    with open(src_sql_path, "r") as f:
        sql_queries = f.readlines()

    new_queries = []
    for query in sql_queries:
        # Convert title alias predicates regardless of alias token (e.g. t / title1 / title).
        query = re.sub(
            r"([A-Za-z_][A-Za-z0-9_]*)\.phonetic_code\s*(<=|>=|=|<|>)\s*'([A-Z]\d*)'",
            lambda m: (
                f"{m.group(1)}.phonetic_code{m.group(2)}"
                f"{_convert_phonetic_code_to_int(m.group(3))}"
            ),
            query,
        )

        query = re.sub(
            r"([A-Za-z_][A-Za-z0-9_]*)\.series_years\s*(<=|>=|=|<|>)\s*'(\d{4}|[?]{4})-(\d{4}|[?]{4})'",
            lambda m: (
                f"{m.group(1)}.series_years{m.group(2)}"
                f"{0 if m.group(3) == '????' else int(m.group(3))}"
            ),
            query,
        )

        query = re.sub(
            r"([A-Za-z_][A-Za-z0-9_]*)\.imdb_index\s*(<=|>=|=|<|>)\s*'([IVXLCDM]+)'",
            lambda m: f"{m.group(1)}.imdb_index{m.group(2)}{_roman_to_int(m.group(3))}",
            query,
        )

        new_queries.append(query)

    os.makedirs(os.path.dirname(dst_sql_path) or ".", exist_ok=True)
    with open(dst_sql_path, "w") as f:
        for q in new_queries:
            f.write(q)
    logger.info(
        "Preprocessed %d JOBLightRanges subqueries -> %s", len(new_queries), dst_sql_path
    )
    return dst_sql_path


# ===================================================================
#  Model loading helper (deterministic ordering)
# ===================================================================

def load_ensemble_sorted(schema, model_dir):
    """
    Load BayesCard BN ensemble from *model_dir* with deterministic file ordering.
    """
    model_dir_slash = model_dir.rstrip("/") + "/"
    bn_ensemble = BN_ensemble(schema)
    pkl_files = sorted(
        f for f in os.listdir(model_dir_slash) if f.endswith(".pkl")
    )
    if not pkl_files:
        raise FileNotFoundError(f"No .pkl model files found in {model_dir_slash}")
    for fname in pkl_files:
        fpath = model_dir_slash + fname
        with open(fpath, "rb") as f:
            bn = pickle.load(f)
            bn.infer_algo = "exact-jit"
            bn.init_inference_method()
        bn_ensemble.bns.append(bn)
        logger.info("Loaded BN model: %s", fname)
    logger.info("Loaded %d BN models from %s", len(bn_ensemble.bns), model_dir)
    return bn_ensemble


# ===================================================================
#  Sub-command: train
# ===================================================================

def cmd_train(args):
    benchmark = args.benchmark.lower()
    csv_path = args.csv_path
    hdf_path = args.hdf_path
    model_dir = args.model_dir
    algorithm = args.algorithm
    max_parents = args.max_parents
    sample_size = args.sample_size
    df_sample_size = args.df_sample_size

    os.makedirs(hdf_path, exist_ok=True)
    os.makedirs(model_dir, exist_ok=True)

    start_time = time.time()
    stats_flag = is_stats_benchmark(benchmark)

    # For JOBLightRanges, preprocess CSV data first
    actual_csv_path = csv_path
    if benchmark == "joblightranges":
        preprocessed_dir = args.preprocessed_dir
        if preprocessed_dir is None:
            preprocessed_dir = os.path.join(model_dir, "imdb_preprocessed")
        actual_csv_path = preprocess_joblr_csv(csv_path, preprocessed_dir)
        logger.info("Using preprocessed data at %s", actual_csv_path)

    schema = get_schema(benchmark, actual_csv_path)

    # Step 1: Generate HDF files from CSV
    logger.info("Generating HDF files in %s ...", hdf_path)
    prepare_all_tables(schema, hdf_path, max_table_data=args.max_table_data, stats=stats_flag)
    logger.info("HDF generation complete.")

    # Step 2: Train BN models (one per relationship)
    meta_data_path = hdf_path + "/meta_data.pkl"
    prep = JoinDataPreparator(meta_data_path, schema, max_table_data=args.max_table_data)

    logger.info("Training BN ensemble on %d relationships:", len(schema.relationships))
    for rel_obj in schema.relationships:
        logger.info("  %s", rel_obj.identifier)

    for i, relationship_obj in enumerate(schema.relationships):
        relation = [relationship_obj.identifier]
        logger.info(
            "Training BN %d/%d on %s ...",
            i + 1, len(schema.relationships), relation[0],
        )
        df, meta_types, null_values, full_join_est = prep.generate_n_samples(
            df_sample_size, relationship_list=relation, post_sampling_factor=10
        )
        columns = list(df.columns)
        assert len(columns) == len(meta_types) == len(null_values)
        meta_info = build_meta_info(df.columns, null_values)

        bn = Bayescard_BN(
            schema, relation, column_names=columns,
            full_join_size=full_join_est,
            table_meta_data=prep.table_meta_data,
            meta_types=meta_types, null_values=null_values,
            meta_info=meta_info,
        )
        bn.build_from_data(
            df, algorithm=algorithm, max_parents=max_parents,
            ignore_cols=["id", "Id"], sample_size=sample_size,
        )

        model_path = os.path.join(model_dir, f"{i}_{algorithm}_{max_parents}.pkl")
        with open(model_path, "wb") as f:
            pickle.dump(bn, f, pickle.HIGHEST_PROTOCOL)
        logger.info("Model saved: %s", model_path)

    elapsed = time.time() - start_time
    logger.info("Training completed in %.1f seconds.", elapsed)



# ===================================================================
#  Sub-command: infer
# ===================================================================

def cmd_infer(args):
    """
    Unified inference for all 4 benchmarks.
    Reads a subquery file (one SQL per line), estimates cardinality for each,
    and writes one float per line to the output file.
    """
    benchmark = args.benchmark.lower()
    csv_path = args.csv_path
    model_dir = args.model_dir
    query_file = args.query_file
    output_file = args.output_file

    # For JOBLightRanges, preprocess the SQL file
    actual_query_file = query_file
    if benchmark == "joblightranges":
        preprocessed_sql = os.path.join(
            os.path.dirname(output_file) or ".",
            "_bayescard_preprocessed_subquery.sql",
        )
        actual_query_file = preprocess_joblr_subquery_sql(query_file, preprocessed_sql)

    schema = get_schema(benchmark, csv_path)

    # Load ensemble (single instance used for both parsing and inference)
    logger.info("Loading BN ensemble from %s ...", model_dir)
    bn_ensemble = load_ensemble_sorted(schema, model_dir)

    # Read queries
    with open(actual_query_file, "r") as f:
        queries = f.readlines()

    total = len(queries)
    logger.info("Running inference on %d queries from %s ...", total, query_file)

    results = []
    latencies = []
    errors = 0
    error_stats = {
        "empty_or_comment": 0,
        "parsing_failed": 0,
        "factor_generation_failed": 0,
        "cardinality_none_or_negative": 0,
        "unexpected_exception": 0,
    }

    for i, query_str in enumerate(queries):
        q = query_str.strip()
        # Skip empty lines and comments, keep a placeholder
        if not q or q.startswith("--"):
            results.append(1.0)
            error_stats["empty_or_comment"] += 1
            continue

        # Strip trailing semicolons; support optional "SQL||true_card" format
        q = q.split("||")[0].rstrip(";").strip()

        t_start = time.time()
        try:
            estimate, fail_reason = _estimate_one_query(bn_ensemble, schema, q)
            if fail_reason:
                error_stats[fail_reason] += 1
                logger.debug("Query %d failed (%s): %s", i, fail_reason, q[:100])
        except Exception as e:
            logger.warning("Query %d unexpected exception: %s\n%s", i, str(e), q[:100])
            estimate = 1.0
            errors += 1
            error_stats["unexpected_exception"] += 1

        latencies.append(time.time() - t_start)
        
        # Ensure valid estimate
        if estimate is None or estimate <= 0:
            estimate = 1.0
            if "cardinality_none_or_negative" not in error_stats:
                error_stats["cardinality_none_or_negative"] = 0
            error_stats["cardinality_none_or_negative"] += 1
        results.append(estimate)

        if (i + 1) % 500 == 0 or (i + 1) == total:
            logger.info(
                "  processed %d / %d  (avg latency: %.4fs)",
                i + 1, total,
                np.mean(latencies),
            )

    # Save results
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w") as f:
        for r in results:
            f.write(str(r) + "\n")

    logger.info("Results saved to %s  (%d lines)", output_file, len(results))
    logger.info(
        "Total time: %.2fs | Avg latency: %.4fs | Errors: %d",
        sum(latencies),
        np.mean(latencies) if latencies else 0,
        errors,
    )
    
    # Print detailed error statistics
    logger.info("=" * 60)
    logger.info("ERROR STATISTICS:")
    total_1s = sum(1 for r in results if r == 1.0)
    logger.info("  Total 1.0 estimates: %d / %d (%.1f%%)", total_1s, len(results), 100.0 * total_1s / len(results))
    logger.info("  Breakdown:")
    for reason, count in sorted(error_stats.items(), key=lambda x: -x[1]):
        if count > 0:
            logger.info("    - %s: %d (%.1f%%)", reason, count, 100.0 * count / len(results))
    logger.info("=" * 60)

    # Clean up preprocessed SQL
    if benchmark == "joblightranges" and actual_query_file != query_file:
        try:
            os.remove(actual_query_file)
        except OSError:
            pass


def _estimate_one_query(bn_ensemble, schema, query_str):
    """
    Parse a single SQL query and return the BayesCard cardinality estimate.
    Uses the same bn_ensemble for parsing and inference to keep bn_index consistent.
    
    Returns: (estimate, fail_reason)
        estimate: float or None
        fail_reason: None if successful, or one of:
            "parsing_failed", "factor_generation_failed", "cardinality_none_or_negative"
    """
    # Step 1: Parse query
    try:
        query = parse_query(query_str, schema)
    except Exception as e:
        # Query parsing failed - likely unsupported relationship or syntax
        logger.debug("Query parsing failed: %s", str(e)[:100])
        return 1.0, "parsing_failed"

    # Step 2: Generate factors
    try:
        first_bn, next_mergeable_relationships, next_mergeable_tables = \
            bn_ensemble._greedily_select_first_cardinality_bn(
                query, rdc_spn_selection=True, rdc_attribute_dict={},
            )

        factors = generate_factors(
            bn_ensemble, query, first_bn,
            next_mergeable_relationships, next_mergeable_tables,
            rdc_bn_selection=True, rdc_attribute_dict={},
            merge_indicator_exp=True,
            exploit_incoming_multipliers=True,
            prefer_disjunct=False,
        )
        factors = factor_refine(factors)

        # Build parse_result (same format as prepare_join_queries)
        parse_result = []
        for factor in factors:
            if isinstance(factor, IndicatorExpectation):
                range_conditions = factor.spn._parse_conditions(
                    factor.conditions, group_by_columns=None, group_by_tuples=None,
                )
                actual_query, fanout = prepare_single_query(range_conditions, factor)
                parse_result.append({
                    "bn_index": bn_ensemble.bns.index(factor.spn),
                    "inverse": factor.inverse,
                    "query": actual_query,
                    "expectation": fanout,
                })
            elif isinstance(factor, Expectation):
                raise NotImplementedError("Expectation factors not supported")
            else:
                # full_join_size (numeric)
                parse_result.append(factor)

        # parse_query_all + cardinality (process single query)
        processed = bn_ensemble.parse_query_all([parse_result])
        estimate = bn_ensemble.cardinality(processed[0])

        if isinstance(estimate, np.ndarray):
            estimate = float(estimate[0])

        if estimate is None or estimate <= 0:
            logger.debug("Cardinality is None or <=0: %s", estimate)
            return 1.0, "cardinality_none_or_negative"
        
        return estimate, None
        
    except Exception as e:
        # Inference failed - likely unsupported query structure
        logger.debug("Inference failed: %s", str(e)[:100])
        return 1.0, "factor_generation_failed"


# ===================================================================
#  Argument parser
# ===================================================================

def build_parser():
    parser = argparse.ArgumentParser(
        description="BayesCard Benchmark Wrapper – train / infer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-command to run")

    # ---- train ----
    p_train = subparsers.add_parser("train", help="Train BayesCard BN ensemble models")
    p_train.add_argument(
        "--benchmark", required=True,
        choices=["stats", "joblight", "joblightranges", "jobm"],
        help="Which benchmark to train for",
    )
    p_train.add_argument(
        "--csv_path", required=True,
        help="Path template to CSV data, e.g. Data/Stats/{}.csv",
    )
    p_train.add_argument(
        "--hdf_path", required=True,
        help="Directory to store intermediate HDF files",
    )
    p_train.add_argument(
        "--model_dir", default="checkpoints/",
        help="Directory to save trained .pkl model files",
    )
    p_train.add_argument(
        "--algorithm", default="chow-liu",
        help="BN structure learning algorithm (default: chow-liu)",
    )
    p_train.add_argument(
        "--max_parents", type=int, default=1,
        help="Maximum number of parents per BN node (default: 1)",
    )
    p_train.add_argument(
        "--sample_size", type=int, default=200000,
        help="Subsample size for BN structure learning (default: 200000)",
    )
    p_train.add_argument(
        "--df_sample_size", type=int, default=10000000,
        help="Number of join samples for BN training (default: 10000000)",
    )
    p_train.add_argument(
        "--max_table_data", type=int, default=20000000,
        help="Maximum rows per HDF file (default: 20000000)",
    )
    p_train.add_argument(
        "--preprocessed_dir", type=str, default=None,
        help="Directory for preprocessed CSV data (JOBLightRanges only)",
    )

    # ---- infer ----
    p_infer = subparsers.add_parser(
        "infer", help="Run cardinality estimation on a subquery file",
    )
    p_infer.add_argument(
        "--benchmark", required=True,
        choices=["stats", "joblight", "joblightranges", "jobm"],
        help="Which benchmark the model was trained for",
    )
    p_infer.add_argument(
        "--csv_path", required=True,
        help="Path template to CSV data (used to build schema), e.g. Data/Stats/{}.csv",
    )
    p_infer.add_argument(
        "--model_dir", required=True,
        help="Directory containing trained .pkl model files",
    )
    p_infer.add_argument(
        "--query_file", required=True,
        help="Subquery SQL file (one SQL per line)",
    )
    p_infer.add_argument(
        "--output_file", required=True,
        help="Output file (one cardinality estimate per line)",
    )

    return parser


# ===================================================================
#  Main
# ===================================================================

def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "train": cmd_train,
        "infer": cmd_infer,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
