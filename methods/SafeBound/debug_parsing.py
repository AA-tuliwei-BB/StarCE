#!/usr/bin/env python3
"""Debug parsing failures for STATS-CEB queries."""

import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bayescard'))

from Schemas.stats.schema import gen_stats_light_schema
from Evaluation.utils import parse_query

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Test queries that fail
test_queries = [
    "SELECT COUNT(*) FROM badges AS badges1,comments AS comments1 WHERE comments1.UserId=badges1.UserId AND badges1.Date<='2014-08-02 12:24:29'::timestamp",
    "SELECT COUNT(*) FROM badges AS badges1,postHistory AS postHistory1,users AS users1 WHERE postHistory1.UserId=users1.Id AND users1.Id=badges1.UserId",
]

schema = gen_stats_light_schema(str(PROJECT_ROOT / "methods/SafeBound/Data/Stats/{}.csv"))

print("=" * 80)
print("SCHEMA RELATIONSHIPS:")
print("=" * 80)
for rel_key in sorted(schema.relationship_dictionary.keys()):
    print(f"  {rel_key}")
print()

for i, q in enumerate(test_queries):
    print("=" * 80)
    print(f"Query {i+1}: {q[:120]}")
    print("=" * 80)
    try:
        result = parse_query(q, schema)
        print(f"✓ SUCCESS")
        print(f"  Tables: {result.table_set}")
        print(f"  Relationships: {result.relationship_set}")
    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}")
        print(f"  Message: {str(e)[:200]}")
        import traceback
        print("  Traceback:")
        for line in traceback.format_exc().split('\n')[-10:]:
            print(f"    {line}")
    print()
