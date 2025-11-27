#!/usr/bin/env python3
"""
获取上证指数和沪深300成分股近五年日线数据

使用TuShare数据源获取：
1. 上证指数(000001.SH)近五年日线数据
2. 沪深300成分股列表及近五年日线数据
3. 将数据保存为qlib可用的格式
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# 添加Qlib路径
sys.path.insert(0, os.path.dirname(__file__))

from qlib import init
from qlib.data import D
from qlib.contrib.data.tushare import TuShareConfig, TuShareProvider
from qlib.contrib.data.tushare.utils import TuShareCodeConverter, TuShareDateUtils

# 设置TuShare Token
TUSHARE_TOKEN = "eb13b3bfd2bd07fd9eb40234f19941c73f230e1e98cc212b8cd407c7"

def get_date_range():
    """获取近五年的日期范围"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5*365)  # 近5年

    # 转换为TuShare格式 (YYYYMMDD)
    start_date_tushare = start_date.strftime('%Y%m%d')
    end_date_tushare = end_date.strftime('%Y%m%d')

    # 转换为标准格式 (YYYY-MM-DD)
    start_date_std = start_date.strftime('%Y-%m-%d')
    end_date_std = end_date.strftime('%Y-%m-%d')

    return start_date_tushare, end_date_tushare, start_date_std, end_date_std

def get_shanghai_index_data():
    """获取上证指数近五年日线数据"""
    print("=" * 60)
    print("📈 获取上证指数(000001.SH)近五年日线数据")
    print("=" * 60)

    try:
        # 直接使用tushare获取数据
        import tushare as ts
        ts.set_token(TUSHARE_TOKEN)
        pro = ts.pro_api()

        # 获取日期范围
        start_date_tushare, end_date_tushare, start_date_std, end_date_std = get_date_range()
        print(f"📅 数据时间范围: {start_date_std} 至 {end_date_std}")

        # 获取上证指数日线数据
        print("📊 获取上证指数数据...")

        # 获取指数日线数据
        index_df = pro.index_daily(
            ts_code="000001.SH",
            start_date=start_date_tushare,
            end_date=end_date_tushare
        )

        if not index_df.empty:
            # 转换为标准格式
            index_df['trade_date'] = pd.to_datetime(index_df['trade_date'])
            index_df = index_df.sort_values('trade_date')

            # 重置索引为日期
            index_df.set_index('trade_date', inplace=True)

            # 选择需要的列并重命名
            index_data = index_df[['open', 'high', 'low', 'close', 'vol', 'amount']].copy()
            index_data.columns = ['open', 'high', 'low', 'close', 'volume', 'amount']

            print(f"✅ 上证指数数据获取成功")
            print(f"   数据形状: {index_data.shape}")
            print(f"   时间范围: {index_data.index[0]} 至 {index_data.index[-1]}")

            # 显示数据样本
            print("\n📋 数据样本:")
            print(index_data.tail())

            # 保存数据
            output_file = "shanghai_index_5years.csv"
            index_data.to_csv(output_file)
            print(f"\n💾 数据已保存至: {output_file}")

            return index_data
        else:
            print("❌ 未获取到上证指数数据")
            return None

    except Exception as e:
        print(f"❌ 获取上证指数数据失败: {e}")
        return None

