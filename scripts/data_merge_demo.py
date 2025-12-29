#!/usr/bin/env python3
"""
数据融合机制演示脚本

演示增量更新如何与本地历史数据融合

使用方法：
    python scripts/data_merge_demo.py
"""

import pandas as pd
from pathlib import Path
from datetime import datetime


def create_sample_old_data():
    """创建示例旧数据（模拟本地历史数据）"""
    print("=" * 60)
    print("步骤 1: 创建示例旧数据")
    print("=" * 60)

    # 创建 2024-12-15 到 2024-12-20 的数据
    dates = ["20241215", "20241216", "20241217", "20241218", "20241219", "20241220"]
    symbols = ["000001.SZ", "000002.SZ", "000003.SZ"]

    data = []
    for date in dates:
        for symbol in symbols:
            data.append({
                "tradedate": date,
                "symbol": symbol,
                "open": 10.0,
                "high": 10.5,
                "low": 9.5,
                "close": 10.25,
                "volume": 1000000,
                "amount": 10250000
            })

    df = pd.DataFrame(data)
    df = df.sort_values(["tradedate", "symbol"], ascending=[False, True])

    print(f"✅ 旧数据创建成功")
    print(f"   行数: {len(df)}")
    print(f"   日期范围: {df['tradedate'].min()} -> {df['tradedate'].max()}")
    print(f"   股票数量: {df['symbol'].nunique()}")
    print()

    # 保存到临时文件
    temp_file = Path("/tmp/stock_data_old.csv")
    df.to_csv(temp_file, index=False)
    print(f"💾 旧数据已保存到: {temp_file}")
    print()

    return temp_file


def create_sample_new_data():
    """创建示例新数据（模拟增量下载的数据）"""
    print("=" * 60)
    print("步骤 2: 创建示例新数据（增量下载）")
    print("=" * 60)

    # 创建 2024-12-23 到 2024-12-25 的数据（假设周末休市）
    dates = ["20241223", "20241224", "20241225"]
    symbols = ["000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ"]  # 新增一只股票

    data = []
    for date in dates:
        for symbol in symbols:
            data.append({
                "tradedate": date,
                "symbol": symbol,
                "open": 11.0,  # 价格略有上涨
                "high": 11.5,
                "low": 10.5,
                "close": 11.25,
                "volume": 1100000,
                "amount": 11250000
            })

    df = pd.DataFrame(data)

    print(f"✅ 新数据创建成功")
    print(f"   行数: {len(df)}")
    print(f"   日期范围: {df['tradedate'].min()} -> {df['tradedate'].max()}")
    print(f"   股票数量: {df['symbol'].nunique()}")
    print()

    return df


def demonstrate_merge_mechanism(old_file, new_df):
    """演示数据融合机制"""
    print("=" * 60)
    print("步骤 3: 演示数据融合机制")
    print("=" * 60)

    # 1. 读取旧数据
    print("1️⃣  读取旧数据")
    old_df = pd.read_csv(old_file)
    print(f"   旧数据行数: {len(old_df):,}")
    print(f"   旧数据列: {list(old_df.columns)}")
    print()

    # 2. 展示新旧数据
    print("2️⃣  数据概览")
    print("   旧数据最新日期:")
    print(f"   {old_df['tradedate'].iloc[0]} (假设数据按日期降序排列)")
    print()
    print("   新数据日期范围:")
    print(f"   {new_df['tradedate'].min()} -> {new_df['tradedate'].max()}")
    print()

    # 3. 拼接数据
    print("3️⃣  拼接新旧数据")
    combined_df = pd.concat([old_df, new_df], ignore_index=True)
    print(f"   合并前行数: {len(old_df):,} + {len(new_df):,} = {len(old_df) + len(new_df):,}")
    print(f"   合并后行数: {len(combined_df):,}")
    print()

    # 4. 去重
    print("4️⃣  去重处理")
    before_dedup = len(combined_df)
    combined_df = combined_df.drop_duplicates(
        subset=["tradedate", "symbol"],
        keep="last"
    )
    after_dedup = len(combined_df)
    duplicates_removed = before_dedup - after_dedup

    print(f"   去重前: {before_dedup:,} 行")
    print(f"   去重后: {after_dedup:,} 行")
    print(f"   移除重复: {duplicates_removed} 行")
    print()
    print("   📝 去重键: ['tradedate', 'symbol']")
    print("   📝 策略: keep='last' (保留最后出现的记录)")
    print()

    # 5. 排序
    print("5️⃣  排序")
    combined_df = combined_df.sort_values(["tradedate", "symbol"])
    print(f"   排序键: ['tradedate', 'symbol']")
    print(f"   顺序: 升序 (旧->新)")
    print()

    # 6. 保存
    print("6️⃣  保存融合后的数据")
    output_file = Path("/tmp/stock_data_merged.csv")
    combined_df.to_csv(output_file, index=False)
    print(f"   保存路径: {output_file}")
    print()

    return output_file, combined_df


