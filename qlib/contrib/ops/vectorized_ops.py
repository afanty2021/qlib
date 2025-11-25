# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
向量化量化操作符实现

提供优化的NumPy向量化计算实现，
作为Cython扩展的备用方案，显著提升性能。
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple, List, Union


class VectorizedMAD:
    """向量化平均绝对偏差计算"""

    def __init__(self, window_size: int):
        self.window_size = window_size

    def compute(self, data: Union[pd.Series, np.ndarray]) -> np.ndarray:
        """
        计算平均绝对偏差

        Parameters
        ----------
        data : Union[pd.Series, np.ndarray]
            输入数据

        Returns
        -------
        np.ndarray
            MAD结果
        """
        if isinstance(data, pd.Series):
            values = data.values
        else:
            values = data

        if len(values) < self.window_size:
            return np.full(len(values), np.nan)

        # 向量化实现
        result = np.full(len(values), np.nan)

        # 使用卷积计算累计和
        valid_mask = ~np.isnan(values)

        # 计算每个窗口的均值
        cumsum = np.cumsum(np.where(valid_mask, values, 0))
        cumcount = np.cumsum(valid_mask.astype(int))

        # 计算移动平均
        window_sum = cumsum[self.window_size - 1:] - np.concatenate([[0], cumsum[:-self.window_size - 1]])
        window_count = cumcount[self.window_size - 1:] - np.concatenate([[0], cumcount[:-self.window_size - 1]])
        window_mean = window_sum / window_count

        # 计算绝对偏差
        abs_diff = np.abs(values - window_mean)
        abs_diff_cumsum = np.cumsum(np.where(valid_mask, abs_diff, 0))
        window_abs_sum = abs_diff_cumsum[self.window_size - 1:] - np.concatenate([[0], abs_diff_cumsum[:-self.window_size - 1]])

        result[self.window_size - 1:] = window_abs_sum / window_count
        return result


class VectorizedWMA:
    """向量化加权移动平均计算"""

    def __init__(self, window_size: int):
        self.window_size = window_size

    def compute(self, data: Union[pd.Series, np.ndarray]) -> np.ndarray:
        """
        计算加权移动平均

        Parameters
        ----------
        data : Union[pd.Series, np.ndarray]
            输入数据

        Returns
        -------
        np.ndarray
            WMA结果
        """
        if isinstance(data, pd.Series):
            values = data.values
        else:
            values = data

        if len(values) < self.window_size:
            return np.full(len(values), np.nan)

        # 预计算权重
        weights = np.arange(1, self.window_size + 1, dtype=np.float64)
        weights = weights / weights.sum()

        # 向量化实现
        result = np.full(len(values), np.nan)

        # 使用卷积计算加权平均
        valid_mask = ~np.isnan(values)

        for i in range(self.window_size - 1, len(values)):
            window_data = values[i - self.window_size + 1:i + 1]
            valid_window_data = window_data[valid_mask[i - self.window_size + 1:i + 1]]

            if len(valid_window_data) > 0:
                valid_weights = weights[:len(valid_window_data)]
                valid_weights = valid_weights / valid_weights.sum()
                result[i] = np.sum(valid_weights * valid_window_data)

        return result


class VectorizedRSI:
    """向量化RSI计算"""

    def __init__(self, window_size: int = 14):
        self.window_size = window_size

    def compute(self, prices: Union[pd.Series, np.ndarray]) -> np.ndarray:
        """
        计算相对强弱指数

        Parameters
        ----------
        prices : Union[pd.Series, np.ndarray]
            价格序列

        Returns
        -------
        np.ndarray
            RSI结果 (0-100)
        """
        if isinstance(prices, pd.Series):
            values = prices.values
        else:
            values = prices

        if len(values) < self.window_size:
            return np.full(len(values), np.nan)

        result = np.full(len(values), np.nan)

        for i in range(self.window_size, len(values)):
            window = values[i - self.window_size:i]

            # 计算涨跌幅
            price_changes = np.diff(window)
            gains = price_changes[price_changes > 0]
            losses = -price_changes[price_changes < 0]

            if len(gains) > 0 and len(losses) > 0:
                avg_gain = np.mean(gains)
                avg_loss = np.mean(losses)
                rs = avg_gain / avg_loss
                result[i] = 100.0 - (100.0 / (1.0 + rs))
            elif len(gains) > 0:
                result[i] = 100.0
            elif len(losses) > 0:
                result[i] = 0.0

        return result


