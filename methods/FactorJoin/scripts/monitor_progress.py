import os
import time
import subprocess
import argparse

def get_ps_info(pid):
    try:
        output = subprocess.check_output(["ps", "-p", str(pid), "-o", "etime,%cpu,%mem"]).decode().split('\n')
        if len(output) > 1:
            return output[1].strip()
    except:
        return None
    return None

def get_last_log_lines(log_file, n=5):
    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
            # 过滤掉 header 信息
            content_lines = [l.strip() for l in lines if not l.startswith("---") and l.strip()]
            return content_lines[-n:]
    except:
        return ["无法读取日志文件"]

def get_db_activity(db_conn):
    try:
        # 提取 dbname
        db_name = "postgres"
        if "dbname=" in db_conn:
            db_name = db_conn.split("dbname=")[1].split()[0]
        
        cmd = f"psql -d {db_name} -t -c \"SELECT query, now() - query_start FROM pg_stat_activity WHERE state != 'idle' AND query NOT LIKE '%pg_stat_activity%';\""
        output = subprocess.check_output(cmd, shell=True).decode().strip()
        if not output:
            return "数据库当前无活跃采样更新 (可能正在处理 Python 逻辑)"
        return output
    except Exception as e:
        return f"无法获取数据库状态: {e}"

def monitor(pid, log_file, db_conn):
    print(f"=== FactorJoin JOBM 进度监控已启动 (PID: {pid}) ===")
    while True:
        ps_info = get_ps_info(pid)
        if not ps_info:
            print("\n[!] 警告: 进程已退出。请检查日志确认是完成还是出错。")
            break
        
        last_logs = get_last_log_lines(log_file, 5)
        db_activity = get_db_activity(db_conn)
        
        print("\n" + "="*60)
        print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"进程状态 (运行时间 CPU% MEM%): {ps_info}")
        print(f"终端最后几行输出:")
        for line in last_logs:
            print(f"  > {line}")
        print("-" * 30)
        print(f"数据库实时查询:")
        print(f"  {db_activity}")
        print("="*60)
        
        time.sleep(30)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--terminal", type=str, required=True)
    parser.add_argument("--db", type=str, required=True)
    args = parser.parse_args()
    
    monitor(args.pid, args.terminal, args.db)
