def filter_large_numbers(input_file1, input_file2, output_file1, output_file2):
    # 打开输入文件
    with open(input_file1, 'r') as file1, open(input_file2, 'r') as file2:
        # 读取文件的内容
        numbers = file1.readlines()
        data = file2.readlines()

    # 过滤条件：数值不超过100000000
    filtered_numbers = []
    filtered_data = []
    for num, line in zip(numbers, data):
        # 将数值转换为整数
        try:
            value = int(num.strip())
        except ValueError:
            print(f"Warning: 无法将 '{num.strip()}' 转换为整数，跳过该行")
            continue

        # 判断是否满足条件
        if value <= 1000000000:
            filtered_numbers.append(num)
            filtered_data.append(line)

    # 将过滤后的结果写入输出文件
    with open(output_file1, 'w') as file1, open(output_file2, 'w') as file2:
        file1.writelines(filtered_numbers)
        file2.writelines(filtered_data)

    print("过滤完成！结果已保存到输出文件。")


# 示例调用
input_file1 = 'numbers.txt'  # 第一个输入文件（数值文件）
input_file2 = 'sql.txt'     # 第二个输入文件（其他数据文件）
output_file1 = 'filtered_numbers.txt'  # 第一个输出文件
output_file2 = 'filtered_sql.txt'     # 第二个输出文件

filter_large_numbers(input_file1, input_file2, output_file1, output_file2)