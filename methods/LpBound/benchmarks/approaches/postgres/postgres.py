import re
import psycopg2
from datetime import datetime

from benchmarks.approaches.postgres.config import PostgresConfig


def get_dbConn(benchmark: str, groupby: bool = False) -> "DatabaseConnection":
    # get the db name for the benchmark
    db_name = PostgresConfig.DB_NAME_DICT[benchmark] if not groupby else PostgresConfig.GROUPBY_DB_NAME_DICT[benchmark]

    return create_db_conn(db_name)


def create_db_conn(dbName: str = "IMDB"):
    print(f"Creating database connection to {dbName} on port {PostgresConfig.DB_PORT}")
    conn = psycopg2.connect(
        dbname=dbName, port=PostgresConfig.DB_PORT, host="localhost", password=PostgresConfig.PASSWORD
    )
    conn.set_session(autocommit=True)
    conn.cursor().execute("Load 'pg_hint_plan';")
    dbConn = DatabaseConnection(conn, dbName)
    return dbConn


def reset_cache():
    # os.system("sudo sh -c '/usr/bin/echo 3 > /proc/sys/vm/drop_caches'") # use this if you have sudo access
    PostgresConfig.restart_postgres()


def make_sql_count_star(query: str) -> str:
    # replace the * in the select clause with count(*)
    query = re.sub(r"SELECT \* FROM", "SELECT COUNT(*) FROM", query)
    return query


class JoinHint:
    def __init__(self, tables: list[str], rowEstimate: int):
        self.tables: list[str] = tables
        self.rowEstimate: int = rowEstimate


class DatabaseConnection:

    def __init__(self, pgConnection: psycopg2.extensions.connection, dbName: str):
        self.conn: psycopg2.extensions.connection = pgConnection
        self.dbName: str = dbName

    def reset(self):
        self.conn.close()
        self.conn = create_db_conn(self.dbName).conn

    def executeQueryWithHints(self, sql: str, hints: list[JoinHint] = [], countStar: bool = False) -> float:
        """
        Execute the query and return the runtime
        """
        cursor = self.conn.cursor()
        query = "/*+\n"
        for hint in hints:
            query += "Rows("
            for table in hint.tables:
                query += table.lower() + " "
            query += "#" + str(min(8223372036854775800, hint.rowEstimate)) + ")\n"
        query += "*/\n"

        if countStar:
            sql = make_sql_count_star(sql)
        query += sql
        # print(query)
        runtimeStart = datetime.now()
        cursor.execute(query)
        runtimeEnd = datetime.now()

        # actual = cursor.fetchone()[0]
        # actualInt = int(actual)
        return (runtimeEnd - runtimeStart).total_seconds()

    def executeQuery(self, query: str) -> None:
        # print(f"Executing query: {query}")
        cursor = self.conn.cursor()
        cursor.execute(query)

    def getSizeEstimateSQL(self, query: str) -> int:
        cursor = self.conn.cursor()
        query = "EXPLAIN " + query
        # print(query)
        cursor.execute(query)
        all_results = cursor.fetchall()
        # for row in all_results:
        #     print(row)
        results = all_results[0][0]

        # results = cursor.fetchone()[0]
        # print(f"Results: {results}")
        estimate = int(re.findall(r"rows=(\d*)", results)[0])
        return estimate

    def getSizeEstimateSQLWithTime(self, query: str) -> tuple[int, float]:
        cursor = self.conn.cursor()
        query = "EXPLAIN " + query
        # print(query)
        start_time = datetime.now()
        cursor.execute(query)
        end_time = datetime.now()
        all_results = cursor.fetchall()
        # for row in all_results:
        #     print(row)
        results = all_results[0][0]

        # results = cursor.fetchone()[0]
        # print(f"Results: {results}")
        estimate = int(re.findall(r"rows=(\d*)", results)[0])
        return estimate, (end_time - start_time).total_seconds() * 1000  # in milliseconds

    def changeStatisticsTarget(self, target: int) -> None:
        query = "ALTER SYSTEM SET default_statistics_target=" + str(target) + ";"
        cursor = self.conn.cursor()
        cursor.execute(query)
        query = "SELECT pg_reload_conf();"
        cursor.execute(query)
        self.runAnalyze()

    def runAnalyze(self):
        cursor = self.conn.cursor()
        query = "ANALYZE;"
        cursor.execute(query)
        query = "VACUUM FULL pg_statistic;"
        cursor.execute(query)
        query = "VACUUM FULL pg_statistic_ext_data;"
        cursor.execute(query)

    def memory(self):
        query = "SELECT pg_total_relation_size('pg_statistic')+pg_total_relation_size('pg_statistic_ext_data');"
        cursor = self.conn.cursor()
        cursor.execute(query)
        memory = cursor.fetchone()[0]
        return int(memory)

    def close(self):
        self.conn.close()
