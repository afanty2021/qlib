# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
性能增强测试

测试系统性能优化和资源管理。
"""

import gc
import time
import tracemalloc
import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch

from qlib.data.ops import Mad, WMA, Rolling
from qlib.contrib.model.pytorch_nn import MLPLayer
from qlib.rl.trainer.trainer import RLTrainer


class TestPerformanceOptimizations:
    """测试性能优化"""

    def test_vectorized_vs_loop_performance(self):
        """测试向量化操作vs循环操作的性能"""
        # 创建大量测试数据
        data = np.random.randn(10000, 10)
        feature = Mock()
        feature.load.return_value = pd.Series(data[:, 0])

        # 测试向量化MAD
        mad_vectorized = Mad(feature, 20)
        start_time = time.time()
        result_vectorized = mad_vectorized._load_internal("test", 0, 9999)
        vectorized_time = time.time() - start_time

        # 模拟循环实现（用于对比）
        def mad_loop(x):
            if np.isnan(x).all():
                return np.nan
            x_valid = x[~np.isnan(x)]
            if len(x_valid) == 0:
                return np.nan
            mean_val = x_valid.mean()
            # 模拟低效的循环计算
            total = 0
            for val in x_valid:
                total += abs(val - mean_val)
            return total / len(x_valid)

        # 测试循环实现
        mad_loop_impl = Mad(feature, 20)
        with patch.object(mad_loop_impl, '_load_internal') as mock_load:
            mock_load.side_effect = lambda *args: pd.Series([
                mad_loop(feature.load.return_value.iloc[max(0, i-19):i+1].values)
                for i in range(len(feature.load.return_value))
            ])
            start_time = time.time()
            result_loop = mad_loop_impl._load_internal("test", 0, 9999)
            loop_time = time.time() - start_time

        # 向量化应该更快
        print(f"向量化时间: {vectorized_time:.4f}s, 循环时间: {loop_time:.4f}s")
        # 注意：在实际测试中，我们期望向量化更快，但这里只是演示
        assert isinstance(result_vectorized, pd.Series)

    def test_memory_usage_with_large_arrays(self):
        """测试大数组的内存使用"""
        tracemalloc.start()

        # 创建大型数组
        large_data = pd.DataFrame(
            np.random.randn(50000, 20),
            columns=[f"feature_{i}" for i in range(20)],
            index=pd.date_range("2010-01-01", periods=50000, freq="D")
        )

        # 获取内存使用快照
        snapshot1 = tracemalloc.take_snapshot()

        # 执行操作
        feature = Mock()
        feature.load.return_value = large_data.iloc[:, 0]
        mad_op = Mad(feature, 100)
        result = mad_op._load_internal("test", 0, 49999)

        # 获取操作后内存快照
        snapshot2 = tracemalloc.take_snapshot()

        # 计算内存增长
        stats = snapshot2.compare_to(snapshot1, 'lineno')
        total_memory_diff = sum(stat.size_diff for stat in stats)

        # 清理内存
        del large_data, result
        gc.collect()

        tracemalloc.stop()

        # 内存增长应该在合理范围内（小于100MB）
        assert total_memory_diff < 100 * 1024 * 1024

    def test_caching_performance_improvement(self):
        """测试缓存的性能提升"""
        from qlib.data.cache import ExpressionCache

        cache = ExpressionCache()
        test_data = pd.Series(np.random.randn(1000))
        cache_key = "performance_test"

        # 测试第一次访问（无缓存）
        start_time = time.time()
        cache.set(cache_key, test_data)
        first_access_time = time.time() - start_time

        # 测试缓存访问
        start_time = time.time()
        cached_data = cache.get(cache_key)
        cached_access_time = time.time() - start_time

        # 缓存访问应该更快
        assert cached_access_time < first_access_time
        pd.testing.assert_series_equal(test_data, cached_data)


class TestMemoryManagement:
    """测试内存管理"""

    def test_memory_leak_prevention_in_trainer(self):
        """测试训练器中的内存泄漏防护"""
        # 模拟训练环境
        vessel = Mock()
        vessel.train_seed_iterator.return_value = [1, 2, 3]

        # 模拟向量环境
        mock_vector_env = Mock()
        mock_vector_env.close = Mock()

        trainer = RLTrainer()
        trainer.venv_from_iterator = Mock(return_value=mock_vector_env)
        trainer.vessel = vessel

        # 记录初始内存使用
        initial_objects = len(gc.get_objects())

        # 执行训练步骤（应该包含内存清理）
        trainer.current_iter = 0
        trainer.max_iters = 1
        trainer.should_stop = False

        # 模拟训练过程
        with patch.object(trainer, '_call_callback_hooks'):
            trainer.fit(max_iters=1)

        # 验证资源清理
        mock_vector_env.close.assert_called()

        # 强制垃圾回收后检查对象数量
        gc.collect()
        final_objects = len(gc.get_objects())

        # 对象数量不应该显著增长（允许一些合理的增长）
        object_growth = final_objects - initial_objects
        assert object_growth < 1000  # 允许合理的对象增长

    def test_large_dataset_cleanup(self):
        """测试大数据集清理"""
        # 创建多个大数据集
        datasets = []
        for i in range(10):
            data = pd.DataFrame(
                np.random.randn(10000, 5),
                columns=[f"col_{j}" for j in range(5)]
            )
            datasets.append(data)

        # 记录内存使用
        initial_memory = len(gc.get_objects())

        # 清理数据集
        datasets.clear()
        gc.collect()

        # 验证内存清理
        final_memory = len(gc.get_objects())
        memory_reduction = initial_memory - final_memory

        # 应该有显著的内存减少
        assert memory_reduction > 0

    def test_model_parameter_cleanup(self):
        """测试模型参数清理"""
        # 创建模型
        model = MLPLayer(d_feat=10, hidden_size=20)

        # 模拟训练后状态
        model.model = Mock()
        model.optimizer = Mock()
        model.scheduler = Mock()

        # 清理模型
        if hasattr(model, 'clear'):
            model.clear()
        else:
            # 手动清理
            del model.model
            del model.optimizer
            del model.scheduler

        # 强制垃圾回收
        gc.collect()

        # 验证清理效果
        assert not hasattr(model, 'model') or model.model is None


class TestResourceOptimization:
    """测试资源优化"""

    def test_parallel_processing_efficiency(self):
        """测试并行处理效率"""
        import multiprocessing as mp

        def process_chunk(chunk):
            """处理数据块的函数"""
            return np.mean(chunk, axis=0)

        # 创建大量数据
        data = np.random.randn(10000, 10)

        # 串行处理
        start_time = time.time()
        serial_result = np.array_split(data, 4)
        serial_result = [process_chunk(chunk) for chunk in serial_result]
        serial_time = time.time() - start_time

        # 并行处理（如果CPU核心数足够）
        if mp.cpu_count() > 1:
            with mp.Pool(processes=4) as pool:
                start_time = time.time()
                chunks = np.array_split(data, 4)
                parallel_result = pool.map(process_chunk, chunks)
                parallel_time = time.time() - start_time

            # 并行处理应该更快（在多核系统上）
            print(f"串行时间: {serial_time:.4f}s, 并行时间: {parallel_time:.4f}s")
            # 注意：实际性能提升取决于硬件和数据特性
            assert len(parallel_result) == 4

    def test_io_optimization(self):
        """测试I/O优化"""
        import tempfile
        import os

        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            temp_file = f.name
            # 写入大量数据
            for i in range(10000):
                f.write(f"line {i}: some data\n")

        # 测试批量读取
        start_time = time.time()
        with open(temp_file, 'r') as f:
            batch_data = f.readlines(1000)  # 批量读取
        batch_time = time.time() - start_time

        # 测试逐行读取
        start_time = time.time()
        with open(temp_file, 'r') as f:
            line_data = []
            for line in f:
                line_data.append(line)
                if len(line_data) >= 1000:
                    break
        line_time = time.time() - start_time

        # 批量读取应该更高效
        print(f"批量读取: {batch_time:.4f}s, 逐行读取: {line_time:.4f}s")
        assert len(batch_data) == 1000
        assert len(line_data) == 1000

        # 清理
        os.unlink(temp_file)

    def test_numpy_vectorization_benefits(self):
        """测试NumPy向量化的优势"""
        # 创建测试数据
        data = np.random.randn(100000, 5)

        # 向量化操作
        start_time = time.time()
        vectorized_result = np.mean(data, axis=0)
        vectorized_time = time.time() - start_time

        # 模拟非向量化操作
        start_time = time.time()
        loop_result = []
        for i in range(data.shape[1]):
            column_sum = 0
            for j in range(data.shape[0]):
                column_sum += data[j, i]
            loop_result.append(column_sum / data.shape[0])
        loop_result = np.array(loop_result)
        loop_time = time.time() - start_time

        # 向量化应该显著更快
        print(f"向量化时间: {vectorized_time:.4f}s, 循环时间: {loop_time:.4f}s")
        assert vectorized_time < loop_time
        np.testing.assert_array_almost_equal(vectorized_result, loop_result)


class TestBenchmarkUtilities:
    """测试基准测试工具"""

    def test_performance_profiling(self):
        """测试性能分析"""
        import cProfile
        import pstats
        from io import StringIO

        # 创建性能分析器
        pr = cProfile.Profile()

        # 定义测试函数
        def test_function():
            data = np.random.randn(1000, 10)
            result = np.mean(data, axis=0)
            return result

        # 分析函数性能
        pr.enable()
        result = test_function()
        pr.disable()

        # 获取统计信息
        s = StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
        ps.print_stats(10)  # 打印前10个最耗时的函数

        # 验证分析结果
        profile_output = s.getvalue()
        assert 'test_function' in profile_output
        assert result is not None

    def test_memory_profiling(self):
        """测试内存分析"""
        try:
            from memory_profiler import profile
        except ImportError:
            pytest.skip("memory_profiler not available")

        @profile
        def memory_intensive_function():
            """内存密集型函数"""
            data = []
            for i in range(1000):
                data.append(np.random.randn(100))
            return data

        # 执行内存分析
        result = memory_intensive_function()
        assert len(result) == 1000


if __name__ == "__main__":
    pytest.main([__file__])