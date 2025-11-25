# -*- coding: utf-8 -*-
# distutils: language = c++
# cython: language_level = 3
# cython: boundscheck = False
# cython: wraparound = False
# cython: initializedcheck = False
# cython: cdivision = True

"""
高性能量化操作符Cython扩展

提供优化的向量化计算实现，显著提升Qlib的数据处理性能。
包括移动平均、标准差、相关性等常用金融指标的高效计算。
"""

import numpy as np
cimport numpy as np
cimport cython

# 导入C数学库
from libc.math cimport sqrt, fabs, pow
from libc.stdio cimport printf


@cython.boundscheck(False)
@cython.wraparound(False)
cdef double[:,:] _create_rolling_weights(int N) nogil:
    """创建滚动权重矩阵（用于WMA等加权平均）"""
    cdef double[:,:] weights = np.empty((N, N), dtype=np.float64)
    cdef int i, j
    cdef double total_weight

    for i in range(N):
        total_weight = 0.0
        for j in range(i+1):
            weights[i, j] = i - j + 1  # 线性递增权重
            total_weight += weights[i, j]

        # 归一化权重
        if total_weight > 0.0:
            for j in range(i+1):
                weights[i, j] = weights[i, j] / total_weight

    return weights


@cython.boundscheck(False)
@cython.wraparound(False)
cdef double _compute_mad(const double[:] data, int start, int end) nogil:
    """计算平均绝对偏差（MAD）"""
    cdef int i
    cdef double mean_val = 0.0
    cdef double mad_val
    cdef int count = 0

    # 计算均值
    for i in range(start, min(end + 1, data.shape[0])):
        if not cython.isnan(data[i]):
            mean_val += data[i]
            count += 1

    if count == 0:
        return np.nan

    mean_val /= count

    # 计算绝对偏差
    mad_val = 0.0
    for i in range(start, min(end + 1, data.shape[0])):
        if not cython.isnan(data[i]):
            mad_val += fabs(data[i] - mean_val)

    return mad_val / count


@cython.boundscheck(False)
@cython.wraparound(False)
cdef double _compute_wma(const double[:] data, const double[:] weights, int start, int end) nogil:
    """计算加权移动平均（WMA）"""
    cdef int i
    cdef double weighted_sum = 0.0
    cdef double weight_sum = 0.0

    for i in range(start, min(end + 1, data.shape[0])):
        if not cython.isnan(data[i]) and i - start < weights.shape[0]:
            weighted_sum += data[i] * weights[i - start]
            weight_sum += weights[i - start]

    if weight_sum == 0.0:
        return np.nan

    return weighted_sum / weight_sum


@cython.boundscheck(False)
@cython.wraparound(False)
cdef double _compute_std(const double[:] data, int start, int end) nogil:
    """计算标准差"""
    cdef int i
    cdef double mean_val = 0.0
    cdef double variance = 0.0
    cdef int count = 0

    # 计算均值
    for i in range(start, min(end + 1, data.shape[0])):
        if not cython.isnan(data[i]):
            mean_val += data[i]
            count += 1

    if count <= 1:
        return np.nan

    mean_val /= count

    # 计算方差
    for i in range(start, min(end + 1, data.shape[0])):
        if not cython.isnan(data[i]):
            variance += pow(data[i] - mean_val, 2)

    variance /= (count - 1)
    return sqrt(variance)


@cython.boundscheck(False)
@cython.wraparound(False)
cdef double _compute_correlation(const double[:] x, const double[:] y, int window_size) nogil:
    """计算相关系数"""
    cdef int i
    cdef double mean_x = 0.0, mean_y = 0.0
    cdef double cov_xy = 0.0, var_x = 0.0, var_y = 0.0
    cdef double diff_x, diff_y

    # 计算均值
    for i in range(window_size):
        if not cython.isnan(x[i]) and not cython.isnan(y[i]):
            mean_x += x[i]
            mean_y += y[i]

    mean_x /= window_size
    mean_y /= window_size

    # 计算协方差和方差
    for i in range(window_size):
        if not cython.isnan(x[i]) and not cython.isnan(y[i]):
            diff_x = x[i] - mean_x
            diff_y = y[i] - mean_y
            cov_xy += diff_x * diff_y
            var_x += diff_x * diff_x
            var_y += diff_y * diff_y

    if var_x == 0.0 or var_y == 0.0:
        return np.nan

    return cov_xy / sqrt(var_x * var_y)


# 公共API函数
def fast_mad_rolling(const double[:] data, int window_size):
    """
    高性能滚动MAD计算

    Parameters
    ----------
    data : const double[:]
        输入数据
    window_size : int
        窗口大小

    Returns
    -------
    double[:]
        MAD结果
    """
    cdef int i
    cdef int n = data.shape[0]
    cdef double[:] result = np.empty(n, dtype=np.float64)

    for i in range(n):
        if i < window_size - 1:
            result[i] = np.nan
        else:
            result[i] = _compute_mad(data, i - window_size + 1, i)

    return np.asarray(result)


def fast_wma_rolling(const double[:] data, int window_size):
    """
    高性能滚动WMA计算

    Parameters
    ----------
    data : const double[:]
        输入数据
    window_size : int
        窗口大小

    Returns
    -------
    double[:]
        WMA结果
    """
    cdef int i
    cdef int n = data.shape[0]
    cdef double[:] result = np.empty(n, dtype=np.float64)
    cdef double[:] weights = np.arange(1, window_size + 1, dtype=np.float64)
    cdef double total_weight = np.sum(weights)
    cdef int j

    # 归一化权重
    for j in range(window_size):
        weights[j] = weights[j] / total_weight

    for i in range(n):
        if i < window_size - 1:
            result[i] = np.nan
        else:
            result[i] = _compute_wma(data, weights, i - window_size + 1, i)

    return np.asarray(result)


