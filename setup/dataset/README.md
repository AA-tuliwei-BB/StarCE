# Datasets

StarCE uses two benchmark datasets:

| Dataset | Tables | Size | Source |
|--------|------|------|------|
| **STATS-CEB** | 8 | ~39 MB (CSV) | StackExchange dump |
| **IMDB** | 21 | ~4.8 GB (CSV after extraction) | Internet Movie Database |

## STATS-CEB

STATS-CEB is provided with the repository, CSV files are located at `Benchmark/STATS/`.

Verify dataset integrity:

```bash
bash setup/dataset/init_stats.sh
```

## IMDB

IMDB data requires download (~3.5 GB archive), ~4.8 GB after extraction, stored in `Benchmark/IMDB/`.

Download and extract:

```bash
bash setup/dataset/init_imdb.sh
```

Download URL: <https://event.cwi.nl/da/job/imdb.tgz>

## Next Steps

Once CSV data is ready, use the scripts in `setup/duckdb/` and `setup/postgresql/` to import the data into databases.
