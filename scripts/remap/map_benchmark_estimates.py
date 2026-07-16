#!/usr/bin/env python3
"""
将 End-to-End-CardEst-Benchmark 中的方法估计结果映射到 Benchmark/ 目录。
支持 FLAT、BayesCard、DeepDB、NeuroCard 四种方法。

归一化策略:
  1. 表名按字典序排序
  2. 对所有等值 join 条件做 Union-Find 建立等价类
  3. 每个等价类内列按字典序排序, 用第一个列做锚点, 生成最小不冗余 join
  4. filter 按字典序排序
  5. 签名 = (sorted_tables, canonical_joins, sorted_filters) 精确匹配
"""

import re, sys
from collections import defaultdict
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent.parent


def parse_sql(sql: str) -> dict | None:
    sql = re.sub(r'\s+', ' ', sql).strip().lower().rstrip(';')
    fm = re.search(r'from (.+?)( where |$)', sql)
    if not fm: return None
    a2t = {}
    tables = []
    for t in fm.group(1).split(","):
        p = t.strip().split()
        if len(p) >= 3 and p[1] == 'as': tbl, als = p[0], p[2]
        elif len(p) >= 2: tbl, als = p[0], p[1]
        else: tbl = als = p[0]
        a2t[als] = tbl
        tables.append(tbl)
    wm = re.search(r'where (.+)$', sql)
    conds = [c.strip() for c in wm.group(1).split(" and ")] if wm else []
    joins, filts = [], []
    for c in conds:
        ps = re.split(r'(<=|>=|!=|<>|=|<|>)', c, maxsplit=1)
        if len(ps) >= 3 and '.' in ps[0] and '.' in ps[2]:
            joins.append((ps[0].strip(), ps[1], ps[2].strip()))
        else:
            filts.append(c)
    return {'tables': tables, 'a2t': a2t, 'joins': joins, 'filts': filts}


def canonicalize(parsed: dict) -> tuple | None:
    """
    返回规范签名: (sorted_tables, canonical_joins, sorted_filters)
    """
    sig, _groups = _canonicalize_inner(parsed)
    return sig


def _canonicalize_inner(parsed: dict) -> tuple:
    """
    返回 (签名, 列等价类列表)。
    列等价类: [[table.column, ...], ...]  每组是等值连接的所有列
    """
    a2t = parsed['a2t']
    tables = [re.sub(r'\d+$', '', t) for t in parsed['tables']]
    tables = tuple(sorted(set(tables)))

    joins = parsed['joins']
    filts = parsed['filts']

    def nc(c):
        a, cn = c.split('.')
        t = re.sub(r'\d+$', '', a2t.get(a, a))
        return f"{t}.{cn}"

    parent = {}
    def find(x):
        if x not in parent: parent[x] = x
        if parent[x] != x: parent[x] = find(parent[x])
        return parent[x]
    def union(x, y):
        parent[find(x)] = find(y)

    for l, op, r in joins:
        if op == '=':
            union(nc(l), nc(r))
            find(nc(l)); find(nc(r))

    groups = defaultdict(set)
    for n in parent:
        groups[find(n)].add(n)

    col_groups = []
    canonical_joins = []
    for g in sorted(groups.values(), key=lambda s: sorted(s)[0] if s else ''):
        if len(g) < 2:
            continue
        cols = sorted(g)
        col_groups.append(cols)
        anchor = cols[0]
        for other in cols[1:]:
            canonical_joins.append(f"{anchor} = {other}")

    canonical_joins = tuple(sorted(canonical_joins))

    def nf(f):
        for a, t in sorted(a2t.items(), key=lambda x: -len(x[0])):
            f = f.replace(f"{a}.", f"{t}.")
        return re.sub(r'\s+', ' ', f).strip()

    canonical_filts = tuple(sorted(nf(f) for f in filts))

    return (tables, canonical_joins, canonical_filts), col_groups


# ── 桥接表推断 ──

# STATS: 根据等值列名推断桥接表
def stats_bridge_for_column(col: str) -> str | None:
    """根据列名推断桥接表: userid/owneruserid -> users, postid/relatedpostid -> posts"""
    col = col.lower()
    if col in ('userid', 'owneruserid', 'lasteditoruserid'):
        return 'users'
    if col in ('postid', 'relatedpostid'):
        return 'posts'
    return None

# JOBLight: movie_id -> title
def joblight_bridge_for_column(col: str) -> str | None:
    col = col.lower()
    if col == 'movie_id':
        return 'title'
    return None

# 桥接表的主键
BRIDGE_KEY = {'users': 'users.id', 'posts': 'posts.id', 'title': 'title.id'}


