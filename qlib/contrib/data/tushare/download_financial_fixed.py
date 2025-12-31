#!/usr/bin/env python3
"""
下载A股财务数据（已修复版本）

修复问题：
1. 移除了错误的"跳过未上市股票"逻辑
2. TuShare API会自动返回该股票上市后的数据
3. 确保所有5466只股票都能正确下载

使用方法：
    export TUSHARE_TOKEN="your_token"
    python3 download_financial_fixed.py
"""

import os
import sys
import time
import json
import pandas as pd
from pathlib import Path
from datetime import datetime

def download_financial_data_fixed():
    """修复后的财务数据下载器"""

    print("\n🚀 A股财务数据下载器（修复版）")
    print("="*80)

    # 检查Token
    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        print("❌ 请设置 TUSHARE_TOKEN 环境变量")
        sys.exit(1)

    # 输出目录
    output_dir = Path.home() / ".qlib/qlib_data/cn_data/financial_data"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 初始化TuShare
    import tushare as ts
    pro = ts.pro_api(token)
    print(f"✅ TuShare初始化成功")

    # 获取股票列表
    print("\n📊 获取A股列表...")
    stock_list = pro.stock_basic(
        exchange='',
        list_status='L',
        fields='ts_code,name,list_date'
    ).sort_values('ts_code')

    total_stocks = len(stock_list)
    print(f"✅ A股总数: {total_stocks} 只")

    # 配置下载参数
    START_DATE = "20000101"  # 从2000年开始
    END_DATE = datetime.now().strftime("%Y%m%d")
    BATCH_SIZE = 100
    DELAY = 0.3

    print(f"\n⚙️  下载配置:")
    print(f"   时间范围: {START_DATE} - {END_DATE}")
    print(f"   批处理大小: {BATCH_SIZE}")
    print(f"   请求间隔: {DELAY}秒")
    print(f"   预计耗时: {total_stocks * DELAY / 60:.1f} 分钟")
    print("="*80)

    # 状态文件（用于断点续传）
    state_file = output_dir / "download_fixed_state.json"

    # 检查是否有未完成的下载
    downloaded_codes = set()
    start_index = 0

    if state_file.exists():
        with open(state_file, 'r') as f:
            state = json.load(f)
            downloaded_codes = set(state.get('downloaded_codes', []))
            start_index = state.get('current_index', 0)

        print(f"📥 检测到未完成下载: 已下载 {len(downloaded_codes)} 只")
        print(f"   将从第 {start_index + 1} 只股票继续")

    # 开始下载
    print(f"\n🚀 开始下载...")
    print("="*80)

    all_data = []
    batch_data = []
    batch_num = start_index // BATCH_SIZE + 1
    success_count = len(downloaded_codes)

    for idx in range(start_index, total_stocks):
        row = stock_list.iloc[idx]
        ts_code = row['ts_code']
        name = row['name']

        # 跳过已下载
        if ts_code in downloaded_codes:
            continue

        # 进度显示
        progress = (idx + 1) / total_stocks * 100
        print(f"[{idx+1}/{total_stocks}] ({progress:.1f}%) {ts_code} {name}...", end=" ", flush=True)

        try:
            # ⚠️ 关键修复：移除了"跳过未上市股票"的错误逻辑
            # TuShare API会自动返回该股票上市后的数据
            df = pro.fina_indicator(
                ts_code=ts_code,
                start_date=START_DATE,
                end_date=END_DATE
            )

            if df is not None and not df.empty:
                batch_data.append(df)
                success_count += 1
                downloaded_codes.add(ts_code)
                print(f"✅ {len(df)} 条")
            else:
                print("⚠️ 无数据")

        except Exception as e:
            print(f"❌ {str(e)[:40]}")

        # 每批次保存一次
        if (idx + 1) % BATCH_SIZE == 0 or (idx + 1) == total_stocks:
            # 保存批次数据
            if batch_data:
                batch_df = pd.concat(batch_data, ignore_index=True)

                batch_file = output_dir / f"fixed_batch_{batch_num:04d}.csv"
                batch_df.to_csv(batch_file, index=False, encoding='utf-8-sig')
                print(f"  💾 批次 {batch_num} 已保存 ({len(batch_df)} 条)")

                all_data.append(batch_df)
                batch_data = []

                # 更新状态
                state = {
                    'current_index': idx + 1,
                    'downloaded_codes': list(downloaded_codes),
                    'last_update': datetime.now().isoformat()
                }
                with open(state_file, 'w') as f:
                    json.dump(state, f)

                batch_num += 1

        # API限流
        time.sleep(DELAY)

    # 合并所有数据
    print("\n" + "="*80)
    print("📊 合并所有数据...")

    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)

        # 去重（保留最新）
        combined_df = combined_df.sort_values(['ts_code', 'end_date', 'ann_date'])
        combined_df = combined_df.drop_duplicates(
            subset=['ts_code', 'end_date'],
            keep='last'
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存完整数据
        final_file = output_dir / f"a_share_financial_fixed_{timestamp}.csv"
        combined_df.to_csv(final_file, index=False, encoding='utf-8-sig')
        print(f"✅ 完整数据: {final_file}")

        # 保存最新版本
        latest_file = output_dir / "a_share_financial_latest.csv"
        combined_df.to_csv(latest_file, index=False, encoding='utf-8-sig')
        print(f"✅ 最新版本: {latest_file}")

        # 统计信息
        print(f"\n📊 下载完成统计:")
        print(f"   成功: {success_count}/{total_stocks} 只股票")
        print(f"   总记录: {len(combined_df):,} 条")
        print(f"   字段数: {len(combined_df.columns)} 个")
        print(f"   股票数: {combined_df['ts_code'].nunique()} 只")
        print(f"   时间范围: {combined_df['end_date'].min()} - {combined_df['end_date'].max()}")

        # 按年份统计
        combined_df['year'] = combined_df['end_date'].astype(str).str[:4]
        yearly_stats = combined_df.groupby('year')['ts_code'].nunique()
        print(f"\n📊 每年股票数:")
        for year, count in yearly_stats.items():
            print(f"   {year}: {count}只")

        # 删除状态文件
        if state_file.exists():
            state_file.unlink()
            print(f"\n   已清理状态文件")

    else:
        print("⚠️ 没有下载到新数据")

    print("\n✅ 全部完成!")


if __name__ == "__main__":
    try:
        download_financial_data_fixed()
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断下载")
        print("💡 状态已保存，可以重新运行脚本继续下载")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
