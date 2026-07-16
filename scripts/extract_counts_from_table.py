#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


COUNT_PATTERN = re.compile(r"│\s*([0-9]+)\s*│")


def extract_counts(text: str) -> list[int]:
    return [int(match.group(1)) for match in COUNT_PATTERN.finditer(text)]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从类似 real.txt 的表格输出中提取 count 结果"
    )
    parser.add_argument("input", type=Path, help="输入文件路径")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="输出文件路径，默认打印到标准输出",
    )
    args = parser.parse_args()

    content = args.input.read_text(encoding="utf-8")
    counts = extract_counts(content)
    output_text = "\n".join(str(value) for value in counts)

    if args.output:
        args.output.write_text(output_text + ("\n" if output_text else ""), encoding="utf-8")
    else:
        if output_text:
            print(output_text)


if __name__ == "__main__":
    main()
