import pickle
import numpy as np
import os
from Join_scheme.binning import apply_binning_to_data_value_count
from Join_scheme.factor import Factor


def load_sample_imdb(table_buckets, tables_alias, query_file_orders, join_keys, table_key_equivalent_group,
                     SPERCENTAGE=1.0, qdir="/home/ubuntu/data_CE/saved_models/binned_cards/{}/job/all_job/"):
    qdir = qdir.format(SPERCENTAGE)
    all_sample_factors = []
    for fn in query_file_orders:
        conditional_factors = load_sample_imdb_one_query(table_buckets, tables_alias, fn, join_keys,
                                                         table_key_equivalent_group, SPERCENTAGE, qdir)
        all_sample_factors.append(conditional_factors)
    return all_sample_factors


def _get_pdf_for_key(key, source_pdfs, gt_factor, table_name, table_buckets):
    """从 source_pdfs 或 ground truth 中获取某 key 的 1D raw count 数组"""
    if source_pdfs is not None and key in source_pdfs:
        return source_pdfs[key]  # 已是 raw counts
    # gt_factor.pdfs 是归一化概率，乘以 table_len 得到 raw counts
    if isinstance(gt_factor.pdfs, dict) and key in gt_factor.pdfs:
        return gt_factor.pdfs[key] * gt_factor.table_len
    n_bins = table_buckets[table_name].bin_sizes.get(key, 1)
    return np.ones(n_bins)


def load_sample_imdb_one_query(table_buckets, tables_alias, query_file_name, join_keys, table_key_equivalent_group,
                               SPERCENTAGE=1.0, qdir="/home/ubuntu/data_CE/saved_models/binned_cards/{}/job/all_job/"):
    qdir = qdir.format(SPERCENTAGE)
    fpath = os.path.join(qdir, query_file_name)
    with open(fpath, "rb") as f:
        data = pickle.load(f)

    # pkl 中的 all_aliases 使用主查询的别名（如 ci, t），
    # 而传入的 tables_alias 使用当前子查询的别名（如 cast_info1, title1）。
    # 两者别名体系不同，必须通过表名作为中间键来匹配。
    # alias_to_table: 主查询别名 -> 表名（物化时保存，如 {ci: cast_info, t: title}）
    # tables_alias:   子查询别名 -> 表名（评估时由 parse_query_simple 生成，如 {title1: title}）
    alias_to_table = data.get("alias_to_table", {})
    if not alias_to_table:
        raise RuntimeError(
            f"pkl {query_file_name} 缺少 alias_to_table 字段，请重新运行 run_materialize_jobm.py"
        )
    # 子查询中 table_name -> subquery_alias 的反向映射
    table_to_subquery_alias = {v: k for k, v in tables_alias.items()}

    # 第一遍：为每个 (subquery_alias, key) 构建 1D pdf
    source_pdfs = dict()   # subquery_alias -> {key -> 1D pdf array}
    filter_size = dict()   # subquery_alias -> filter_count

    for i, alias in enumerate(data["all_aliases"]):
        cards = data["results"][i][0]
        if cards is None:
            continue
        column = data["all_columns"][i]
        alias = alias[0]
        # 将主查询别名转为表名
        table_name = alias_to_table.get(alias)
        if table_name is None:
            raise KeyError(f"主查询别名 {alias!r} 不在 alias_to_table 中: {alias_to_table}")
        # 找该表在当前子查询中的别名；子查询是主查询的子集，不包含的表正常跳过
        subquery_alias = table_to_subquery_alias.get(table_name)
        if subquery_alias is None:
            continue
        key = table_name + "." + column
        if table_name not in table_buckets:
            raise KeyError(f"表 {table_name!r} 不在 table_buckets 中")
        if key not in table_buckets[table_name].bin_sizes:
            raise KeyError(f"key {key!r} 不在 table_buckets[{table_name!r}].bin_sizes 中")
        n_bins = table_buckets[table_name].bin_sizes[key]
        pdfs = np.zeros(n_bins)
        for (j, val) in cards:
            if j is None:
                j = 0
            pdfs[j] += val
        table_len = np.sum(pdfs)
        if table_len == 0:
            # 空采样说明过滤后数据极少，保守地设 filter_size=1（与 sample_on_the_fly.py 一致）。
            # pdfs 用 gt 归一化概率 * 1 = 极小 raw counts，与 table_len 量纲一致。
            gt = table_key_equivalent_group[table_name]
            table_len = 1
            pdfs = gt.pdfs[key]  # 归一化概率，sum≈1，作为极小 raw counts
        # 保持 raw counts，不归一化
        if subquery_alias not in source_pdfs:
            source_pdfs[subquery_alias] = dict()
            filter_size[subquery_alias] = table_len
        source_pdfs[subquery_alias][key] = pdfs

    # 第二遍：为每个子查询表创建 Factor（pdfs 为 numpy array，1D 或 2D）
    conditional_factors = dict()
    for alias in tables_alias:
        table_name = tables_alias[alias]
        gt_factor = table_key_equivalent_group[table_name]

        if alias in source_pdfs:
            fs = filter_size[alias]
            table_len = min(gt_factor.table_len, fs / (SPERCENTAGE / 100))
            na_values = gt_factor.na_values
            sp = source_pdfs[alias]
        else:
            fs = gt_factor.table_len
            table_len = gt_factor.table_len
            na_values = gt_factor.na_values
            sp = None

        # 当前子查询中该表参与的 join key（以真实表名.列名表示），排序保证确定性
        alias_keys = sorted(join_keys.get(alias, set()))

        if len(alias_keys) == 0:
            # 无 join key，回退到 ground truth
            conditional_factors[alias] = gt_factor
        elif len(alias_keys) == 1:
            key = alias_keys[0]
            # pdf_1d 为 raw counts（与 oned_bin_modes 量纲一致）
            pdf_1d = _get_pdf_for_key(key, sp, gt_factor, table_name, table_buckets)
            conditional_factors[alias] = Factor(table_name, table_len, [key], pdf_1d,
                                                na_values=na_values)
        else:
            # 2 个 join key：以外积（独立性假设）构建 2D 联合分布（raw counts）
            # outer[j,k] = pdf1[j]*pdf2[k]/fs，使 sum(outer) = fs（与 1D 量纲一致）
            key1, key2 = alias_keys[0], alias_keys[1]
            pdf1 = _get_pdf_for_key(key1, sp, gt_factor, table_name, table_buckets)
            pdf2 = _get_pdf_for_key(key2, sp, gt_factor, table_name, table_buckets)
            outer = np.outer(pdf1, pdf2)
            if fs > 0:
                outer = outer / fs
            conditional_factors[alias] = Factor(table_name, table_len, [key1, key2], outer,
                                                na_values=na_values)

    return conditional_factors


def get_ground_truth_no_filter(equivalent_keys, data, bins, table_lens, na_values):
    all_factor_pdfs = dict()
    for PK in equivalent_keys:
        bin_value = bins[PK]
        for key in equivalent_keys[PK]:
            table = key.split(".")[0]
            temp = apply_binning_to_data_value_count(bin_value, data[key])
            if table not in all_factor_pdfs:
                all_factor_pdfs[table] = dict()
            all_factor_pdfs[table][key] = temp / np.sum(temp)

    all_factors = dict()
    for table in all_factor_pdfs:
        all_factors[table] = Factor(table, table_lens[table], list(all_factor_pdfs[table].keys()),
                                    all_factor_pdfs[table], na_values=na_values[table])
    return all_factors
