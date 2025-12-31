#!/usr/bin/env python3
"""
财务数据下载进度监控工具

实时查看2000-2025财务数据下载进度
"""

import os
import psutil
import pandas as pd
from pathlib import Path
from datetime import datetime

def check_process_status(pid: int) -> dict:
    """检查进程状态"""
    try:
        proc = psutil.Process(pid)
        return {
            "running": True,
            "cpu_percent": proc.cpu_percent(),
            "memory_mb": proc.memory_info().rss / 1024 / 1024,
            "runtime": datetime.now() - datetime.fromtimestamp(proc.create_time())
        }
    except psutil.NoSuchProcess:
        return {"running": False, "cpu_percent": 0, "memory_mb": 0, "runtime": None}

def check_phase_files(data_dir: Path) -> list:
    """检查已下载的阶段文件"""
    phase_files = sorted(data_dir.glob("phase_*.csv"))

    results = []
    for phase_file in phase_files:
        df = pd.read_csv(phase_file)
        file_size_mb = phase_file.stat().st_size / 1024 / 1024

        # 提取阶段名称
        phase_name = phase_file.stem.replace("phase_", "").replace("_", " ")

        # 年份范围
        df['year'] = df['end_date'].astype(str).str[:4]
        years = sorted(df['year'].unique())

        results.append({
            "name": phase_name,
            "file": phase_file.name,
            "records": len(df),
            "stocks": df['ts_code'].nunique(),
            "years": f"{years[0]}-{years[-1]}" if years else "N/A",
            "quarters": df['end_date'].nunique(),
            "size_mb": round(file_size_mb, 2),
            "modified": datetime.fromtimestamp(phase_file.stat().st_mtime)
        })

    return results

def check_log_file(log_path: str, lines: int = 50) -> str:
    """查看日志文件最后N行"""
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            return ''.join(all_lines[-lines:])
    except Exception as e:
        return f"无法读取日志: {str(e)}"

def estimate_completion(total_stocks: int, current_stock: int, elapsed_time) -> dict:
    """估算完成时间"""
    if current_stock == 0:
        return {"percent": 0, "eta": None, "speed": 0}

    percent = (current_stock / total_stocks) * 100
    speed = current_stock / elapsed_time.total_seconds() if elapsed_time.total_seconds() > 0 else 0

    remaining_stocks = total_stocks - current_stock
    eta_seconds = remaining_stocks / speed if speed > 0 else 0

    return {
        "percent": round(percent, 1),
        "eta_seconds": int(eta_seconds),
        "speed": round(speed, 2),
        "eta_formatted": format_time(eta_seconds)
    }

def format_time(seconds: int) -> str:
    """格式化时间"""
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        return f"{seconds//60}分{seconds%60}秒"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}小时{minutes}分"

