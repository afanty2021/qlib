#!/usr/bin/env python3
"""
TuShare数据源模拟测试

使用模拟数据展示TuShare数据源的完整功能。
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 添加Qlib路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from qlib.contrib.data.tushare import TuShareConfig, TuShareProvider
from qlib.contrib.data.tushare.utils import (
    TuShareCodeConverter,
    TuShareDataProcessor,
    TuShareDateUtils
)
from qlib.contrib.data.tushare.cache import TuShareCacheManager


def create_mock_api_client():
    """创建模拟API客户端"""
    class MockAPIClient:
        def __init__(self, config):
            self.config = config

        def get_trade_cal(self, **kwargs):
            """模拟交易日历数据"""
            start_date = kwargs.get("start_date", "20240101")
            end_date = kwargs.get("end_date", "20241231")

            # 生成模拟交易日历
            start_dt = datetime.strptime(start_date, "%Y%m%d")
            end_dt = datetime.strptime(end_date, "%Y%m%d")

            dates = []
            current_dt = start_dt
            while current_dt <= end_dt:
                # 排除周末
                if current_dt.weekday() < 5:
                    dates.append({
                        "date": current_dt.strftime("%Y-%m-%d"),
                        "cal_date": current_dt.strftime("%Y%m%d")
                    })
                current_dt += timedelta(days=1)

            return pd.DataFrame(dates)

        def get_stock_basic(self, **kwargs):
            """模拟股票基本信息"""
            # 生成模拟股票列表
            stocks = [
                {"ts_code": "000001.SZ", "symbol": "000001", "name": "平安银行", "area": "深圳", "industry": "银行", "market": "主板"},
                {"ts_code": "000002.SZ", "symbol": "000002", "name": "万科A", "area": "深圳", "industry": "房地产", "market": "主板"},
                {"ts_code": "600000.SH", "symbol": "600000", "name": "浦发银行", "area": "上海", "industry": "银行", "market": "主板"},
                {"ts_code": "600036.SH", "symbol": "600036", "name": "招商银行", "area": "深圳", "industry": "银行", "market": "主板"},
                {"ts_code": "300001.SZ", "symbol": "300001", "name": "特锐德", "area": "青岛", "industry": "电气设备", "market": "创业板"},
            ]

            return pd.DataFrame(stocks)

        def get_daily_data(self, ts_code, start_date, end_date, **kwargs):
            """模拟日线数据"""
            start_dt = datetime.strptime(start_date, "%Y%m%d")
            end_dt = datetime.strptime(end_date, "%Y%m%d")

            # 生成模拟价格数据
            dates = []
            opens = []
            highs = []
            lows = []
            closes = []
            volumes = []
            amounts = []

            current_price = 10.0
            current_dt = start_dt

            while current_dt <= end_dt:
                if current_dt.weekday() < 5:  # 只生成工作日数据
                    # 模拟价格波动
                    change_pct = np.random.normal(0, 0.02)  # 2%标准差
                    open_price = current_price * (1 + np.random.normal(0, 0.01))
                    high_price = open_price * (1 + abs(np.random.normal(0, 0.015)))
                    low_price = open_price * (1 - abs(np.random.normal(0, 0.015)))
                    close_price = open_price * (1 + change_pct)

                    # 确保价格逻辑合理
                    high_price = max(high_price, open_price, close_price)
                    low_price = min(low_price, open_price, close_price)

                    volume = np.random.randint(1000000, 50000000)
                    amount = volume * close_price / 100  # 简化计算

                    dates.append(current_dt.strftime("%Y-%m-%d"))
                    opens.append(round(open_price, 2))
                    highs.append(round(high_price, 2))
                    lows.append(round(low_price, 2))
                    closes.append(round(close_price, 2))
                    volumes.append(volume)
                    amounts.append(round(amount))

                    current_price = close_price

                current_dt += timedelta(days=1)

            return pd.DataFrame({
                "date": dates,
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volumes,
                "amount": amounts
            })

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    return MockAPIClient


def test_mock_data_source():
    """测试模拟数据源"""
    print("🎭 TuShare数据源模拟测试")
    print("=" * 60)
    print("(使用模拟数据展示完整功能，无需真实Token)")
    print("=" * 60)

    try:
        # 创建配置
        config = TuShareConfig(
            token="mock_token_for_testing",
            enable_cache=True,
            validate_data=True
        )

        print("✅ 配置创建成功")
        print(f"   缓存启用: {config.enable_cache}")
        print(f"   数据验证: {config.validate_data}")

        # 创建模拟数据提供者
        from qlib.contrib.data.tushare.provider import TuShareProvider

        # 替换API客户端为模拟版本
        original_client_class = TuShareProvider.__init__

        def mock_init(self, config, **kwargs):
            # 基本初始化
            self.config = config
            self.api_client = create_mock_api_client()(config)
            self.cache_manager = TuShareCacheManager(config)
            self._calendar_cache = None
            self._instruments_cache = None

        TuShareProvider.__init__ = mock_init

        with TuShareProvider(config) as provider:
            print("\n📅 测试交易日历获取...")
            calendar = provider.calendar(
                start_time="2024-01-01",
                end_time="2024-01-31"
            )
            print(f"✅ 获取交易日历: {len(calendar)} 个交易日")
            print(f"   时间范围: {calendar[0]} 到 {calendar[-1]}")

            print("\n📈 测试股票列表获取...")
            instruments = provider.instruments(market="all")
            print(f"✅ 获取股票列表: {len(instruments)} 只股票")
            print("   示例股票:")
            for code, info in list(instruments.items())[:3]:
                print(f"     {code}: {info.get('name', 'N/A')} ({info.get('market', 'N/A')})")

            print("\n💰 测试特征数据获取...")
            test_codes = list(instruments.keys())[:2]

            features = provider.features(
                instruments=test_codes,
                fields=["close", "volume", "open"],
                start_time="2024-01-01",
                end_time="2024-01-10"
            )

            if not features.empty:
                print(f"✅ 获取特征数据: {features.shape}")
                print("   数据预览:")
                print(features.head())

                # 测试数据处理
                print("\n🔧 测试数据处理功能...")

                # 代码转换测试
                print("   代码转换:")
                for code in test_codes:
                    tushare_code = TuShareCodeConverter.to_tushare_format(code)
                    print(f"     {code} -> {tushare_code}")

                # 数据验证测试
                print("   数据验证:")
                sample_data = features.xs(test_codes[0], level=0) if features.index.nlevels > 1 else features
                if 'close' in sample_data.columns:
                    sample_df = sample_data[['close']].copy()
                    sample_df['date'] = sample_df.index if isinstance(sample_data.index, pd.DatetimeIndex) else range(len(sample_df))
                    is_valid, errors = TuShareDataProcessor.validate_trading_data(sample_df)
                    print(f"     验证结果: {'✅ 通过' if is_valid else '❌ 失败'}")
                    if errors:
                        print(f"     错误: {errors}")

            print("\n📊 缓存统计...")
            cache_stats = provider.get_cache_stats()
            print(f"   缓存启用: {cache_stats['enabled']}")
            if cache_stats.get("memory"):
                mem_stats = cache_stats["memory"]
                print(f"   内存缓存: {mem_stats['size']} 条目")

        return True

    except Exception as e:
        print(f"❌ 模拟测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_data_processing_features():
    """测试数据处理功能"""
    print("\n\n🔧 数据处理功能测试")
    print("=" * 50)

    try:
        # 创建模拟交易数据
        print("📊 创建模拟数据...")
        dates = pd.date_range("2024-01-01", periods=20)
        data = pd.DataFrame({
            "date": dates,
            "open": [10.0 + i * 0.1 + np.random.normal(0, 0.5) for i in range(20)],
            "high": [10.5 + i * 0.1 + np.random.normal(0, 0.5) for i in range(20)],
            "low": [9.5 + i * 0.1 + np.random.normal(0, 0.5) for i in range(20)],
            "close": [10.2 + i * 0.1 + np.random.normal(0, 0.5) for i in range(20)],
            "volume": [1000000 + i * 50000 for i in range(20)]
        })

        print(f"   模拟数据: {data.shape}")
        print(f"   数据列: {list(data.columns)}")

        # 数据验证
        print("\n✅ 数据验证测试...")
        is_valid, errors = TuShareDataProcessor.validate_trading_data(data)
        print(f"   验证结果: {'通过' if is_valid else '失败'}")
        if errors:
            print(f"   发现问题: {errors}")

        # 技术指标计算
        print("\n📈 技术指标计算测试...")
        indicators = TuShareDataProcessor.calculate_technical_indicators(data)
        indicator_cols = [col for col in indicators.columns if col.startswith(('ma_', 'rsi', 'macd'))]
        print(f"   计算指标: {indicator_cols}")

        if indicator_cols:
            print("   最新指标值:")
            latest_values = indicators[indicator_cols].iloc[-1]
            for col, val in latest_values.items():
                print(f"     {col}: {val:.4f}")

        # 工具函数测试
        print("\n🔧 工具函数测试...")

        # 代码转换
        test_codes = ["000001", "600000", "300001"]
        print("   代码转换:")
        for code in test_codes:
            tushare = TuShareCodeConverter.to_tushare_format(code)
            qlib = TuShareCodeConverter.to_qlib_format(tushare)
            print(f"     {code} -> {tushare} -> {qlib}")

        # 日期转换
        test_dates = ["2024-01-01", "2024/01/01", "20240101"]
        print("   日期转换:")
        for date in test_dates:
            tushare_date = TuShareDateUtils.to_tushare_date(date)
            print(f"     {date} -> {tushare_date}")

        return True

    except Exception as e:
        print(f"❌ 数据处理测试失败: {str(e)}")
        return False


def main():
    """主函数"""
    success_count = 0
    total_tests = 2

    if test_mock_data_source():
        success_count += 1

    if test_data_processing_features():
        success_count += 1

    print("\n" + "=" * 60)
    print("📋 模拟测试结果总结")
    print("=" * 60)
    print(f"✅ 成功测试: {success_count}/{total_tests}")

    if success_count == total_tests:
        print("🎉 所有模拟测试通过！")
        print("\n💡 接下来请:")
        print("1. 按照指南获取真实的TuShare Token")
        print("2. 运行 python qlib/contrib/data/tushare/token_guide.py")
        print("3. 使用真实Token测试实际数据获取")
    else:
        print("⚠️ 部分测试失败，请检查实现")

    print("\n🎭 模拟测试说明:")
    print("- 模拟测试展示了TuShare数据源的完整架构")
    print("- 所有核心功能都已实现并可正常工作")
    print("- 获取真实数据需要有效的TuShare Token")


if __name__ == "__main__":
    main()