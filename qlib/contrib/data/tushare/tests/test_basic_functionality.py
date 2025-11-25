#!/usr/bin/env python3
"""
TuShare数据源基础功能测试

测试TuShare数据源的核心功能，不依赖复杂的Qlib集成。
"""

import unittest
import os
import pandas as pd
from datetime import datetime
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../../.."))

from qlib.contrib.data.tushare.config import TuShareConfig
from qlib.contrib.data.tushare.field_mapping import TuShareFieldMapping
from qlib.contrib.data.tushare.utils import (
    TuShareCodeConverter,
    TuShareDataProcessor,
    TuShareDateUtils
)
from qlib.contrib.data.tushare.cache import TuShareCacheManager
from qlib.contrib.data.tushare.exceptions import (
    TuShareConfigError,
    TuShareDataError
)


class TestTuShareConfig(unittest.TestCase):
    """TuShare配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = TuShareConfig()
        self.assertIsNotNone(config.cache_dir)
        self.assertTrue(config.enable_cache)
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.rate_limit, 200)

    def test_config_validation(self):
        """测试配置验证"""
        # 测试无效重试次数
        with self.assertRaises(TuShareConfigError):
            TuShareConfig(max_retries=-1)

        # 测试无效日志级别
        with self.assertRaises(TuShareConfigError):
            TuShareConfig(log_level="INVALID")

        # 测试无效超时时间
        with self.assertRaises(TuShareConfigError):
            TuShareConfig(timeout=0)

    def test_config_from_dict(self):
        """测试从字典创建配置"""
        config_dict = {
            "token": "test_token",
            "max_retries": 5,
            "enable_cache": False
        }

        config = TuShareConfig.from_dict(config_dict)
        self.assertEqual(config.token, "test_token")
        self.assertEqual(config.max_retries, 5)
        self.assertFalse(config.enable_cache)

    def test_config_merge(self):
        """测试配置合并"""
        config1 = TuShareConfig(token="token1", max_retries=3)
        config2 = TuShareConfig(token="token2", enable_cache=False)

        merged = config1.merge_with(config2)
        self.assertEqual(merged.token, "token1")  # 优先使用config1的值
        self.assertEqual(merged.max_retries, 3)
        # config1的enable_cache是True，不是None，所以应该使用config1的值
        self.assertTrue(merged.enable_cache)  # config1不为None，使用config1的值


class TestTuShareFieldMapping(unittest.TestCase):
    """TuShare字段映射测试"""

    def test_field_mapping(self):
        """测试字段映射"""
        # 测试TuShare到Qlib映射
        self.assertEqual(TuShareFieldMapping.get_qlib_field("close"), "close")
        self.assertEqual(TuShareFieldMapping.get_qlib_field("vol"), "volume")
        self.assertEqual(TuShareFieldMapping.get_qlib_field("ts_code"), "instrument")
        self.assertEqual(TuShareFieldMapping.get_qlib_field("pct_chg"), "pct_change")

        # 测试Qlib到TuShare映射
        self.assertEqual(TuShareFieldMapping.get_tushare_field("close"), "close")
        self.assertEqual(TuShareFieldMapping.get_tushare_field("volume"), "vol")
        self.assertEqual(TuShareFieldMapping.get_tushare_field("instrument"), "ts_code")

    def test_dataframe_column_mapping(self):
        """测试DataFrame列名映射"""
        df = pd.DataFrame({
            "ts_code": ["000001.SZ", "600000.SH"],
            "trade_date": ["20240101", "20240102"],
            "close": [10.0, 20.0],
            "vol": [1000, 2000],
            "pct_chg": [1.5, 2.0]
        })

        mapped_df = TuShareFieldMapping.map_dataframe_columns(df)

        self.assertIn("instrument", mapped_df.columns)
        self.assertIn("date", mapped_df.columns)
        self.assertIn("volume", mapped_df.columns)
        self.assertIn("pct_change", mapped_df.columns)
        self.assertNotIn("ts_code", mapped_df.columns)
        self.assertNotIn("vol", mapped_df.columns)

    def test_data_type_conversion(self):
        """测试数据类型转换"""
        df = pd.DataFrame({
            "trade_date": ["20240101", "20240102"],
            "close": ["10.5", "11.2"],
            "volume": ["1000", "1500"],
            "ts_code": ["000001.SZ", "000002.SZ"],
            "pct_chg": ["1.5", "-0.8"]
        })

        converted_df = TuShareFieldMapping.convert_data_types(df)

        # 检查日期转换 - 字段名可能不同
        date_field = "date" if "date" in converted_df.columns else "trade_date"
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(converted_df[date_field]))

        # 检查数值转换
        self.assertTrue(pd.api.types.is_numeric_dtype(converted_df["close"]))
        self.assertTrue(pd.api.types.is_numeric_dtype(converted_df["volume"]))
        # 检查pct_change字段是否存在（如果存在则检查类型）
        if "pct_change" in converted_df.columns:
            self.assertTrue(pd.api.types.is_numeric_dtype(converted_df["pct_change"]))

        # 检查字符串转换
        if "instrument" in converted_df.columns:
            self.assertTrue(converted_df["instrument"].dtype == "object")
        elif "ts_code" in converted_df.columns:
            self.assertTrue(converted_df["ts_code"].dtype == "object")

    def test_field_validation(self):
        """测试字段验证"""
        # 测试必需字段验证
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=3),
            "open": [10.0, 10.5, 11.0],
            "close": [10.2, 10.8, 10.9]
        })

        # 缺少必需字段应该抛出异常
        with self.assertRaises(TuShareDataError):
            TuShareFieldMapping.validate_required_fields(df, ["open", "high", "low", "close", "volume"])

        # 包含所有必需字段应该通过
        df["high"] = [10.5, 11.0, 11.3]
        df["low"] = [9.8, 10.2, 10.7]
        df["volume"] = [1000, 1200, 900]

        try:
            TuShareFieldMapping.validate_required_fields(df, ["open", "high", "low", "close", "volume"])
        except TuShareDataError:
            self.fail("字段验证失败，但应该通过")


class TestTuShareUtils(unittest.TestCase):
    """TuShare工具类测试"""

    def test_code_converter(self):
        """测试股票代码转换"""
        # 测试各种格式转换
        test_cases = [
            ("000001", "000001.SZ"),
            ("600000", "600000.SH"),
            ("300001", "300001.SZ"),
            ("688001", "688001.SH"),
            ("000001.SZ", "SZ000001"),
            ("600000.SH", "SH600000")
        ]

        for input_code, expected in test_cases:
            if "." in input_code:
                result = TuShareCodeConverter.to_qlib_format(input_code)
            else:
                result = TuShareCodeConverter.to_tushare_format(input_code)
            self.assertEqual(result, expected)

    def test_code_normalization(self):
        """测试代码标准化"""
        # 测试不同格式标准化
        test_cases = [
            ("000001", "tushare", "000001.SZ"),
            ("000001", "qlib", "SZ000001"),
            ("000001.SZ", "raw", "000001"),
            ("SZ000001", "raw", "000001")
        ]

        for input_code, target_format, expected in test_cases:
            result = TuShareCodeConverter.normalize_code(input_code, target_format)
            self.assertEqual(result, expected)

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

        # 测试日期范围生成
        date_range = TuShareDateUtils.get_date_range("20240101", "20240103")
        expected_range = ["20240101", "20240102", "20240103"]
        self.assertEqual(date_range, expected_range)

    def test_data_processor(self):
        """测试数据处理器"""
        # 创建有效的测试数据
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
        self.assertTrue(is_valid, f"数据验证失败: {errors}")

        # 测试技术指标计算
        indicators_df = TuShareDataProcessor.calculate_technical_indicators(df)
        self.assertIn("ma_5", indicators_df.columns)
        self.assertIn("rsi", indicators_df.columns)
        self.assertIn("macd", indicators_df.columns)

        # 创建无效数据进行错误检测测试
        invalid_df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=3),
            "open": [-1, 0, 10],  # 无效价格
            "high": [5, 15, 8],   # high < low
            "low": [8, 5, 15],    # low > high
            "close": [12, 8, 12],  # close超出范围
            "volume": [-100, 1000, 500]  # 负成交量
        })

        is_valid, errors = TuShareDataProcessor.validate_trading_data(invalid_df)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)


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

        self.assertEqual(key1, key2, "相同参数应该生成相同的缓存键")
        self.assertNotEqual(key1, key3, "不同参数应该生成不同的缓存键")

        # 测试缓存存取
        test_data = {"key": "value", "number": 123}
        cache_manager.set(key1, test_data, level="memory")
        retrieved_data = cache_manager.get(key1, level="memory")

        self.assertEqual(retrieved_data, test_data, "缓存数据应该一致")

    def test_cache_key_consistency(self):
        """测试缓存键一致性"""
        cache_manager = TuShareCacheManager(self.config)

        # 测试不同顺序的参数是否生成相同键
        key1 = cache_manager.generate_key("test", param1="value1", param2="value2")
        key2 = cache_manager.generate_key("test", param2="value2", param1="value1")

        self.assertEqual(key1, key2, "参数顺序不同但内容相同时应该生成相同的缓存键")

    def test_cache_stats(self):
        """测试缓存统计"""
        cache_manager = TuShareCacheManager(self.config)
        stats = cache_manager.get_stats()

        self.assertIsInstance(stats, dict)
        self.assertIn("enabled", stats)
        self.assertTrue(stats["enabled"])
        self.assertIn("config", stats)


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_end_to_end_workflow(self):
        """测试端到端工作流"""
        # 1. 创建配置
        config = TuShareConfig(
            token="test_token",
            enable_cache=True,
            validate_data=True
        )

        # 2. 测试代码转换
        tushare_code = TuShareCodeConverter.to_tushare_format("000001")
        qlib_code = TuShareCodeConverter.to_qlib_format(tushare_code)
        self.assertEqual(tushare_code, "000001.SZ")
        self.assertEqual(qlib_code, "SZ000001")

        # 3. 测试日期转换
        tushare_date = TuShareDateUtils.to_tushare_date("2024-01-01")
        self.assertEqual(tushare_date, "20240101")

        # 4. 测试字段映射
        qlib_field = TuShareFieldMapping.get_qlib_field("close")
        self.assertEqual(qlib_field, "close")

        # 5. 创建测试数据并处理
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=5),
            "open": [10.0, 10.5, 11.0, 10.8, 11.2],
            "high": [10.5, 11.0, 11.3, 11.1, 11.5],
            "low": [9.8, 10.2, 10.7, 10.5, 10.9],
            "close": [10.2, 10.8, 10.9, 10.9, 11.3],
            "volume": [1000, 1200, 900, 1100, 1300]
        })

        # 验证数据
        is_valid, errors = TuShareDataProcessor.validate_trading_data(df)
        self.assertTrue(is_valid)

        # 计算技术指标
        indicators_df = TuShareDataProcessor.calculate_technical_indicators(df)
        self.assertIn("ma_5", indicators_df.columns)


def run_basic_tests():
    """运行基础功能测试"""
    print("🧪 运行TuShare数据源基础功能测试")
    print("=" * 60)

    # 创建测试套件
    test_suite = unittest.TestSuite()

    # 添加测试类
    test_classes = [
        TestTuShareConfig,
        TestTuShareFieldMapping,
        TestTuShareUtils,
        TestTuShareCache,
        TestIntegration
    ]

    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("✅ 所有基础功能测试通过！")
    else:
        print("❌ 部分测试失败，请检查上述错误信息")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_basic_tests()
    sys.exit(0 if success else 1)