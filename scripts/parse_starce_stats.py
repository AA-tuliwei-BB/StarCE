#!/usr/bin/env python3
"""
Parse StarCE statistics JSON file, interactively view EqualSet degree sequence statistics.

Usage:
    python parse_starce_stats.py [json_file_path]

If no file path is specified, automatically uses the first statistics_*.json file found under running_space.
"""

import json
import sys
from pathlib import Path


def load_json(filepath):
    with open(filepath) as f:
        return json.load(f)


def is_subset_of(small_entries, large_entries):
    """
    Check whether small entries are a subset of large entries.
    Loose matching: when ColumnName in a small entry is an empty string (single-table EqualSet),
    it is considered a match as long as TableName exists in large.
    """
    large_set = {(e["TableName"], e["ColumnName"]) for e in large_entries}
    for se in small_entries:
        if se["ColumnName"] == "":
            if not any(le[0] == se["TableName"] for le in large_set):
                return False
        else:
            if (se["TableName"], se["ColumnName"]) not in large_set:
                return False
    return True


def is_strict_subset(small_entries, large_entries):
    """Strict subset: small is a subset of large and has fewer entries"""
    if len(small_entries) >= len(large_entries):
        return False
    return is_subset_of(small_entries, large_entries)


def find_maximal_equalsets(stats):
    """
    Find indices of all maximal EqualSets.
    An EqualSet is maximal iff no other EqualSet strictly contains it.
    """
    n = len(stats)
    maximal_indices = []
    for i in range(n):
        is_maximal = True
        es_i = stats[i]["EqualSet"]["Entries"]
        for j in range(n):
            if i == j:
                continue
            if is_strict_subset(es_i, stats[j]["EqualSet"]["Entries"]):
                is_maximal = False
                break
        if is_maximal:
            maximal_indices.append(i)
    return maximal_indices


def get_sub_equalsets(stats, parent_idx):
    """Get indices of all sub-Equalsets belonging to a maximal Equalset (including itself)"""
    parent_entries = stats[parent_idx]["EqualSet"]["Entries"]
    sub_indices = []
    for i, s in enumerate(stats):
        if is_subset_of(s["EqualSet"]["Entries"], parent_entries):
            sub_indices.append(i)
    return sub_indices


def format_equalset(entries):
    """Format Equalset entries as a readable string"""
    parts = []
    for e in entries:
        if e["ColumnName"]:
            parts.append(f"{e['TableName']}.{e['ColumnName']}")
        else:
            parts.append(f"[{e['TableName']}]")
    return "{" + ", ".join(parts) + "}"


def format_cardinality(card):
    """Human-readable cardinality display"""
    if card >= 1e9:
        return f"{card/1e9:.2f}B"
    elif card >= 1e6:
        return f"{card/1e6:.2f}M"
    elif card >= 1e3:
        return f"{card/1e3:.1f}K"
    else:
        return f"{card:.0f}"


def print_degree_sequence(ds_list, indent=2):
    """Print degree sequence, truncate display when bin count is large"""
    prefix = " " * indent
    if not ds_list:
        print(f"{prefix}(empty)")
        return

    print(f"{prefix}Total {len(ds_list)} bins:")
    max_show = 20
    if len(ds_list) <= max_show:
        for bin_data in ds_list:
            md = bin_data["MaxDegree"]
            cnt = bin_data["Count"]
            print(f"{prefix}  MaxDegree={md:>14.2f}  Count={cnt:>10,}")
    else:
        for bin_data in ds_list[:10]:
            md = bin_data["MaxDegree"]
            cnt = bin_data["Count"]
            print(f"{prefix}  MaxDegree={md:>14.2f}  Count={cnt:>10,}")
        skipped = len(ds_list) - max_show
        print(f"{prefix}  ... skipping {skipped} bins ...")
        for bin_data in ds_list[-10:]:
            md = bin_data["MaxDegree"]
            cnt = bin_data["Count"]
            print(f"{prefix}  MaxDegree={md:>14.2f}  Count={cnt:>10,}")


