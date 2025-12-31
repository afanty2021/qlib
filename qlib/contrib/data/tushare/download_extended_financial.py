#!/usr/bin/env python3
"""
下载2000-2025年全部A股财务数据

分批下载策略：
- 批次1: 2000-2004年 (20个季度)
- 批次2: 2005-2009年 (20个季度)
- 批次3: 2010-2014年 (20个季度)
- 批次4: 2015-2019年 (20个季度)
- 批次5: 2020-2022年 (12个季度，已有2023-2024)
- 批次6: 2025年 (已公告数据)
"""

import os
import sys
import time
import json
import pandas as pd
from pathlib import Path
from datetime import datetime

def download_extended_financial_data():
    """下载扩展财务数据 (2000-2025)"""

    print("\n🚀 下载扩展财务数据 (2000-2025)")
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

    # 定义下载批次
    download_batches = [
        {
            "name": "2020-2022 (补充)",
            "start": "20200101",
            "end": "20221231",
            "priority": 1
        },
        {
            "name": "2015-2019",
            "start": "20150101",
            "end": "20191231",
            "priority": 2
        },
        {
            "name": "2010-2014",
            "start": "20100101",
            "end": "20141231",
            "priority": 3
        },
        {
            "name": "2005-2009",
            "start": "20050101",
            "end": "20091231",
            "priority": 4
        },
        {
            "name": "2000-2004",
            "start": "20000101",
            "end": "20041231",
            "priority": 5
        },
        {
            "name": "2025 (已公告)",
            "start": "20250101",
            "end": "20251231",
            "priority": 6
        }
    ]

    print(f"\n📋 下载计划: {len(download_batches)} 个批次")
    for i, batch in enumerate(download_batches, 1):
        print(f"   {i}. {batch['name']}: {batch['start']} - {batch['end']}")

    # 获取股票列表
    print("\n📊 获取A股列表...")
    stock_list = pro.stock_basic(
        exchange='',
        list_status='L',
        fields='ts_code,name,list_date'
    ).sort_values('ts_code')

    total_stocks = len(stock_list)
    print(f"✅ A股总数: {total_stocks} 只")

    # 检查现有数据
    existing_file = output_dir / "a_share_financial_latest.csv"
    existing_data = None
    existing_periods = set()

    if existing_file.exists():
        existing_data = pd.read_csv(existing_file)
        existing_data['end_date'] = existing_data['end_date'].astype(int)
        existing_periods = set(existing_data['end_date'].unique())
        print(f"✅ 已有数据: {len(existing_data)} 条")
        print(f"   已覆盖期数: {len(existing_periods)} 个")
        print(f"   时间范围: {min(existing_periods)} - {max(existing_periods)}")

    # 配置
    BATCH_SIZE = 100  # 每批100只股票
    DELAY = 0.3       # 300ms间隔

    print(f"\n⚙️  下载配置:")
    print(f"   批处理大小: {BATCH_SIZE}")
    print(f"   请求间隔: {DELAY}秒")

    # 开始分批下载
    for batch_info in download_batches:
        batch_name = batch_info['name']
        start_date = batch_info['start']
        end_date = batch_info['end']

        print("\n" + "="*80)
        print(f"📥 批次: {batch_name}")
        print(f"   时间范围: {start_date} - {end_date}")
        print("="*80)

        # 创建批次状态文件
        state_file = output_dir / f"state_{batch_name.replace(' ', '_').replace('-', '_')}.json"

        # 检查是否已完成
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
            if state.get('completed', False):
                print(f"✅ {batch_name} 已完成，跳过")
                continue

        # 初始化状态
        downloaded_codes = set()
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
                downloaded_codes = set(state.get('downloaded_codes', []))

        all_batch_data = []
        success_count = len(downloaded_codes)

        # 下载本批次数据
        for idx in range(total_stocks):
            row = stock_list.iloc[idx]
            ts_code = row['ts_code']
            name = row['name']
            list_date = row['list_date']

            # 跳过已下载
            if ts_code in downloaded_codes:
                continue

            # 跳过未上市的股票
            if list_date and int(list_date) > int(end_date[:4]):
                continue

            # 进度显示
            progress = (idx + 1) / total_stocks * 100
            print(f"[{idx+1}/{total_stocks}] ({progress:.1f}%) {ts_code} {name}...", end=" ", flush=True)

            try:
                # 下载财务数据
                df = pro.fina_indicator(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )

                if df is not None and not df.empty:
                    all_batch_data.append(df)
                    success_count += 1
                    downloaded_codes.add(ts_code)
                    print(f"✅ {len(df)} 条")
                else:
                    print("⚠️ 无数据")

            except Exception as e:
                error_msg = str(e)[:50]
                print(f"❌ {error_msg}")

            # 每BATCH_SIZE只保存一次
            if (idx + 1) % BATCH_SIZE == 0 or (idx + 1) == total_stocks:
                # 保存批次数据
                if all_batch_data:
                    batch_df = pd.concat(all_batch_data, ignore_index=True)

                    # 保存临时文件
                    temp_file = output_dir / f"temp_{batch_name.replace(' ', '_').replace('-', '_')}.csv"
                    batch_df.to_csv(temp_file, index=False, encoding='utf-8-sig')
                    print(f"  💾 临时保存: {len(batch_df)} 条")

                    all_batch_data = []

                # 更新状态
                state = {
                    'current_index': idx + 1,
                    'downloaded_codes': list(downloaded_codes),
                    'last_update': datetime.now().isoformat(),
                    'completed': False
                }
                with open(state_file, 'w') as f:
                    json.dump(state, f)

            # API限流
            time.sleep(DELAY)

        # 保存本批次最终数据
        if all_batch_data:
            final_batch_df = pd.concat(all_batch_data, ignore_index=True)

            # 保存
            batch_file = output_dir / f"{batch_name.replace(' ', '_').replace('-', '_')}.csv"
            final_batch_df.to_csv(batch_file, index=False, encoding='utf-8-sig')
            print(f"\n✅ {batch_name} 完成: {len(final_batch_df)} 条")

            # 标记完成
            state['completed'] = True
            with open(state_file, 'w') as f:
                json.dump(state, f)

    # 合并所有数据
    print("\n" + "="*80)
    print("📊 合并所有数据...")
    print("="*80)

    # 读取所有批次文件
    all_data = []

    # 读取现有数据
    if existing_data is not None:
        all_data.append(existing_data)
        print(f"✅ 现有数据: {len(existing_data)} 条")

    # 读取新批次数据
    for batch_info in download_batches:
        batch_file = output_dir / f"{batch_info['name'].replace(' ', '_').replace('-', '_')}.csv"
        if batch_file.exists():
            batch_df = pd.read_csv(batch_file)
            all_data.append(batch_df)
            print(f"✅ {batch_info['name']}: {len(batch_df)} 条")

    # 读取临时文件
    temp_files = list(output_dir.glob("temp_*.csv"))
    for temp_file in temp_files:
        temp_df = pd.read_csv(temp_file)
        all_data.append(temp_df)
        print(f"✅ 临时数据: {len(temp_df)} 条")
        # 删除临时文件
        temp_file.unlink()

    if all_data:
        # 合并
        combined_df = pd.concat(all_data, ignore_index=True)

        # 去重（保留最新）
        combined_df = combined_df.sort_values(['ts_code', 'end_date', 'ann_date'])
        combined_df = combined_df.drop_duplicates(
            subset=['ts_code', 'end_date'],
            keep='last'
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存完整数据
        final_file = output_dir / f"a_share_financial_full_{timestamp}.csv"
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
        print(f"   报告期: {combined_df['end_date'].nunique()} 个")

        # 时间范围
        combined_df['year'] = combined_df['end_date'].astype(str).str[:4]
        years = sorted(combined_df['year'].unique())
        print(f"   年份范围: {years[0]} - {years[-1]} ({len(years)} 年)")

    print("\n✅ 全部完成!")


if __name__ == "__main__":
    try:
        download_extended_financial_data()
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断下载")
        print("💡 状态已保存，可以重新运行脚本继续下载")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