def get_csi300_stocks_data():
    """获取沪深300成分股及近五年日线数据"""
    print("\n" + "=" * 60)
    print("📊 获取沪深300成分股近五年日线数据")
    print("=" * 60)

    try:
        # 直接使用tushare获取数据
        import tushare as ts
        ts.set_token(TUSHARE_TOKEN)
        pro = ts.pro_api()

        # 获取日期范围
        start_date_tushare, end_date_tushare, start_date_std, end_date_std = get_date_range()

        print("🔍 获取沪深300成分股列表...")

        # 获取沪深300成分股
        try:
            # 获取沪深300指数成分股
            index_cons_df = pro.index_cons(
                ts_code="000300.SH",  # 沪深300指数代码
                start_date=start_date_tushare,
                end_date=end_date_tushare
            )

            if not index_cons_df.empty:
                # 获取唯一的股票代码
                stock_codes = index_cons_df['con_code'].unique().tolist()
                print(f"✅ 沪深300成分股数量: {len(stock_codes)}")

                # 显示前10只股票
                sample_stocks = stock_codes[:10]
                print(f"   前10只股票: {sample_stocks}")
            else:
                print("⚠️ 未能获取沪深300成分股，使用示例股票")
                # 使用一些主要的沪深300成分股作为示例
                stock_codes = [
                    "000001.SZ", "000002.SZ", "000858.SZ", "002415.SZ", "002594.SZ",
                    "600000.SH", "600036.SH", "600519.SH", "600887.SH", "601318.SH",
                    "601398.SH", "601857.SH", "601988.SH", "603259.SH", "000063.SZ"
                ]
                print(f"   使用示例股票: {len(stock_codes)} 只")

        except Exception as e:
            print(f"⚠️ 获取沪深300成分股失败: {e}")
            print("   使用示例股票")
            stock_codes = [
                "000001.SZ", "000002.SZ", "000858.SZ", "002415.SZ", "002594.SZ",
                "600000.SH", "600036.SH", "600519.SH", "600887.SH", "601318.SH"
            ]

        # 分批获取数据（避免API限制）
        all_data = []
        batch_size = 5  # 每批5只股票，减少API压力

        print(f"\n📈 开始获取日线数据 (每批 {batch_size} 只股票)...")

        for i in range(0, len(stock_codes), batch_size):
            batch_stocks = stock_codes[i:i+batch_size]
            print(f"   处理第 {i//batch_size + 1} 批: {batch_stocks}")

            batch_data_list = []
            for stock_code in batch_stocks:
                try:
                    # 获取单只股票日线数据
                    stock_df = pro.daily(
                        ts_code=stock_code,
                        start_date=start_date_tushare,
                        end_date=end_date_tushare
                    )

                    if not stock_df.empty:
                        # 添加股票代码
                        stock_df['instrument'] = stock_code
                        # 转换日期格式
                        stock_df['trade_date'] = pd.to_datetime(stock_df['trade_date'])
                        batch_data_list.append(stock_df)
                        print(f"     ✅ {stock_code}: {stock_df.shape[0]} 天数据")
                    else:
                        print(f"     ⚠️ {stock_code}: 无数据")

                except Exception as e:
                    print(f"     ❌ {stock_code}: 获取失败 - {e}")
                    continue

                # 避免API频率限制
                import time
                time.sleep(0.5)  # 每只股票间隔0.5秒

            if batch_data_list:
                batch_data = pd.concat(batch_data_list, ignore_index=True)
                # 设置多级索引
                batch_data.set_index(['instrument', 'trade_date'], inplace=True)
                all_data.append(batch_data)
                print(f"     ✅ 批次合并: {batch_data.shape}")

            # 批次间等待
            if i + batch_size < len(stock_codes):
                print("     ⏳ 等待2秒避免API限制...")
                time.sleep(2)

        # 合并所有数据
        if all_data:
            csi300_data = pd.concat(all_data, ignore_index=False)
            # 重命名列以匹配标准格式
            csi300_data.rename(columns={'vol': 'volume'}, inplace=True)

            # 选择需要的列
            csi300_data = csi300_data[['open', 'high', 'low', 'close', 'volume', 'amount']]

            print(f"\n✅ 沪深300数据合并完成")
            print(f"   总数据形状: {csi300_data.shape}")
            print(f"   股票数量: {csi300_data.index.get_level_values(0).nunique()}")
            print(f"   交易日期: {csi300_data.index.get_level_values(1).nunique()} 天")

            # 显示数据样本
            print("\n📋 数据样本:")
            print(csi300_data.head(10))

            # 保存数据
            output_file = "csi300_stocks_5years.csv"
            csi300_data.to_csv(output_file)
            print(f"\n💾 数据已保存至: {output_file}")

            return csi300_data
        else:
            print("❌ 未获取到任何沪深300数据")
            return None

    except Exception as e:
        print(f"❌ 获取沪深300数据失败: {e}")
        return None

