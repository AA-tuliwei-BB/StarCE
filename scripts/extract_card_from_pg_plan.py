"""Extract estimated row counts from PostgreSQL EXPLAIN output.

PG EXPLAIN format: "Seq Scan on t  (cost=0.00..1.18 rows=18 width=4)"
DuckDB EXPLAIN format: "└───────────────────────────────────── 18 Rows"
"""
import re
from pathlib import Path


def extract_cardinalities(explain_output: Path) -> list[int]:
    """Parse a PG EXPLAIN output file and return estimated row counts per query.

    Args:
        explain_output: Path to the EXPLAIN output file.

    Returns:
        List of estimated row counts, one per query.
    """
    text = Path(explain_output).read_text(encoding="utf-8")

    # Split by double newlines to separate query results
    sections = text.split("\n\n")
    pattern = re.compile(r"rows=(\d+)", re.IGNORECASE)

    results = []
    for section in sections:
        match = pattern.search(section)
        if match:
            results.append(int(match.group(1)))

    return results
