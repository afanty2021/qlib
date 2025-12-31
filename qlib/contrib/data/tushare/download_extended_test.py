#!/usr/bin/env python3
"""
扩展财务数据下载 - 快速测试版

先下载2000-2022年的少量股票测试连接和速度
"""

import os
import sys
import time
import pandas as pd
from pathlib import Path
from datetime import datetime

print("\n🎯 扩展财务数据下载测试")
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

# 获取股票列表（前50只测试）
print("\n📊 获取股票列表（前50只测试）...")
stock_list = pro.stock_basic(
    exchange='',
    list_status='L',
    fields='ts_code,name,list_date'
).sort_values('ts_code').head(50)

print(f"✅ 测试股票: {len(stock_list)} 只")

# 测试下载2000-2022数据
print("\n📥 测试下载 2020-2022 数据...")
print("="*80)

test_data = []

for idx, row in stock_list.iterrows():
    ts_code = row['ts_code']
    name = row['name']

    print(f"[{idx+1}/50] {ts_code} {name}...", end=" ", flush=True)

    try:
        # 下载2020-2022数据
        df = pro.fina_indicator(
            ts_code=ts_code,
            start_date="20200101",
            end_date="20221231"
        )

        if df is not None and not df.empty:
            test_data.append(df)
            print(f"✅ {len(df)} 条")
        else:
            print("⚠️ 无数据")

    except Exception as e:
        print(f"❌ {str(e)[:40]}")

    time.sleep(0.2)

# 合并测试数据
if test_data:
    combined = pd.concat(test_data, ignore_index=True)

    print("\n" + "="*80)
    print("📊 测试结果:")
    print(f"   成功: {len(test_data)} 只股票")
    print(f"   总记录: {len(combined)} 条")
    print(f"   字段数: {len(combined.columns)} 个")

    # 时间分布
    combined['year'] = combined['end_date'].astype(str).str[:4]
    year_counts = combined['year'].value_counts().sort_index()
    print(f"\n   年份分布:")
    for year, count in year_counts.items():
        print(f"     {year}: {count} 条")

    # 保存测试数据
    test_file = output_dir / "test_2000_2022.csv"
    combined.to_csv(test_file, index=False, encoding='utf-8-sig')
    print(f"\n✅ 测试数据已保存: {test_file}")

    print("\n💡 如果测试成功，将开始全部下载:")
    print("   • 2000-2022: 23年 × 4季度 × 5000股票 ≈ 460,000条")
    print("   • 2023-2024: 已有")
    print("   • 2025: 已公告数据")
    print("   • 总计: 约500,000条记录")
    print("   • 预计耗时: 2-3小时")

    print("\n🚀 准备开始全部下载...")
    print("   (这将在后台运行)")

else:
    print("❌ 测试失败，请检查API连接")

print("\n✅ 测试完成!")
