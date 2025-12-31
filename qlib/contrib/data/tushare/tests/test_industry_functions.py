#!/usr/bin/env python3
"""
行业板块功能测试

测试新增的行业板块相关功能，包括：
- API客户端行业接口测试
- 行业因子计算测试
- 数据提供者集成测试
"""

import unittest
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

try:
    from qlib.contrib.data.tushare.config import TuShareConfig
    from qlib.contrib.data.tushare.api_client import TuShareAPIClient
    from qlib.contrib.data.tushare.industry_factors import (
        IndustryFactorCalculator,
        calculate_industry_exposure,
        normalize_industry_factors
    )
    from qlib.contrib.data.tushare.provider import TuShareProvider
except ImportError:
    # 如果导入失败，尝试直接从当前目录导入
    sys.path.insert(0, os.path.dirname(__file__))
    from config import TuShareConfig
    from api_client import TuShareAPIClient
    from industry_factors import (
        IndustryFactorCalculator,
        calculate_industry_exposure,
        normalize_industry_factors
    )
    from provider import TuShareProvider


class TestIndustryAPI(unittest.TestCase):
    """测试行业API接口"""

    def setUp(self):
        """测试前准备"""
        self.config = TuShareConfig(token="test_token")

    def test_api_client_initialization(self):
        """测试API客户端初始化"""
        client = TuShareAPIClient(self.config)
        self.assertIsNotNone(client)
        self.assertIsNotNone(client.config)
        self.assertIsNotNone(client.session)

    @patch('qlib.contrib.data.tushare.api_client.TuShareAPIClient._make_request')
    def test_get_industry(self, mock_request):
        """测试获取行业分类"""
        # 模拟API响应
        mock_response = {
            'fields': ['industry_code', 'industry_name', 'level', 'is_parent'],
            'items': [
                ['801010', '农林牧渔', 'L1', 'Y'],
                ['801020', '采掘', 'L1', 'Y'],
                ['801030', '化工', 'L1', 'Y']
            ]
        }
        mock_request.return_value = mock_response

        client = TuShareAPIClient(self.config)
        result = client.get_industry(src="SW2021", level="L1")

        # 验证返回结果
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 3)
        self.assertIn('industry_code', result.columns)
        self.assertIn('industry_name', result.columns)

        # 验证API调用参数
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], "industry")
        self.assertEqual(call_args[0][1]['src'], "SW2021")
        self.assertEqual(call_args[0][1]['level'], "L1")

    @patch('qlib.contrib.data.tushare.api_client.TuShareAPIClient._make_request')
    def test_get_concept(self, mock_request):
        """测试获取概念板块"""
        mock_response = {
            'fields': ['id', 'concept_name', 'concept_type'],
            'items': [
                ['TS001', '新能源汽车', '主题'],
                ['TS002', '人工智能', '主题']
            ]
        }
        mock_request.return_value = mock_response

        client = TuShareAPIClient(self.config)
        result = client.get_concept()

        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 2)
        self.assertIn('concept_name', result.columns)

    @patch('qlib.contrib.data.tushare.api_client.TuShareAPIClient._make_request')
    def test_get_index_member(self, mock_request):
        """测试获取指数成分股"""
        mock_response = {
            'fields': ['index_code', 'con_code', 'in_date', 'out_date', 'is_new'],
            'items': [
                ['000300.SH', '600000.SH', '20100101', '', 'N'],
                ['000300.SH', '600004.SH', '20100101', '', 'N']
            ]
        }
        mock_request.return_value = mock_response

        client = TuShareAPIClient(self.config)
        result = client.get_index_member(index_code="000300.SH")

        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 2)
        self.assertIn('index_code', result.columns)
        self.assertIn('con_code', result.columns)

    @patch('qlib.contrib.data.tushare.api_client.TuShareAPIClient._make_request')
    def test_get_index_classify(self, mock_request):
        """测试获取指数行业分类"""
        mock_response = {
            'fields': ['index_code', 'industry_code', 'industry_name'],
            'items': [
                ['000300.SH', '801010', '农林牧渔'],
                ['000300.SH', '801020', '采掘']
            ]
        }
        mock_request.return_value = mock_response

        client = TuShareAPIClient(self.config)
        result = client.get_index_classify(level="L1", src="SW2021")

        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 2)
        self.assertIn('index_code', result.columns)


