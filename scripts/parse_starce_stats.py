#!/usr/bin/env python3
"""
解析 StarCE 统计 JSON 文件，交互式查看 Equalset 的度序列统计信息。

用法:
    python parse_starce_stats.py [json_file_path]

如果不指定文件路径，自动使用 running_space 下第一个找到的 statistics_*.json 文件。
"""

import json
import sys
from pathlib import Path


def load_json(filepath):
    with open(filepath) as f:
        return json.load(f)


def is_subset_of(small_entries, large_entries):
    """
    检查 small 的 entries 是否是 large 的 entries 的子集。
    宽松匹配：当 small 中某条的 ColumnName 为空字符串时（单表 Equalset），
    只要 TableName 在 large 中即视为匹配。
    """
    large_set = {(e["TableName"], e["ColumnName"]) for e in large_entries}
    for se in small_entries:
        if se["ColumnName"] == "":
            if not any(le[0] == se["TableName"] for le in large_set):
                return False
        else:
            if (se["TableName"], se["ColumnName"]) not in large_set:
                return False
    return True


def is_strict_subset(small_entries, large_entries):
    """严格子集：small 是 large 的子集且条目数更少"""
    if len(small_entries) >= len(large_entries):
        return False
    return is_subset_of(small_entries, large_entries)


def find_maximal_equalsets(stats):
    """
    找出所有极大 Equalset 的索引。
    一个 Equalset 是极大的，当且仅当不存在另一个 Equalset 严格包含它。
    """
    n = len(stats)
    maximal_indices = []
    for i in range(n):
        is_maximal = True
        es_i = stats[i]["EqualSet"]["Entries"]
        for j in range(n):
            if i == j:
                continue
            if is_strict_subset(es_i, stats[j]["EqualSet"]["Entries"]):
                is_maximal = False
                break
        if is_maximal:
            maximal_indices.append(i)
    return maximal_indices


def get_sub_equalsets(stats, parent_idx):
    """获取属于某个极大 Equalset 的所有子 Equalset 的索引（包括自身）"""
    parent_entries = stats[parent_idx]["EqualSet"]["Entries"]
    sub_indices = []
    for i, s in enumerate(stats):
        if is_subset_of(s["EqualSet"]["Entries"], parent_entries):
            sub_indices.append(i)
    return sub_indices


def format_equalset(entries):
    """将 Equalset entries 格式化为可读字符串"""
    parts = []
    for e in entries:
        if e["ColumnName"]:
            parts.append(f"{e['TableName']}.{e['ColumnName']}")
        else:
            parts.append(f"[{e['TableName']}]")
    return "{" + ", ".join(parts) + "}"


def format_cardinality(card):
    """人性化显示基数"""
    if card >= 1e9:
        return f"{card/1e9:.2f}B"
    elif card >= 1e6:
        return f"{card/1e6:.2f}M"
    elif card >= 1e3:
        return f"{card/1e3:.1f}K"
    else:
        return f"{card:.0f}"


def print_degree_sequence(ds_list, indent=2):
    """打印度序列，bin 数量多时截断显示"""
    prefix = " " * indent
    if not ds_list:
        print(f"{prefix}(空)")
        return

    print(f"{prefix}共 {len(ds_list)} 个 bin:")
    max_show = 20
    if len(ds_list) <= max_show:
        for bin_data in ds_list:
            md = bin_data["MaxDegree"]
            cnt = bin_data["Count"]
            print(f"{prefix}  MaxDegree={md:>14.2f}  Count={cnt:>10,}")
    else:
        for bin_data in ds_list[:10]:
            md = bin_data["MaxDegree"]
            cnt = bin_data["Count"]
            print(f"{prefix}  MaxDegree={md:>14.2f}  Count={cnt:>10,}")
        skipped = len(ds_list) - max_show
        print(f"{prefix}  ... 省略 {skipped} 个 bin ...")
        for bin_data in ds_list[-10:]:
            md = bin_data["MaxDegree"]
            cnt = bin_data["Count"]
            print(f"{prefix}  MaxDegree={md:>14.2f}  Count={cnt:>10,}")


