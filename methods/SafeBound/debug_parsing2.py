#!/usr/bin/env python3
"""Debug sqlparse token structure."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bayescard'))

import sqlparse

# Test query
q = "SELECT COUNT(*) FROM badges AS badges1,comments AS comments1 WHERE comments1.UserId=badges1.UserId AND badges1.Date<='2014-08-02 12:24:29'::timestamp"

parsed = sqlparse.parse(q)[0]
print("=" * 80)
print("PARSED QUERY STRUCTURE")
print("=" * 80)

# Find WHERE clause
for token in parsed.tokens:
    if isinstance(token, sqlparse.sql.Where):
        print(f"\nWHERE clause tokens: {len(token.tokens)}")
        for i, t in enumerate(token.tokens):
            print(f"  [{i}] {type(t).__name__}: {repr(t)}")
            if isinstance(t, sqlparse.sql.Comparison):
                print(f"      Comparison tokens: {len(t.tokens)}")
                for j, ct in enumerate(t.tokens):
                    print(f"        [{j}] {type(ct).__name__}: {repr(ct)}")
                    if isinstance(ct, sqlparse.sql.Identifier):
                        print(f"            Identifier tokens: {len(ct.tokens)}")
                        for k, it in enumerate(ct.tokens):
                            print(f"              [{k}] {type(it).__name__} / {it.ttype}: {repr(it.value)}")
