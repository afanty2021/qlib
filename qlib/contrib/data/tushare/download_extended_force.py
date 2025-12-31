#!/usr/bin/env python3
"""
强制下载2000-2025财务数据

分阶段下载：
阶段1: 2020-2022年
阶段2: 2015-2019年
阶段3: 2010-2014年
阶段4: 2005-2009年
阶段5: 2000-2004年
阶段6: 2025年（已有公告）
"""

import os
import sys
import time
import pandas as pd
from pathlib import Path
from datetime import datetime

print("\n🚀 强制下载2000-2025财务数据")
print("="*80)

# 检查Token
token = os.getenv("TUSHARE_TOKEN")
if not token:
    print("❌ 请设置TUSHARE_TOKEN环境变量")
    sys.exit(1)

# 输出目录
output_dir = Path.home() / ".qlib/qlib_data/cn_data/financial_data"
output_dir.mkdir(parents=True, exist_ok=True)

# 初始化TuShare
import tushare as ts
pro = ts.pro_api(token)
print(f"✅ TuShare初始化成功")

# 定义下载阶段
download_phases = [
    ("2020-2022", "20200101", "20221231"),
    ("2015-2019", "20150101", "20191231"),
    ("2010-2014", "20100101", "20141231"),
    ("2005-2009", "20050101", "20091231"),
    ("2000-2004", "20000101", "20041231"),
    ("2025最新", "20250101", "20251231"),
]

# 获取股票列表
print("\n📊 获取A股列表...")
stock_list = pro.stock_basic(
    exchange='',
    list_status='L',
    fields='ts_code,name,list_date'
).sort_values('ts_code')

total_stocks = len(stock_list)
print(f"✅ A股总数: {total_stocks} 只")

# 配置
BATCH_SIZE = 200
DELAY = 0.2

print(f"\n⚙️  下载配置:")
print(f"   批处理大小: {BATCH_SIZE}")
print(f"   请求间隔: {DELAY}秒")
print(f"   预计总耗时: {len(download_phases) * total_stocks * DELAY / 60:.1f} 分钟")

# 开始分阶段下载
all_phase_data = []

for phase_name, start_date, end_date in download_phases:
    print("\n" + "="*80)
    print(f"📥 阶段: {phase_name}")
    print(f"   时间范围: {start_date} - {end_date}")
    print("="*80)

    phase_data = []
    success_count = 0

    for idx in range(total_stocks):
        row = stock_list.iloc[idx]
        ts_code = row['ts_code']
        name = row['name']
        list_date = row['list_date']

        # 跳过未上市的
        if list_date and pd.notna(list_date):
            if int(str(list_date)[:4]) > int(end_date[:4]):
                continue

        # 进度
        progress = (idx + 1) / total_stocks * 100

        try:
            # 下载数据
            df = pro.fina_indicator(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )

            if df is not None and not df.empty:
                phase_data.append(df)
                success_count += 1
                print(f"[{idx+1}/{total_stocks}] ({progress:.1f}%) {ts_code} ✅ {len(df)}条")
            else:
                print(f"[{idx+1}/{total_stocks}] ({progress:.1f}%) {ts_code} ⚠️ 无数据")

        except Exception as e:
            print(f"[{idx+1}/{total_stocks}] ({progress:.1f}%) {ts_code} ❌ {str(e)[:30]}")

        # 每BATCH_SIZE保存一次
        if (idx + 1) % BATCH_SIZE == 0 or (idx + 1) == total_stocks:
            if phase_data:
                # 保存阶段数据
                phase_df = pd.concat(phase_data, ignore_index=True)
                phase_file = output_dir / f"phase_{phase_name.replace('-', '_').replace(' ', '_')}.csv"
                phase_df.to_csv(phase_file, index=False, encoding='utf-8-sig')
                print(f"  💾 阶段保存: {len(phase_df)} 条")
                all_phase_data.append(phase_df)
                phase_data = []

        # API限流
        time.sleep(DELAY)

    print(f"✅ {phase_name} 完成: {success_count}/{total_stocks} 只股票")

# 合并所有数据
print("\n" + "="*80)
print("📊 合并所有阶段数据...")
print("="*80)

# 读取现有数据
existing_file = output_dir / "a_share_financial_latest.csv"
if existing_file.exists():
    existing_data = pd.read_csv(existing_file)
    all_phase_data.append(existing_data)
    print(f"✅ 现有数据: {len(existing_data)} 条")

# 读取阶段文件
for phase_name, _, _ in download_phases:
    phase_file = output_dir / f"phase_{phase_name.replace('-', '_').replace(' ', '_')}.csv"
    if phase_file.exists():
        phase_df = pd.read_csv(phase_file)
        all_phase_data.append(phase_df)
        print(f"✅ {phase_name}: {len(phase_df)} 条")

if all_phase_data:
    # 合并所有数据
    print("\n正在合并...")
    combined_df = pd.concat(all_phase_data, ignore_index=True)

    # 去重
    print("正在去重...")
    combined_df['end_date'] = combined_df['end_date'].astype(int)
    combined_df = combined_df.sort_values(['ts_code', 'end_date', 'ann_date'])
    combined_df = combined_df.drop_duplicates(
        subset=['ts_code', 'end_date'],
        keep='last'
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 保存完整数据
    final_file = output_dir / f"a_share_financial_2000_2025_{timestamp}.csv"
    combined_df.to_csv(final_file, index=False, encoding='utf-8-sig')
    print(f"\n✅ 完整数据: {final_file}")

    # 保存最新版本
    latest_file = output_dir / "a_share_financial_latest.csv"
    combined_df.to_csv(latest_file, index=False, encoding='utf-8-sig')
    print(f"✅ 最新版本: {latest_file}")

    # 统计
    print(f"\n📊 最终统计:")
    print(f"   总记录: {len(combined_df):,} 条")
    print(f"   股票数: {combined_df['ts_code'].nunique()} 只")
    print(f"   字段数: {len(combined_df.columns)} 个")

    # 年份统计
    combined_df['year'] = combined_df['end_date'].astype(str).str[:4]
    year_counts = combined_df['year'].value_counts().sort_index()
    print(f"\n   年份分布 ({len(year_counts)} 年):")
    for year in sorted(year_counts.index):
        print(f"     {year}: {year_counts[year]:,} 条")

    print(f"\n   时间范围: {year_counts.index.min()} - {year_counts.index.max()}")

print("\n✅ 全部完成!")