class TestIndustryFactorCalculator(unittest.TestCase):
    """测试行业因子计算器"""

    def setUp(self):
        """测试前准备"""
        # 创建模拟行业数据
        self.industry_data = pd.DataFrame({
            'instrument': ['sh600000', 'sh600004', 'sh600006', 'sz000001', 'sz000002'],
            'industry_code': ['801010', '801010', '801020', '801020', '801030'],
            'industry_name': ['农林牧渔', '农林牧渔', '采掘', '采掘', '化工']
        })

        # 创建模拟价格数据
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        self.price_data = pd.DataFrame({
            'instrument': np.repeat(['sh600000', 'sh600004', 'sh600006'], 50),
            'date': np.tile(dates, 3),
            'close': np.random.randn(150) * 0.02 + 10,
            'volume': np.random.randint(1000000, 10000000, 150)
        })

    def test_calculator_initialization(self):
        """测试计算器初始化"""
        calculator = IndustryFactorCalculator(
            industry_data=self.industry_data,
            price_data=self.price_data
        )
        self.assertIsNotNone(calculator)
        self.assertEqual(len(calculator.industry_data), 5)
        self.assertEqual(len(calculator.price_data), 150)

    def test_calculate_industry_momentum(self):
        """测试计算行业动量因子"""
        calculator = IndustryFactorCalculator(
            industry_data=self.industry_data,
            price_data=self.price_data
        )

        momentum_df = calculator.calculate_industry_momentum(window=20)

        # 验证返回结果
        self.assertIsInstance(momentum_df, pd.DataFrame)
        self.assertIn('date', momentum_df.columns)
        self.assertIn('industry_code', momentum_df.columns)
        self.assertIn('momentum', momentum_df.columns)
        self.assertGreater(len(momentum_df), 0)

    def test_calculate_industry_concentration(self):
        """测试计算行业集中度"""
        calculator = IndustryFactorCalculator(
            industry_data=self.industry_data,
            price_data=self.price_data
        )

        # 创建模拟持仓数据
        holdings = pd.DataFrame({
            'instrument': ['sh600000', 'sh600004', 'sh600006'],
            'weight': [0.4, 0.3, 0.3]
        })

        concentration_df = calculator.calculate_industry_concentration(holdings)

        # 验证返回结果
        self.assertIsInstance(concentration_df, pd.DataFrame)
        self.assertIn('industry_code', concentration_df.columns)
        self.assertIn('concentration', concentration_df.columns)

        # 验证集中度值在0-1之间
        self.assertTrue((concentration_df['concentration'] >= 0).all())
        self.assertTrue((concentration_df['concentration'] <= 1).all())

    def test_calculate_industry_momentum_rank(self):
        """测试计算行业动量排名"""
        calculator = IndustryFactorCalculator(
            industry_data=self.industry_data,
            price_data=self.price_data
        )

        rank_df = calculator.calculate_industry_momentum_rank(window=20)

        # 验证返回结果
        self.assertIsInstance(rank_df, pd.DataFrame)
        self.assertIn('rank', rank_df.columns)

        # 验证排名是正整数
        self.assertTrue((rank_df['rank'] > 0).all())


