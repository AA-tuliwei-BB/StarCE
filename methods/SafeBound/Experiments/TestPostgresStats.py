import argparse
import re
import os
import sys
import time
import psycopg2


rootFileDirectory = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/"
sys.path.append(rootFileDirectory + "Source")

from DBConnectionUtils import DatabaseConnection
from JoinGraphUtils import JoinQueryGraph


class RawSqlValue:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value

    def __eq__(self, other):
        if isinstance(other, RawSqlValue):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, RawSqlValue):
            return self.value < other.value
        if isinstance(other, str):
            return self.value < other
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, RawSqlValue):
            return self.value <= other.value
        if isinstance(other, str):
            return self.value <= other
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, RawSqlValue):
            return self.value > other.value
        if isinstance(other, str):
            return self.value > other
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, RawSqlValue):
            return self.value >= other.value
        if isinstance(other, str):
            return self.value >= other
        return NotImplemented


def parse_sql_value(raw_value, keep_type_cast=True):
    raw_value = raw_value.strip()
    if raw_value.upper() == "NULL":
        return RawSqlValue("NULL")
    if raw_value.startswith("'"):
        if "::" in raw_value:
            if keep_type_cast:
                return RawSqlValue(raw_value)
            value_part = raw_value.split("::", 1)[0].strip()
            if value_part.endswith("'") and len(value_part) >= 2:
                return value_part[1:-1]
            return value_part
        if raw_value.endswith("'") and len(raw_value) >= 2:
            return raw_value[1:-1]
        return RawSqlValue(raw_value)
    if re.match(r"^-?\d+$", raw_value):
        return int(raw_value)
    if re.match(r"^-?\d+\.\d+$", raw_value):
        return float(raw_value)
    return RawSqlValue(raw_value)


def sql_to_joingraph(sql_query, keep_type_cast=True):
    """
    Parse SQL query and convert to JoinQueryGraph (for Stats benchmark)
    Parse FROM clause, WHERE equi-join conditions, and filter predicates.
    """
    import re

    query = JoinQueryGraph()

    from_match = re.search(r"FROM\s+(.+?)(?:\s+WHERE|$)", sql_query, re.IGNORECASE)
    if not from_match:
        raise ValueError("Invalid SQL query: missing FROM clause")

    tables = [t.strip() for t in from_match.group(1).split(",")]
    for table in tables:
        if " AS " in table.upper():
            table_name, alias = re.split(r"\s+AS\s+", table, flags=re.IGNORECASE)
        else:
            table_name = alias = table.split()[-1]
        query.addAlias(table_name.strip(), alias.strip())

    where_match = re.search(r"WHERE\s+(.+?)(?:\s*;|$)", sql_query, re.IGNORECASE)
    if where_match:
        join_conditions = re.split(r"\s+AND\s+", where_match.group(1), flags=re.IGNORECASE)
        for condition in join_conditions:
            condition = condition.strip().rstrip(";")
            join_match = re.match(r"(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)$", condition, re.IGNORECASE)
            if join_match:
                table1, col1, table2, col2 = join_match.groups()
                query.addJoin(table1, col1, table2, col2)
                continue
            pred_match = re.match(
                r"(\w+)\.(\w+)\s*(=|<=|>=|<|>)\s*(.+)$",
                condition,
                re.IGNORECASE,
            )
            if pred_match:
                alias, col, op, raw_value = pred_match.groups()
                value = parse_sql_value(raw_value, keep_type_cast=keep_type_cast)
                query.addPredicate(alias, col, op, value)

    return query


def load_stats_queries(sql_file_path):
    with open(sql_file_path, "r") as f:
        lines = f.readlines()
    sqls = []
    for sql in lines:
        sql = sql.strip()
        if not sql:
            continue
        sqls.append(sql)
    return sqls


def collect_predicate_examples(sqls, max_per_type=2):
    examples = {}
    for idx, sql in enumerate(sqls, 1):
        where_match = re.search(r"WHERE\s+(.+?)(?:\s*;|$)", sql, re.IGNORECASE)
        if not where_match:
            continue
        conditions = re.split(r"\s+AND\s+", where_match.group(1), flags=re.IGNORECASE)
        for condition in conditions:
            condition = condition.strip().rstrip(";")
            join_match = re.match(r"(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)$", condition, re.IGNORECASE)
            if join_match:
                continue
            pred_match = re.match(
                r"(\w+)\.(\w+)\s*(=|<=|>=|<|>)\s*(.+)$",
                condition,
                re.IGNORECASE,
            )
            if not pred_match:
                continue
            _, _, op, raw_value = pred_match.groups()
            raw_value = raw_value.strip()
            value_type = "timestamp" if "::" in raw_value else "numeric" if re.match(r"^-?\d+(\.\d+)?$", raw_value) else "other"
            key = f"{op}:{value_type}"
            if key not in examples:
                examples[key] = []
            if len(examples[key]) < max_per_type:
                examples[key].append(idx)
    return examples