def fast_std_rolling(const double[:] data, int window_size):
    """
    高性能滚动标准差计算

    Parameters
    ----------
    data : const double[:]
        输入数据
    window_size : int
        窗口大小

    Returns
    -------
    double[:]
        标准差结果
    """
    cdef int i
    cdef int n = data.shape[0]
    cdef double[:] result = np.empty(n, dtype=np.float64)

    for i in range(n):
        if i < window_size - 1:
            result[i] = np.nan
        else:
            result[i] = _compute_std(data, i - window_size + 1, i)

    return np.asarray(result)


def fast_correlation_rolling(const double[:] x, const double[:] y, int window_size):
    """
    高性能滚动相关系数计算

    Parameters
    ----------
    x : const double[:]
        第一个序列
    y : const double[:]
        第二个序列
    window_size : int
        窗口大小

    Returns
    -------
    double[:]
        相关系数结果
    """
    cdef int i
    cdef int n = min(x.shape[0], y.shape[0])
    cdef double[:] result = np.empty(n, dtype=np.float64)

    for i in range(n):
        if i < window_size - 1:
            result[i] = np.nan
        else:
            result[i] = _compute_correlation(
                x[i-window_size+1:i+1] if i >= window_size else x[:i+1],
                y[i-window_size+1:i+1] if i >= window_size else y[:i+1],
                window_size
            )

    return np.asarray(result)


def fast_rsi(const double[:] prices, int window_size=14):
    """
    高性能RSI计算

    Parameters
    ----------
    prices : const double[:]
        价格序列
    window_size : int, default 14
        RSI窗口大小

    Returns
    -------
    double[:]
        RSI结果 (0-100)
    """
    cdef int i
    cdef int n = prices.shape[0]
    cdef double[:] result = np.empty(n, dtype=np.float64)
    cdef double gains, losses, avg_gain, avg_loss, rs

    for i in range(n):
        if i < window_size:
            result[i] = np.nan
        else:
            gains = 0.0
            losses = 0.0

            # 计算窗口内的涨跌幅
            for j in range(i - window_size + 1, i + 1):
                if j > 0:  # 避免数组越界
                    diff = prices[j] - prices[j-1]
                    if diff > 0:
                        gains += diff
                    else:
                        losses += -diff

            if losses == 0.0:
                result[i] = 100.0
            elif gains == 0.0:
                result[i] = 0.0
            else:
                avg_gain = gains / window_size
                avg_loss = losses / window_size
                rs = avg_gain / avg_loss
                result[i] = 100.0 - (100.0 / (1.0 + rs))

    return np.asarray(result)


def fast_bollinger_bands(const double[:] prices, int window_size=20, double num_std=2.0):
    """
    高性能布林带计算

    Parameters
    ----------
    prices : const double[:]
        价格序列
    window_size : int, default 20
        移动平均窗口大小
    num_std : double, default 2.0
        标准差倍数

    Returns
    -------
    tuple
        (上轨, 中轨, 下轨)
    """
    cdef int i
    cdef int n = prices.shape[0]
    cdef double[:] upper_band = np.empty(n, dtype=np.float64)
    cdef double[:] middle_band = np.empty(n, dtype=np.float64)
    cdef double[:] lower_band = np.empty(n, dtype=np.float64)
    cdef double std_val, ma_val

    # 首先计算移动平均
    middle_band = fast_wma_rolling(prices, window_size)

    # 计算每个点的标准差
    for i in range(n):
        if i < window_size - 1:
            std_val = np.nan
        else:
            std_val = _compute_std(prices, i - window_size + 1, i)

        ma_val = middle_band[i]
        if not cython.isnan(std_val) and not cython.isnan(ma_val):
            upper_band[i] = ma_val + num_std * std_val
            lower_band[i] = ma_val - num_std * std_val
        else:
            upper_band[i] = np.nan
            lower_band[i] = np.nan

    return np.asarray(upper_band), np.asarray(middle_band), np.asarray(lower_band)


# 批量处理函数
def batch_compute_features(double[:,:] data, list feature_types, list window_sizes):
    """
    批量计算多个特征

    Parameters
    ----------
    data : double[:, :]
        输入数据 (时间 x 特征)
    feature_types : list
        特征类型列表 ['mad', 'wma', 'std', 'rsi']
    window_sizes : list
        对应的窗口大小

    Returns
    -------
    double[:, :]
        计算结果
    """
    cdef int n_features = len(feature_types)
    cdef int n_timesteps = data.shape[0]
    cdef double[:,:] result = np.empty((n_timesteps, n_features), dtype=np.float64)
    cdef int i, j
    cdef str feature_type
    cdef int window_size

    for j in range(n_features):
        feature_type = feature_types[j]
        window_size = window_sizes[j]

        for i in range(n_timesteps):
            if feature_type == 'mad':
                if i < window_size - 1:
                    result[i, j] = np.nan
                else:
                    result[i, j] = _compute_mad(data[:, j], i - window_size + 1, i)
            elif feature_type == 'wma':
                if i < window_size - 1:
                    result[i, j] = np.nan
                else:
                    # 创建简单权重
                    cdef double[:] weights = np.arange(1, window_size + 1, dtype=np.float64)
                    cdef double total_weight = (window_size * (window_size + 1)) / 2.0
                    weights = weights / total_weight
                    result[i, j] = _compute_wma(data[:, j], weights, i - window_size + 1, i)
            elif feature_type == 'std':
                if i < window_size - 1:
                    result[i, j] = np.nan
                else:
                    result[i, j] = _compute_std(data[:, j], i - window_size + 1, i)
            else:
                result[i, j] = np.nan

    return np.asarray(result)