class TestIndustryExposure(unittest.TestCase):
    """测试行业暴露度计算"""

    def setUp(self):
        """测试前准备"""
        self.stock_industry_map = pd.DataFrame({
            'instrument': ['sh600000', 'sh600004', 'sh600006', 'sz000001', 'sz000002'],
            'industry_code': ['801010', '801010', '801020', '801020', '801030'],
            'industry_name': ['农林牧渔', '农林牧渔', '采掘', '采掘', '化工']
        })

    def test_calculate_industry_exposure(self):
        """测试计算行业暴露度"""
        target_industries = ['801010', '801020']  # 农林牧渔、采掘

        exposure_df = calculate_industry_exposure(
            self.stock_industry_map,
            target_industries
        )

        # 验证返回结果
        self.assertIsInstance(exposure_df, pd.DataFrame)
        self.assertIn('exposure', exposure_df.columns)

        # 验证暴露度值为0或1
        self.assertTrue(exposure_df['exposure'].isin([0.0, 1.0]).all())

        # 验证目标行业的股票暴露度为1
        target_stocks = exposure_df[exposure_df['industry_code'].isin(target_industries)]
        self.assertTrue((target_stocks['exposure'] == 1.0).all())


class TestNormalizeIndustryFactors(unittest.TestCase):
    """测试因子标准化"""

    def setUp(self):
        """测试前准备"""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        self.factor_df = pd.DataFrame({
            'date': np.tile(dates, 3),
            'industry_code': ['801010'] * 10 + ['801020'] * 10 + ['801030'] * 10,
            'industry_name': ['农林牧渔'] * 10 + ['采掘'] * 10 + ['化工'] * 10,
            'momentum': np.random.randn(30)
        })

    def test_normalize_zscore(self):
        """测试Z-score标准化"""
        normalized_df = normalize_industry_factors(
            self.factor_df,
            method="zscore",
            group_by="date"
        )

        # 验证返回结果
        self.assertIn('factor_norm', normalized_df.columns)

        # 验证标准化后均值接近0，标准差接近1
        for date in normalized_df['date'].unique():
            date_data = normalized_df[normalized_df['date'] == date]['factor_norm']
            self.assertAlmostEqual(date_data.mean(), 0, places=10)
            # 使用相对误差检查，允许0.1%的误差
            self.assertTrue(abs(date_data.std() - 1) < 0.001,
                          f"标准差 {date_data.std()} 与1的差异超过0.001")

    def test_normalize_minmax(self):
        """测试Min-Max标准化"""
        normalized_df = normalize_industry_factors(
            self.factor_df,
            method="minmax",
            group_by="date"
        )

        # 验证返回结果
        self.assertIn('factor_norm', normalized_df.columns)

        # 验证标准化后值在0-1之间
        self.assertTrue((normalized_df['factor_norm'] >= 0).all())
        self.assertTrue((normalized_df['factor_norm'] <= 1).all())

    def test_normalize_rank(self):
        """测试排名标准化"""
        normalized_df = normalize_industry_factors(
            self.factor_df,
            method="rank",
            group_by="date"
        )

        # 验证返回结果
        self.assertIn('factor_norm', normalized_df.columns)

        # 验证排名在0-1之间
        self.assertTrue((normalized_df['factor_norm'] >= 0).all())
        self.assertTrue((normalized_df['factor_norm'] <= 1).all())


