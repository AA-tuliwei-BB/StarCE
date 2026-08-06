#!/usr/bin/env python3
import argparse
import os
import sys
from typing import List, Tuple


def _split_line_ending(s: str) -> Tuple[str, str]:
    if s.endswith("\r\n"):
        return s[:-2], "\r\n"
    if s.endswith("\n"):
        return s[:-1], "\n"
    return s, ""


def _is_comment_or_empty(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith("--"):
        return True
    if stripped.startswith("#"):
        return True
    return False


def _remove_explain_prefix(sql: str) -> str:
    lstripped = sql.lstrip()
    if lstripped[:7].lower() != "explain":
        return sql
    rest = lstripped[7:]
    rest = rest.lstrip()
    return rest


def transform_lines(lines: List[str], mode: str) -> List[str]:
    out: List[str] = []
    for raw in lines:
        line, eol = _split_line_ending(raw)
        if _is_comment_or_empty(line):
            out.append(line + eol)
            continue

        stripped_left = line.lstrip()
        has_explain = stripped_left[:7].lower() == "explain" and (len(stripped_left) == 7 or stripped_left[7].isspace())

        if mode == "remove":
            if has_explain:
                out.append(_remove_explain_prefix(line) + eol)
            else:
                out.append(line + eol)
            continue

        if mode == "add":
            if has_explain:
                out.append(line + eol)
            else:
                out.append("EXPLAIN " + stripped_left + eol)
            continue

        if mode == "toggle":
            if has_explain:
                out.append(_remove_explain_prefix(line) + eol)
            else:
                out.append("EXPLAIN " + stripped_left + eol)
            continue

        raise ValueError(f"unknown mode: {mode}")

    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Batch add/remove EXPLAIN for SQL files (expects one statement per line)."
    )
    p.add_argument(
        "inputs",
        nargs="+",
        help="Input .sql file(s).",
    )
    p.add_argument(
        "--mode",
        choices=["add", "remove", "toggle"],
        default="toggle",
        help="How to transform EXPLAIN prefix.",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite input files in place.",
    )
    g.add_argument(
        "-o",
        "--out-dir",
        help="Write outputs to this directory (keeps basename).",
    )
    p.add_argument(
        "--suffix",
        default="_explain",
        help="Suffix to add before extension when using --out-dir (default: _explain).",
    )
    return p.parse_args()


def output_path(in_path: str, out_dir: str, suffix: str) -> str:
    base = os.path.basename(in_path)
    name, ext = os.path.splitext(base)
    ext = ext if ext else ".sql"
    return os.path.join(out_dir, name + suffix + ext)


def main() -> int:
    args = parse_args()

    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)

    for in_path in args.inputs:
        with open(in_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        out_lines = transform_lines(lines, args.mode)

        if args.in_place:
            out_path = in_path
        else:
            out_path = output_path(in_path, args.out_dir, args.suffix)

        with open(out_path, "w", encoding="utf-8") as f:
            f.writelines(out_lines)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
