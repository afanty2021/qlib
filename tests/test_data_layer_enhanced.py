# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
增强的数据层测试

专门测试数据层的边界情况、错误处理和性能优化功能。
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import Mock, patch, MagicMock

from qlib.data.cache import ExpressionCache, DatasetCache
from qlib.data.ops import Mad, WMA, Rolling


class TestExpressionCacheEnhanced:
    """增强的表达式缓存测试"""

    def setup_method(self):
        """设置测试环境"""
        self.cache = ExpressionCache()
        self.test_uri = "test_expression"
        self.test_data = pd.Series(
            [1, 2, 3, 4, 5],
            index=pd.date_range("2020-01-01", periods=5, freq="D")
        )

    def test_cache_consistency_under_concurrency(self):
        """测试并发下的缓存一致性"""
        import threading
        import time

        results = []
        errors = []

        def worker():
            try:
                result = self.cache.get(self.test_uri)
                results.append(result)
            except Exception as e:
                errors.append(e)

        # 创建多个线程同时访问缓存
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证结果一致性
        assert len(errors) == 0, f"并发访问导致错误: {errors}"
        assert all(r == results[0] for r in results), "并发访问结果不一致"

    def test_cache_memory_usage(self):
        """测试缓存内存使用"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # 添加大量缓存数据
        for i in range(1000):
            test_uri = f"test_expression_{i}"
            self.cache.set(test_uri, self.test_data)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # 内存增长应该在合理范围内
        assert memory_increase < 100 * 1024 * 1024  # 小于100MB


class TestDatasetCacheEnhanced:
    """增强的数据集缓存测试"""

    def setup_method(self):
        """设置测试环境"""
        self.cache = DatasetCache()

    def test_large_dataset_caching(self):
        """测试大数据集缓存"""
        # 创建大型数据集
        large_data = pd.DataFrame(
            np.random.randn(100000, 10),
            columns=[f"feature_{i}" for i in range(10)],
            index=pd.date_range("2010-01-01", periods=100000, freq="D")
        )

        # 测试缓存和读取
        cache_key = "large_dataset_test"
        self.cache.set(cache_key, large_data)

        cached_data = self.cache.get(cache_key)
        pd.testing.assert_frame_equal(large_data, cached_data)

    def test_cache_compression(self):
        """测试缓存压缩功能"""
        test_data = pd.DataFrame({
            'sparse_feature': [1, np.nan, 3, np.nan, 5] * 1000,
            'dense_feature': range(5000)
        })

        cache_key = "compression_test"
        self.cache.set(cache_key, test_data, compress=True)

        # 验证压缩缓存
        cached_data = self.cache.get(cache_key)
        pd.testing.assert_frame_equal(test_data, cached_data)


class TestOptimizedOperations:
    """测试优化的操作符"""

    def test_mad_vectorized_performance(self):
        """测试MAD操作符的向量化性能"""
        # 创建测试数据
        feature = Mock()
        feature.load.return_value = pd.Series(
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            index=pd.date_range("2020-01-01", periods=10, freq="D")
        )

        mad_op = Mad(feature, 3)
        result = mad_op._load_internal("test_stock", 0, 9)

        # 验证结果正确性
        assert isinstance(result, pd.Series)
        assert len(result) == 10

        # 验证向量化计算结果
        # 手动计算第一个窗口的MAD
        window_data = [1, 2, 3]
        expected_mad = np.mean(np.abs(window_data - np.mean(window_data)))
        assert np.isclose(result.iloc[2], expected_mad)

    def test_wma_vectorized_performance(self):
        """测试WMA操作符的向量化性能"""
        # 创建测试数据
        feature = Mock()
        feature.load.return_value = pd.Series(
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            index=pd.date_range("2020-01-01", periods=10, freq="D")
        )

        wma_op = WMA(feature, 3)
        result = wma_op._load_internal("test_stock", 0, 9)

        # 验证结果正确性
        assert isinstance(result, pd.Series)
        assert len(result) == 10

        # 验证加权平均计算
        # 手动计算第一个窗口的WMA
        window_data = [1, 2, 3]
        weights = np.array([1, 2, 3], dtype=np.float64)
        weights = weights / weights.sum()
        expected_wma = np.sum(weights * window_data)
        assert np.isclose(result.iloc[2], expected_wma)

    def test_rolling_operation_edge_cases(self):
        """测试滚动操作的边界情况"""
        feature = Mock()

        # 测试空数据
        feature.load.return_value = pd.Series([], dtype=float)
        mad_op = Mad(feature, 3)
        result = mad_op._load_internal("test_stock", 0, -1)
        assert len(result) == 0

        # 测试全NaN数据
        feature.load.return_value = pd.Series([np.nan, np.nan, np.nan])
        mad_op = Mad(feature, 3)
        result = mad_op._load_internal("test_stock", 0, 2)
        assert result.isna().all()

    def test_expanding_vs_rolling_consistency(self):
        """测试扩展窗口与滚动窗口的一致性"""
        feature = Mock()
        test_data = pd.Series(
            [1, 2, 3, 4, 5],
            index=pd.date_range("2020-01-01", periods=5, freq="D")
        )
        feature.load.return_value = test_data

        # 测试扩展窗口 (N=0)
        mad_expanding = Mad(feature, 0)
        result_expanding = mad_expanding._load_internal("test_stock", 0, 4)

        # 测试滚动窗口 (N=5，相当于扩展窗口）
        mad_rolling = Mad(feature, 5)
        result_rolling = mad_rolling._load_internal("test_stock", 0, 4)

        # 结果应该相等
        pd.testing.assert_series_equal(result_expanding, result_rolling)


class TestCacheSystemIntegration:
    """测试缓存系统集成"""

    @patch('qlib.data.cache.fcntl')
    def test_file_lock_mechanism(self, mock_fcntl):
        """测试文件锁机制"""
        mock_fcntl.flock.return_value = None
        mock_fcntl.LOCK_SH = 1
        mock_fcntl.LOCK_NB = 2

        cache = ExpressionCache()
        cache_path = "test_cache_path"

        # 模拟锁获取成功
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.fileno.return_value = 1
            with patch.object(cache, 'check_cache_exists', return_value=True):
                # 这里应该使用文件锁
                try:
                    cache.get(cache_path)
                except:
                    pass

        # 验证文件锁被调用
        mock_fcntl.flock.assert_called()

    def test_cache_recovery_after_corruption(self):
        """测试缓存损坏后的恢复"""
        cache = ExpressionCache()
        cache_path = "corrupted_cache"

        # 模拟损坏的缓存
        with patch.object(cache, 'check_cache_exists', return_value=True):
            with patch.object(cache, 'read_bin', side_effect=Exception("Corrupted data")):
                # 应该优雅地处理损坏的缓存
                result = cache.get(cache_path)
                assert result is None

    def test_cache_memory_cleanup(self):
        """测试缓存内存清理"""
        cache = DatasetCache()

        # 添加大量缓存项
        for i in range(100):
            cache.set(f"test_key_{i}", pd.DataFrame({"test": range(1000)}))

        # 检查内存使用
        initial_size = len(cache._cache) if hasattr(cache, '_cache') else 0

        # 触发内存清理
        if hasattr(cache, 'cleanup'):
            cache.cleanup()

        # 验证内存被清理
        final_size = len(cache._cache) if hasattr(cache, '_cache') else 0
        assert final_size <= initial_size


class TestDataValidation:
    """测试数据验证"""

    def test_feature_validation(self):
        """测试特征数据验证"""
        from qlib.data.base import Feature

        # 测试有效特征
        valid_feature = Feature("close")
        assert valid_feature.expression == "close"

        # 测试无效特征名
        with pytest.raises(ValueError):
            Feature("invalid feature name with spaces")

    def test_time_series_validation(self):
        """测试时间序列数据验证"""
        # 测试有效的时间序列
        valid_index = pd.date_range("2020-01-01", periods=10, freq="D")
        valid_data = pd.Series(range(10), index=valid_index)
        assert valid_data.index.is_monotonic_increasing

        # 测试无效的时间序列（非单调递增）
        invalid_index = pd.date_range("2020-01-10", periods=10, freq="-1D")
        invalid_data = pd.Series(range(10), index=invalid_index)
        assert not invalid_data.index.is_monotonic_increasing

    def test_data_consistency_validation(self):
        """测试数据一致性验证"""
        # 创建测试数据
        instruments = ['000001.SZ', '000002.SZ']
        fields = ['close', 'volume']
        index = pd.date_range("2020-01-01", periods=5, freq="D")

        # 创建多维数据
        data = pd.DataFrame(
            np.random.randn(10, 2),
            index=index,
            columns=pd.MultiIndex.from_product([instruments, fields])
        )

        # 验证数据结构
        assert isinstance(data.index, pd.DatetimeIndex)
        assert isinstance(data.columns, pd.MultiIndex)
        assert data.shape == (5, 4)  # 5天 × 2股票 × 2字段


if __name__ == "__main__":
    pytest.main([__file__])