"""
测试 IN 谓词对 SafeBound JOBM 估计时间的影响

对 JOBM 子查询采样，比较带 IN 和不带 IN 谓词的估计时间，
量化 IN 谓词组合爆炸在总评估开销中的占比。
"""
import sys
import os
import time
import re
import pickle
import random
from pathlib import Path
import numpy as np

# 路径设置
project_root = Path(__file__).resolve().parent.parent
safeBound_root = os.path.join(project_root, 'methods/SafeBound')
sys.path.append(os.path.join(safeBound_root, 'Source'))

from SafeBoundUtils import *
from JoinGraphUtils import *
from SQLParser import *

# 加载统计对象
stat_path = os.path.join(project_root, 'experiment/checkpoint/SafeBound/SafeBound_3_JOBM.pkl')
print(f'加载统计对象: {stat_path}')
t0 = time.time()
stats = pickle.load(open(stat_path, 'rb'))
print(f'加载耗时: {time.time()-t0:.1f}s, 统计对象内存: {stats.memory()} bytes')

# 读取子查询
sql_path = os.path.join(project_root, 'Benchmark/workloads/JOBM/subquery/subquery2.sql')
with open(sql_path) as f:
    all_queries = [l.strip() for l in f.readlines() if l.strip()]
print(f'总查询数: {len(all_queries)}')

# 采样
random.seed(42)
sample_size = 500
sample = random.sample(all_queries, min(sample_size, len(all_queries)))

# 统计所有查询的 IN 谓词信息（快速扫描，不运行估计）
in_query_count = 0
in_value_products = []
for sql in all_queries:
    jgs = SQLQueriesToJoinQueryGraphs(sql)
    if jgs:
        jg = jgs[0]
        in_counts = []
        for v in jg.vertexDict.values():
            for p in v.predicates:
                if p.predType == 'IN':
                    in_counts.append(len(p.compValue))
        if in_counts:
            in_query_count += 1
            in_value_products.append(int(np.prod(in_counts)))

print(f'\n=== 全量统计（{len(all_queries)} 条查询）===')
print(f'含 IN 谓词的查询: {in_query_count} ({100*in_query_count/len(all_queries):.1f}%)')
print(f'IN 组合数分布:')
print(f'  最小: {min(in_value_products)}')
print(f'  最大: {max(in_value_products)}')
print(f'  平均: {np.mean(in_value_products):.1f}')
print(f'  中位数: {np.median(in_value_products):.1f}')
print(f'  总组合数（所有查询的 IN product 之和）: {sum(in_value_products)}')
print(f'  如果无 IN 则总循环次数 = {len(all_queries)}（每条查询一次）')
print(f'  有 IN 则总循环次数 ≈ {len(all_queries) - in_query_count + sum(in_value_products)}')
total_loops_with_in = len(all_queries) - in_query_count + sum(in_value_products)
print(f'  IN 导致的循环膨胀倍数: {total_loops_with_in / len(all_queries):.1f}x')

# 按 IN product 分组统计
bins = [(1, 1), (2, 5), (6, 10), (11, 20), (21, 50), (51, 100), (101, 1000)]
print(f'\n  IN 组合数分布详情:')
for lo, hi in bins:
    count = sum(1 for p in in_value_products if lo <= p <= hi)
    if count > 0:
        print(f'    [{lo}, {hi}]: {count} 条查询 ({100*count/len(in_value_products):.1f}%)')

print(f'\n=== 采样 {sample_size} 条查询进行实际计时测试 ===')

# 对采样查询进行实际计时
results = []
parse_failures = 0

for i, sql in enumerate(sample):
    if i % 50 == 0:
        print(f'  进度: {i}/{sample_size}')

    try:
        # 解析原始查询
        jgs = SQLQueriesToJoinQueryGraphs(sql)
        if not jgs:
            parse_failures += 1
            continue
        jg = jgs[0]

        # 统计 IN 谓词
        in_counts = []
        for v in jg.vertexDict.values():
            for p in list(v.predicates):
                if p.predType == 'IN':
                    in_counts.append(len(p.compValue))

        num_tables = len(jg.vertexDict)
        num_joins = sum(len(v.edgeAliases) for v in jg.vertexDict.values()) // 2

        # 计时：原始查询
        t0 = time.perf_counter()
        bound_orig = stats.functionalFrequencyBound(jg.copy())
        t_orig = time.perf_counter() - t0

        if in_counts:
            # 创建无 IN 谓词的版本：从 JoinQueryGraph 中移除 IN 谓词
            jg_no_in = jg.copy()
            for v in jg_no_in.vertexDict.values():
                v.predicates = [p for p in v.predicates if p.predType != 'IN']

            # 计时：无 IN 谓词
            t0 = time.perf_counter()
            bound_no_in = stats.functionalFrequencyBound(jg_no_in)
            t_no_in = time.perf_counter() - t0

            in_product = int(np.prod(in_counts))
            speedup = t_orig / t_no_in if t_no_in > 0 else float('inf')

            results.append({
                'idx': i,
                'has_in': True,
                'in_counts': in_counts,
                'in_product': in_product,
                'time_orig': t_orig,
                'time_no_in': t_no_in,
                'speedup': speedup,
                'tables': num_tables,
                'joins': num_joins,
            })
        else:
            results.append({
                'idx': i,
                'has_in': False,
                'time_orig': t_orig,
                'tables': num_tables,
                'joins': num_joins,
            })

    except Exception as e:
        parse_failures += 1
        continue