def main():
    """主函数"""
    print("\n" + "="*80)
    print("📊 2000-2025财务数据下载进度监控")
    print("="*80)

    # 配置
    PID = 51049
    LOG_PATH = "/tmp/financial_extended_force.log"
    DATA_DIR = Path.home() / ".qlib/qlib_data/cn_data/financial_data"
    TOTAL_STOCKS = 5466

    # 1. 进程状态
    print("\n1️⃣ 进程状态")
    print("-" * 40)
    proc_status = check_process_status(PID)
    if proc_status["running"]:
        print(f"✅ 进程运行中 (PID: {PID})")
        print(f"   CPU使用率: {proc_status['cpu_percent']}%")
        print(f"   内存使用: {proc_status['memory_mb']:.1f} MB")
        if proc_status["runtime"]:
            print(f"   运行时间: {format_time(int(proc_status['runtime'].total_seconds()))}")
    else:
        print(f"❌ 进程已结束")

    # 2. 日志摘要
    print("\n2️⃣ 下载日志（最新进度）")
    print("-" * 40)
    if proc_status["running"]:
        # 提取当前进度
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            last_line = lines[-1].strip()

            # 解析进度
            if "/" in last_line and "%" in last_line:
                parts = last_line.split()
                for part in parts:
                    if "/" in part and ")" in part:
                        try:
                            current = int(part.split("/")[0].strip("[]"))
                            progress_info = estimate_completion(
                                TOTAL_STOCKS,
                                current,
                                proc_status["runtime"]
                            )
                            print(f"📈 当前进度: {current}/{TOTAL_STOCKS} ({progress_info['percent']}%)")
                            print(f"⚡ 下载速度: {progress_info['speed']} 只/秒")
                            print(f"⏱️  预计剩余: {progress_info['eta_formatted']}")
                            break
                        except:
                            pass
            print(f"\n最新状态: {last_line}")
    else:
        print("进程已结束，查看日志详情:")
        recent_log = check_log_file(LOG_PATH, 20)
        print(recent_log)

    # 3. 阶段文件统计
    print("\n3️⃣ 已下载阶段文件")
    print("-" * 40)
    phases = check_phase_files(DATA_DIR)

    if phases:
        print(f"\n已完成 {len(phases)} 个阶段:\n")

        total_records = 0
        total_size = 0

        for i, phase in enumerate(phases, 1):
            print(f"  {i}. {phase['name']}")
            print(f"     记录数: {phase['records']:,} 条")
            print(f"     股票数: {phase['stocks']} 只")
            print(f"     季度数: {phase['quarters']} 个")
            print(f"     年份范围: {phase['years']}")
            print(f"     文件大小: {phase['size_mb']} MB")
            print(f"     保存时间: {phase['modified'].strftime('%H:%M:%S')}")
            print()

            total_records += phase['records']
            total_size += phase['size_mb']

        print(f"  📊 总计: {total_records:,} 条记录, {total_size:.2f} MB")

        # 预估最终数据量
        total_phases = 6
        completed_phases = len(phases)
        if completed_phases > 0:
            avg_records = total_records / completed_phases
            estimated_total = avg_records * total_phases
            print(f"\n  📈 预估最终数据量: ~{estimated_total:,.0f} 条记录")
    else:
        print("暂无阶段文件")

    # 4. 数据库状态
    print("\n4️⃣ 现有财务数据")
    print("-" * 40)
    latest_file = DATA_DIR / "a_share_financial_latest.csv"
    if latest_file.exists():
        df_latest = pd.read_csv(latest_file)
        print(f"📄 a_share_financial_latest.csv")
        print(f"   总记录: {len(df_latest):,} 条")
        print(f"   股票数: {df_latest['ts_code'].nunique()} 只")
        print(f"   字段数: {len(df_latest.columns)} 个")

        df_latest['year'] = df_latest['end_date'].astype(str).str[:4]
        years = sorted(df_latest['year'].unique())
        print(f"   年份范围: {years[0]} - {years[-1]} ({len(years)} 年)")
    else:
        print("暂无最新数据文件")

    # 5. 目录空间
    print("\n5️⃣ 存储空间")
    print("-" * 40)
    total_size = sum(f.stat().st_size for f in DATA_DIR.rglob('*') if f.is_file())
    size_gb = total_size / 1024 / 1024 / 1024
    print(f"财务数据目录: {DATA_DIR}")
    print(f"总占用空间: {size_gb:.2f} GB")

    # 6. 下一步提示
    print("\n6️⃣ 后续操作")
    print("-" * 40)
    if proc_status["running"]:
        print("⏳ 下载进行中，请耐心等待...")
        print(f"   查看实时日志: tail -f {LOG_PATH}")
        print(f"   查看进程状态: ps -p {PID}")
        print(f"   重新运行监控: python3 {__file__}")
    else:
        if len(phases) == 6:
            print("✅ 所有阶段下载完成！")
            print("   下一步: 验证数据完整性并合并")
            print("   运行: python3 qlib/contrib/data/tushare/merge_financial_data.py")
        else:
            print(f"⚠️ 下载中断，已完成 {len(phases)}/6 个阶段")
            print("   可以重新运行下载脚本继续下载")

    print("\n" + "="*80)
    print(f"监控时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
