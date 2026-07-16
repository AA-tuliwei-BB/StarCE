import os
import pickle
from pathlib import Path

# JobJoin 无谓词、主查询级评估的输入准备。
# 从 Benchmark/workloads/JobJoin/queries.sql（31 行、每行一条纯 join 的 SELECT COUNT(*)）产出：
#   1. checkpoints/jobjoin_main_queries/{1..31}.sql —— 每文件一条查询，供 get_query_binned_cards 按目录物化
#   2. checkpoints/jobjoin_queries_clean.sql        —— 31 行干净 SELECT，供 test_on_jobjoin 逐行评估
#   3. checkpoints/jobjoin_sub_to_main.pkl          —— 恒等映射 ["1",...,"31"]，评估时拼 {main_id}.pkl

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

queries_file = str(PROJECT_ROOT / "Benchmark/workloads/JobJoin/queries.sql")
main_queries_dir = str(PROJECT_ROOT / "methods/FactorJoin/checkpoints/jobjoin_main_queries/")
clean_queries_file = str(PROJECT_ROOT / "methods/FactorJoin/checkpoints/jobjoin_queries_clean.sql")
output_pkl = str(PROJECT_ROOT / "methods/FactorJoin/checkpoints/jobjoin_sub_to_main.pkl")

os.makedirs(main_queries_dir, exist_ok=True)

with open(queries_file, "r") as f:
    queries = [line.strip() for line in f if line.strip()]

mapping = []
with open(clean_queries_file, "w") as cf:
    for i, sql in enumerate(queries, start=1):
        main_id = str(i)
        with open(os.path.join(main_queries_dir, f"{main_id}.sql"), "w") as mf:
            mf.write(sql)
        cf.write(sql + "\n")
        mapping.append(main_id)

with open(output_pkl, "wb") as f:
    pickle.dump(mapping, f)

print(f"Main queries: {len(queries)}")
print(f"Per-query .sql written to {main_queries_dir}")
print(f"Clean query file: {clean_queries_file}")
print(f"Mapping saved to {output_pkl}")
