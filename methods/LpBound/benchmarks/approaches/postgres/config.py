import os


class PostgresConfig:

    # Database configuration -- change these to match your setup
    DB_PORT: int = 5433
    PASSWORD: str = "MyStrongAndSecureP@ssw0rd!"

    # map from benchmark to postgres database name
    # this is used by some experiments to map the benchmark name to a database name
    DB_NAME_DICT: dict[str, str] = {
        "jobjoin": "imdb",
        "jobrange": "imdblightranges",
        "joblight": "imdblight",
        "stats": "stats",
        "subgraph_matching": "dblp",
    }

    # map from benchmark to database name for groupby queries
    GROUPBY_DB_NAME_DICT: dict[str, str] = {
        "jobjoin": "imdb",
        "jobrange": "imdb",
        "joblight": "imdb",
        "stats": "stats",
    }

    @staticmethod
    def restart_postgres():
        os.system("sudo systemctl restart postgresql-13")