def convert_to_qlib_format(data, filename_prefix):
    """将数据转换为Qlib标准格式"""
    print("\n" + "=" * 60)
    print("🔄 转换数据为Qlib标准格式")
    print("=" * 60)

    if data is None or data.empty:
        print("❌ 没有数据需要转换")
        return

    try:
        # 重置索引
        if data.index.nlevels > 1:
            data_flat = data.reset_index()
            # 重命名列
            data_flat.columns = ['instrument', 'date'] + list(data_flat.columns[2:])
        else:
            data_flat = data.reset_index()
            data_flat.columns = ['date'] + list(data_flat.columns[1:])
            data_flat['instrument'] = data_flat['date']  # 临时列，后面会替换

        # 确保日期格式正确
        data_flat['date'] = pd.to_datetime(data_flat['date']).dt.strftime('%Y-%m-%d')

        # 按Qlib格式保存
        qlib_file = f"{filename_prefix}_qlib_format.csv"
        data_flat.to_csv(qlib_file, index=False)

        print(f"✅ 数据已转换为Qlib格式")
        print(f"   输出文件: {qlib_file}")
        print(f"   数据形状: {data_flat.shape}")
        print(f"   列名: {list(data_flat.columns)}")

        return data_flat

    except Exception as e:
        print(f"❌ 数据格式转换失败: {e}")
        return None

def generate_summary_report(index_data, csi300_data):
    """生成数据获取总结报告"""
    print("\n" + "=" * 80)
    print("📊 数据获取总结报告")
    print("=" * 80)

    # 获取日期范围
    start_date_tushare, end_date_tushare, start_date_std, end_date_std = get_date_range()

    print(f"📅 数据时间范围: {start_date_std} 至 {end_date_std}")
    print(f"📅 总交易日: 约 {5*365} 天")

    if index_data is not None and not index_data.empty:
        print(f"\n📈 上证指数(000001.SH):")
        print(f"   ✅ 数据获取成功")
        print(f"   📊 数据形状: {index_data.shape}")
        if index_data.index.nlevels > 1:
            trading_days = index_data.index.get_level_values(1).nunique()
            print(f"   📅 交易天数: {trading_days}")

        # 显示最新价格信息
        if not index_data.empty:
            latest_data = index_data.iloc[-1]
            if 'close' in latest_data:
                latest_close = latest_data['close']
                print(f"   💰 最新收盘价: {latest_close:.2f}")

    if csi300_data is not None and not csi300_data.empty:
        print(f"\n📊 沪深300成分股:")
        print(f"   ✅ 数据获取成功")
        print(f"   📊 数据形状: {csi300_data.shape}")

        if csi300_data.index.nlevels > 1:
            stock_count = csi300_data.index.get_level_values(0).nunique()
            trading_days = csi300_data.index.get_level_values(1).nunique()
            print(f"   🏢 股票数量: {stock_count}")
            print(f"   📅 交易天数: {trading_days}")
            print(f"   📈 总数据点: {stock_count * trading_days:,}")

    print(f"\n📁 输出文件:")
    output_files = []
    if index_data is not None:
        output_files.append("shanghai_index_5years.csv")
        output_files.append("shanghai_index_5years_qlib_format.csv")

    if csi300_data is not None:
        output_files.append("csi300_stocks_5years.csv")
        output_files.append("csi300_stocks_5years_qlib_format.csv")

    for file in output_files:
        if os.path.exists(file):
            file_size = os.path.getsize(file) / 1024 / 1024  # MB
            print(f"   📄 {file} ({file_size:.2f} MB)")

    print(f"\n🎉 数据获取任务完成！")
    print(f"   💡 提示: 数据已保存为CSV格式，可直接用于Qlib量化分析")

def main():
    """主函数"""
    print("🎯 上证指数和沪深300成分股近五年日线数据获取")
    print("=" * 80)

    # 检查TuShare Token
    if not TUSHARE_TOKEN:
        print("❌ 未设置TuShare Token")
        print("   请在代码中设置正确的TUSHARE_TOKEN")
        return

    print(f"🔑 TuShare Token: {TUSHARE_TOKEN[:10]}...{TUSHARE_TOKEN[-4:]}")

    # 获取上证指数数据
    index_data = get_shanghai_index_data()

    # 获取沪深300成分股数据
    csi300_data = get_csi300_stocks_data()

    # 转换为Qlib格式
    if index_data is not None:
        convert_to_qlib_format(index_data, "shanghai_index_5years")

    if csi300_data is not None:
        convert_to_qlib_format(csi300_data, "csi300_stocks_5years")

    # 生成总结报告
    generate_summary_report(index_data, csi300_data)

if __name__ == "__main__":
    main()