def print_dsstatistic(ds_stat):
    """Print complete DSStatistic info"""
    card = ds_stat["Cardinality"]
    print(f"Cardinality: {card:,.0f}  ({format_cardinality(card)})")
    print()

    print("Central degree sequence (CentralDS) — distribution of row count products for each join-key value:")
    print_degree_sequence(ds_stat.get("CentralDS", []), indent=2)
    print()

    # per-table degree sequences
    per_table = ds_stat.get("DSStatistic", [])
    if per_table:
        print(f"Per-table degree sequences ({len(per_table)} tables):")
        for table_ds in per_table:
            table_name = table_ds["Table"]
            ds = table_ds.get("DegreeSequence", [])
            # compute total entry count for this table
            total_count = sum(bin_["Count"] for bin_ in ds)
            print(f"\n  [{table_name}] — {total_count:,} distinct values, {len(ds)} bins:")
            print_degree_sequence(ds, indent=4)


def main():
    # --- 1. Load JSON file ---
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        running_space = Path(__file__).parent / "running_space"
        json_files = sorted(running_space.glob("statistics_*.json"))
        if not json_files:
            print("Error: no statistics JSON file found, please specify a file path")
            print(f"Usage: python {Path(__file__).name} <json_file_path>")
            sys.exit(1)
        filepath = str(json_files[0])

    print(f"Loading statistics file: {filepath}")
    data = load_json(filepath)
    stats = data["Statistics"]
    print(f"AdjustRate: {data['AdjustRate']:.4f}")
    print(f"Total {len(stats)} Equalset entries\n")

    # --- 2. Find maximal Equalsets ---
    maximal_idx = find_maximal_equalsets(stats)
    # Sort by size descending
    maximal_idx.sort(key=lambda i: len(stats[i]["EqualSet"]["Entries"]), reverse=True)

    print(f"Found {len(maximal_idx)} maximal Equalset(s):\n")
    for display_idx, orig_i in enumerate(maximal_idx):
        es = stats[orig_i]["EqualSet"]["Entries"]
        card = stats[orig_i]["DSStatistic"]["Cardinality"]
        print(
            f"  [{display_idx}] size={len(es):>2} | rows={format_cardinality(card):>8} | "
            f"{format_equalset(es)}"
        )

    # --- 3. User selects a large Equalset ---
    print()
    choice = input(f"Select a maximal Equalset [0-{len(maximal_idx)-1}] (q to quit): ").strip()
    if choice.lower() == "q":
        return
    selected_parent = maximal_idx[int(choice)]

    # --- 4. List sub-Equalsets ---
    sub_idx_list = get_sub_equalsets(stats, selected_parent)
    # Sort by size ascending (small to large), easier to see hierarchy
    sub_idx_list.sort(key=lambda i: len(stats[i]["EqualSet"]["Entries"]))

    parent_es = stats[selected_parent]["EqualSet"]["Entries"]
    print(f"\nParent Equalset: {format_equalset(parent_es)}")
    print(f"Total {len(sub_idx_list)} sub-Equalsets (including self):\n")
    for display_idx, orig_i in enumerate(sub_idx_list):
        es = stats[orig_i]["EqualSet"]["Entries"]
        card = stats[orig_i]["DSStatistic"]["Cardinality"]
        print(
            f"  [{display_idx}] size={len(es):>2} | rows={format_cardinality(card):>8} | "
            f"{format_equalset(es)}"
        )

    # --- 5. User selects a sub-Equalset ---
    print()
    choice = input(f"Select a sub-Equalset [0-{len(sub_idx_list)-1}] (q to quit): ").strip()
    if choice.lower() == "q":
        return
    selected_sub = sub_idx_list[int(choice)]

    # --- 6. Output degree sequence statistics ---
    es = stats[selected_sub]["EqualSet"]["Entries"]
    print(f"\n{'='*65}")
    print(f"Selected Equalset: {format_equalset(es)}")
    print(f"{'='*65}\n")
    print_dsstatistic(stats[selected_sub]["DSStatistic"])


if __name__ == "__main__":
    main()