print(f'\n解析失败: {parse_failures}')
print(f'成功测试: {len(results)} 条查询')

# 分类统计
with_in = [r for r in results if r['has_in']]
without_in = [r for r in results if not r['has_in']]

print(f'\n=== 计时结果 ===')
print(f'无 IN 谓词的查询: {len(without_in)} 条')
if without_in:
    times = [r['time_orig'] for r in without_in]
    print(f'  平均估计时间: {np.mean(times)*1000:.2f} ms')
    print(f'  中位数估计时间: {np.median(times)*1000:.2f} ms')
    print(f'  总时间: {sum(times):.2f} s')

print(f'\n有 IN 谓词的查询: {len(with_in)} 条')
if with_in:
    times_orig = [r['time_orig'] for r in with_in]
    times_no_in = [r['time_no_in'] for r in with_in]
    speedups = [r['speedup'] for r in with_in]
    products = [r['in_product'] for r in with_in]

    print(f'  原始总时间（带 IN）: {sum(times_orig):.2f} s')
    print(f'  去 IN 总时间: {sum(times_no_in):.2f} s')
    print(f'  总加速比: {sum(times_orig)/sum(times_no_in):.1f}x')
    print(f'  平均单查询时间（带 IN）: {np.mean(times_orig)*1000:.2f} ms')
    print(f'  平均单查询时间（去 IN）: {np.mean(times_no_in)*1000:.2f} ms')
    print(f'  中位数单查询时间（带 IN）: {np.median(times_orig)*1000:.2f} ms')
    print(f'  中位数单查询时间（去 IN）: {np.median(times_no_in)*1000:.2f} ms')
    print(f'  加速比分布:')
    print(f'    最小: {min(speedups):.1f}x')
    print(f'    最大: {max(speedups):.1f}x')
    print(f'    平均: {np.mean(speedups):.1f}x')
    print(f'    中位数: {np.median(speedups):.1f}x')

# 按 IN product 分组分析
print(f'\n=== 按 IN 组合数分组的加速比 ===')
product_bins = [(1, 5), (6, 10), (11, 20), (21, 50), (51, 100), (101, 500)]
for lo, hi in product_bins:
    group = [r for r in with_in if lo <= r['in_product'] <= hi]
    if group:
        avg_speedup = np.mean([r['speedup'] for r in group])
        avg_time_orig = np.mean([r['time_orig'] for r in group]) * 1000
        avg_time_no_in = np.mean([r['time_no_in'] for r in group]) * 1000
        print(f'  IN product [{lo}, {hi}]: {len(group)} 条, '
              f'平均加速 {avg_speedup:.1f}x, '
              f'平均时间(带IN) {avg_time_orig:.1f}ms, '
              f'平均时间(去IN) {avg_time_no_in:.1f}ms')

# 最重要的统计：如果去掉所有 IN 谓词，评价时间能从 260s 降到多少？
print(f'\n=== 推算全量评估时间 ===')
# 从采样推算
ratio_in_sample = len(with_in) / len(results)  # 含 IN 查询的比例
avg_time_no_in_all = np.mean([r['time_no_in'] if r['has_in'] else r['time_orig'] for r in results])
avg_time_orig_all = np.mean([r['time_orig'] for r in results])

# 全量查询数
total_queries = len(all_queries)
# 推算原始总时间
estimated_total_orig = total_queries * avg_time_orig_all
# 推算去 IN 总时间
estimated_total_no_in = total_queries * avg_time_no_in_all

print(f'采样平均时间（原始）: {avg_time_orig_all*1000:.2f} ms/query')
print(f'采样平均时间（去 IN）: {avg_time_no_in_all*1000:.2f} ms/query')
print(f'推算全量原始总时间: {estimated_total_orig:.1f} s')
print(f'推算全量去 IN 总时间: {estimated_total_no_in:.1f} s')
print(f'去 IN 可节省: {estimated_total_orig - estimated_total_no_in:.1f} s ({(estimated_total_orig - estimated_total_no_in)/estimated_total_orig*100:.1f}%)')

# 按表数分组
print(f'\n=== 按表数分组的单查询时间（去 IN 后） ===')
for t in sorted(set(r['tables'] for r in results)):
    group = [r for r in results if r['tables'] == t]
    times = [r['time_no_in'] if r['has_in'] else r['time_orig'] for r in group]
    print(f'  {t} 表: {len(group)} 条, 平均 {np.mean(times)*1000:.1f} ms')