def print_dsstatistic(ds_stat):
    """打印完整的 DSStatistic 信息"""
    card = ds_stat["Cardinality"]
    print(f"基数 (Cardinality): {card:,.0f}  ({format_cardinality(card)})")
    print()

    print("中心度序列 (CentralDS) — 各 join-key 值的行数乘积的分布:")
    print_degree_sequence(ds_stat.get("CentralDS", []), indent=2)
    print()

    # 各表度序列
    per_table = ds_stat.get("DSStatistic", [])
    if per_table:
        print(f"各表度序列 ({len(per_table)} 个表):")
        for table_ds in per_table:
            table_name = table_ds["Table"]
            ds = table_ds.get("DegreeSequence", [])
            # 计算该表的总条目数
            total_count = sum(bin_["Count"] for bin_ in ds)
            print(f"\n  [{table_name}] — {total_count:,} 个不同值, {len(ds)} 个 bin:")
            print_degree_sequence(ds, indent=4)


def main():
    # --- 1. 加载 JSON 文件 ---
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        running_space = Path(__file__).parent / "running_space"
        json_files = sorted(running_space.glob("statistics_*.json"))
        if not json_files:
            print("错误: 未找到统计 JSON 文件，请指定文件路径")
            print(f"用法: python {Path(__file__).name} <json_file_path>")
            sys.exit(1)
        filepath = str(json_files[0])

    print(f"加载统计文件: {filepath}")
    data = load_json(filepath)
    stats = data["Statistics"]
    print(f"AdjustRate: {data['AdjustRate']:.4f}")
    print(f"共 {len(stats)} 个 Equalset 条目\n")

    # --- 2. 找极大 Equalset ---
    maximal_idx = find_maximal_equalsets(stats)
    # 按 size 降序排列
    maximal_idx.sort(key=lambda i: len(stats[i]["EqualSet"]["Entries"]), reverse=True)

    print(f"找到 {len(maximal_idx)} 个极大 (maximal) Equalset:\n")
    for display_idx, orig_i in enumerate(maximal_idx):
        es = stats[orig_i]["EqualSet"]["Entries"]
        card = stats[orig_i]["DSStatistic"]["Cardinality"]
        print(
            f"  [{display_idx}] size={len(es):>2} | rows={format_cardinality(card):>8} | "
            f"{format_equalset(es)}"
        )

    # --- 3. 用户选择大 Equalset ---
    print()
    choice = input(f"选择一个大 Equalset [0-{len(maximal_idx)-1}] (q 退出): ").strip()
    if choice.lower() == "q":
        return
    selected_parent = maximal_idx[int(choice)]

    # --- 4. 列出子 Equalset ---
    sub_idx_list = get_sub_equalsets(stats, selected_parent)
    # 按 size 升序（从小到大），方便看层级关系
    sub_idx_list.sort(key=lambda i: len(stats[i]["EqualSet"]["Entries"]))

    parent_es = stats[selected_parent]["EqualSet"]["Entries"]
    print(f"\n父 Equalset: {format_equalset(parent_es)}")
    print(f"共有 {len(sub_idx_list)} 个子 Equalset（含自身）:\n")
    for display_idx, orig_i in enumerate(sub_idx_list):
        es = stats[orig_i]["EqualSet"]["Entries"]
        card = stats[orig_i]["DSStatistic"]["Cardinality"]
        print(
            f"  [{display_idx}] size={len(es):>2} | rows={format_cardinality(card):>8} | "
            f"{format_equalset(es)}"
        )

    # --- 5. 用户选择子 Equalset ---
    print()
    choice = input(f"选择一个子 Equalset [0-{len(sub_idx_list)-1}] (q 退出): ").strip()
    if choice.lower() == "q":
        return
    selected_sub = sub_idx_list[int(choice)]

    # --- 6. 输出度序列统计 ---
    es = stats[selected_sub]["EqualSet"]["Entries"]
    print(f"\n{'='*65}")
    print(f"选中 Equalset: {format_equalset(es)}")
    print(f"{'='*65}\n")
    print_dsstatistic(stats[selected_sub]["DSStatistic"])


if __name__ == "__main__":
    main()