class TestTuShareProviderIndustry(unittest.TestCase):
    """测试TuShareProvider行业功能"""

    @patch('qlib.contrib.data.tushare.provider.TuShareAPIClient')
    @patch('qlib.contrib.data.tushare.provider.TuShareCacheManager')
    def test_get_industry_classification(self, mock_cache, mock_api_client):
        """测试获取行业分类"""
        # 创建模拟配置
        config = TuShareConfig(token="test_token")

        # 模拟缓存
        mock_cache_instance = Mock()
        mock_cache.return_value = mock_cache_instance
        mock_cache_instance.get.return_value = None  # 缓存未命中

        # 模拟API响应
        mock_api_response = pd.DataFrame({
            'industry_code': ['801010', '801020'],
            'industry_name': ['农林牧渔', '采掘']
        })

        mock_client_instance = Mock()
        mock_api_client.return_value = mock_client_instance
        mock_client_instance.get_industry.return_value = mock_api_response

        # 创建提供者
        provider = TuShareProvider(config)

        # 调用方法
        result = provider.get_industry_classification(src="SW2021", level="L1")

        # 验证结果
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 2)

        # 验证API被调用
        mock_client_instance.get_industry.assert_called_once_with(src="SW2021", level="L1")

    @patch('qlib.contrib.data.tushare.provider.TuShareAPIClient')
    @patch('qlib.contrib.data.tushare.provider.TuShareCacheManager')
    def test_get_industry_factors(self, mock_cache, mock_api_client):
        """测试获取行业因子"""
        config = TuShareConfig(token="test_token")

        # 模拟缓存
        mock_cache_instance = Mock()
        mock_cache.return_value = mock_cache_instance
        mock_cache_instance.get.return_value = None

        # 模拟API响应
        mock_industry_response = pd.DataFrame({
            'instrument': ['sh600000', 'sh600004'],
            'industry_code': ['801010', '801010'],
            'industry_name': ['农林牧渔', '农林牧渔']
        })

        mock_client_instance = Mock()
        mock_api_client.return_value = mock_client_instance
        mock_client_instance.get_industry.return_value = mock_industry_response

        # 模拟features方法
        with patch.object(TuShareProvider, 'features') as mock_features:
            mock_price_df = pd.DataFrame({
                'close': np.random.randn(20) + 10,
                'volume': np.random.randint(1000000, 10000000, 20)
            })
            mock_price_df.index = pd.MultiIndex.from_arrays([
                ['sh600000'] * 20,
                pd.date_range('2024-01-01', periods=20, freq='D')
            ], names=['instrument', 'date'])
            mock_features.return_value = mock_price_df

            # 创建提供者
            provider = TuShareProvider(config)

            # 调用方法
            result = provider.get_industry_factors(
                instruments=['sh600000', 'sh600004'],
                factor_type="momentum",
                window=20
            )

            # 验证结果（可能返回空DataFrame因为模拟数据）
            self.assertIsInstance(result, pd.DataFrame)


class TestDataValidation(unittest.TestCase):
    """测试数据验证"""

    def test_empty_industry_data(self):
        """测试空行业数据处理"""
        calculator = IndustryFactorCalculator(
            industry_data=pd.DataFrame(),
            price_data=pd.DataFrame()
        )

        # 空数据不应报错，但应该有警告
        with self.assertRaises(ValueError):
            calculator.calculate_industry_momentum()

    def test_missing_columns(self):
        """测试缺失列处理"""
        # 缺少必需列的industry_data
        invalid_industry_data = pd.DataFrame({
            'code': ['sh600000', 'sh600004']  # 应该是'instrument'
        })

        price_data = pd.DataFrame({
            'instrument': ['sh600000'],
            'date': ['2024-01-01'],
            'close': [10.0]
        })

        # 应该有警告但不应该抛出异常
        import warnings
        with warnings.catch_warnings(record=True):
            calculator = IndustryFactorCalculator(
                industry_data=invalid_industry_data,
                price_data=price_data
            )
            self.assertIsNotNone(calculator)


def run_tests():
    """运行所有测试"""
    print("="*80)
    print("运行行业板块功能测试")
    print("="*80)

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestIndustryAPI))
    suite.addTests(loader.loadTestsFromTestCase(TestIndustryFactorCalculator))
    suite.addTests(loader.loadTestsFromTestCase(TestIndustryExposure))
    suite.addTests(loader.loadTestsFromTestCase(TestNormalizeIndustryFactors))
    suite.addTests(loader.loadTestsFromTestCase(TestTuShareProviderIndustry))
    suite.addTests(loader.loadTestsFromTestCase(TestDataValidation))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出测试结果
    print("\n" + "="*80)
    print("测试结果汇总")
    print("="*80)
    print(f"运行测试数: {result.testsRun}")
    print(f"成功数: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败数: {len(result.failures)}")
    print(f"错误数: {len(result.errors)}")
    print(f"跳过数: {len(result.skipped)}")

    if result.wasSuccessful():
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 部分测试失败")
        if result.failures:
            print("\n失败的测试:")
            for test, traceback in result.failures:
                print(f"  - {test}")
        if result.errors:
            print("\n错误的测试:")
            for test, traceback in result.errors:
                print(f"  - {test}")

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
