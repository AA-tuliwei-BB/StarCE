#!/bin/bash
# ============================================================
# 一键测量各 Benchmark 的 pgsql 单表基数估计耗时
# 口径: bpftrace uprobe/uretprobe 挂 clauselist_selectivity 函数本体
#       (谓词选择率计算总入口, 天然剔除 parse/join 规划/EXPLAIN 格式化等包装开销)
# 用法: bash experiment/measure_pg_single_query_est.sh
# 说明: 仅 bpftrace 需要 root, 脚本内部自动调用 sudo (首次会提示输入密码);
#       文件均由当前用户创建, owner 不会被 root 污染
# 依赖: sudo 权限, bpftrace, 运行中的 PostgreSQL, psql
# 输出 (checkpoint/Postgre/pg_single_query_est/):
#   {Benchmark}.json   机器可读数据 (统计量 + 直方图桶)
#   summary.json       全量 JSON
# ============================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNING_SPACE="$PROJECT_ROOT/experiment/running_space"
BENCHMARK_DIR="$PROJECT_ROOT/Benchmark/workloads"
CHECKPOINT_DIR="$PROJECT_ROOT/experiment/checkpoint/Postgre/pg_single_query_est"
PYTHON="$(command -v python3 || echo /usr/bin/python3)"

mkdir -p "$CHECKPOINT_DIR"

PSQL="${PSQL:-/usr/local/pgsql/13.1/bin/psql}"
[ -x "$PSQL" ] || PSQL="$(command -v psql)"
[ -x "$PSQL" ] || { echo "错误: 未找到 psql" >&2; exit 1; }

PG_PID="$(pgrep -f 'bin/postgres -D' | head -1 || true)"
[ -n "$PG_PID" ] || { echo "错误: PostgreSQL 未在运行" >&2; exit 1; }
POSTGRES_BIN="$(readlink -f "/proc/$PG_PID/exe")"

BPFTRACE="$(command -v bpftrace || echo /usr/local/bin/bpftrace)"
[ -x "$BPFTRACE" ] || { echo "错误: 未找到 bpftrace" >&2; exit 1; }

# 精简探针: 仅耗时直方图(µs) + 调用计数
BPF_PROG="uprobe:${POSTGRES_BIN}:clauselist_selectivity { @start[tid] = nsecs; }
uretprobe:${POSTGRES_BIN}:clauselist_selectivity /@start[tid]/ { @dur_us = hist((nsecs - @start[tid]) / 1000); @count = count(); delete(@start[tid]); }"

BENCHMARKS=("STATS-CEB:stats" "JOBM:imdbm" "JOBLight:imdblight" "JOBLightRanges:imdblightranges")

gen_limit0_sql() {
    "$PYTHON" - "$1" "$2" <<'EOF'
import re, sys
src, dst = sys.argv[1], sys.argv[2]
lines = []
for line in open(src):
    line = line.strip()
    if not line:
        continue
    line = re.sub(r"count\s*\(\s*\*\s*\)", "*", line, flags=re.I)
    line = line.rstrip(";").strip() + " LIMIT 0;"
    lines.append(line)
open(dst, "w").write("\n".join(lines) + "\n")
EOF
}

SUMMARY_ROWS=()