def add_bridges_and_match(our_sig, col_groups, sp_map, bridge_fn):
    """
    对未匹配的查询尝试加桥接表。每个等价类按列名推断桥接表,
    添加桥接表的主键列到等价类中, 重新规范化后匹配。
    返回匹配到的 estimate 或 None。
    """
    tables, joins, filts = our_sig
    if not col_groups:
        return None

    # 为每个等价类推断桥接表
    bridge_tables = set()
    extra_joins = []  # 需要额外添加的 join 条件 (table.col = bridge.key)

    for group in col_groups:
        # 从该组的列名推断桥接
        col_names = {c.split('.')[1] for c in group}
        bridges_for_group = set()
        for cn in col_names:
            b = bridge_fn(cn)
            if b:
                bridges_for_group.add(b)

        for bt in bridges_for_group:
            bridge_tables.add(bt)
            # 将该组所有列连接到桥接表主键
            bk = BRIDGE_KEY[bt]
            for col in group:
                extra_joins.append(f"{col} = {bk}")

    if not bridge_tables:
        return None

    # 构建新的表集和 join 集
    new_tables = tuple(sorted(set(tables) | bridge_tables))
    # 将原有 join 和新增桥接 join 合并, 重新做 Union-Find
    all_joins = list(joins) + extra_joins

    # 模拟 parse_sql 的输出结构来重新 canonicalize
    # 需要 a2t 来规范化列名, 但这里已经是规范化的 table.column 了
    # 直接做 Union-Find
    parent = {}
    def find(x):
        if x not in parent: parent[x] = x
        if parent[x] != x: parent[x] = find(parent[x])
        return parent[x]
    def union(x, y):
        parent[find(x)] = find(y)

    for j in all_joins:
        parts = j.split(' = ')
        if len(parts) == 2:
            union(parts[0], parts[1])
            find(parts[0]); find(parts[1])

    groups = defaultdict(set)
    for n in parent:
        groups[find(n)].add(n)

    new_joins = []
    for g in sorted(groups.values(), key=lambda s: sorted(s)[0] if s else ''):
        if len(g) < 2:
            continue
        cols = sorted(g)
        anchor = cols[0]
        for other in cols[1:]:
            new_joins.append(f"{anchor} = {other}")

    new_sig = (new_tables, tuple(sorted(new_joins)), filts)

    if new_sig in sp_map:
        return sp_map[new_sig]
    return None