def verify_merge_result(merged_file, merged_df):
    """验证融合结果"""
    print("=" * 60)
    print("步骤 4: 验证融合结果")
    print("=" * 60)

    # 确保 tradedate 是字符串类型
    merged_df['tradedate'] = merged_df['tradedate'].astype(str)

    # 数据完整性
    print("✅ 数据完整性检查")
    print(f"   总行数: {len(merged_df):,}")
    print(f"   日期范围: {merged_df['tradedate'].min()} -> {merged_df['tradedate'].max()}")
    print(f"   股票数量: {merged_df['symbol'].nunique()}")
    print()

    # 去重验证
    print("✅ 去重验证")
    duplicate_count = merged_df.duplicated(subset=["tradedate", "symbol"]).sum()
    print(f"   重复记录数: {duplicate_count}")
    if duplicate_count == 0:
        print("   ✅ 没有重复记录，去重成功！")
    print()

    # 排序验证
    print("✅ 排序验证")
    is_sorted = merged_df['tradedate'].is_monotonic_increasing
    print(f"   日期是否升序: {is_sorted}")
    if is_sorted:
        print("   ✅ 数据已正确排序！")
    print()

    # 展示部分数据
    print("✅ 数据预览")
    print("   最早的数据:")
    print(merged_df.head(3).to_string(index=False))
    print()
    print("   最新的数据:")
    print(merged_df.tail(3).to_string(index=False))
    print()

    # 统计信息
    print("✅ 统计信息")
    print(f"   文件大小: {merged_file.stat().st_size / 1024:.2f} KB")
    print(f"   平均每交易日记录数: {len(merged_df) / merged_df['tradedate'].nunique():.0f}")
    print()


def demonstrate_edge_cases():
    """演示边界情况处理"""
    print("=" * 60)
    print("步骤 5: 边界情况演示")
    print("=" * 60)

    # 情况 1: 数据修正
    print("1️⃣  情况 1: 数据修正")
    print("   假设 2024-12-20 的数据有误，需要修正")
    data_old = pd.DataFrame([{
        "tradedate": "20241220",
        "symbol": "000001.SZ",
        "close": 10.25,  # 旧价格
        "volume": 1000000
    }])
    data_new = pd.DataFrame([{
        "tradedate": "20241220",
        "symbol": "000001.SZ",
        "close": 10.30,  # 修正后的价格
        "volume": 1000000
    }])

    combined = pd.concat([data_old, data_new])
    combined = combined.drop_duplicates(subset=["tradedate", "symbol"], keep="last")

    print(f"   旧价格: {data_old['close'].iloc[0]}")
    print(f"   新价格: {data_new['close'].iloc[0]}")
    print(f"   最终价格: {combined['close'].iloc[0]}")
    print(f"   ✅ keep='last' 保留了新数据（修正后的价格）")
    print()

    # 情况 2: 新增股票
    print("2️⃣  情况 2: 新增股票")
    print("   假设 000004.SZ 是新上市的股票")
    data_has_stock = pd.DataFrame([{
        "tradedate": "20241223",
        "symbol": "000004.SZ",
        "close": 11.25
    }])
    print(f"   新股票: {data_has_stock['symbol'].iloc[0]}")
    print(f"   上市日期: {data_has_stock['tradedate'].iloc[0]}")
    print(f"   ✅ 新股票可以直接添加，不会冲突")
    print()


def main():
    """主函数"""
    print("\n")
    print("🎯" * 30)
    print("数据融合机制演示")
    print("🎯" * 30)
    print("\n")

    try:
        # 创建示例数据
        old_file = create_sample_old_data()
        new_df = create_sample_new_data()

        # 演示融合机制
        merged_file, merged_df = demonstrate_merge_mechanism(old_file, new_df)

        # 验证结果
        verify_merge_result(merged_file, merged_df)

        # 边界情况
        demonstrate_edge_cases()

        print("=" * 60)
        print("🎉 演示完成！")
        print("=" * 60)
        print()
        print("📊 融合后的数据文件:")
        print(f"   {merged_file}")
        print()
        print("💡 核心要点:")
        print("   1. 增量检测: 仅读取文件第一行获取最新日期")
        print("   2. 数据拼接: pd.concat() 合并新旧数据")
        print("   3. 去重策略: drop_duplicates(subset=[...], keep='last')")
        print("   4. 排序保证: sort_values() 确保数据一致性")
        print()

    except Exception as e:
        print(f"❌ 演示失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
