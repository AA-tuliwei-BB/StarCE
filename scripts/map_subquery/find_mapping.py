#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Find line number mapping from old_subquery.sql to new_subquery.sql
Handles cases where predicate order differs
"""

import re
from collections import defaultdict

def normalize_sql(sql):
    """
    Normalize SQL query, handling predicate order differences
    1. Extract conditions in WHERE clause
    2. Sort conditions
    3. Return normalized string
    """
    sql = sql.strip().rstrip(';')
    if not sql:
        return ""

    # Extract WHERE clause
    where_match = re.search(r'WHERE\s+(.+?)(?:;|$)', sql, re.IGNORECASE | re.DOTALL)
    if not where_match:
        # No WHERE clause, return entire SQL (normalize whitespace)
        return re.sub(r'\s+', ' ', sql).strip()

    where_clause = where_match.group(1).strip().rstrip(';')

    # Extract SELECT and FROM parts (unchanged portions)
    select_from_match = re.search(r'(SELECT.*?FROM[^W]+)', sql, re.IGNORECASE | re.DOTALL)
    if select_from_match:
        select_from = select_from_match.group(1).strip()
    else:
        # Fallback method
        parts = sql.split('WHERE', 1)
        if len(parts) > 0:
            select_from = parts[0].strip()
        else:
            select_from = sql

    # Use regex to split by AND, but avoid matching inside strings or parentheses
    # Simple approach: first replace string contents, split, then restore
    conditions = []

    # Protect string contents
    string_placeholders = {}
    placeholder_counter = 0

    def replace_string(match):
        nonlocal placeholder_counter
        placeholder = f"__STRING_{placeholder_counter}__"
        string_placeholders[placeholder] = match.group(0)
        placeholder_counter += 1
        return placeholder

    # Replace all string literals
    protected_where = re.sub(r"'[^']*'", replace_string, where_clause)

    # Now we can safely split by AND
    # Use regex matching word-boundary AND
    parts = re.split(r'\s+AND\s+', protected_where, flags=re.IGNORECASE)

    # Restore strings and normalize each condition
    normalized_conditions = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Restore strings
        for placeholder, original in string_placeholders.items():
            part = part.replace(placeholder, original)

        # Normalize whitespace
        part = re.sub(r'\s+', ' ', part).strip()
        normalized_conditions.append(part)

    # Sort conditions (making order irrelevant)
    normalized_conditions.sort()

    # Recombine
    if normalized_conditions:
        normalized_where = ' AND '.join(normalized_conditions)
        normalized_sql = f"{select_from} WHERE {normalized_where}"
    else:
        normalized_sql = select_from

    # Final whitespace normalization
    normalized_sql = re.sub(r'\s+', ' ', normalized_sql).strip()

    return normalized_sql

def build_mapping(old_file, new_file, output_file):
    """
    Build mapping from old file line numbers to new file line numbers
    """
    print("Reading old file and building index...")
    # Read old file, build normalized SQL to line number mapping
    old_sql_to_lines = defaultdict(list)
    with open(old_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            normalized = normalize_sql(line)
            if normalized:
                old_sql_to_lines[normalized].append(line_num)

    print(f"Old file has {len(old_sql_to_lines)} distinct queries")

    print("Reading new file and building mapping...")
    # Read new file, find corresponding line numbers
    mapping = {}  # old_line -> new_line
    unmatched_old = set()  # Unmatched line numbers in old file
    unmatched_new = []  # Unmatched line numbers in new file

    with open(new_file, 'r', encoding='utf-8') as f:
        for new_line_num, line in enumerate(f, 1):
            normalized = normalize_sql(line)
            if not normalized:
                continue

            # Look for matching old file line number
            if normalized in old_sql_to_lines:
                old_lines = old_sql_to_lines[normalized]
                if old_lines:
                    # Take the first unmatched old line number
                    old_line = old_lines.pop(0)
                    mapping[old_line] = new_line_num
                    if not old_lines:
                        del old_sql_to_lines[normalized]
                else:
                    unmatched_new.append(new_line_num)
            else:
                unmatched_new.append(new_line_num)

    # Find unmatched old line numbers
    for normalized, old_lines in old_sql_to_lines.items():
        unmatched_old.update(old_lines)

    print(f"Successfully matched: {len(mapping)} entries")
    print(f"Unmatched old line numbers: {len(unmatched_old)} entries")
    print(f"Unmatched new line numbers: {len(unmatched_new)} entries")

    # Write mapping results
    print(f"Writing mapping results to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Old file line number -> New file line number mapping\n")
        f.write("# Format: old_line:new_line\n\n")

        # Write matched mappings (sorted by old line number)
        for old_line in sorted(mapping.keys()):
            f.write(f"{old_line}:{mapping[old_line]}\n")

        # Write unmatched info
        if unmatched_old:
            f.write(f"\n# Unmatched old line numbers ({len(unmatched_old)} entries):\n")
            for old_line in sorted(unmatched_old):
                f.write(f"# {old_line}:?\n")

        if unmatched_new:
            f.write(f"\n# Unmatched new line numbers ({len(unmatched_new)} entries):\n")
            for new_line in sorted(unmatched_new):
                f.write(f"# ?:{new_line}\n")

    print("Done!")
    return mapping, unmatched_old, unmatched_new

if __name__ == '__main__':
    import sys
    import os

    script_dir = os.path.dirname(os.path.abspath(__file__))
    old_file = os.path.join(script_dir, 'old_subquery.sql')
    new_file = os.path.join(script_dir, 'new_subquery.sql')
    output_file = os.path.join(script_dir, 'line_mapping.txt')

    if not os.path.exists(old_file):
        print(f"Error: cannot find file {old_file}")
        sys.exit(1)

    if not os.path.exists(new_file):
        print(f"Error: cannot find file {new_file}")
        sys.exit(1)

    build_mapping(old_file, new_file, output_file)

