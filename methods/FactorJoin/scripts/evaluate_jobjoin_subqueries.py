"""
JobJoin subquery-level FactorJoin evaluation script.
Read subquery.sql (9565 entries), call get_cardinality_bound_one for each,
produce Benchmark/workloads/JobJoin/subquery/result/factorjoin.txt.

Usage:
  cd methods/FactorJoin
  python scripts/evaluate_jobjoin_subqueries.py
"""
import sys, os, time, pickle, re

# Ensure FactorJoin directory is in path
_factorjoin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _factorjoin_dir)

# Import data_prepare first to break bound.py <-> data_prepare.py circular import
from Join_scheme.data_prepare import identify_key_values  # noqa: F401
from Join_scheme.bound import Bound_ensemble  # noqa: E402


def normalize_table_names(sql):
    """Normalize table names, aliases, and column name case in subquery.sql:
    1. Lowercase table names (fix MOVIE_keyword/AKA_name issues)
    2. Lowercase aliases (fix CT/MC uppercase aliases)
    3. Lowercase column names in alias.column in WHERE clauses (fix ID/company_type_ID, etc.)
    4. Lowercase alias references in alias.column in WHERE clauses"""
    match = re.search(r'\bFROM\b\s+(.*?)\s+\bWHERE\b', sql, re.IGNORECASE)
    if not match:
        return sql
    from_clause = match.group(1)
    alias_map = {}  # original alias -> lowercase alias
    parts = []
    for part in from_clause.split(','):
        part = part.strip()
        m = re.match(r'(\S+)\s+AS\s+(\S+)', part, re.IGNORECASE)
        if m:
            table_name = m.group(1).lower()
            alias_orig = m.group(2)
            alias_lower = alias_orig.lower()
            alias_map[alias_orig] = alias_lower
            parts.append(f'{table_name} AS {alias_lower}')
        else:
            parts.append(part)
    new_from = ', '.join(parts)

    # Replace alias references and column names in WHERE clause (and beyond)
    rest = sql[match.end(1):]
    # Sort by alias length descending to avoid accidental short alias replacement
    for orig, lower in sorted(alias_map.items(), key=lambda x: -len(x[0])):
        # Replace alias.column -> lower.column_lower
        # Match alias.ColumnName pattern, lowercase column names starting with uppercase or all-uppercase
        rest = re.sub(
            r'\b' + re.escape(orig) + r'\.(\w+)',
            lambda m, lo=lower: lo + '.' + m.group(1).lower(),
            rest
        )
    return sql[:match.start(1)] + new_from + rest


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    factorjoin_dir = os.path.dirname(script_dir)
    proj_root = os.path.normpath(os.path.join(factorjoin_dir, "../.."))

    model_path = os.path.join(factorjoin_dir, "checkpoints/model_imdb_default.pkl")
    query_file = os.path.join(proj_root, "Benchmark/workloads/JobJoin/subquery/subquery.sql")
    mapping_file = os.path.join(factorjoin_dir, "checkpoints/jobjoin_subquery_to_main.pkl")
    sample_loc = os.path.join(factorjoin_dir, "checkpoints/binned_cards_{}/")
    save_file = os.path.join(proj_root, "Benchmark/workloads/JobJoin/subquery/result/factorjoin.txt")

    print(f"Model: {model_path}")
    print(f"Query file: {query_file}")
    print(f"Mapping file: {mapping_file}")
    print(f"Sample directory: {sample_loc}")
    print(f"Output file: {save_file}")

    # Load model
    print("Loading model...")
    with open(model_path, "rb") as f:
        be = pickle.load(f)
    print(f"  bns: {be.bns}, n_dim_dist: {be.n_dim_dist}")
    print(f"  ground_truth_factors_no_filter table count: {len(be.ground_truth_factors_no_filter)}")

    # Set sampling parameters
    be.SPERCENTAGE = 1.0
    be.query_sample_location = sample_loc

    # Load mapping
    with open(mapping_file, "rb") as f:
        mapping = pickle.load(f)

    # Load subqueries
    with open(query_file, "r") as f:
        queries = [line.strip() for line in f.readlines() if line.strip()]

    assert len(queries) == len(mapping), \
        f"Query count ({len(queries)}) != mapping count ({len(mapping)})"

    print(f"Total {len(queries)} subqueries")

    preds = []
    failed = []
    t_start = time.time()

    for i, sql in enumerate(queries):
        main_id = mapping[i]
        try:
            sql_norm = normalize_table_names(sql)
            res = be.get_cardinality_bound_one(sql_norm, query_name=f"{main_id}.pkl")
            preds.append(res)
        except Exception as e:
            preds.append("MISSING")
            failed.append((i + 1, type(e).__name__, str(e)))

        if (i + 1) % 500 == 0:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed
            eta = (len(queries) - (i + 1)) / rate if rate > 0 else 0
            print(f"  Estimated {i+1}/{len(queries)} ({100*(i+1)/len(queries):.1f}%), "
                  f"Total {elapsed:.0f}s, rate {rate:.1f} q/s, ETA {eta:.0f}s")

    elapsed = time.time() - t_start
    print(f"Total time: {elapsed:.1f}s, avg {elapsed/len(queries):.3f}s/q")

    if failed:
        print(f"{len(failed)} queries failed (MISSING):")
        for qid, etype, emsg in failed[:20]:
            print(f"  row {qid}: {etype}: {emsg[:120]}")
        if len(failed) > 20:
            print(f"  ... and {len(failed)-20} more")

    # Ensure output directory exists
    os.makedirs(os.path.dirname(save_file), exist_ok=True)

    # Save results
    with open(save_file, "w") as f:
        for p in preds:
            f.write(str(p) + "\n")

    print(f"Results saved: {save_file}")
    print(f"Rows: {len(preds)} (valid: {sum(1 for p in preds if p != 'MISSING')}, "
          f"MISSING: {sum(1 for p in preds if p == 'MISSING')})")


if __name__ == "__main__":
    main()