run_one_benchmark() {
    local name="$1" db="$2"
    local sql_file="$RUNNING_SPACE/pg_single_query_${name}_limit0.sql"
    local bpf_out="$RUNNING_SPACE/pg_sel_${name}.txt"
    local json_out="$CHECKPOINT_DIR/${name}.json"
    local nq output count mean median p95 pmax

    gen_limit0_sql "$BENCHMARK_DIR/$name/single_query/single_query.sql" "$sql_file"
    nq="$(wc -l < "$sql_file")"
    echo "=== $name ($db, $nq 条单表查询) ==="

    # 仅 bpftrace 需要 root; 重定向由当前用户 shell 完成, 输出文件归当前用户
    sudo timeout -s INT 40 "$BPFTRACE" -e "$BPF_PROG" > "$bpf_out" 2>&1 &
    local bpf_pid=$!
    sleep 3
    "$PSQL" "host=127.0.0.1 port=5432 user=postgres dbname=$db" \
        -v ON_ERROR_STOP=1 -f "$sql_file" -o /dev/null
    sleep 1
    # SIGINT 经 sudo -> timeout -> bpftrace 转发; 若转发失败由 timeout 40s 兜底
    sudo kill -INT "$bpf_pid" 2>/dev/null || true
    wait "$bpf_pid" 2>/dev/null || true

    output="$("$PYTHON" - "$bpf_out" "$json_out" "$name" "$db" "$nq" <<'EOF'
import json, re, sys
bpf_out, json_out, name, db, nq = sys.argv[1:6]
text = open(bpf_out).read()
m = re.search(r"@count:\s*(\d+)", text)
count = int(m.group(1)) if m else 0
m = re.search(r"@dur_us:\s*\n(.*?)(?=\n@|\Z)", text, re.S)
buckets = []
raw_hist = ""
if m:
    raw_hist = m.group(1)
    for line in raw_hist.splitlines():
        mm = re.match(r"\[(\d+)(?:,\s*(\d+))?[)\]]\s+(\d+)", line.strip())
        if mm:
            lo = int(mm.group(1))
            hi = mm.group(2)
            n = int(mm.group(3))
            if hi is None:
                if lo == 1:
                    lo, hi = 0, 1
                else:
                    lo, hi = lo, lo * 2
            buckets.append((lo, int(hi), n))
total = sum(n for _, _, n in buckets)
if total:
    mean = sum(n * (lo + hi) / 2 for lo, hi, n in buckets) / total
    def quantile(q):
        s = 0
        for lo, hi, n in sorted(buckets):
            s += n
            if s >= total * q:
                return (lo + hi) / 2
        return 0
    median, p95 = quantile(0.5), quantile(0.95)
    pmax = max(hi for _, hi, _ in buckets)
else:
    mean = median = p95 = pmax = 0

data = {
    "benchmark": name,
    "database": db,
    "num_queries": int(nq),
    "num_calls": count,
    "statistics_us": {
        "mean": round(mean, 1),
        "median": round(median, 1),
        "p95": round(p95, 1),
        "max": pmax,
    },
    "histogram_us": [{"lo": lo, "hi": hi, "count": n} for lo, hi, n in buckets],
}
json.dump(data, open(json_out, "w"), indent=2)

print(f"benchmark: {name}")
print(f"database: {db}")
print(f"num_queries: {nq}")
print(f"num_calls: {count}")
print(f"mean_us: {mean:.1f}")
print(f"median_us: {median:.1f}")
print(f"p95_us: {p95:.1f}")
print(f"max_us: {pmax}")
print("histogram_us (raw):")
print(raw_hist.rstrip())
print(f"ROW|{count}|{mean:.1f}|{median:.1f}|{p95:.1f}|{pmax}")
EOF
)"
    echo "$output" | grep -v '^ROW|'
    row="$(grep '^ROW|' <<< "$output")"
    IFS='|' read -r _ count mean median p95 pmax <<< "$row"
    SUMMARY_ROWS+=("$name|$nq|$count|$mean|$median|$p95|$pmax")
}

for entry in "${BENCHMARKS[@]}"; do
    run_one_benchmark "${entry%%:*}" "${entry##*:}"
done

echo ""
echo "===== 汇总 (clauselist_selectivity 函数本体耗时, µs) ====="
printf "%-16s %8s %8s %8s %10s %8s %8s\n" "Benchmark" "查询条数" "调用次数" "平均µs" "中位数µs" "P95µs" "最大µs"
for row in "${SUMMARY_ROWS[@]}"; do
    IFS='|' read -r name nq count mean median p95 pmax <<< "$row"
    printf "%-16s %8s %8s %8s %10s %8s %8s\n" "$name" "$nq" "$count" "$mean" "$median" "$p95" "$pmax"
done

"$PYTHON" - "$CHECKPOINT_DIR" <<'EOF'
import json, sys
d = sys.argv[1]
data = {}
for name in ["STATS-CEB", "JOBM", "JOBLight", "JOBLightRanges"]:
    try:
        data[name] = json.load(open(f"{d}/{name}.json"))
    except FileNotFoundError:
        pass
json.dump(data, open(f"{d}/summary.json", "w"), indent=2)
EOF

echo ""
echo "结果已保存: $CHECKPOINT_DIR/"
