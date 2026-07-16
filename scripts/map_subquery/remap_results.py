#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rearrange result files from old_result folder according to line_mapping.txt mappings
and save to new_result folder
"""

import os
from pathlib import Path

def load_mapping(mapping_file):
    """
    Load mapping file, return dictionary {old_line: new_line}
    """
    mapping = {}
    with open(mapping_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Parse old_line:new_line
            if ':' in line:
                parts = line.split(':', 1)
                try:
                    old_line = int(parts[0].strip())
                    new_line = int(parts[1].strip())
                    mapping[old_line] = new_line
                except ValueError:
                    continue

    return mapping

def remap_result_file(old_file, new_file, mapping):
    """
    Rearrange result file according to mapping relationships
    """
    # Read all lines from old file
    with open(old_file, 'r', encoding='utf-8') as f:
        old_lines = [line.rstrip('\n\r') for line in f]

    # Find the maximum new line number to determine new file line count
    max_new_line = max(mapping.values()) if mapping else 0
    new_lines = [''] * max_new_line

    # Fill new file according to mapping relationships
    for old_line, new_line in mapping.items():
        # old_line is 1-based, need to convert to 0-based index
        if 1 <= old_line <= len(old_lines):
            # new_line is also 1-based, need to convert to 0-based index
            if 1 <= new_line <= max_new_line:
                new_lines[new_line - 1] = old_lines[old_line - 1]

    # Write new file
    os.makedirs(os.path.dirname(new_file), exist_ok=True)
    with open(new_file, 'w', encoding='utf-8') as f:
        for line in new_lines:
            f.write(line + '\n')

    return len([l for l in new_lines if l])  # Return non-empty line count

def main():
    script_dir = Path(__file__).parent
    mapping_file = script_dir / 'line_mapping.txt'
    old_result_dir = script_dir / 'old_result'
    new_result_dir = script_dir / 'new_result'

    # Check if files exist
    if not mapping_file.exists():
        print(f"Error: cannot find mapping file {mapping_file}")
        return

    if not old_result_dir.exists():
        print(f"Error: cannot find old result folder {old_result_dir}")
        return

    # Load mapping relationships
    print("Loading mapping relationships...")
    mapping = load_mapping(mapping_file)
    print(f"Loaded {len(mapping)} mapping relationships")

    # Create new result folder
    new_result_dir.mkdir(exist_ok=True)

    # Process all txt files in old_result folder
    txt_files = list(old_result_dir.glob('*.txt'))
    if not txt_files:
        print(f"Warning: no txt files found in {old_result_dir}")
        return

    print(f"\nFound {len(txt_files)} result files, starting processing...")

    for old_file in txt_files:
        filename = old_file.name
        new_file = new_result_dir / filename

        print(f"Processing {filename}...", end=' ')
        try:
            mapped_count = remap_result_file(old_file, new_file, mapping)
            print(f"Done (mapped {mapped_count} lines)")
        except Exception as e:
            print(f"Error: {e}")

    print("\nAll files processed!")

if __name__ == '__main__':
    main()








