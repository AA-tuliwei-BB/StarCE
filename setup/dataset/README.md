# 数据集

StarCE 使用两个基准数据集：

| 数据集 | 表数 | 大小 | 来源 |
|--------|------|------|------|
| **STATS-CEB** | 8 张 | ~39 MB (CSV) | StackExchange dump |
| **IMDB** | 21 张 | ~4.8 GB (CSV 解压后) | Internet Movie Database |

## STATS-CEB

STATS-CEB 已随仓库提供，CSV 文件位于 `Benchmark/STATS/`。

验证数据集完整性：

```bash
bash setup/dataset/init_stats.sh
```

## IMDB

IMDB 数据需要下载（~3.5 GB 压缩包），解压后约 4.8 GB，存放在 `Benchmark/IMDB/`。

下载并解压：

```bash
bash setup/dataset/init_imdb.sh
```

下载地址：<https://event.cwi.nl/da/job/imdb.tgz>

## 后续步骤

CSV 数据就绪后，使用 `setup/duckdb/` 和 `setup/postgresql/` 中的脚本将数据导入数据库。
