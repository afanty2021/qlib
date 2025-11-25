#!/usr/bin/env python3
"""
TuShare数据源集成测试

测试TuShare数据源与Qlib的集成功能。
"""

import unittest
import os
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../../.."))

from qlib.contrib.data.tushare import (
    TuShareConfig,
    TuShareProvider,
    TuShareError,
    TuShareConfigError,
    TuShareAPIError
)
from qlib.contrib.data.tushare.utils import (
    TuShareCodeConverter,
    TuShareDataProcessor,
    TuShareDateUtils
)
from qlib.contrib.data.tushare.field_mapping import TuShareFieldMapping
from qlib.contrib.data.tushare.cache import TuShareCacheManager


class TestTuShareConfig(unittest.TestCase):
    """TuShare配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = TuShareConfig()
        self.assertIsNotNone(config.cache_dir)
        self.assertTrue(config.enable_cache)
        self.assertEqual(config.max_retries, 3)

    def test_config_validation(self):
        """测试配置验证"""
        # 测试无效配置
        with self.assertRaises(TuShareConfigError):
            TuShareConfig(max_retries=-1)

        with self.assertRaises(TuShareConfigError):
            TuShareConfig(log_level="INVALID")

    def test_config_from_env(self):
        """测试从环境变量加载配置"""
        # 设置环境变量
        test_token = "test_token_12345"
        os.environ["TUSHARE_TOKEN"] = test_token
        os.environ["TUSHARE_MAX_RETRIES"] = "5"

        try:
            config = TuShareConfig.from_env()
            self.assertEqual(config.token, test_token)
            self.assertEqual(config.max_retries, 5)
        finally:
            # 清理环境变量
            os.environ.pop("TUSHARE_TOKEN", None)
            os.environ.pop("TUSHARE_MAX_RETRIES", None)


class TestTuShareFieldMapping(unittest.TestCase):
    """TuShare字段映射测试"""

    def test_field_mapping(self):
        """测试字段映射"""
        # 测试TuShare到Qlib映射
        self.assertEqual(TuShareFieldMapping.get_qlib_field("close"), "close")
        self.assertEqual(TuShareFieldMapping.get_qlib_field("vol"), "volume")
        self.assertEqual(TuShareFieldMapping.get_qlib_field("ts_code"), "instrument")

        # 测试Qlib到TuShare映射
        self.assertEqual(TuShareFieldMapping.get_tushare_field("close"), "close")
        self.assertEqual(TuShareFieldMapping.get_tushare_field("volume"), "vol")
        self.assertEqual(TuShareFieldMapping.get_tushare_field("instrument"), "ts_code")

    def test_dataframe_column_mapping(self):
        """测试DataFrame列名映射"""
        df = pd.DataFrame({
            "ts_code": ["000001.SZ", "600000.SH"],
            "close": [10.0, 20.0],
            "vol": [1000, 2000]
        })

        mapped_df = TuShareFieldMapping.map_dataframe_columns(df)

        self.assertIn("instrument", mapped_df.columns)
        self.assertIn("volume", mapped_df.columns)
        self.assertNotIn("ts_code", mapped_df.columns)
        self.assertNotIn("vol", mapped_df.columns)

    def test_data_type_conversion(self):
        """测试数据类型转换"""
        df = pd.DataFrame({
            "trade_date": ["20240101", "20240102"],
            "close": ["10.5", "11.2"],
            "volume": ["1000", "1500"],
            "ts_code": ["000001.SZ", "000002.SZ"]
        })

        converted_df = TuShareFieldMapping.convert_data_types(df)

        # 检查日期转换
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(converted_df["trade_date"]))

        # 检查数值转换
        self.assertTrue(pd.api.types.is_numeric_dtype(converted_df["close"]))
        self.assertTrue(pd.api.types.is_numeric_dtype(converted_df["volume"]))

        # 检查字符串转换
        self.assertTrue(pd.api.types.is_string_dtype(converted_df["ts_code"]))


class TestTuShareUtils(unittest.TestCase):
    """TuShare工具类测试"""

    def test_code_converter(self):
        """测试股票代码转换"""
        # 测试各种格式转换
        test_cases = [
            ("000001", "000001.SZ"),
            ("600000", "600000.SH"),
            ("300001", "300001.SZ"),
            ("688001", "688001.SH")
        ]

        for input_code, expected_tushare in test_cases:
            result = TuShareCodeConverter.to_tushare_format(input_code)
            self.assertEqual(result, expected_tushare)

            # 测试反向转换
            qlib_result = TuShareCodeConverter.to_qlib_format(result)
            self.assertIn(qlib_result[:2], ["SZ", "SH"])

    def test_date_utils(self):
        """测试日期工具"""
        # 测试日期格式转换
        test_dates = [
            "2024-01-01",
            "2024/01/01",
            "20240101"
        ]

        for date_str in test_dates:
            tushare_date = TuShareDateUtils.to_tushare_date(date_str)
            self.assertEqual(tushare_date, "20240101")

            # 测试反向转换
            dt_obj = TuShareDateUtils.from_tushare_date(tushare_date)
            self.assertEqual(dt_obj.year, 2024)
            self.assertEqual(dt_obj.month, 1)
            self.assertEqual(dt_obj.day, 1)

    def test_data_processor(self):
        """测试数据处理器"""
        # 创建测试数据
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=5),
            "open": [10.0, 10.5, 11.0, 10.8, 11.2],
            "high": [10.5, 11.0, 11.3, 11.1, 11.5],
            "low": [9.8, 10.2, 10.7, 10.5, 10.9],
            "close": [10.2, 10.8, 10.9, 10.9, 11.3],
            "volume": [1000, 1200, 900, 1100, 1300]
        })

        # 测试数据验证
        is_valid, errors = TuShareDataProcessor.validate_trading_data(df)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

        # 测试技术指标计算
        indicators_df = TuShareDataProcessor.calculate_technical_indicators(df)
        self.assertIn("ma_5", indicators_df.columns)
        self.assertIn("rsi", indicators_df.columns)
        self.assertIn("macd", indicators_df.columns)


class TestTuShareCache(unittest.TestCase):
    """TuShare缓存测试"""

    def setUp(self):
        """设置测试环境"""
        self.config = TuShareConfig(
            enable_cache=True,
            cache_ttl=1,  # 1秒过期，方便测试
            max_cache_size=1024 * 1024  # 1MB
        )

    def test_cache_manager(self):
        """测试缓存管理器"""
        cache_manager = TuShareCacheManager(self.config)

        # 测试缓存键生成
        key1 = cache_manager.generate_key("test", "param1", "param2")
        key2 = cache_manager.generate_key("test", "param1", "param2")
        key3 = cache_manager.generate_key("test", "param1", "param3")

        self.assertEqual(key1, key2)
        self.assertNotEqual(key1, key3)

        # 测试缓存存取
        test_data = {"key": "value", "number": 123}
        cache_manager.set(key1, test_data)
        retrieved_data = cache_manager.get(key1)

        self.assertEqual(retrieved_data, test_data)

    def test_cache_expiry(self):
        """测试缓存过期"""
        cache_manager = TuShareCacheManager(self.config)

        key = cache_manager.generate_key("expiry_test")
        test_data = "test_data"

        # 设置缓存
        cache_manager.set(key, test_data)

        # 立即获取应该成功
        self.assertEqual(cache_manager.get(key), test_data)

        # 等待过期
        import time
        time.sleep(2)

        # 过期后获取应该返回None
        self.assertIsNone(cache_manager.get(key))


class TestTuShareProvider(unittest.TestCase):
    """TuShare数据提供者测试"""

    def setUp(self):
        """设置测试环境"""
        self.config = TuShareConfig(
            token="test_token",
            enable_cache=True
        )

    @patch('qlib.contrib.data.tushare.api_client.TuShareAPIClient')
    def test_provider_initialization(self, mock_client_class):
        """测试数据提供者初始化"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        provider = TuShareProvider(self.config)

        self.assertIsNotNone(provider.config)
        self.assertIsNotNone(provider.api_client)
        self.assertIsNotNone(provider.cache_manager)

    @patch('qlib.contrib.data.tushare.api_client.TuShareAPIClient')
    def test_calendar_retrieval(self, mock_client_class):
        """测试交易日历获取"""
        # 模拟API返回数据
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_calendar_data = pd.DataFrame({
            "date": ["2024-01-02", "2024-01-03", "2024-01-04"]
        })
        mock_client.get_trade_cal.return_value = mock_calendar_data

        provider = TuShareProvider(self.config)
        calendar = provider.calendar(
            start_time="2024-01-01",
            end_time="2024-01-31"
        )

        self.assertIsInstance(calendar, list)
        self.assertEqual(len(calendar), 3)

    @patch('qlib.contrib.data.tushare.api_client.TuShareAPIClient')
    def test_instruments_retrieval(self, mock_client_class):
        """测试股票列表获取"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_instruments_data = pd.DataFrame({
            "instrument": ["000001.SZ", "600000.SH"],
            "name": ["平安银行", "浦发银行"],
            "market": ["主板", "主板"],
            "industry": ["银行", "银行"]
        })
        mock_client.get_stock_basic.return_value = mock_instruments_data

        provider = TuShareProvider(self.config)
        instruments = provider.instruments()

        self.assertIsInstance(instruments, dict)
        self.assertGreater(len(instruments), 0)

    @patch('qlib.contrib.data.tushare.api_client.TuShareAPIClient')
    def test_features_retrieval(self, mock_client_class):
        """测试特征数据获取"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_features_data = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=3),
            "close": [10.0, 10.5, 11.0],
            "volume": [1000, 1200, 900]
        })
        mock_client.get_daily_data.return_value = mock_features_data

        provider = TuShareProvider(self.config)
        features = provider.features(
            instruments=["SZ000001"],
            fields=["close", "volume"],
            start_time="2024-01-01",
            end_time="2024-01-03"
        )

        self.assertIsInstance(features, pd.DataFrame)

    def test_error_handling(self):
        """测试错误处理"""
        # 测试配置错误
        with self.assertRaises(TuShareConfigError):
            TuShareProvider(
                TuShareConfig(
                    token="",  # 空token
                    max_retries=-1  # 无效重试次数
                )
            )


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def setUp(self):
        """设置测试环境"""
        self.config = TuShareConfig(
            token="test_token",
            enable_cache=True,
            validate_data=True
        )

    @patch('qlib.contrib.data.tushare.api_client.TuShareAPIClient')
    def test_end_to_end_workflow(self, mock_client_class):
        """测试端到端工作流"""
        # 模拟完整的API响应
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # 模拟交易日历
        mock_client.get_trade_cal.return_value = pd.DataFrame({
            "date": ["2024-01-02", "2024-01-03", "2024-01-04"]
        })

        # 模拟股票列表
        mock_client.get_stock_basic.return_value = pd.DataFrame({
            "instrument": ["000001.SZ"],
            "name": ["平安银行"],
            "market": ["主板"],
            "industry": ["银行"]
        })

        # 模拟交易数据
        mock_client.get_daily_data.return_value = pd.DataFrame({
            "date": pd.date_range("2024-01-02", periods=3),
            "open": [10.0, 10.2, 10.5],
            "high": [10.3, 10.6, 10.8],
            "low": [9.8, 10.0, 10.2],
            "close": [10.2, 10.5, 10.7],
            "volume": [1000, 1200, 1100]
        })

        # 测试完整工作流
        with TuShareProvider(self.config) as provider:
            # 1. 获取交易日历
            calendar = provider.calendar(
                start_time="2024-01-01",
                end_time="2024-01-31"
            )
            self.assertEqual(len(calendar), 3)

            # 2. 获取股票列表
            instruments = provider.instruments()
            self.assertEqual(len(instruments), 1)
            self.assertIn("SZ000001", instruments)

            # 3. 获取特征数据
            features = provider.features(
                instruments=["SZ000001"],
                fields=["close", "volume"],
                start_time="2024-01-01",
                end_time="2024-01-05"
            )
            self.assertFalse(features.empty)

            # 4. 获取缓存统计
            cache_stats = provider.get_cache_stats()
            self.assertTrue(cache_stats["enabled"])


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    test_suite = unittest.TestSuite()

    # 添加测试类
    test_classes = [
        TestTuShareConfig,
        TestTuShareFieldMapping,
        TestTuShareUtils,
        TestTuShareCache,
        TestTuShareProvider,
        TestIntegration
    ]

    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    print("🧪 运行TuShare数据源集成测试")
    print("=" * 60)

    success = run_tests()

    if success:
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 部分测试失败，请检查上述错误信息")
        sys.exit(1)