class VectorizedBollingerBands:
    """向量化布林带计算"""

    def __init__(self, window_size: int = 20, num_std: float = 2.0):
        self.window_size = window_size
        self.num_std = num_std

    def compute(self, prices: Union[pd.Series, np.ndarray]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        计算布林带

        Parameters
        ----------
        prices : Union[pd.Series, np.ndarray]
            价格序列
        window_size : int
            移动平均窗口大小
        num_std : float
            标准差倍数

        Returns
        -------
        Tuple[np.ndarray, np.ndarray, np.ndarray]
            (上轨, 中轨, 下轨)
        """
        if isinstance(prices, pd.Series):
            values = prices.values
        else:
            values = prices

        if len(values) < self.window_size:
            n = len(values)
            return (
                np.full(n, np.nan),
                np.full(n, np.nan),
                np.full(n, np.nan)
            )

        # 计算移动平均（中轨）
        wma = VectorizedWMA(self.window_size)
        middle_band = wma.compute(values)

        # 计算标准差
        std_values = []
        for i in range(self.window_size - 1, len(values)):
            window = values[i - self.window_size + 1:i + 1]
            valid_window = window[~np.isnan(window)]
            if len(valid_window) > 1:
                std_values.append(np.std(valid_window, ddof=1))
            else:
                std_values.append(np.nan)

        std_values = np.array(std_values)

        # 扩展到完整长度
        full_std = np.full(len(values), np.nan)
        full_std[self.window_size - 1:] = std_values

        # 计算上下轨
        upper_band = middle_band + self.num_std * full_std
        lower_band = middle_band - self.num_std * full_std

        return upper_band, middle_band, lower_band


class BatchVectorizedOps:
    """批量向量化操作"""

    @staticmethod
    def compute_all_features(
        data: Union[pd.DataFrame, np.ndarray],
        features: List[str],
        window_sizes: Optional[List[int]] = None
    ) -> np.ndarray:
        """
        批量计算多个特征

        Parameters
        ----------
        data : Union[pd.DataFrame, np.ndarray]
            输入数据 (时间 x 特征)
        features : List[str]
            特征类型列表 ['mad', 'wma', 'rsi', 'std', 'bollinger']
        window_sizes : Optional[List[int]]
            对应的窗口大小

        Returns
        -------
        np.ndarray
            计算结果 (时间 x 特征)
        """
        if isinstance(data, pd.DataFrame):
            values = data.values
        else:
            values = data

        if window_sizes is None:
            window_sizes = [20] * len(features)

        result = np.full((values.shape[0], len(features)), np.nan)

        for i, (feature, window_size) in enumerate(zip(features, window_sizes)):
            if feature == 'mad':
                op = VectorizedMAD(window_size)
                result[:, i] = op.compute(values[:, 0] if values.ndim == 2 else values)
            elif feature == 'wma':
                op = VectorizedWMA(window_size)
                result[:, i] = op.compute(values[:, 0] if values.ndim == 2 else values)
            elif feature == 'rsi':
                op = VectorizedRSI(window_size)
                result[:, i] = op.compute(values[:, 0] if values.ndim == 2 else values)
            elif feature == 'std':
                op = VectorizedSTD(window_size)
                result[:, i] = op.compute(values[:, 0] if values.ndim == 2 else values)
            elif feature == 'bollinger':
                op = VectorizedBollingerBands(window_size)
                upper, middle, lower = op.compute(values[:, 0] if values.ndim == 2 else values)
                # 布林带返回三个值，这里取中轨
                result[:, i] = middle
            else:
                raise ValueError(f"Unsupported feature: {feature}")

        return result


# 便捷函数
def vectorized_mad(data: Union[pd.Series, np.ndarray], window_size: int = 20) -> np.ndarray:
    """向量化MAD计算"""
    return VectorizedMAD(window_size).compute(data)


def vectorized_wma(data: Union[pd.Series, np.ndarray], window_size: int = 20) -> np.ndarray:
    """向量化WMA计算"""
    return VectorizedWMA(window_size).compute(data)


def vectorized_rsi(data: Union[pd.Series, np.ndarray], window_size: int = 14) -> np.ndarray:
    """向量化RSI计算"""
    return VectorizedRSI(window_size).compute(data)


def vectorized_bollinger_bands(
    data: Union[pd.Series, np.ndarray],
    window_size: int = 20,
    num_std: float = 2.0
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """向量化布林带计算"""
    return VectorizedBollingerBands(window_size, num_std).compute(data)


def vectorized_correlation(
    x: Union[pd.Series, np.ndarray],
    y: Union[pd.Series, np.ndarray],
    window_size: int = 20
) -> np.ndarray:
    """向量化相关系数计算"""
    if isinstance(x, pd.Series):
        x_values = x.values
    else:
        x_values = x

    if isinstance(y, pd.Series):
        y_values = y.values
    else:
        y_values = y

    n = min(len(x_values), len(y_values))
    result = np.full(n, np.nan)

    for i in range(window_size - 1, n):
        window_x = x_values[i - window_size + 1:i + 1]
        window_y = y_values[i - window_size + 1:i + 1]

        # 过滤NaN值
        valid_mask = ~(np.isnan(window_x) | np.isnan(window_y))
        if np.sum(valid_mask) > 1:
            valid_x = window_x[valid_mask]
            valid_y = window_y[valid_mask]
            corr_matrix = np.corrcoef(valid_x, valid_y)
            result[i] = corr_matrix[0, 1]

    return result


# 向量化标准差计算
class VectorizedSTD:
    """向量化标准差计算"""

    def __init__(self, window_size: int):
        self.window_size = window_size

    def compute(self, data: Union[pd.Series, np.ndarray]) -> np.ndarray:
        """
        计算标准差
        """
        if isinstance(data, pd.Series):
            values = data.values
        else:
            values = data

        if len(values) < self.window_size:
            return np.full(len(values), np.nan)

        result = np.full(len(values), np.nan)

        # 向量化实现
        for i in range(self.window_size - 1, len(values)):
            window = values[i - self.window_size + 1:i + 1]
            valid_window = window[~np.isnan(window)]
            if len(valid_window) > 1:
                result[i] = np.std(valid_window, ddof=1)

        return result


# 导出的函数列表（用于__all__）
__all__ = [
    'VectorizedMAD', 'VectorizedWMA', 'VectorizedRSI', 'VectorizedBollingerBands',
    'VectorizedSTD', 'BatchVectorizedOps',
    'vectorized_mad', 'vectorized_wma', 'vectorized_rsi', 'vectorized_bollinger_bands',
    'vectorized_correlation'
]