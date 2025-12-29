#!/usr/bin/env python3
"""
快速下载测试 - 下载100只股票的财务数据
"""

import os
import sys
import time
import pandas as pd
from pathlib import Path
from datetime import datetime

# 添加qlib路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

def download_financial_data_test():
    """下载测试数据（100只股票）"""

    print("\n🎯 A股财务数据下载测试")
    print("="*80)

    # 检查Token
    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        print("❌ 请设置TUSHARE_TOKEN环境变量")
        sys.exit(1)

    # 输出目录
    output_dir = Path.home() / ".qlib/qlib_data/cn_data/financial_data"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"✅ 输出目录: {output_dir}")

    # 初始化TuShare
    import tushare as ts
    pro = ts.pro_api(token)
    print(f"✅ TuShare初始化成功")

    # 获取股票列表（前100只）
    print("\n📊 获取股票列表...")
    stock_list = pro.stock_basic(
        exchange='',
        list_status='L',
        fields='ts_code,name'
    )

    test_stocks = stock_list.head(100)
    print(f"✅ 测试股票: {len(test_stocks)} 只")

    # 下载数据
    print("\n📥 开始下载财务数据...")
    print("="*80)

    all_data = []
    success_count = 0

    for idx, row in test_stocks.iterrows():
        ts_code = row['ts_code']
        name = row['name']

        print(f"[{idx+1}/100] {ts_code} {name}...", end=" ", flush=True)

        try:
            df = pro.fina_indicator(
                ts_code=ts_code,
                start_date="20240101",
                end_date="20241231"
            )

            if df is not None and not df.empty:
                all_data.append(df)
                success_count += 1
                print(f"✅ {len(df)} 条")
            else:
                print("⚠️ 无数据")

        except Exception as e:
            print(f"❌ {str(e)[:30]}")

        # API限流
        time.sleep(0.2)

    # 合并并保存
    print("\n" + "="*80)
    print("💾 保存数据...")

    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存完整数据
        filename = output_dir / f"test_financial_{timestamp}.csv"
        combined_df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"✅ 数据文件: {filename}")

        # 保存最新版本
        latest_file = output_dir / "financial_test_latest.csv"
        combined_df.to_csv(latest_file, index=False, encoding='utf-8-sig')
        print(f"✅ 最新版本: {latest_file}")

        print(f"\n📊 下载统计:")
        print(f"   成功: {success_count} 只股票")
        print(f"   总记录: {len(combined_df)} 条")
        print(f"   字段数: {len(combined_df.columns)} 个")

        # 显示样例数据
        print(f"\n📄 数据预览:")
        print(combined_df[['ts_code', 'end_date', 'roe', 'roa', 'or_yoy']].head(10))

    else:
        print("⚠️ 没有下载到数据")

    print("\n✅ 测试完成!")

if __name__ == "__main__":
    try:
        download_financial_data_test()
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
