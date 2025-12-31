"""
行业因子计算模块

提供基于行业板块数据的各类因子计算功能，包括：
- 行业动量因子
- 行业相对强度因子
- 行业估值因子
- 行业集中度因子
- 行业轮动因子
- 行业市值因子

主要功能：
- calculate_industry_momentum: 计算行业动量因子
- calculate_industry_relative_strength: 计算行业相对强度
- calculate_industry_pe_ratio: 计算行业市盈率
- calculate_industry_concentration: 计算行业集中度
- calculate_industry_momentum_rank: 计算行业动量排名
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Tuple
from datetime import datetime, timedelta
import warnings


class IndustryFactorCalculator:
    """
    行业因子计算器

    提供各类行业因子的计算功能，支持申万、中信、证监会等多种行业分类标准。
    """

    def __init__(
        self,
        industry_data: pd.DataFrame = None,
        price_data: pd.DataFrame = None,
        index_data: pd.DataFrame = None,
        industry_classification: str = "SW2021"
    ):
        """
        初始化行业因子计算器

        Args:
            industry_data: 行业分类数据
                         必需字段: [instrument, industry_code, industry_name, level]
            price_data: 股票价格数据
                       必需字段: [instrument, date, close, market_cap]
            index_data: 指数数据（用于计算相对强度）
                      必需字段: [date, close]
            industry_classification: 行业分类标准 (SW2021, ZJH, CITIC)
        """
        self.industry_data = industry_data
        self.price_data = price_data
        self.index_data = index_data
        self.industry_classification = industry_classification

        # 验证数据
        self._validate_data()

    def _validate_data(self) -> None:
        """验证输入数据的完整性"""
        if self.industry_data is not None:
            required_industry_cols = ['instrument', 'industry_code', 'industry_name']
            missing_cols = [col for col in required_industry_cols
                          if col not in self.industry_data.columns]
            if missing_cols:
                warnings.warn(f"行业数据缺少必需字段: {missing_cols}")

        if self.price_data is not None:
            required_price_cols = ['instrument', 'date', 'close']
            missing_cols = [col for col in required_price_cols
                          if col not in self.price_data.columns]
            if missing_cols:
                warnings.warn(f"价格数据缺少必需字段: {missing_cols}")

    def calculate_industry_momentum(
        self,
        window: int = 20,
        method: str = "return"
    ) -> pd.DataFrame:
        """
        计算行业动量因子

        行业动量 = 过去N日行业指数收益率

        Args:
            window: 时间窗口（天），默认20天
            method: 计算方法
                   - "return": 简单收益率
                   - "log_return": 对数收益率
                   - "volatility_adjusted": 波动率调整收益率

        Returns:
            行业动量因子DataFrame，包含：
            - date: 日期
            - industry_code: 行业代码
            - industry_name: 行业名称
            - momentum: 动量因子值
        """
        if self.price_data is None or self.price_data.empty:
            raise ValueError("价格数据为空，无法计算动量因子")

        # 确保有行业分类信息
        if self.industry_data is None or self.industry_data.empty:
            raise ValueError("行业数据为空，无法计算行业动量")

        # 合并价格数据和行业分类
        merged = pd.merge(
            self.price_data,
            self.industry_data[['instrument', 'industry_code', 'industry_name']],
            on='instrument',
            how='left'
        )

        # 按行业和日期分组计算行业平均收益率
        merged['return'] = merged.groupby('industry_code')['close'].pct_change()
        industry_returns = merged.groupby(['date', 'industry_code', 'industry_name'])['return'].mean().reset_index()

        # 计算滚动动量
        industry_returns = industry_returns.sort_values(['industry_code', 'date'])
        industry_returns['momentum'] = (
            industry_returns.groupby('industry_code')['return']
            .rolling(window=window, min_periods=1)
            .apply(lambda x: x.sum())
            .reset_index(level=0, drop=True)
        )

        # 特殊处理：对数收益率
        if method == "log_return":
            industry_returns['momentum'] = np.log1p(industry_returns['momentum'])
        elif method == "volatility_adjusted":
            # 计算波动率
            volatility = (
                industry_returns.groupby('industry_code')['return']
                .rolling(window=window, min_periods=1)
                .std()
                .reset_index(level=0, drop=True)
            )
            industry_returns['momentum'] = industry_returns['momentum'] / (volatility + 1e-6)

        return industry_returns[['date', 'industry_code', 'industry_name', 'momentum']].dropna()

    def calculate_industry_relative_strength(
        self,
        benchmark: str = "market",
        window: int = 20
    ) -> pd.DataFrame:
        """
        计算行业相对强度因子

        行业相对强度 = 行业收益率 / 基准收益率 - 1

        Args:
            benchmark: 基准类型
                      - "market": 市场平均
                      - "index": 指数（需要index_data）
                      - "industry_median": 行业中位数
            window: 时间窗口（天）

        Returns:
            行业相对强度DataFrame
        """
        # 先计算行业动量
        industry_momentum = self.calculate_industry_momentum(window=window)

        if benchmark == "market":
            # 计算市场平均收益率
            market_return = self.price_data.groupby('date')['close'].apply(
                lambda x: x.pct_change().mean()
            ).reset_index()
            market_return.columns = ['date', 'market_return']

            # 合并数据
            result = pd.merge(
                industry_momentum,
                market_return,
                on='date',
                how='left'
            )

            # 计算相对强度
            result['relative_strength'] = result['momentum'] / (result['market_return'] + 1e-6) - 1

        elif benchmark == "index":
            if self.index_data is None or self.index_data.empty:
                raise ValueError("使用指数基准需要提供index_data")

            # 计算指数收益率
            index_returns = self.index_data.set_index('date')['close'].pct_change()
            index_returns = index_returns.reset_index()
            index_returns.columns = ['date', 'index_return']

            # 合并数据
            result = pd.merge(
                industry_momentum,
                index_returns,
                on='date',
                how='left'
            )

            # 计算相对强度
            result['relative_strength'] = result['momentum'] / (result['index_return'] + 1e-6) - 1

        elif benchmark == "industry_median":
            # 计算行业中位数收益率
            industry_median = industry_momentum.groupby('date')['momentum'].median().reset_index()
            industry_median.columns = ['date', 'industry_median']

            # 合并数据
            result = pd.merge(
                industry_momentum,
                industry_median,
                on='date',
                how='left'
            )

            # 计算相对强度
            result['relative_strength'] = result['momentum'] / (result['industry_median'] + 1e-6) - 1

        else:
            raise ValueError(f"不支持的基准类型: {benchmark}")

        return result[['date', 'industry_code', 'industry_name', 'relative_strength']].dropna()

    def calculate_industry_concentration(
        self,
        holdings: pd.DataFrame,
        weights: Optional[pd.Series] = None
    ) -> pd.DataFrame:
        """
        计算行业集中度因子

        行业集中度 = Σ(股票在行业中权重²)

        Args:
            holdings: 持仓数据 DataFrame
                     必需字段: [instrument, date, weight（可选）]
            weights: 权重Series（可选），如果holdings中无weight列

        Returns:
            行业集中度DataFrame，包含：
            - date: 日期
            - industry_code: 行业代码
            - concentration: 集中度值（0-1之间，越接近1越集中）
        """
        if holdings is None or holdings.empty:
            raise ValueError("持仓数据为空")

        # 如果没有提供权重，假设等权重
        if 'weight' not in holdings.columns:
            if weights is None:
                holdings = holdings.copy()
                holdings['weight'] = 1.0 / len(holdings)
            else:
                holdings = holdings.copy()
                holdings['weight'] = weights

        # 合并行业分类
        merged = pd.merge(
            holdings,
            self.industry_data[['instrument', 'industry_code', 'industry_name']],
            on='instrument',
            how='left'
        )

        # 检查是否有date列
        has_date = 'date' in merged.columns

        if has_date:
            # 按日期和行业分组计算
            industry_weights = merged.groupby(['date', 'industry_code', 'industry_name'])['weight'].sum().reset_index()

            # 计算集中度（赫芬达尔指数）
            concentration = industry_weights.groupby(['date', 'industry_code', 'industry_name']).apply(
                lambda x: (x['weight'] ** 2).sum()
            ).reset_index()
            concentration.columns = ['date', 'industry_code', 'industry_name', 'concentration']
        else:
            # 不按日期分组，直接按行业计算
            industry_weights = merged.groupby(['industry_code', 'industry_name'])['weight'].sum().reset_index()

            # 计算集中度（赫芬达尔指数）
            concentration = industry_weights.groupby(['industry_code', 'industry_name']).apply(
                lambda x: (x['weight'] ** 2).sum()
            ).reset_index()
            concentration.columns = ['industry_code', 'industry_name', 'concentration']

        return concentration

    def calculate_industry_pe_ratio(
        self,
        fundamental_data: pd.DataFrame,
        method: str = "median"
    ) -> pd.DataFrame:
        """
        计算行业市盈率因子

        Args:
            fundamental_data: 基本面数据
                             必需字段: [instrument, date, pe（市盈率）]
            method: 计算方法
                    - "mean": 平均值
                    - "median": 中位数
                    - "weighted": 市值加权

        Returns:
            行业市盈率DataFrame
        """
        if fundamental_data is None or fundamental_data.empty:
            raise ValueError("基本面数据为空")

        # 合并行业分类
        merged = pd.merge(
            fundamental_data,
            self.industry_data[['instrument', 'industry_code', 'industry_name']],
            on='instrument',
            how='left'
        )

        # 计算行业市盈率
        if method == "mean":
            industry_pe = merged.groupby(['date', 'industry_code', 'industry_name'])['pe'].mean().reset_index()
        elif method == "median":
            industry_pe = merged.groupby(['date', 'industry_code', 'industry_name'])['pe'].median().reset_index()
        elif method == "weighted":
            if 'market_cap' not in merged.columns:
                raise ValueError("市值加权计算需要market_cap字段")

            # 计算权重
            merged['weight'] = merged.groupby(['date', 'industry_code'])['market_cap'].transform(
                lambda x: x / x.sum()
            )

            # 加权平均
            merged['weighted_pe'] = merged['pe'] * merged['weight']
            industry_pe = merged.groupby(['date', 'industry_code', 'industry_name'])['weighted_pe'].sum().reset_index()
            industry_pe.columns = ['date', 'industry_code', 'industry_name', 'pe']
        else:
            raise ValueError(f"不支持的计算方法: {method}")

        industry_pe.columns = ['date', 'industry_code', 'industry_name', 'industry_pe']

        return industry_pe.dropna()

    def calculate_industry_momentum_rank(
        self,
        window: int = 20,
        rank_method: str = "dense"
    ) -> pd.DataFrame:
        """
        计算行业动量排名因子

        Args:
            window: 时间窗口（天）
            rank_method: 排名方法
                        - "dense": 密集排名（相同值相同排名）
                        - "average": 平均排名
                        - "min": 最小排名
                        - "max": 最大排名

        Returns:
            行业动量排名DataFrame
        """
        # 计算行业动量
        momentum = self.calculate_industry_momentum(window=window)

        # 按日期排名
        momentum['rank'] = momentum.groupby('date')['momentum'].rank(
            method=rank_method,
            ascending=False
        )

        return momentum[['date', 'industry_code', 'industry_name', 'rank']].dropna()

    def calculate_industry_rotation(
        self,
        lookback: int = 5,
        threshold: float = 0.3
    ) -> pd.DataFrame:
        """
        计算行业轮动因子

        行业轮动 = 当期强势行业占比 - 上期强势行业占比

        Args:
            lookback: 回溯期数
            threshold: 强势行业判定阈值（排名前X%）

        Returns:
            行业轮动因子DataFrame
        """
        # 计算动量排名
        rank = self.calculate_industry_momentum_rank(window=20)

        # 判断强势行业（排名前30%）
        rank['is_strong'] = rank['rank'] <= rank['rank'].quantile(threshold)

        # 计算强势行业占比
        strong_ratio = rank.groupby('date')['is_strong'].mean().reset_index()
        strong_ratio.columns = ['date', 'strong_ratio']

        # 计算轮动（变化率）
        strong_ratio['rotation'] = strong_ratio['strong_ratio'].diff(lookback)

        return strong_ratio[['date', 'rotation']].dropna()

    def calculate_cross_industry_allocation(
        self,
        holdings: pd.DataFrame,
        benchmark: pd.DataFrame
    ) -> pd.DataFrame:
        """
        计算跨行业配置因子

        跨行业配置 = |组合行业配置 - 基准行业配置|

        Args:
            holdings: 组合持仓数据
            benchmark: 基准持仓数据

        Returns:
            跨行业配置偏离度DataFrame
        """
        # 计算组合行业配置
        portfolio_industry = self.calculate_industry_concentration(holdings)
        portfolio_allocation = portfolio_industry.groupby(['date', 'industry_code'])['concentration'].sum().reset_index()
        portfolio_allocation.columns = ['date', 'industry_code', 'portfolio_weight']

        # 计算基准行业配置
        benchmark_industry = self.calculate_industry_concentration(benchmark)
        benchmark_allocation = benchmark_industry.groupby(['date', 'industry_code'])['concentration'].sum().reset_index()
        benchmark_allocation.columns = ['date', 'industry_code', 'benchmark_weight']

        # 合并计算差异
        merged = pd.merge(
            portfolio_allocation,
            benchmark_allocation,
            on=['date', 'industry_code'],
            how='outer'
        ).fillna(0)

        # 计算绝对偏离度
        merged['deviation'] = abs(merged['portfolio_weight'] - merged['benchmark_weight'])

        # 汇总偏离度
        total_deviation = merged.groupby('date')['deviation'].sum().reset_index()
        total_deviation.columns = ['date', 'cross_industry_deviation']

        return total_deviation


def calculate_industry_exposure(
    stock_industry_map: pd.DataFrame,
    target_industries: List[str]
) -> pd.DataFrame:
    """
    计算股票对目标行业的暴露度

    Args:
        stock_industry_map: 股票行业映射 DataFrame
                           必需字段: [instrument, industry_code]
        target_industries: 目标行业代码列表

    Returns:
        行业暴露度DataFrame
    """
    # 创建目标行业集合
    target_set = set(target_industries)

    # 计算暴露度
    stock_industry_map['exposure'] = stock_industry_map['industry_code'].apply(
        lambda x: 1.0 if x in target_set else 0.0
    )

    return stock_industry_map[['instrument', 'industry_code', 'exposure']]


def normalize_industry_factors(
    factor_df: pd.DataFrame,
    method: str = "zscore",
    group_by: str = "date"
) -> pd.DataFrame:
    """
    标准化行业因子

    Args:
        factor_df: 因子DataFrame
        method: 标准化方法
                - "zscore": Z-score标准化
                - "minmax": Min-Max标准化
                - "rank": 排名标准化
        group_by: 分组字段

    Returns:
        标准化后的因子DataFrame
    """
    result = factor_df.copy()

    if method == "zscore":
        result['factor_norm'] = result.groupby(group_by)['momentum'].transform(
            lambda x: (x - x.mean()) / (x.std() + 1e-6)
        )
    elif method == "minmax":
        result['factor_norm'] = result.groupby(group_by)['momentum'].transform(
            lambda x: (x - x.min()) / (x.max() - x.min() + 1e-6)
        )
    elif method == "rank":
        result['factor_norm'] = result.groupby(group_by)['momentum'].rank(pct=True)
    else:
        raise ValueError(f"不支持的标准化方法: {method}")

    return result
