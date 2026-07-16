#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
找出old_subquery.sql到new_subquery.sql的行号映射
处理谓词顺序不同的情况
"""

import re
from collections import defaultdict

def normalize_sql(sql):
    """
    标准化SQL查询，处理谓词顺序不同的问题
    1. 提取WHERE子句中的条件
    2. 对条件进行排序
    3. 返回标准化的字符串
    """
    sql = sql.strip().rstrip(';')
    if not sql:
        return ""
    
    # 提取WHERE子句
    where_match = re.search(r'WHERE\s+(.+?)(?:;|$)', sql, re.IGNORECASE | re.DOTALL)
    if not where_match:
        # 没有WHERE子句，返回整个SQL（标准化空格）
        return re.sub(r'\s+', ' ', sql).strip()
    
    where_clause = where_match.group(1).strip().rstrip(';')
    
    # 提取SELECT和FROM部分（不变的部分）
    select_from_match = re.search(r'(SELECT.*?FROM[^W]+)', sql, re.IGNORECASE | re.DOTALL)
    if select_from_match:
        select_from = select_from_match.group(1).strip()
    else:
        # 备用方法
        parts = sql.split('WHERE', 1)
        if len(parts) > 0:
            select_from = parts[0].strip()
        else:
            select_from = sql
    
    # 使用正则表达式按AND分割，但要避免在字符串或括号内匹配
    # 简单方法：先替换字符串中的内容，分割后再恢复
    conditions = []
    
    # 保护字符串中的内容
    string_placeholders = {}
    placeholder_counter = 0
    
    def replace_string(match):
        nonlocal placeholder_counter
        placeholder = f"__STRING_{placeholder_counter}__"
        string_placeholders[placeholder] = match.group(0)
        placeholder_counter += 1
        return placeholder
    
    # 替换所有字符串字面量
    protected_where = re.sub(r"'[^']*'", replace_string, where_clause)
    
    # 现在可以安全地按AND分割
    # 使用正则匹配单词边界的AND
    parts = re.split(r'\s+AND\s+', protected_where, flags=re.IGNORECASE)
    
    # 恢复字符串并标准化每个条件
    normalized_conditions = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # 恢复字符串
        for placeholder, original in string_placeholders.items():
            part = part.replace(placeholder, original)
        
        # 标准化空格
        part = re.sub(r'\s+', ' ', part).strip()
        normalized_conditions.append(part)
    
    # 排序条件（使顺序无关）
    normalized_conditions.sort()
    
    # 重新组合
    if normalized_conditions:
        normalized_where = ' AND '.join(normalized_conditions)
        normalized_sql = f"{select_from} WHERE {normalized_where}"
    else:
        normalized_sql = select_from
    
    # 最终标准化空格
    normalized_sql = re.sub(r'\s+', ' ', normalized_sql).strip()
    
    return normalized_sql

def build_mapping(old_file, new_file, output_file):
    """
    建立旧文件行号到新文件行号的映射
    """
    print("正在读取旧文件并建立索引...")
    # 读取旧文件，建立标准化SQL到行号的映射
    old_sql_to_lines = defaultdict(list)
    with open(old_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            normalized = normalize_sql(line)
            if normalized:
                old_sql_to_lines[normalized].append(line_num)
    
    print(f"旧文件共 {len(old_sql_to_lines)} 个不同的查询")
    
    print("正在读取新文件并建立映射...")
    # 读取新文件，找出对应的行号
    mapping = {}  # old_line -> new_line
    unmatched_old = set()  # 旧文件中未匹配的行号
    unmatched_new = []  # 新文件中未匹配的行号
    
    with open(new_file, 'r', encoding='utf-8') as f:
        for new_line_num, line in enumerate(f, 1):
            normalized = normalize_sql(line)
            if not normalized:
                continue
            
            # 查找匹配的旧文件行号
            if normalized in old_sql_to_lines:
                old_lines = old_sql_to_lines[normalized]
                if old_lines:
                    # 取第一个未匹配的旧行号
                    old_line = old_lines.pop(0)
                    mapping[old_line] = new_line_num
                    if not old_lines:
                        del old_sql_to_lines[normalized]
                else:
                    unmatched_new.append(new_line_num)
            else:
                unmatched_new.append(new_line_num)
    
    # 找出未匹配的旧行号
    for normalized, old_lines in old_sql_to_lines.items():
        unmatched_old.update(old_lines)
    
    print(f"成功匹配: {len(mapping)} 个")
    print(f"未匹配的旧行号: {len(unmatched_old)} 个")
    print(f"未匹配的新行号: {len(unmatched_new)} 个")
    
    # 写入映射结果
    print(f"正在写入映射结果到 {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# 旧文件行号 -> 新文件行号映射\n")
        f.write("# 格式: old_line:new_line\n\n")
        
        # 写入匹配的映射（按旧行号排序）
        for old_line in sorted(mapping.keys()):
            f.write(f"{old_line}:{mapping[old_line]}\n")
        
        # 写入未匹配的信息
        if unmatched_old:
            f.write(f"\n# 未匹配的旧行号 ({len(unmatched_old)} 个):\n")
            for old_line in sorted(unmatched_old):
                f.write(f"# {old_line}:?\n")
        
        if unmatched_new:
            f.write(f"\n# 未匹配的新行号 ({len(unmatched_new)} 个):\n")
            for new_line in sorted(unmatched_new):
                f.write(f"# ?:{new_line}\n")
    
    print("完成！")
    return mapping, unmatched_old, unmatched_new

if __name__ == '__main__':
    import sys
    import os
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    old_file = os.path.join(script_dir, 'old_subquery.sql')
    new_file = os.path.join(script_dir, 'new_subquery.sql')
    output_file = os.path.join(script_dir, 'line_mapping.txt')
    
    if not os.path.exists(old_file):
        print(f"错误: 找不到文件 {old_file}")
        sys.exit(1)
    
    if not os.path.exists(new_file):
        print(f"错误: 找不到文件 {new_file}")
        sys.exit(1)
    
    build_mapping(old_file, new_file, output_file)

