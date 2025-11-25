# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
高性能量化操作符Python接口

为Cython扩展提供Python接口，集成到Qlib的操作符系统中。
包含移动平均、标准差、相关系数等常用金融指标的高效计算。
"""

import numpy as np
from typing import Optional, Tuple, List, Union

# 尝试导入编译的Cython扩展
try:
    from . import fast_ops_cython
    CYTHON_AVAILABLE = True
except ImportError:
    CYTHON_AVAILABLE = False
    print("Warning: Cython extensions not available. Using NumPy implementations.")
    print("Install Cython extensions for better performance:")
    print("  pip install cython numpy")
    print("  cd qlib/contrib/ops && python setup.py build_ext --inplace")


class FastOpsBase:
    """高性能操作符基类"""

    def __init__(self, fallback_to_numpy: bool = True):
        self.fallback_to_numpy = fallback_to_numpy
        self.cython_available = CYTHON_AVAILABLE

    def _check_cython(self) -> bool:
        """检查Cython是否可用"""
        if not self.cython_available and not self.fallback_to_numpy:
            raise RuntimeError(
                "Cython extensions not available and fallback disabled. "
                "Install Cython extensions or enable fallback."
            )
        return self.cython_available


class FastMAD(FastOpsBase):
    """高性能平均绝对偏差计算"""

    def __init__(self, window_size: int, fallback_to_numpy: bool = True):
        super().__init__(fallback_to_numpy)
        self.window_size = window_size

    def compute(self, data: np.ndarray) -> np.ndarray:
        """计算MAD"""
        if self._check_cython():
            return fast_ops_cython.fast_mad_rolling(data, self.window_size)
        else:
            return self._numpy_mad(data, self.window_size)

    def _numpy_mad(self, data: np.ndarray, window_size: int) -> np.ndarray:
        """NumPy备用实现"""
        result = np.full(len(data), np.nan)
        for i in range(window_size - 1, len(data)):
            window = data[i - window_size + 1:i + 1]
            valid_window = window[~np.isnan(window)]
            if len(valid_window) > 0:
                result[i] = np.mean(np.abs(valid_window - np.mean(valid_window)))
        return result


class FastWMA(FastOpsBase):
    """高性能加权移动平均计算"""

    def __init__(self, window_size: int, fallback_to_numpy: bool = True):
        super().__init__(fallback_to_numpy)
        self.window_size = window_size

    def compute(self, data: np.ndarray) -> np.ndarray:
        """计算WMA"""
        if self._check_cython():
            # 创建线性递增权重
            weights = fast_ops_cython._create_rolling_weights(self.window_size)
            return fast_ops_cython.fast_wma_rolling(data, weights)
        else:
            return self._numpy_wma(data, self.window_size)

    def _numpy_wma(self, data: np.ndarray, window_size: int) -> np.ndarray:
        """NumPy备用实现"""
        result = np.full(len(data), np.nan)
        for i in range(window_size - 1, len(data)):
            window = data[i - window_size + 1:i + 1]
            valid_window = window[~np.isnan(window)]
            if len(valid_window) > 0:
                weights = np.arange(1, len(valid_window) + 1, dtype=np.float64)
                weights = weights / weights.sum()
                result[i] = np.sum(weights * valid_window)
        return result


class FastSTD(FastOpsBase):
    """高性能标准差计算"""

    def __init__(self, window_size: int, fallback_to_numpy: bool = True):
        super().__init__(fallback_to_numpy)
        self.window_size = window_size

    def compute(self, data: np.ndarray) -> np.ndarray:
        """计算标准差"""
        if self._check_cython():
            return fast_ops_cython.fast_std_rolling(data, self.window_size)
        else:
            return self._numpy_std(data, self.window_size)

    def _numpy_std(self, data: np.ndarray, window_size: int) -> np.ndarray:
        """NumPy备用实现"""
        result = np.full(len(data), np.nan)
        for i in range(window_size - 1, len(data)):
            window = data[i - window_size + 1:i + 1]
            valid_window = window[~np.isnan(window)]
            if len(valid_window) > 1:
                result[i] = np.std(valid_window, ddof=1)
        return result


class FastCorrelation(FastOpsBase):
    """高性能相关系数计算"""

    def __init__(self, window_size: int, fallback_to_numpy: bool = True):
        super().__init__(fallback_to_numpy)
        self.window_size = window_size

    def compute(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """计算相关系数"""
        if self._check_cython():
            return fast_ops_cython.fast_correlation_rolling(x, y, self.window_size)
        else:
            return self._numpy_correlation(x, y, self.window_size)

    def _numpy_correlation(self, x: np.ndarray, y: np.ndarray, window_size: int) -> np.ndarray:
        """NumPy备用实现"""
        n = min(len(x), len(y))
        result = np.full(n, np.nan)
        for i in range(window_size - 1, n):
            window_x = x[i - window_size + 1:i + 1]
            window_y = y[i - window_size + 1:i + 1]

            # 过滤NaN值
            valid_mask = ~(np.isnan(window_x) | np.isnan(window_y))
            if np.sum(valid_mask) > 1:
                valid_x = window_x[valid_mask]
                valid_y = window_y[valid_mask]

                if len(valid_x) > 1:
                    corr_matrix = np.corrcoef(valid_x, valid_y)
                    result[i] = corr_matrix[0, 1]
        return result


class FastRSI(FastOpsBase):
    """高性能RSI计算"""

    def __init__(self, window_size: int = 14, fallback_to_numpy: bool = True):
        super().__init__(fallback_to_numpy)
        self.window_size = window_size

    def compute(self, prices: np.ndarray) -> np.ndarray:
        """计算RSI"""
        if self._check_cython():
            return fast_ops_cython.fast_rsi(prices, self.window_size)
        else:
            return self._numpy_rsi(prices, self.window_size)

    def _numpy_rsi(self, prices: np.ndarray, window_size: int) -> np.ndarray:
        """NumPy备用实现"""
        n = len(prices)
        result = np.full(n, np.nan)

        for i in range(window_size, n):
            window = prices[i - window_size:i]

            gains = []
            losses = []
            for j in range(1, len(window)):
                diff = window[j] - window[j-1]
                if diff > 0:
                    gains.append(diff)
                elif diff < 0:
                    losses.append(-diff)

            if gains and losses:
                avg_gain = np.mean(gains)
                avg_loss = np.mean(losses)
                rs = avg_gain / avg_loss
                result[i] = 100.0 - (100.0 / (1.0 + rs))
            elif gains:
                result[i] = 100.0
            else:
                result[i] = 0.0

        return result


class FastBollingerBands(FastOpsBase):
    """高性能布林带计算"""

    def __init__(self, window_size: int = 20, num_std: float = 2.0, fallback_to_numpy: bool = True):
        super().__init__(fallback_to_numpy)
        self.window_size = window_size
        self.num_std = num_std

    def compute(self, prices: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """计算布林带

        Returns
        -------
        tuple
            (上轨, 中轨, 下轨)
        """
        if self._check_cython():
            return fast_ops_cython.fast_bollinger_bands(prices, self.window_size, self.num_std)
        else:
            return self._numpy_bollinger(prices, self.window_size, self.num_std)

    def _numpy_bollinger(self, prices: np.ndarray, window_size: int, num_std: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """NumPy备用实现"""
        # 计算移动平均（中轨）
        wma = FastWMA(window_size, fallback_to_numpy=False)
        middle_band = wma.compute(prices)

        # 计算标准差
        std = FastSTD(window_size, fallback_to_numpy=False)
        std_values = std.compute(prices)

        # 计算上下轨
        upper_band = middle_band + num_std * std_values
        lower_band = middle_band - num_std * std_values

        return upper_band, middle_band, lower_band


class BatchFastOps:
    """批量高性能计算"""

    @staticmethod
    def compute_features(data: np.ndarray, feature_configs: List[dict]) -> np.ndarray:
        """
        批量计算多个特征

        Parameters
        ----------
        data : np.ndarray
            输入数据 (时间 x 特征)
        feature_configs : List[dict]
            特征配置列表，每个配置包含：
            - 'type': 特征类型 ('mad', 'wma', 'std', 'rsi', 'correlation')
            - 'window_size': 窗口大小
            - 'num_std': 标准差倍数（仅布林带）

        Returns
        -------
        np.ndarray
            计算结果 (时间 x 特征)
        """
        if CYTHON_AVAILABLE:
            # 使用Cython批量处理
            feature_types = [config['type'] for config in feature_configs]
            window_sizes = [config['window_size'] for config in feature_configs]

            return fast_ops_cython.batch_compute_features(
                data.astype(np.float64), feature_types, window_sizes
            )
        else:
            # 使用NumPy逐个计算
            n_timesteps = data.shape[0]
            n_features = len(feature_configs)
            result = np.full((n_timesteps, n_features), np.nan)

            for i, config in enumerate(feature_configs):
                feature_type = config['type']
                window_size = config['window_size']

                if feature_type == 'mad':
                    mad_op = FastMAD(window_size, fallback_to_numpy=False)
                    result[:, i] = mad_op.compute(data[:, 0] if data.ndim == 2 else data)
                elif feature_type == 'wma':
                    wma_op = FastWMA(window_size, fallback_to_numpy=False)
                    result[:, i] = wma_op.compute(data[:, 0] if data.ndim == 2 else data)
                elif feature_type == 'std':
                    std_op = FastSTD(window_size, fallback_to_numpy=False)
                    result[:, i] = std_op.compute(data[:, 0] if data.ndim == 2 else data)
                elif feature_type == 'rsi':
                    rsi_op = FastRSI(window_size, fallback_to_numpy=False)
                    result[:, i] = rsi_op.compute(data[:, 0] if data.ndim == 2 else data)
                elif feature_type == 'bollinger':
                    num_std = config.get('num_std', 2.0)
                    bb_op = FastBollingerBands(window_size, num_std, fallback_to_numpy=False)
                    upper, middle, lower = bb_op.compute(data[:, 0] if data.ndim == 2 else data)
                    # 布林带返回三个值，这里取中轨
                    result[:, i] = middle
                else:
                    raise ValueError(f"Unsupported feature type: {feature_type}")

            return result


# 性能比较工具
class PerformanceBenchmark:
    """性能基准测试工具"""

    @staticmethod
    def benchmark_implementations(
        data: np.ndarray,
        window_size: int,
        iterations: int = 100
    ) -> dict:
        """
        比较Cython和NumPy实现的性能

        Returns
        -------
        dict
            性能统计信息
        """
        import time

        # 测试数据
        test_data = data[:min(1000, len(data))]  # 限制测试数据大小

        results = {}

        # MAD基准测试
        if CYTHON_AVAILABLE:
            mad_cython = FastMAD(window_size, fallback_to_numpy=False)
            start_time = time.time()
            for _ in range(iterations):
                _ = mad_cython.compute(test_data)
            cython_time = time.time() - start_time

            mad_numpy = FastMAD(window_size, fallback_to_numpy=True)
            start_time = time.time()
            for _ in range(iterations):
                _ = mad_numpy.compute(test_data)
            numpy_time = time.time() - start_time

            results['mad'] = {
                'cython_time': cython_time,
                'numpy_time': numpy_time,
                'speedup': numpy_time / cython_time if cython_time > 0 else float('inf')
            }

        # WMA基准测试
        if CYTHON_AVAILABLE:
            wma_cython = FastWMA(window_size, fallback_to_numpy=False)
            start_time = time.time()
            for _ in range(iterations):
                _ = wma_cython.compute(test_data)
            cython_time = time.time() - start_time

            wma_numpy = FastWMA(window_size, fallback_to_numpy=True)
            start_time = time.time()
            for _ in range(iterations):
                _ = wma_numpy.compute(test_data)
            numpy_time = time.time() - start_time

            results['wma'] = {
                'cython_time': cython_time,
                'numpy_time': numpy_time,
                'speedup': numpy_time / cython_time if cython_time > 0 else float('inf')
            }

        return results


# 便捷函数
def fast_mad(data: np.ndarray, window_size: int) -> np.ndarray:
    """快速MAD计算"""
    return FastMAD(window_size).compute(data)


def fast_wma(data: np.ndarray, window_size: int) -> np.ndarray:
    """快速WMA计算"""
    return FastWMA(window_size).compute(data)


def fast_std(data: np.ndarray, window_size: int) -> np.ndarray:
    """快速标准差计算"""
    return FastSTD(window_size).compute(data)


def fast_rsi(data: np.ndarray, window_size: int = 14) -> np.ndarray:
    """快速RSI计算"""
    return FastRSI(window_size).compute(data)


def fast_bollinger_bands(data: np.ndarray, window_size: int = 20, num_std: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """快速布林带计算"""
    return FastBollingerBands(window_size, num_std).compute(data)


def fast_correlation(x: np.ndarray, y: np.ndarray, window_size: int) -> np.ndarray:
    """快速相关系数计算"""
    return FastCorrelation(window_size).compute(x, y)


# 导出的函数列表（用于__all__）
__all__ = [
    'FastMAD', 'FastWMA', 'FastSTD', 'FastRSI',
    'FastCorrelation', 'FastBollingerBands', 'BatchFastOps',
    'PerformanceBenchmark',
    'fast_mad', 'fast_wma', 'fast_std', 'fast_rsi',
    'fast_bollinger_bands', 'fast_correlation'
]