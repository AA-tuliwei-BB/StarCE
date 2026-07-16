import sys
import numpy as np
import matplotlib.pyplot as plt
from math import log10, floor

def read_valid_lines(file_names):
    """
    从多个文件中读取有效行
    :param file_names: 文件名列表
    :return: 有效行的数据列表，每个文件对应一个子列表
    """
    data = [[] for _ in file_names]  # 初始化存储数据的列表

    # 打开所有文件
    files = [open(file_name, 'r') for file_name in file_names]

    # 逐行读取
    for lines in zip(*files):
        try:
            # 尝试将真实值转换为浮点数
            true_value = float(lines[0].strip())
        except ValueError:
            print(f"Warning: 真实值文件中的行 '{lines[0].strip()}' 无效，跳过该行")
            continue

        # 如果真实值有效，则处理其他文件的数据
        for i, line in enumerate(lines):
            try:
                data[i].append(float(line.strip()))
            except ValueError:
                print(f"Warning: 文件 '{file_names[i]}' 中的行 '{line.strip()}' 无效，跳过该行")
                continue

    # 关闭所有文件
    for file in files:
        file.close()

    return data

def calculate_relative_errors(true_values, data_values):
    """
    计算相对误差
    :param true_values: 真实值列表
    :param data_values: 其他文件的数据列表
    :return: 相对误差列表
    """
    relative_errors = []
    for true, data in zip(true_values, data_values):
        if true == 0:
            print("Warning: 真实值为0，无法计算相对误差，跳过该行")
            continue
        relative_errors.append(data / true)
    return relative_errors

def generate_bins(relative_errors):
    """
    自动生成区间边界
    :param relative_errors: 相对误差列表
    :return: 区间边界列表
    """
    if not relative_errors:
        return [0.1, 1, 10, 100]  # 默认区间
    
    # 找到最小和最大相对误差的对数值
    min_error = min(relative_errors)
    max_error = max(relative_errors)
    
    # 计算最小和最大量级
    min_magnitude = floor(log10(min_error)) if min_error > 0 else -1
    max_magnitude = floor(log10(max_error)) if max_error > 0 else 1
    
    # 生成区间边界
    bins = [10 ** i for i in range(min_magnitude, max_magnitude + 2)]
    return bins

def plot_histogram(relative_errors, file_name):
    print('plotting')
    """
    绘制直方图
    :param relative_errors: 相对误差列表
    :param file_name: 用于保存图像的输出文件名
    """
    # 自动生成区间边界
    bins = generate_bins(relative_errors)
    print('plotting2')

    # 绘制直方图
    counts, bin_edges, _ = plt.hist(relative_errors, bins=bins, edgecolor='black', alpha=0.7)
    
    # 生成区间标签（指数表示法）
    bin_labels = [f'$10^{{{int(log10(bin_edges[i]))}}}$ to $10^{{{int(log10(bin_edges[i+1]))}}}$' 
                  for i in range(len(bin_edges) - 1)]
    
    # 添加图例
    plt.legend(handles=[plt.Rectangle((0, 0), 1, 1, fc='blue', alpha=0.7)], 
               labels=[f'{label}: {count}' for label, count in zip(bin_labels, counts)],
               loc='upper right')
    
    # 设置横轴为对数刻度
    plt.xscale('log')
    plt.xlabel('Relative Error Magnitude')
    plt.ylabel('Count')
    plt.title(f'Relative Error Histogram ({file_name})')
    plt.grid(True, which="both", ls="--", linewidth=0.5)
    
    # 保存图像
    plt.savefig(f'{file_name}_histogram.png')
    plt.close()

def main(file_names):
    """
    主函数
    :param file_names: 输入文件名列表
    """
    # 读取所有文件的有效行
    data = read_valid_lines(file_names)
    true_values = data[0]  # 第一个文件是真实值

    # 处理其他文件
    for i, file_name in enumerate(file_names[1:]):
        data_values = data[i + 1]
        
        # 计算相对误差
        relative_errors = calculate_relative_errors(true_values, data_values)
        
        # 绘制并保存直方图
        plot_histogram(relative_errors, file_name)
        print(f"直方图已保存为 {file_name}_histogram.png")

if __name__ == "__main__":
    # 检查输入参数
    if len(sys.argv) < 3:
        print("用法: python script.py <真实值文件> <其他文件1> <其他文件2> ...")
        sys.exit(1)
    
    # 获取文件名列表
    file_names = sys.argv[1:]
    
    # 调用主函数
    main(file_names)