import re

def find_unique_matches(file_path):
    # 定义正则表达式模式
    pattern = re.compile(r'([a-z_0-9]+) AS ([a-z_0-9]+)')
    
    # 用于存储匹配结果的集合
    unique_matches = set()
    
    # 打开文件并逐行读取
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            # 在每一行中查找匹配的模式
            matches = pattern.findall(line)
            # 将匹配结果添加到集合中
            for match in matches:
                unique_matches.add(match)
    
    # 输出去重后的匹配结果
    for name1, name2 in unique_matches:
        print(f"{name1} AS {name2}")

# 使用示例
file_path = 'alias.txt'  # 替换为你的文件路径
find_unique_matches(file_path)