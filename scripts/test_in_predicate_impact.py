"""
Test the impact of IN predicates on SafeBound JOBM estimation time.

Sample JOBM subqueries, compare estimation time with and without IN predicates,
quantify the proportion of IN predicate combinatorial explosion in total evaluation overhead.
"""
import sys
import os
import time
import re
import pickle
import random
from pathlib import Path
import numpy as np

# path setup
project_root = Path(__file__).resolve().parent.parent
safeBound_root = os.path.join(project_root, 'methods/SafeBound')
sys.path.append(os.path.join(safeBound_root, 'Source'))

from SafeBoundUtils import *
from JoinGraphUtils import *
from SQLParser import *

# load statistics object
stat_path = os.path.join(project_root, 'experiment/checkpoint/SafeBound/SafeBound_3_JOBM.pkl')
print(f'Loading statistics object: {stat_path}')
t0 = time.time()
stats = pickle.load(open(stat_path, 'rb'))
print(f'Load time: {time.time()-t0:.1f}s, stats object memory: {stats.memory()} bytes')

# read subqueries
sql_path = os.path.join(project_root, 'Benchmark/workloads/JOBM/subquery/subquery2.sql')
with open(sql_path) as f:
    all_queries = [l.strip() for l in f.readlines() if l.strip()]
print(f'Total queries: {len(all_queries)}')

# sample
random.seed(42)
sample_size = 500
sample = random.sample(all_queries, min(sample_size, len(all_queries)))

# collect IN predicate info for all queries (fast scan, no estimation)
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

print(f'\n=== Full population stats ({len(all_queries)} queries) ===')
print(f'Queries with IN predicates: {in_query_count} ({100*in_query_count/len(all_queries):.1f}%)')
print(f'IN combination count distribution:')
print(f'  min: {min(in_value_products)}')
print(f'  max: {max(in_value_products)}')
print(f'  mean: {np.mean(in_value_products):.1f}')
print(f'  median: {np.median(in_value_products):.1f}')
print(f'  total combinations (sum of IN products across all queries): {sum(in_value_products)}')
print(f'  without IN, total loop count = {len(all_queries)} (once per query)')
print(f'  with IN, total loop count ~= {len(all_queries) - in_query_count + sum(in_value_products)}')
total_loops_with_in = len(all_queries) - in_query_count + sum(in_value_products)
print(f'  IN-caused loop explosion factor: {total_loops_with_in / len(all_queries):.1f}x')

# group stats by IN product
bins = [(1, 1), (2, 5), (6, 10), (11, 20), (21, 50), (51, 100), (101, 1000)]
print(f'\n  IN combination count distribution detail:')
for lo, hi in bins:
    count = sum(1 for p in in_value_products if lo <= p <= hi)
    if count > 0:
        print(f'    [{lo}, {hi}]: {count} queries ({100*count/len(in_value_products):.1f}%)')

print(f'\n=== Sample {sample_size} queries for actual timing test ===')

# actual timing on sampled queries
results = []
parse_failures = 0

for i, sql in enumerate(sample):
    if i % 50 == 0:
        print(f'  progress: {i}/{sample_size}')

    try:
        # parse original query
        jgs = SQLQueriesToJoinQueryGraphs(sql)
        if not jgs:
            parse_failures += 1
            continue
        jg = jgs[0]

        # count IN predicates
        in_counts = []
        for v in jg.vertexDict.values():
            for p in list(v.predicates):
                if p.predType == 'IN':
                    in_counts.append(len(p.compValue))

        num_tables = len(jg.vertexDict)
        num_joins = sum(len(v.edgeAliases) for v in jg.vertexDict.values()) // 2

        # timing: original query
        t0 = time.perf_counter()
        bound_orig = stats.functionalFrequencyBound(jg.copy())
        t_orig = time.perf_counter() - t0

        if in_counts:
            # create version without IN predicates: remove IN predicates from JoinQueryGraph
            jg_no_in = jg.copy()
            for v in jg_no_in.vertexDict.values():
                v.predicates = [p for p in v.predicates if p.predType != 'IN']

            # timing: without IN predicates
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

print(f'\nParse failures: {parse_failures}')
print(f'Successful tests: {len(results)} queries')

