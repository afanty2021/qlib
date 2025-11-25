#!/usr/bin/env python3
"""
Qlib TuShare数据源使用示例

演示如何使用TuShare数据源进行量化投资研究。
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta

# 添加Qlib路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from qlib import init
from qlib.data import D
from qlib.contrib.data.tushare import TuShareConfig, TuShareProvider
from qlib.contrib.data.tushare.utils import (
    TuShareCodeConverter,
    TuShareDataProcessor,
    TuShareDateUtils
)
from qlib.contrib.data.tushare.field_mapping import TuShareFieldMapping


def example_basic_usage():
    """
    基本使用示例
    """
    print("=" * 60)
    print("📊 基本使用示例")
    print("=" * 60)

    # 从环境变量加载配置
    config = TuShareConfig.from_env()
    print(f"✅ 配置加载完成: {config}")

    # 使用TuShare数据源初始化Qlib
    print("\n🚀 初始化Qlib...")
    init(provider_uri="tushare", default_conf={"tushare": config})

    # 获取交易日历
    print("\n📅 获取交易日历...")
    calendar = D.calendar(start_time="2024-01-01", end_time="2024-12-31")
    print(f"2024年共有 {len(calendar)} 个交易日")
    print(f"第一个交易日: {calendar[0]}")
    print(f"最后一个交易日: {calendar[-1]}")

    # 获取股票列表
    print("\n📈 获取股票列表...")
    try:
        instruments = D.instruments("csi300")
        print(f"CIS300成分股数量: {len(instruments)}")

        # 显示前5只股票
        sample_stocks = list(instruments)[:5]
        print(f"前5只股票: {sample_stocks}")
    except Exception as e:
        print(f"⚠️ 获取股票列表失败: {e}")
        # 使用默认股票列表
        sample_stocks = ["SZ000001", "SH600000"]

    # 获取股票数据
    print("\n💰 获取股票数据...")
    try:
        data = D.features(
            instruments=sample_stocks,
            fields=["close", "volume", "open"],
            start_time="2024-01-01",
            end_time="2024-01-31"
        )
        print(f"数据形状: {data.shape}")
        print(f"数据列: {list(data.columns)}")
        print("数据示例:")
        print(data.head())
    except Exception as e:
        print(f"❌ 获取数据失败: {e}")


def example_advanced_usage():
    """
    高级使用示例
    """
    print("\n" + "=" * 60)
    print("🔧 高级使用示例")
    print("=" * 60)

    # 自定义配置
    config = TuShareConfig(
        token=os.getenv("TUSHARE_TOKEN"),
        enable_cache=True,
        cache_ttl=3600,  # 1小时缓存
        max_retries=3,
        rate_limit=180,  # 降低请求频率
        validate_data=True,
        adjust_price=True,  # 启用复权
        log_level="INFO"
    )
    print(f"✅ 自定义配置: {config}")

    # 使用上下文管理器
    with TuShareProvider(config) as provider:
        print("\n📅 获取交易日历...")
        calendar = provider.calendar(
            start_time="2024-01-01",
            end_time="2024-03-31"
        )
        print(f"Q1交易日数量: {len(calendar)}")

        print("\n📈 获取股票信息...")
        try:
            instruments = provider.instruments(market="all")
            print(f"总股票数量: {len(instruments)}")

            # 显示统计信息
            markets = {}
            for code, info in instruments.items():
                market = info.get("market", "unknown")
                markets[market] = markets.get(market, 0) + 1

            print("市场分布:")
            for market, count in markets.items():
                print(f"  {market}: {count}")
        except Exception as e:
            print(f"⚠️ 获取股票信息失败: {e}")

        print("\n💰 获取特征数据...")
        try:
            features = provider.features(
                instruments=["SZ000001", "SH600000"],
                fields=["open", "high", "low", "close", "volume"],
                start_time="2024-01-01",
                end_time="2024-01-10"
            )

            if not features.empty:
                print(f"数据形状: {features.shape}")
                print("数据统计:")
                print(features.describe())
            else:
                print("❌ 未获取到数据")
        except Exception as e:
            print(f"❌ 获取特征数据失败: {e}")

        print("\n📊 缓存统计...")
        cache_stats = provider.get_cache_stats()
        print(f"缓存启用: {cache_stats['enabled']}")
        if cache_stats.get("memory"):
            print(f"内存缓存: {cache_stats['memory']['size']} 条目")
        if cache_stats.get("disk"):
            print(f"磁盘缓存: {cache_stats['disk']['count']} 条目")


def example_data_processing():
    """
    数据处理示例
    """
    print("\n" + "=" * 60)
    print("🔍 数据处理示例")
    print("=" * 60)

    # 代码转换示例
    print("📝 股票代码转换:")
    codes = ["000001", "600000", "300001"]
    for code in codes:
        tushare_code = TuShareCodeConverter.to_tushare_format(code)
        qlib_code = TuShareCodeConverter.to_qlib_format(code)
        print(f"  {code} -> TuShare: {tushare_code} -> Qlib: {qlib_code}")

    # 字段映射示例
    print("\n🗂️ 字段映射:")
    tushare_fields = ["open", "high", "low", "close", "vol", "amount"]
    for field in tushare_fields:
        qlib_field = TuShareFieldMapping.get_qlib_field(field)
        print(f"  {field} -> {qlib_field}")

    # 日期处理示例
    print("\n📅 日期处理:")
    dates = ["2024-01-01", "2024/01/01", "20240101"]
    for date in dates:
        tushare_date = TuShareDateUtils.to_tushare_date(date)
        dt_obj = TuShareDateUtils.from_tushare_date(tushare_date)
        print(f"  {date} -> {tushare_date} -> {dt_obj}")

    # 获取一些示例数据进行处理
    print("\n🔧 数据处理演示:")
    try:
        config = TuShareConfig.from_env()
        with TuShareProvider(config) as provider:
            # 获取单只股票数据
            df = provider.features(
                instruments=["SZ000001"],
                fields=["open", "high", "low", "close", "volume"],
                start_time="2024-01-01",
                end_time="2024-01-10"
            )

            if not df.empty:
                # 转换为单只股票格式
                if df.index.nlevels > 1:
                    stock_data = df.xs("SZ000001", level=0)
                else:
                    stock_data = df

                print(f"原始数据形状: {stock_data.shape}")

                # 数据验证
                is_valid, errors = TuShareDataProcessor.validate_trading_data(stock_data)
                print(f"数据验证: {'✅ 通过' if is_valid else '❌ 失败'}")
                if errors:
                    print(f"错误: {errors}")

                # 数据清洗
                cleaned_data = TuShareDataProcessor.clean_trading_data(stock_data)
                print(f"清洗后数据形状: {cleaned_data.shape}")

                # 技术指标计算
                indicators_data = TuShareDataProcessor.calculate_technical_indicators(cleaned_data)
                indicator_cols = [col for col in indicators_data.columns if col in ["ma_5", "ma_20", "rsi", "macd"]]
                if indicator_cols:
                    print(f"技术指标示例:")
                    print(indicators_data[indicator_cols].tail())
            else:
                print("⚠️ 无法获取示例数据")

    except Exception as e:
        print(f"❌ 数据处理演示失败: {e}")


def example_error_handling():
    """
    错误处理示例
    """
    print("\n" + "=" * 60)
    print("⚠️ 错误处理示例")
    print("=" * 60)

    from qlib.contrib.data.tushare.exceptions import (
        TuShareError,
        TuShareConfigError,
        TuShareAPIError,
        TuShareDataError
    )

    # 配置错误示例
    print("1️⃣ 配置错误处理:")
    try:
        invalid_config = TuShareConfig(
            token="",  # 空Token
            max_retries=-1  # 无效重试次数
        )
    except TuShareConfigError as e:
        print(f"✅ 捕获配置错误: {e}")

    # API错误处理示例
    print("\n2️⃣ API错误处理:")
    try:
        config = TuShareConfig(token="invalid_token")
        with TuShareProvider(config) as provider:
            # 这会触发Token错误
            provider.features(
                instruments=["SZ000001"],
                fields=["close"],
                start_time="2024-01-01",
                end_time="2024-01-02"
            )
    except TuShareAPIError as e:
        print(f"✅ 捕获API错误: {e}")
        print(f"   状态码: {e.status_code}")
        print(f"   API方法: {e.api_method}")
    except TuShareError as e:
        print(f"✅ 捕获通用TuShare错误: {e}")

    # 数据错误处理示例
    print("\n3️⃣ 数据错误处理:")
    try:
        # 创建无效数据进行测试
        invalid_data = pd.DataFrame({
            "open": [-1, 0, 10],  # 无效价格
            "high": [5, 15, 8],   # high < low
            "low": [8, 5, 15],    # low > high
            "close": [12, 8, 12],  # close超出范围
            "volume": [-100, 1000, 500]  # 负成交量
        })

        is_valid, errors = TuShareDataProcessor.validate_trading_data(invalid_data)
        if not is_valid:
            print(f"✅ 检测到数据错误: {len(errors)} 个")
            for i, error in enumerate(errors, 1):
                print(f"   {i}. {error}")
    except Exception as e:
        print(f"❌ 数据验证失败: {e}")


def example_performance_monitoring():
    """
    性能监控示例
    """
    print("\n" + "=" * 60)
    print("📈 性能监控示例")
    print("=" * 60)

    import time

    # 配置监控
    config = TuShareConfig(
        enable_cache=True,
        enable_api_logging=True,
        log_level="INFO"
    )

    with TuShareProvider(config) as provider:
        # 测试缓存性能
        print("🚀 缓存性能测试:")

        # 第一次请求（无缓存）
        start_time = time.time()
        try:
            data1 = provider.features(
                instruments=["SZ000001", "SH600000"],
                fields=["close", "volume"],
                start_time="2024-01-01",
                end_time="2024-01-31"
            )
            first_request_time = time.time() - start_time
            print(f"  首次请求耗时: {first_request_time:.2f}秒")
            print(f"  数据量: {data1.shape if not data1.empty else 0}")
        except Exception as e:
            print(f"  ❌ 首次请求失败: {e}")
            first_request_time = float('inf')

        # 第二次请求（使用缓存）
        if first_request_time != float('inf'):
            start_time = time.time()
            try:
                data2 = provider.features(
                    instruments=["SZ000001", "SH600000"],
                    fields=["close", "volume"],
                    start_time="2024-01-01",
                    end_time="2024-01-31"
                )
                cached_request_time = time.time() - start_time
                print(f"  缓存请求耗时: {cached_request_time:.2f}秒")

                if cached_request_time < first_request_time:
                    speedup = first_request_time / cached_request_time
                    print(f"  缓存加速比: {speedup:.1f}x")
            except Exception as e:
                print(f"  ❌ 缓存请求失败: {e}")

        # 缓存统计
        print("\n📊 缓存统计:")
        cache_stats = provider.get_cache_stats()
        print(f"  缓存启用: {cache_stats['enabled']}")

        if cache_stats.get("memory"):
            mem_stats = cache_stats["memory"]
            print(f"  内存缓存: {mem_stats['size']}/{mem_stats['max_size']} 条目")
            print(f"  使用率: {mem_stats['usage_ratio']:.1%}")

        if cache_stats.get("disk"):
            disk_stats = cache_stats["disk"]
            size_mb = disk_stats["total_size"] / 1024 / 1024
            print(f"  磁盘缓存: {disk_stats['count']} 条目")
            print(f"  占用空间: {size_mb:.2f}MB")
            print(f"  使用率: {disk_stats['usage_ratio']:.1%}")


def main():
    """
    主函数
    """
    print("🎯 Qlib TuShare数据源使用示例")
    print("=" * 80)

    # 检查环境变量
    if not os.getenv("TUSHARE_TOKEN"):
        print("⚠️ 警告: 未设置TUSHARE_TOKEN环境变量")
        print("   某些示例可能无法正常运行")
        print("   请设置: export TUSHARE_TOKEN='your_token_here'")
        print()

    # 运行各种示例
    try:
        example_basic_usage()
    except Exception as e:
        print(f"❌ 基本使用示例失败: {e}")

    try:
        example_advanced_usage()
    except Exception as e:
        print(f"❌ 高级使用示例失败: {e}")

    try:
        example_data_processing()
    except Exception as e:
        print(f"❌ 数据处理示例失败: {e}")

    try:
        example_error_handling()
    except Exception as e:
        print(f"❌ 错误处理示例失败: {e}")

    try:
        example_performance_monitoring()
    except Exception as e:
        print(f"❌ 性能监控示例失败: {e}")

    print("\n" + "=" * 80)
    print("🎉 示例运行完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()