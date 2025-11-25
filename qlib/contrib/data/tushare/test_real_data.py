#!/usr/bin/env python3
"""
TuShare真实数据获取测试

使用真实的Token测试TuShare数据源获取A股日线数据。
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta
import time

# 添加Qlib路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from qlib.contrib.data.tushare import TuShareConfig, TuShareProvider
from qlib.contrib.data.tushare.api_client import TuShareAPIClient


def test_api_client():
    """测试API客户端直接调用"""
    print("🔌 测试TuShare API客户端")
    print("=" * 50)

    try:
        # 从JSON配置文件加载配置
        config = TuShareConfig.from_file("demo_tushare_config.json")
        print(f"✅ 配置加载成功")
        print(f"   Token: {config.token[:10]}...")
        print(f"   API地址: {config.api_url}")

        # 创建API客户端
        with TuShareAPIClient(config) as client:
            print("\n📊 获取交易日历...")

            # 获取最近的交易日历
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

            calendar = client.get_trade_cal(
                start_date=start_date,
                end_date=end_date,
                is_open="1"
            )

            if calendar.empty:
                print("⚠️ 未获取到交易日历数据")
                return False

            print(f"✅ 获取交易日历成功: {len(calendar)} 个交易日")
            print(f"   最新交易日: {calendar['date'].iloc[-1]}")

            print("\n📈 获取股票基本信息...")
            # 获取沪深主板前10只股票
            stocks = client.get_stock_basic(
                list_status="L",
                fields="ts_code,symbol,name,area,industry,market,list_date"
            )

            if stocks.empty:
                print("⚠️ 未获取到股票信息")
                return False

            print(f"✅ 获取股票信息成功: {len(stocks)} 只股票")

            # 选择几只代表性股票
            sample_stocks = []
            for market in ['主板', '中小板', '创业板']:
                market_stocks = stocks[stocks['market'].str.contains(market, na=False)]
                if not market_stocks.empty:
                    sample_stocks.append(market_stocks.iloc[0]['ts_code'])

            sample_stocks = sample_stocks[:3]  # 最多取3只
            print(f"   测试股票: {sample_stocks}")

            print("\n💰 获取股票日线数据...")
            # 获取日线数据
            test_stock = sample_stocks[0]
            daily_data = client.get_daily_data(
                ts_code=test_stock,
                start_date=start_date,
                end_date=end_date,
                adj="qfq"  # 前复权
            )

            if daily_data.empty:
                print(f"⚠️ 未获取到 {test_stock} 的日线数据")
                return False

            print(f"✅ 获取 {test_stock} 日线数据成功: {len(daily_data)} 条记录")
            print(f"   数据字段: {list(daily_data.columns)}")
            print(f"   最新数据:")
            print(daily_data.tail(3)[['date', 'open', 'high', 'low', 'close', 'volume']].to_string())

            print("\n📊 获取每日基本面数据...")
            basic_data = client.get_daily_basic(
                ts_code=test_stock,
                start_date=start_date,
                end_date=end_date
            )

            if not basic_data.empty:
                print(f"✅ 获取基本面数据成功: {len(basic_data)} 条记录")
                print(f"   最新PE: {basic_data['pe'].iloc[-1]:.2f}")
                print(f"   最新PB: {basic_data['pb'].iloc[-1]:.2f}")

            return True

    except Exception as e:
        print(f"❌ API客户端测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_provider_integration():
    """测试数据提供者集成"""
    print("\n\n🏭 测试TuShare数据提供者集成")
    print("=" * 50)

    try:
        # 从配置文件加载
        config = TuShareConfig.from_file("demo_tushare_config.json")

        # 创建数据提供者
        with TuShareProvider(config) as provider:
            print("✅ 数据提供者创建成功")

            print("\n📅 测试交易日历获取...")
            # 获取交易日历
            end_date = datetime.now()
            start_date = end_date - timedelta(days=10)

            calendar = provider.calendar(
                start_time=start_date.strftime("%Y-%m-%d"),
                end_time=end_date.strftime("%Y-%m-%d")
            )

            if calendar:
                print(f"✅ 获取交易日历成功: {len(calendar)} 个交易日")
                print(f"   日期范围: {calendar[0]} 到 {calendar[-1]}")
            else:
                print("⚠️ 未获取到交易日历")

            print("\n📈 测试股票列表获取...")
            # 获取股票列表
            instruments = provider.instruments(market="all")

            if instruments:
                print(f"✅ 获取股票列表成功: {len(instruments)} 只股票")

                # 显示前几只股票信息
                sample_instruments = list(instruments.items())[:3]
                for code, info in sample_instruments:
                    print(f"   {code}: {info.get('name', 'N/A')} ({info.get('market', 'N/A')})")
            else:
                print("⚠️ 未获取到股票列表")
                return False

            print("\n💰 测试特征数据获取...")
            # 选择测试股票
            test_codes = list(instruments.keys())[:2]

            # 获取最近10天的特征数据
            end_time = datetime.now().strftime("%Y-%m-%d")
            start_time = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")

            features = provider.features(
                instruments=test_codes,
                fields=["close", "volume", "open"],
                start_time=start_time,
                end_time=end_time
            )

            if not features.empty:
                print(f"✅ 获取特征数据成功: {features.shape}")
                print(f"   数据列: {list(features.columns)}")
                print(f"   最新数据样例:")
                print(features.tail(3))
            else:
                print("⚠️ 未获取到特征数据")

            print("\n📊 缓存统计信息...")
            # 获取缓存统计
            cache_stats = provider.get_cache_stats()
            print(f"   缓存启用: {cache_stats['enabled']}")

            if cache_stats.get("memory"):
                mem_stats = cache_stats["memory"]
                print(f"   内存缓存: {mem_stats['size']} 条目")

            if cache_stats.get("disk"):
                disk_stats = cache_stats["disk"]
                print(f"   磁盘缓存: {disk_stats['count']} 条目")
                size_mb = disk_stats["total_size"] / 1024 / 1024
                print(f"   占用空间: {size_mb:.2f}MB")

            return True

    except Exception as e:
        print(f"❌ 数据提供者集成测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_performance():
    """测试性能"""
    print("\n\n⚡ 性能测试")
    print("=" * 50)

    try:
        config = TuShareConfig.from_file("demo_tushare_config.json")

        with TuShareAPIClient(config) as client:
            test_stock = "000001.SZ"  # 平安银行
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")

            print(f"🏃 测试 {test_stock} 60天数据获取性能...")

            # 第一次请求（无缓存）
            start_time = time.time()
            data1 = client.get_daily_data(test_stock, start_date, end_date)
            first_time = time.time() - start_time

            if data1.empty:
                print(f"⚠️ 未获取到 {test_stock} 的数据")
                return False

            print(f"   首次请求耗时: {first_time:.3f}秒")
            print(f"   数据量: {len(data1)} 条")

            # 第二次请求（可能有缓存）
            start_time = time.time()
            data2 = client.get_daily_data(test_stock, start_date, end_date)
            second_time = time.time() - start_time

            print(f"   第二次请求耗时: {second_time:.3f}秒")

            if second_time < first_time:
                speedup = first_time / second_time
                print(f"   性能提升: {speedup:.1f}x")

            print("\n📊 数据质量检查...")
            # 检查数据完整性
            missing_data = data1.isnull().sum()
            if missing_data.sum() > 0:
                print(f"   缺失数据: {missing_data.to_dict()}")
            else:
                print("   ✅ 无缺失数据")

            # 检查数据范围合理性
            price_cols = ['open', 'high', 'low', 'close']
            for col in price_cols:
                if col in data1.columns:
                    invalid_prices = (data1[col] <= 0).sum()
                    if invalid_prices > 0:
                        print(f"   ⚠️ {col} 存在非正价格: {invalid_prices} 条")
                    else:
                        print(f"   ✅ {col} 价格数据正常")

            return True

    except Exception as e:
        print(f"❌ 性能测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("🧪 TuShare真实数据获取测试")
    print("=" * 80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # 检查配置文件
    if not os.path.exists("demo_tushare_config.json"):
        print("❌ 未找到配置文件 demo_tushare_config.json")
        print("请先运行 demo.py 生成配置文件，或手动创建配置文件")
        return False

    success_count = 0
    total_tests = 3

    # 运行测试
    if test_api_client():
        success_count += 1

    if test_provider_integration():
        success_count += 1

    if test_performance():
        success_count += 1

    # 总结
    print("\n" + "=" * 80)
    print("📋 测试结果总结")
    print("=" * 80)
    print(f"✅ 成功测试: {success_count}/{total_tests}")

    if success_count == total_tests:
        print("🎉 所有测试通过！TuShare数据源集成正常工作")
    elif success_count > 0:
        print("⚠️ 部分测试通过，请检查失败的测试")
    else:
        print("❌ 所有测试失败，请检查配置和网络连接")

    print("\n💡 使用建议:")
    print("1. 首次使用建议先调用 provider.instruments() 获取股票列表")
    print("2. 使用缓存机制可以显著提升数据获取速度")
    print("3. 注意API调用频率限制，合理设置请求间隔")
    print("4. 定期检查和更新Token权限")

    return success_count == total_tests


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)