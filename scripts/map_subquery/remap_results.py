#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据line_mapping.txt的映射关系，将old_result文件夹中的结果文件
重新排列并保存到new_result文件夹中
"""

import os
from pathlib import Path

def load_mapping(mapping_file):
    """
    加载映射文件，返回字典 {old_line: new_line}
    """
    mapping = {}
    with open(mapping_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 跳过注释和空行
            if not line or line.startswith('#'):
                continue
            
            # 解析 old_line:new_line
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
    根据映射关系重新排列结果文件
    """
    # 读取旧文件的所有行
    with open(old_file, 'r', encoding='utf-8') as f:
        old_lines = [line.rstrip('\n\r') for line in f]
    
    # 找出最大的新行号，确定新文件的行数
    max_new_line = max(mapping.values()) if mapping else 0
    new_lines = [''] * max_new_line
    
    # 根据映射关系填充新文件
    for old_line, new_line in mapping.items():
        # old_line是1-based，需要转换为0-based索引
        if 1 <= old_line <= len(old_lines):
            # new_line也是1-based，需要转换为0-based索引
            if 1 <= new_line <= max_new_line:
                new_lines[new_line - 1] = old_lines[old_line - 1]
    
    # 写入新文件
    os.makedirs(os.path.dirname(new_file), exist_ok=True)
    with open(new_file, 'w', encoding='utf-8') as f:
        for line in new_lines:
            f.write(line + '\n')
    
    return len([l for l in new_lines if l])  # 返回非空行数

def main():
    script_dir = Path(__file__).parent
    mapping_file = script_dir / 'line_mapping.txt'
    old_result_dir = script_dir / 'old_result'
    new_result_dir = script_dir / 'new_result'
    
    # 检查文件是否存在
    if not mapping_file.exists():
        print(f"错误: 找不到映射文件 {mapping_file}")
        return
    
    if not old_result_dir.exists():
        print(f"错误: 找不到旧结果文件夹 {old_result_dir}")
        return
    
    # 加载映射关系
    print("正在加载映射关系...")
    mapping = load_mapping(mapping_file)
    print(f"加载了 {len(mapping)} 个映射关系")
    
    # 创建新结果文件夹
    new_result_dir.mkdir(exist_ok=True)
    
    # 处理old_result文件夹中的所有txt文件
    txt_files = list(old_result_dir.glob('*.txt'))
    if not txt_files:
        print(f"警告: 在 {old_result_dir} 中未找到任何txt文件")
        return
    
    print(f"\n找到 {len(txt_files)} 个结果文件，开始处理...")
    
    for old_file in txt_files:
        filename = old_file.name
        new_file = new_result_dir / filename
        
        print(f"处理 {filename}...", end=' ')
        try:
            mapped_count = remap_result_file(old_file, new_file, mapping)
            print(f"完成 (映射了 {mapped_count} 行)")
        except Exception as e:
            print(f"错误: {e}")
    
    print("\n所有文件处理完成！")

if __name__ == '__main__':
    main()