def print_sql_roundtrip(sqls, indices):
    for idx in indices:
        if idx < 1 or idx > len(sqls):
            print(f"Index out of range: {idx}")
            continue
        sql = sqls[idx - 1]
        print(f"\n--- SQL #{idx} original ---")
        print(sql)
        try:
            query = sql_to_joingraph(sql)
            query.buildJoinGraph()
            print("--- getSQLQuery ---")
            print(query.getSQLQuery())
        except Exception as e:
            print(f"Parse failed: {e}")


def create_db_conn(db_name, host, port, user):
    conn = psycopg2.connect(dbname=db_name, host=host, port=port, user=user)
    conn.set_session(autocommit=True)
    try:
        conn.cursor().execute("Load 'pg_hint_plan';")
    except psycopg2.Error:
        pass
    return DatabaseConnection(conn, db_name)


def evaluate_postgres_stats(
    sql_file_path,
    output_file,
    statistics_target=100,
    limit=None,
    db_name="stats",
    host="127.0.0.1",
    port=5432,
    user=None,
):
    if user is None:
        user = os.environ.get("USER")
    dbConn = create_db_conn(db_name=db_name, host=host, port=port, user=user)
    dbConn.changeStatisticsTarget(statistics_target)

    sqls = load_stats_queries(sql_file_path)
    if limit is not None:
        sqls = sqls[:limit]

    postgres_estimates = []

    for i, sql in enumerate(sqls):
        query = sql_to_joingraph(sql)
        query.buildJoinGraph()

        start_time = time.time()
        estimate = dbConn.getSizeEstimate(query)
        end_time = time.time()

        postgres_estimates.append(estimate)

        if i % 10 == 1:
            print(f"Postgres Inference Stats :{100 * float(i) / len(sqls):.2f}% Done")

    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_file, "w") as f:
        for estimate in postgres_estimates:
            f.write(f"{estimate}\n")

    print(f"Results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Test PostgreSQL cardinality estimation on Stats (SafeBound interface)")
    parser.add_argument(
        "--sql-file",
        default=rootFileDirectory + "Workloads/StatsQueries.sql",
        help="Stats query file path",
    )
    parser.add_argument(
        "--output-file",
        default="Postgres_Inference_Stats_manual.txt",
        help="Output TXT path (one estimate per line)",
    )
    parser.add_argument(
        "--statistics-target",
        type=int,
        default=100,
        help="PostgreSQL default_statistics_target",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Test only first N queries (optional)",
    )
    parser.add_argument(
        "--check-indices",
        default="",
        help="Print SQL reconstruction results for specified SQL indices (1-based, comma-separated)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only do SQL reconstruction check, do not execute estimation",
    )
    parser.add_argument(
        "--verify-predicates",
        action="store_true",
        help="Auto-pick typical predicate types and print reconstruction results",
    )
    parser.add_argument(
        "--db-host",
        default="127.0.0.1",
        help="Database host",
    )
    parser.add_argument(
        "--db-port",
        type=int,
        default=5432,
        help="Database port",
    )
    parser.add_argument(
        "--db-user",
        default=os.environ.get("USER"),
        help="Database username",
    )
    parser.add_argument(
        "--db-name",
        default="stats",
        help="Database name",
    )
    args = parser.parse_args()

    sqls = load_stats_queries(args.sql_file)
    if args.check_indices:
        indices = [int(x) for x in args.check_indices.split(",") if x.strip()]
        print_sql_roundtrip(sqls, indices)
        if args.check_only:
            return
    if args.verify_predicates:
        examples = collect_predicate_examples(sqls)
        picked = []
        for key in sorted(examples.keys()):
            picked.extend(examples[key])
        print("Auto-selected indices:", ",".join(str(x) for x in picked))
        print_sql_roundtrip(sqls, picked)
        if args.check_only:
            return

    evaluate_postgres_stats(
        sql_file_path=args.sql_file,
        output_file=args.output_file,
        statistics_target=args.statistics_target,
        limit=args.limit,
        db_name=args.db_name,
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
    )


if __name__ == "__main__":
    main()
