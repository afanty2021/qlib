#!/usr/bin/env python3
"""
行业轮动选股策略示例

演示如何使用行业板块数据构建基于行业轮动的选股策略
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# 添加qlib路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))


# ============================================================
# 行业因子计算类
# ============================================================

class IndustryMomentumFactor:
    """行业动量因子"""

    def __init__(self, price_data: pd.DataFrame, industry_map: Dict[str, str]):
        """
        初始化行业动量因子

        Args:
            price_data: 价格数据 (包含日期、股票代码、收盘价)
            industry_map: 股票到行业的映射
        """
        self.price_data = price_data
        self.industry_map = industry_map

    def calculate(
        self,
        window: int = 20,
        method: str = "return"
    ) -> pd.DataFrame:
        """
        计算行业动量因子

        Args:
            window: 时间窗口
            method: 计算方法 ("return"收益率, "std"波动率)

        Returns:
            行业动量因子DataFrame
        """
        # 将行业映射添加到价格数据
        df = self.price_data.copy()
        df['industry'] = df['stock_code'].map(self.industry_map)

        # 按日期和行业分组
        if method == "return":
            # 计算收益率
            df['return'] = df.groupby('stock_code')['close'].pct_change()
            # 行业平均收益率
            momentum = df.groupby(['date', 'industry'])['return'].mean().reset_index()
            momentum.columns = ['date', 'industry', 'momentum']

        elif method == "std":
            # 计算波动率
            volatility = df.groupby(['date', 'industry', 'stock_code'])['close'].transform(
                lambda x: x.pct_change().rolling(window).std()
            )
            df['volatility'] = volatility
            momentum = df.groupby(['date', 'industry'])['volatility'].mean().reset_index()
            momentum.columns = ['date', 'industry', 'momentum']

        else:
            raise ValueError(f"未知的计算方法: {method}")

        # 计算滚动动量
        momentum['momentum_ma'] = momentum.groupby('industry')['momentum'].transform(
            lambda x: x.rolling(window).mean()
        )

        print(f"✅ 计算行业动量因子: {len(momentum)} 条记录")

        return momentum


class IndustryRotationFactor:
    """行业轮动因子"""

    def __init__(self, momentum_data: pd.DataFrame):
        """
        初始化行业轮动因子

        Args:
            momentum_data: 行业动量数据
        """
        self.momentum_data = momentum_data

    def calculate(
        self,
        lookback: int = 5,
        threshold: float = 0.3
    ) -> pd.DataFrame:
        """
        计算行业轮动信号

        Args:
            lookback: 回看期间
            threshold: 轮动阈值

        Returns:
            行业轮动信号DataFrame
        """
        df = self.momentum_data.copy()

        # 计算动量变化
        df['momentum_change'] = df.groupby('industry')['momentum'].transform(
            lambda x: x.diff()
        )

        # 计算动量排名变化
        df['momentum_rank'] = df.groupby('date')['momentum'].rank(pct=True)
        df['rank_change'] = df.groupby('industry')['momentum_rank'].transform(
            lambda x: x.diff()
        )

        # 识别轮动信号
        df['rotation_signal'] = 0
        df.loc[df['momentum_change'] > threshold, 'rotation_signal'] = 1  # 强势
        df.loc[df['momentum_change'] < -threshold, 'rotation_signal'] = -1  # 弱势

        print(f"✅ 计算行业轮动因子: {len(df)} 条记录")

        return df


class IndustryValueFactor:
    """行业估值因子"""

    def __init__(self, valuation_data: pd.DataFrame, industry_map: Dict[str, str]):
        """
        初始化行业估值因子

        Args:
            valuation_data: 估值数据 (PE, PB等)
            industry_map: 股票到行业的映射
        """
        self.valuation_data = valuation_data
        self.industry_map = industry_map

    def calculate(
        self,
        metric: str = "pe",
        method: str = "median"
    ) -> pd.DataFrame:
        """
        计算行业估值因子

        Args:
            metric: 估值指标 ("pe", "pb", "ps")
            method: 统计方法 ("median", "mean")

        Returns:
            行业估值因子DataFrame
        """
        df = self.valuation_data.copy()
        df['industry'] = df['stock_code'].map(self.industry_map)

        # 过滤异常值
        df = df[df[metric] > 0]
        df = df[df[metric] < df[metric].quantile(0.99)]

        # 计算行业估值
        if method == "median":
            industry_valuation = df.groupby(['date', 'industry'])[metric].median().reset_index()
        else:
            industry_valuation = df.groupby(['date', 'industry'])[metric].mean().reset_index()

        industry_valuation.columns = ['date', 'industry', f'industry_{metric}']

        # 计算估值分位数
        industry_valuation[f'{metric}_percentile'] = industry_valuation.groupby('date')[
            f'industry_{metric}'
        ].rank(pct=True)

        print(f"✅ 计算行业估值因子: {len(industry_valuation)} 条记录")

        return industry_valuation


# ============================================================
# 选股策略类
# ============================================================

class IndustryRotationStrategy:
    """基于行业轮动的选股策略"""

    def __init__(
        self,
        price_data: pd.DataFrame,
        industry_map: Dict[str, str],
        valuation_data: pd.DataFrame = None
    ):
        """
        初始化行业轮动策略

        Args:
            price_data: 价格数据
            industry_map: 股票到行业的映射
            valuation_data: 估值数据 (可选)
        """
        self.price_data = price_data
        self.industry_map = industry_map
        self.valuation_data = valuation_data

        # 初始化因子计算器
        self.momentum_factor = IndustryMomentumFactor(price_data, industry_map)
        if valuation_data is not None:
            self.value_factor = IndustryValueFactor(valuation_data, industry_map)
        else:
            self.value_factor = None

    def select_stocks(
        self,
        date: str,
        top_industries: int = 3,
        stocks_per_industry: int = 5,
        momentum_window: int = 20
    ) -> List[str]:
        """
        选择股票

        Args:
            date: 选股日期
            top_industries: 选择行业数量
            stocks_per_industry: 每个行业选择股票数量
            momentum_window: 动量计算窗口

        Returns:
            选中股票列表
        """
        # 计算行业动量
        momentum_df = self.momentum_factor.calculate(window=momentum_window)

        # 获取指定日期的动量数据
        date_momentum = momentum_df[momentum_df['date'] == date]

        if len(date_momentum) == 0:
            print(f"⚠️ 日期 {date} 没有动量数据")
            return []

        # 选择动量最强的行业
        top_industries_df = date_momentum.nlargest(top_industries, 'momentum_ma')
        selected_industries = top_industries_df['industry'].tolist()

        print(f"✅ 选择强势行业: {selected_industries}")

        # 为每个行业选择股票
        selected_stocks = []

        # 添加行业映射到价格数据
        df = self.price_data.copy()
        df['industry'] = df['stock_code'].map(self.industry_map)

        for industry in selected_industries:
            # 获取该行业的股票
            industry_stocks = df[
                (df['date'] == date) & (df['industry'] == industry)
            ]['stock_code'].unique()

            # 计算这些股票的动量
            stock_momentum = []
            for stock in industry_stocks:
                stock_data = df[df['stock_code'] == stock].tail(momentum_window)
                if len(stock_data) >= momentum_window:
                    # 计算收益率
                    returns = stock_data['close'].pct_change().dropna()
                    momentum = returns.mean()
                    stock_momentum.append((stock, momentum))

            # 选择动量最强的股票
            if stock_momentum:
                stock_momentum.sort(key=lambda x: x[1], reverse=True)
                top_stocks = [s[0] for s in stock_momentum[:stocks_per_industry]]
                selected_stocks.extend(top_stocks)
                print(f"   {industry}: 选择 {len(top_stocks)} 只股票")

        return selected_stocks


class IndustryNeutralStrategy:
    """行业中性选股策略"""

    def __init__(
        self,
        price_data: pd.DataFrame,
        industry_map: Dict[str, str]
    ):
        """
        初始化行业中性策略

        Args:
            price_data: 价格数据
            industry_map: 股票到行业的映射
        """
        self.price_data = price_data
        self.industry_map = industry_map

    def select_stocks(
        self,
        date: str,
        stocks_per_industry: int = 2,
        score_column: str = "score"
    ) -> List[str]:
        """
        行业内选股（行业中性）

        Args:
            date: 选股日期
            stocks_per_industry: 每个行业选择股票数量
            score_column: 评分列名

        Returns:
            选中股票列表
        """
        # 添加行业映射
        df = self.price_data.copy()
        df['industry'] = df['stock_code'].map(self.industry_map)

        # 获取指定日期的数据
        date_data = df[df['date'] == date].copy()

        if len(date_data) == 0:
            print(f"⚠️ 日期 {date} 没有数据")
            return []

        # 在每个行业内选择股票
        selected_stocks = []

        for industry in date_data['industry'].unique():
            industry_data = date_data[date_data['industry'] == industry]

            if score_column in industry_data.columns:
                # 按评分选择
                top_stocks = industry_data.nlargest(stocks_per_industry, score_column)
            else:
                # 随机选择（示例）
                top_stocks = industry_data.sample(min(stocks_per_industry, len(industry_data)))

            selected_stocks.extend(top_stocks['stock_code'].tolist())

        print(f"✅ 行业中性选股: {len(selected_stocks)} 只股票，覆盖 {len(date_data['industry'].unique())} 个行业")

        return selected_stocks


# ============================================================
# 示例函数
# ============================================================

def generate_sample_data() -> Tuple[pd.DataFrame, Dict[str, str]]:
    """生成示例数据"""
    print("📊 生成示例数据...")

    # 示例股票列表
    stock_list = [f"{i:06d}.SZ" for i in range(1, 101)]

    # 生成日期范围
    dates = pd.date_range("2024-01-01", "2024-12-31", freq="D")

    # 生成价格数据
    price_data = []
    for stock in stock_list:
        for date in dates:
            price = 10 + np.random.randn() * 2  # 随机价格
            price_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'stock_code': stock,
                'close': price
            })

    price_df = pd.DataFrame(price_data)

    # 生成行业映射
    industries = ['银行', '地产', '医药', '科技', '消费', '制造', '金融', '能源']
    industry_map = {stock: np.random.choice(industries) for stock in stock_list}

    print(f"   生成 {len(price_df)} 条价格数据")
    print(f"   {len(stock_list)} 只股票，{len(industries)} 个行业")

    return price_df, industry_map


def example_1_industry_momentum():
    """示例1: 行业动量策略"""
    print("\n" + "="*80)
    print("示例1: 行业动量策略")
    print("="*80)

    # 生成示例数据
    price_data, industry_map = generate_sample_data()

    # 创建策略
    strategy = IndustryRotationStrategy(price_data, industry_map)

    # 执行选股
    selected_stocks = strategy.select_stocks(
        date="2024-12-31",
        top_industries=3,
        stocks_per_industry=5,
        momentum_window=20
    )

    print(f"\n✅ 选中的股票: {len(selected_stocks)} 只")
    print(selected_stocks[:10])  # 显示前10只


def example_2_industry_neutral():
    """示例2: 行业中性策略"""
    print("\n" + "="*80)
    print("示例2: 行业中性策略")
    print("="*80)

    # 生成示例数据
    price_data, industry_map = generate_sample_data()

    # 添加随机评分
    price_data['score'] = np.random.randn(len(price_data))

    # 创建策略
    strategy = IndustryNeutralStrategy(price_data, industry_map)

    # 执行选股
    selected_stocks = strategy.select_stocks(
        date="2024-12-31",
        stocks_per_industry=2,
        score_column="score"
    )

    print(f"\n✅ 选中的股票: {len(selected_stocks)} 只")
    print(selected_stocks[:10])  # 显示前10只


def example_3_momentum_factors():
    """示例3: 计算行业动量因子"""
    print("\n" + "="*80)
    print("示例3: 计算行业动量因子")
    print("="*80)

    # 生成示例数据
    price_data, industry_map = generate_sample_data()

    # 计算动量因子
    momentum_factor = IndustryMomentumFactor(price_data, industry_map)

    # 收益率动量
    print("\n📊 计算收益率动量...")
    return_momentum = momentum_factor.calculate(window=20, method="return")
    print(return_momentum.head(10))

    # 波动率动量
    print("\n📊 计算波动率动量...")
    volatility_momentum = momentum_factor.calculate(window=20, method="std")
    print(volatility_momentum.head(10))


# ============================================================
# 主函数
# ============================================================

def main():
    """主函数 - 运行所有示例"""
    print("\n🎯 行业轮动选股策略示例")
    print("="*80)
    print("本示例演示如何使用行业数据构建选股策略")
    print("="*80)

    try:
        # 示例1: 行业动量策略
        example_1_industry_momentum()

        # 示例2: 行业中性策略
        example_2_industry_neutral()

        # 示例3: 计算行业动量因子
        example_3_momentum_factors()

        print("\n" + "="*80)
        print("✅ 所有示例运行完成！")
        print("="*80)

        print("\n💡 使用建议:")
        print("   1. 使用真实的价格数据和行业映射")
        print("   2. 结合多个因子进行综合评分")
        print("   3. 添加风险控制和仓位管理")
        print("   4. 进行回测验证策略效果")
        print("   5. 定期优化策略参数")

        print("\n📝 后续步骤:")
        print("   1. 集成风险管理模块")
        print("   2. 添加回测框架")
        print("   3. 实现业绩归因分析")

    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