# categorized stats
with_in = [r for r in results if r['has_in']]
without_in = [r for r in results if not r['has_in']]

print(f'\n=== Timing Results ===')
print(f'Queries without IN predicates: {len(without_in)}')
if without_in:
    times = [r['time_orig'] for r in without_in]
    print(f'  avg estimation time: {np.mean(times)*1000:.2f} ms')
    print(f'  median estimation time: {np.median(times)*1000:.2f} ms')
    print(f'  total time: {sum(times):.2f} s')

print(f'\nQueries with IN predicates: {len(with_in)}')
if with_in:
    times_orig = [r['time_orig'] for r in with_in]
    times_no_in = [r['time_no_in'] for r in with_in]
    speedups = [r['speedup'] for r in with_in]
    products = [r['in_product'] for r in with_in]

    print(f'  original total time (with IN): {sum(times_orig):.2f} s')
    print(f'  total time without IN: {sum(times_no_in):.2f} s')
    print(f'  total speedup: {sum(times_orig)/sum(times_no_in):.1f}x')
    print(f'  avg per-query time (with IN): {np.mean(times_orig)*1000:.2f} ms')
    print(f'  avg per-query time (without IN): {np.mean(times_no_in)*1000:.2f} ms')
    print(f'  median per-query time (with IN): {np.median(times_orig)*1000:.2f} ms')
    print(f'  median per-query time (without IN): {np.median(times_no_in)*1000:.2f} ms')
    print(f'  speedup distribution:')
    print(f'    min: {min(speedups):.1f}x')
    print(f'    max: {max(speedups):.1f}x')
    print(f'    mean: {np.mean(speedups):.1f}x')
    print(f'    median: {np.median(speedups):.1f}x')

# speedup grouped by IN product
print(f'\n=== Speedup by IN combination count ===')
product_bins = [(1, 5), (6, 10), (11, 20), (21, 50), (51, 100), (101, 500)]
for lo, hi in product_bins:
    group = [r for r in with_in if lo <= r['in_product'] <= hi]
    if group:
        avg_speedup = np.mean([r['speedup'] for r in group])
        avg_time_orig = np.mean([r['time_orig'] for r in group]) * 1000
        avg_time_no_in = np.mean([r['time_no_in'] for r in group]) * 1000
        print(f'  IN product [{lo}, {hi}]: {len(group)} queries, '
              f'avg speedup {avg_speedup:.1f}x, '
              f'avg time (with IN) {avg_time_orig:.1f}ms, '
              f'avg time (without IN) {avg_time_no_in:.1f}ms')

# Key question: if we remove all IN predicates, how much does evaluation time drop?
print(f'\n=== Projected full evaluation time ===')
# project from sample
ratio_in_sample = len(with_in) / len(results)  # proportion of queries with IN
avg_time_no_in_all = np.mean([r['time_no_in'] if r['has_in'] else r['time_orig'] for r in results])
avg_time_orig_all = np.mean([r['time_orig'] for r in results])

# total query count
total_queries = len(all_queries)
# projected original total time
estimated_total_orig = total_queries * avg_time_orig_all
# projected total time without IN
estimated_total_no_in = total_queries * avg_time_no_in_all

print(f'sample avg time (original): {avg_time_orig_all*1000:.2f} ms/query')
print(f'sample avg time (without IN): {avg_time_no_in_all*1000:.2f} ms/query')
print(f'projected full original total time: {estimated_total_orig:.1f} s')
print(f'projected full total time without IN: {estimated_total_no_in:.1f} s')
print(f'savings from removing IN: {estimated_total_orig - estimated_total_no_in:.1f} s ({(estimated_total_orig - estimated_total_no_in)/estimated_total_orig*100:.1f}%)')

# grouped by table count
print(f'\n=== Per-query time by table count (after removing IN) ===')
for t in sorted(set(r['tables'] for r in results)):
    group = [r for r in results if r['tables'] == t]
    times = [r['time_no_in'] if r['has_in'] else r['time_orig'] for r in group]
    print(f'  {t} tables: {len(group)} queries, avg {np.mean(times)*1000:.1f} ms')