def map_dataset(name, sp_sqls, estimates, our_sqls, out_path, bridge_fn=None):
    print(f"\n{'='*60}")
    print(f"{name}")
    print(f"{'='*60}")

    # 构建 SP 映射: 签名 -> [(line_no, estimate)]
    sp_sig_to_list = defaultdict(list)
    sp_err = 0
    for i, sql in enumerate(sp_sqls):
        p = parse_sql(sql)
        if not p: sp_err += 1; continue
        sig = canonicalize(p)
        if not sig: sp_err += 1; continue
        sp_sig_to_list[sig].append((i, estimates[i]))

    sp_map = {sig: lst[0][1] for sig, lst in sp_sig_to_list.items()}

    sp_conflicts = sum(1 for sig, lst in sp_sig_to_list.items()
                       if len(set(e for _, e in lst)) > 1)

    print(f"  SP: {len(sp_sqls)}条 -> {len(sp_map)}个唯一签名, "
          f"签名内冲突:{sp_conflicts}, 解析失败:{sp_err}")

    # 匹配
    out = [None] * len(our_sqls)
    unmatched = []
    bridge_matched = 0
    match_count_per_sp = defaultdict(int)

    for i, sql in enumerate(our_sqls):
        p = parse_sql(sql)
        if not p: unmatched.append((i, "parse", sql[:120])); continue
        sig, col_groups = _canonicalize_inner(p)
        if not sig: unmatched.append((i, "sig", sql[:120])); continue

        if sig in sp_map:
            out[i] = sp_map[sig]
            match_count_per_sp[sig] += 1
        elif bridge_fn is not None:
            est = add_bridges_and_match(sig, col_groups, sp_map, bridge_fn)
            if est is not None:
                out[i] = est
                bridge_matched += 1
            else:
                unmatched.append((i, sig))
        else:
            unmatched.append((i, sig))

    m = sum(1 for e in out if e is not None)
    u = len(unmatched)
    print(f"  直接匹配: {m - bridge_matched}, 桥接匹配: {bridge_matched}")
    print(f"  总计: {m}/{len(our_sqls)} ({100*m/len(our_sqls):.1f}%)")
    print(f"  未匹配: {u}")

    # 重复使用检测
    sp_multi_use = [(sig, cnt) for sig, cnt in match_count_per_sp.items() if cnt > 1]
    if sp_multi_use:
        sp_multi_use.sort(key=lambda x: -x[1])
        print(f"  SP签名被多条our匹配: {len(sp_multi_use)}个签名, 涉及{sum(cnt for _,cnt in sp_multi_use)}条our")

    # 按表数分布
    by_n = defaultdict(lambda: [0, 0])
    for i, sql in enumerate(our_sqls):
        p = parse_sql(sql)
        if not p: continue
        sig, _ = _canonicalize_inner(p)
        if not sig: continue
        n = len(sig[0])
        if out[i] is not None: by_n[n][0] += 1
        else: by_n[n][1] += 1
    for n in sorted(by_n):
        ma, um = by_n[n]
        if ma + um > 0:
            print(f"    {n}表: {ma} matched, {um} unmatched ({100*ma/(ma+um):.0f}%)")

    # 按原因分类
    tbl_diff = 0; join_diff = 0; filt_diff = 0
    for item in unmatched:
        if isinstance(item[1], str): continue
        sig = item[1]
        same_tbl_join = [s for s in sp_map if s[0] == sig[0] and s[1] == sig[1]]
        same_tbl = [s for s in sp_map if s[0] == sig[0]]
        if same_tbl_join: filt_diff += 1
        elif same_tbl: join_diff += 1
        else: tbl_diff += 1
    print(f"    table_mismatch: {tbl_diff}, join_mismatch: {join_diff}, filter_mismatch: {filt_diff}")

    if unmatched:
        print(f"\n  ── 未匹配示例 (前10条) ──")
        for idx, sig in unmatched[:10]:
            if isinstance(sig, str): print(f"    [{idx}] {sig}"); continue
            t, j, f = sig
            print(f"    [{idx}] tables={t}, joins={j[:2]}, filters={f[:2]}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        for e in out:
            f.write(f"{e}\n" if e is not None else "MISSING\n")
    ok = (u == 0)
    print(f"\n  结果: {'OK' if ok else f'MISSING={u}'} -> {out_path}")
    return ok


def main():
    all_ok = True

    # ═══ STATS-CEB ═══
    sp_raw = [l.strip() for l in (PROJ / "Stats-CEB/End-to-End-CardEst-Benchmark/workloads/stats_CEB/sub_plan_queries/stats_CEB_sub_queries.sql").read_text().splitlines() if l.strip()]
    sp_sqls = []
    for l in sp_raw:
        parts = l.split("||")
        sp_sqls.append(parts[0].strip().rstrip(';'))
    our_stats = [l.strip().rstrip(';') for l in (PROJ / "Benchmark/workloads/STATS-CEB/subquery/subquery.sql").read_text().splitlines() if l.strip()]

    stats_est_dir = PROJ / "Stats-CEB/End-to-End-CardEst-Benchmark/workloads/stats_CEB/sub_plan_queries/estimates"
    for method in ['flat', 'bayescard', 'deepdb', 'neurocard']:
        est_file = stats_est_dir / f"stats_CEB_sub_queries_{method}.txt"
        ests = [float(l) for l in est_file.read_text().splitlines() if l.strip()]
        assert len(sp_sqls) == len(ests), f"{method}: {len(sp_sqls)} vs {len(ests)}"
        all_ok &= map_dataset(f"STATS-CEB/{method}", sp_sqls, ests, our_stats,
                              PROJ / f"Benchmark/workloads/STATS-CEB/subquery/result/{method}.txt",
                              bridge_fn=stats_bridge_for_column)

    # ═══ JOBLight ═══
    jl_sp = PROJ / "Stats-CEB/End-to-End-CardEst-Benchmark/workloads/job-light/sub_plan_queries/job_light_sub_query.sql"
    our_jl_path = PROJ / "Benchmark/workloads/JOBLight/subquery/subquery.sql"
    if our_jl_path.exists():
        jl_sp_lines = [l.strip().rstrip(';') for l in jl_sp.read_text().splitlines() if l.strip()]
        our_jl_lines = [l.strip().rstrip(';') for l in our_jl_path.read_text().splitlines() if l.strip()]

        jl_est_dir = PROJ / "Stats-CEB/End-to-End-CardEst-Benchmark/workloads/job-light/sub_plan_queries/estimates"
        for method in ['flat', 'bayescard', 'deepdb', 'neurocard']:
            est_file = jl_est_dir / f"job_light_sub_queries_{method}.txt"
            jl_ests = [float(l) for l in est_file.read_text().splitlines() if l.strip()]
            assert len(jl_sp_lines) == len(jl_ests), f"JOBLight {method}: {len(jl_sp_lines)} vs {len(jl_ests)}"
            all_ok &= map_dataset(f"JOBLight/{method}", jl_sp_lines, jl_ests, our_jl_lines,
                                  PROJ / f"Benchmark/workloads/JOBLight/subquery/result/{method}.txt",
                                  bridge_fn=joblight_bridge_for_column)

    if not all_ok:
        print("\n" + "=" * 60)
        print("存在无法匹配的查询。")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
