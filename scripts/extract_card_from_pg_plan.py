#!/usr/bin/env python3
"""
从PostgreSQL EXPLAIN输出文件中提取每个查询的最终估计基数
"""

import re
import sys
from pathlib import Path


def extract_cardinalities(file_path):
    """
    从PostgreSQL EXPLAIN文件中提取每个查询的基数
    
    Args:
        file_path: EXPLAIN文件路径
        
    Returns:
        list: 包含每个查询基数的列表
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    cardinalities = []
    plan_count = 0
    in_query_plan = False
    found_separator = False

    for line in lines:
        # 检测QUERY PLAN标题
        if 'QUERY PLAN' in line:
            in_query_plan = True
            found_separator = False
            plan_count += 1
            continue

        # 检测分隔线（全是由-组成的行）
        if in_query_plan and re.match(r'^-+\s*$', line):
            found_separator = True
            continue

        # 在分隔线后的第一行中查找rows=
        if in_query_plan and found_separator:
            match = re.search(r'rows=(\d+)', line)
            if match:
                cardinality = int(match.group(1))
                cardinalities.append(cardinality)
                # 重置状态，准备查找下一个查询计划
                in_query_plan = False
                found_separator = False

    if len(cardinalities) != plan_count:
        raise RuntimeError(
            f"基数提取不完整: 检测到 {plan_count} 个查询计划，但只提取了 {len(cardinalities)} 个基数。"
            f"PostgreSQL EXPLAIN 输出格式可能已变更")

    return cardinalities


def main():
    if len(sys.argv) < 2:
        print("用法: python extract_cardinality.py <explain_file>")
        print("示例: python extract_cardinality.py build/pg_est_single.txt")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not Path(file_path).exists():
        print(f"错误: 文件 '{file_path}' 不存在")
        sys.exit(1)
    
    try:
        cardinalities = extract_cardinalities(file_path)
        
        print(f"共找到 {len(cardinalities)} 个查询计划")
        
        # 保存到文件：每行一个基数，行号对应查询编号
        output_file = Path(file_path).with_suffix('.cardinalities.txt')
        with open(output_file, 'w', encoding='utf-8') as f:
            for card in cardinalities:
                f.write(f"{card}\n")
        print(f"\n结果已保存到: {output_file}")
        print(f"格式: 每行一个基数，第N行对应第N个查询")
        
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

