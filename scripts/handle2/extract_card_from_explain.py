import re
import sys

def process_data(data):
    # 以两个回车符分割数据
    sections = data.split('\n\n')
    
    # 正则表达式匹配 [数字] Rows 的模式
    pattern = re.compile(r'[\d]+ Rows')
    
    results = []
    
    for section in sections:
        # 在每部分中查找第一个匹配的模式
        match = pattern.search(section)
        if match:
            results.append(match.group())
    
    return results

def main():
    # 检查是否提供了文件名作为参数
    if len(sys.argv) != 2:
        print("Usage: python script.py <filename>")
        sys.exit(1)
    
    filename = sys.argv[1]
    
    try:
        # 从文件中读取数据
        with open(filename, 'r', encoding='utf-8') as file:
            data = file.read()
        
        # 处理数据
        extracted_rows = process_data(data)
        
        # 输出结果
        for row in extracted_rows:
            print(row)
    
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()