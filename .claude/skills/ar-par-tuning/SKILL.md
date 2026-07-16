---
name: ar-par-tuning
description: StarCE PM0 AR/PAR 参数自动调优实验：通过调用 StarCE 探索候选 AR×PAR 网格、用 |bias|+k*spread 指标评估、选择最优参数并与 PM1 基线对比。当用户提到 AR/PAR 调优、AdjustRate、PredicateAdjustRate、|bias|+spread、2D 网格、正交小提琴图、PM0 参数选择、tune_two_phase、update_summary 时使用。
---

# AR/PAR 参数自动调优实验

## 目录结构

```
experiment/ar_par_tuning/
├── __init__.py                  # 包导出
├── tuner.py                     # 核心调优引擎 (ARPARTuner)
├── splitting.py                 # 子查询级随机拆分
├── update_summary.py            # ★ 更新 summary 的统一入口
├── TuneARPAR.ipynb              # 主实验 notebook（1D 扫描）
├── PlotTuningResults.ipynb      # 1D 结果可视化
├── Plot2DGrid.ipynb             # 2D 正交网格可视化
├── run_all.py                   # 批量运行 1D 扫描（已过时）
├── tune_two_phase.py            # 两阶段调优（先 PAR 后 AR）
└── checkpoint/                  # 拆分索引 + 调优汇总 + 最终估值 + 图表 PDF
    ├── all_summary.json         # 所有 benchmark 的汇总
    └── {benchmark}/
        ├── split_tuning_indices.json
        ├── split_eval_indices.json
        ├── tuning_summary.json           # 最优 AR/PAR + grid_scores + 各项统计
        └── card_{benchmark}_tuned_optimal.txt  # 最优参数下的子查询基数估值
```

候选估值文件沿用 StarCE checkpoint 模式：
```
experiment/checkpoint/StarCE/ar_par_tuning/{benchmark}/card_{benchmark}_AR{ar}_PAR{par}.txt
```

## 更新 summary

**`update_summary.py` 是唯一入口**，无需手动操作。两种模式：

```bash
# 仅改指标（如换 k 值），不重跑 StarCE — 秒级
python update_summary.py --analyze-only -k 3

# 完整流程：跑 2D 候选扫描 + 最终评估 + 写 summary
python update_summary.py

# 只更新指定 benchmark
python update_summary.py --analyze-only --benchmarks STATS JOBM
```

每次运行自动更新：
- `checkpoint/{benchmark}/tuning_summary.json` — 单 benchmark 详情（含 grid_scores）
- `checkpoint/all_summary.json` — 四 benchmark 汇总

`tuning_summary.json` 结构：
```json
{
  "benchmark": "STATS",
  "best_ar": 0.1, "best_par": 0.0,
  "score_k": 2.0,
  "estimate_file": "checkpoint/STATS/card_STATS_tuned_optimal.txt",
  "grid_scores": {"AR0p1_PAR0": {"ar": 0.1, "par": 0.0, "score": 2.347, ...}, ...},
  "full_stats":   {"score": 2.353, "pm1_score": 2.542, "|bias|": 0.373, "spread": 0.990},
  "tuning_stats": {"score": 2.347, ...},
  "eval_stats":   {"score": 2.369, "pm1_score": 2.574, ...}
}
```

## 核心指标：|bias| + k*spread

不用 Q-Error，而是带符号的对数误差：

- `e_i = log10(est_i / true_i)` — 正=高估，负=低估
- `bias = mean(e_i)` — 系统性偏差方向与大小
- `spread = std(e_i)` — 不一致程度（高低估混合越大 spread 越大）
- `score = |bias| + k * spread` — 默认 k=2

**spread 权重 2 倍于 bias**：一致性比无偏更重要。全部高估 2x 比一半低估 10x 一半高估 10x 好得多。

## 候选参数

`[0, 0.01, 0.1, 1.0]`。1D 扫描（AR=PAR）4 候选，2D 正交（AR×PAR）16 候选。

## 模块

### tuner.py — ARPARTuner

```python
tuner = ARPARTuner(project_root, benchmark, runner)
candidates = tuner.generate_candidates(ar_values=[0,0.01,0.1,1.0], mode_2d=True)
tuner.run_candidate_sweep(candidates, run_starce=True)  # 写 checkpoint
tuner.run_tuned_evaluation(ar, par)                       # 最终评估
```

关键方法：
- `generate_candidates(ar_values, par_values, mode_2d)` — 生成候选列表
- `run_candidate_sweep(candidates)` — 每候选运行 StarCE，保存到 checkpoint
- `run_tuned_evaluation(ar, par, label)` — 跑最终评估，写到 tuning_checkpoint

### splitting.py

- `split_subqueries(n, tune_ratio, seed)` — 随机拆分子查询索引
- `get_n_subqueries(benchmark)` — 读 real.txt 行数
- `load_split_indices(dir)` / `save_split_indices(dir, ...)` — JSON 持久化

## Notebooks

### Plot2DGrid.ipynb — AR×PAR 正交可视化

4×4 网格，每格：共享 x 轴的 KDE 密度曲线（窄=集中，宽=分散），红色=中位数，蓝色=均值。背景色=score 热力图，金色框=最优。全局归一化带宽保证跨格宽度可比。

### PlotTuningResults.ipynb — 1D 结果可视化

|bias| vs spread 散点图、Score 柱状图、误差分布小提琴图、评估集箱线图、Score 分解堆叠图。

### TuneARPAR.ipynb — 早期 1D 实验

Phase 0: 子查询拆分 → Phase 1: 1D 候选扫描 → Phase 2: 逐子查询最优（均值聚合，已弃用）→ Phase 3: 评估 vs PM1。

### tune_two_phase.py — 两阶段调优

Phase 1: 在单Star子查询上调 PAR（AR=1.0）  
Phase 2: 用最优 PAR，在全量上调 AR

单Star = 所有表共享至少一个公共 EqualSet 的子查询（AR 不影响这部分估计）。

## 实验结果（2D 正交网格，k=2）

| Benchmark | AR | PAR | Eval Score | PM1 Score | Winner |
|---|---|---|---|---|---|
| **STATS** | 0.1 | 0.0 | 2.369 | 2.574 | **PM0** |
| **JOBM** | 0.0 | 0.01 | 2.091 | 2.519 | **PM0** |
| JOBLight | 0.0 | 0.01 | 1.011 | 0.939 | PM1 |
| **JOBLightRanges** | 0.0 | 0.01 | 1.633 | 2.106 | **PM0** |

结论：
- **PAR 在所有 benchmark 上都是 0 或 0.01**：谓词过滤应完全收缩到均值
- **STATS 上 AR=0.1 优于 AR=0**：Join 收缩可以略有保留，但 PAR 必须为 0
- 1D 对角线（AR=PAR）无法发现 STATS 的最优组合（PAR=0.1 会恶化）；2D 正交解耦后才能找到
- STATS、JOBM、JOBLightRanges 三个 benchmark 上 tuned PM0 显著优于 PM1
