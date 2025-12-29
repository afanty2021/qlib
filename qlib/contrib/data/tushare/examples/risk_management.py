#!/usr/bin/env python3
"""
行业风险管理示例

演示如何使用行业数据进行风险控制和投资组合管理
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
# 行业风险分析类
# ============================================================

class IndustryConcentrationRisk:
    """行业集中度风险控制"""

    def __init__(self, max_industry_weight: float = 0.3):
        """
        初始化行业集中度风险控制

        Args:
            max_industry_weight: 单个行业最大权重
        """
        self.max_industry_weight = max_industry_weight

    def calculate_concentration(
        self,
        holdings: pd.DataFrame,
        industry_map: Dict[str, str]
    ) -> pd.DataFrame:
        """
        计算行业集中度

        Args:
            holdings: 持仓数据 (stock_code, weight)
            industry_map: 股票到行业的映射

        Returns:
            行业集中度DataFrame
        """
        df = holdings.copy()
        df['industry'] = df['stock_code'].map(industry_map)

        # 计算行业权重
        industry_weights = df.groupby('industry')['weight'].sum().reset_index()
        industry_weights.columns = ['industry', 'weight']
        industry_weights = industry_weights.sort_values('weight', ascending=False)

        # 计算集中度指标
        total_weight = industry_weights['weight'].sum()
        industry_weights['weight_pct'] = industry_weights['weight'] / total_weight

        # 累计权重（用于计算基尼系数）
        industry_weights['cumsum_weight'] = industry_weights['weight_pct'].cumsum()

        # 计算HHI (Herfindahl-Hirschman Index)
        hhi = (industry_weights['weight_pct'] ** 2).sum()

        # 计算前N大行业权重
        top1_weight = industry_weights.iloc[0]['weight_pct'] if len(industry_weights) > 0 else 0
        top3_weight = industry_weights.head(3)['weight_pct'].sum()
        top5_weight = industry_weights.head(5)['weight_pct'].sum()

        metrics = {
            'hhi': hhi,
            'top1_weight': top1_weight,
            'top3_weight': top3_weight,
            'top5_weight': top5_weight
        }

        print(f"✅ 计算行业集中度:")
        print(f"   HHI: {hhi:.4f}")
        print(f"   前1大行业权重: {top1_weight:.2%}")
        print(f"   前3大行业权重: {top3_weight:.2%}")
        print(f"   前5大行业权重: {top5_weight:.2%}")

        return industry_weights, metrics

    def check_concentration(
        self,
        holdings: pd.DataFrame,
        industry_map: Dict[str, str]
    ) -> Tuple[bool, List[str]]:
        """
        检查行业集中度是否超限

        Args:
            holdings: 持仓数据
            industry_map: 股票到行业的映射

        Returns:
            (是否通过, 警告信息列表)
        """
        industry_weights, metrics = self.calculate_concentration(holdings, industry_map)

        warnings = []

        # 检查单行业权重
        overweight_industries = industry_weights[
            industry_weights['weight_pct'] > self.max_industry_weight
        ]

        if len(overweight_industries) > 0:
            passed = False
            for _, row in overweight_industries.iterrows():
                warnings.append(
                    f"⚠️ 行业 {row['industry']} 权重 {row['weight_pct']:.2%} "
                    f"超过限制 {self.max_industry_weight:.2%}"
                )
        else:
            passed = True
            warnings.append("✅ 所有行业权重在限制范围内")

        return passed, warnings

    def adjust_portfolio(
        self,
        holdings: pd.DataFrame,
        industry_map: Dict[str, str],
        method: str = "capping"
    ) -> pd.DataFrame:
        """
        调整投资组合以控制行业集中度

        Args:
            holdings: 原始持仓
            industry_map: 行业映射
            method: 调整方法 ("capping"封顶, "equal_weight"等权重)

        Returns:
            调整后的持仓
        """
        df = holdings.copy()
        df['industry'] = df['stock_code'].map(industry_map)

        if method == "capping":
            # 方法1: 权重封顶
            while True:
                industry_weights, _ = self.calculate_concentration(df, industry_map)
                overweight = industry_weights[
                    industry_weights['weight_pct'] > self.max_industry_weight
                ]

                if len(overweight) == 0:
                    break

                # 对超限行业按比例缩减
                for _, row in overweight.iterrows():
                    industry = row['industry']
                    current_weight = row['weight_pct']
                    scale_factor = self.max_industry_weight / current_weight

                    # 缩减该行业所有股票权重
                    mask = df['industry'] == industry
                    df.loc[mask, 'weight'] *= scale_factor

            # 重新归一化
            df['weight'] = df['weight'] / df['weight'].sum()

        elif method == "equal_weight":
            # 方法2: 行业内等权重
            industry_weights = {}
            for industry in df['industry'].unique():
                industry_stocks = df[df['industry'] == industry]
                equal_weight = 1.0 / len(industry_stocks)
                df.loc[df['industry'] == industry, 'weight'] = equal_weight

        print(f"✅ 调整投资组合，方法: {method}")

        return df


class IndustryExposureAnalysis:
    """行业暴露分析"""

    def __init__(self):
        """初始化行业暴露分析"""
        pass

    def calculate_exposure(
        self,
        portfolio: pd.DataFrame,
        benchmark: pd.DataFrame,
        industry_map: Dict[str, str]
    ) -> pd.DataFrame:
        """
        计算相对基准的行业暴露

        Args:
            portfolio: 投资组合持仓
            benchmark: 基准持仓
            industry_map: 行业映射

        Returns:
            行业暴露DataFrame
        """
        # 计算组合行业权重
        portfolio_df = portfolio.copy()
        portfolio_df['industry'] = portfolio_df['stock_code'].map(industry_map)
        portfolio_weights = portfolio_df.groupby('industry')['weight'].sum().reset_index()
        portfolio_weights.columns = ['industry', 'portfolio_weight']

        # 计算基准行业权重
        benchmark_df = benchmark.copy()
        benchmark_df['industry'] = benchmark_df['stock_code'].map(industry_map)
        benchmark_weights = benchmark_df.groupby('industry')['weight'].sum().reset_index()
        benchmark_weights.columns = ['industry', 'benchmark_weight']

        # 合并
        exposure = pd.merge(
            portfolio_weights,
            benchmark_weights,
            on='industry',
            how='outer'
        ).fillna(0)

        # 计算超低配
        exposure['active_weight'] = exposure['portfolio_weight'] - exposure['benchmark_weight']

        # 按超配排序
        exposure = exposure.sort_values('active_weight', ascending=False)

        print(f"✅ 计算行业暴露: {len(exposure)} 个行业")

        return exposure

    def analyze_risk_factors(
        self,
        exposure: pd.DataFrame
    ) -> Dict[str, float]:
        """
        分析风险因子

        Args:
            exposure: 行业暴露数据

        Returns:
            风险指标字典
        """
        # 绝对偏离度
        abs_deviation = exposure['active_weight'].abs().sum()

        # 跟踪误差（简化版）
        tracking_error = np.sqrt((exposure['active_weight'] ** 2).sum())

        # 最大超配
        max_overweight = exposure['active_weight'].max()

        # 最大低配
        max_underweight = exposure['active_weight'].min()

        # 超配行业数
        overweight_count = len(exposure[exposure['active_weight'] > 0])

        # 低配行业数
        underweight_count = len(exposure[exposure['active_weight'] < 0])

        risk_metrics = {
            'absolute_deviation': abs_deviation,
            'tracking_error': tracking_error,
            'max_overweight': max_overweight,
            'max_underweight': max_underweight,
            'overweight_count': overweight_count,
            'underweight_count': underweight_count
        }

        print(f"✅ 分析风险因子:")
        for key, value in risk_metrics.items():
            print(f"   {key}: {value:.4f}")

        return risk_metrics


class IndustryStressTest:
    """行业压力测试"""

    def __init__(self):
        """初始化压力测试"""
        pass

    def scenario_analysis(
        self,
        holdings: pd.DataFrame,
        industry_map: Dict[str, str],
        scenarios: Dict[str, Dict[str, float]]
    ) -> pd.DataFrame:
        """
        情景分析

        Args:
            holdings: 持仓数据
            industry_map: 行业映射
            scenarios: 情景定义
                例如: {
                    "牛市": {"银行": 0.10, "地产": 0.15},
                    "熊市": {"银行": -0.08, "地产": -0.12}
                }

        Returns:
            情景分析结果
        """
        df = holdings.copy()
        df['industry'] = df['stock_code'].map(industry_map)

        results = []

        for scenario_name, scenario_shocks in scenarios.items():
            # 计算组合在情景下的收益
            scenario_return = 0.0

            for industry, shock in scenario_shocks.items():
                industry_weight = df[df['industry'] == industry]['weight'].sum()
                scenario_return += industry_weight * shock

            results.append({
                'scenario': scenario_name,
                'return': scenario_return
            })

        result_df = pd.DataFrame(results)

        print(f"✅ 情景分析: {len(scenarios)} 个情景")

        return result_df

    def calculate_var(
        self,
        holdings: pd.DataFrame,
        industry_returns: pd.DataFrame,
        confidence: float = 0.95
    ) -> float:
        """
        计算行业VaR (Value at Risk)

        Args:
            holdings: 持仓数据
            industry_returns: 行业收益率历史数据
            confidence: 置信水平

        Returns:
            VaR值
        """
        df = holdings.copy()
        df['industry'] = df['stock_code'].map(industry_map)

        # 计算组合在各行业的权重
        industry_weights = df.groupby('industry')['weight'].sum().reset_index()
        industry_weights.columns = ['industry', 'weight']

        # 计算历史收益率
        portfolio_returns = []

        for _, row in industry_returns.iterrows():
            daily_return = 0.0
            for _, industry_w in industry_weights.iterrows():
                industry = industry_w['industry']
                weight = industry_w['weight']
                if industry in row:
                    daily_return += weight * row[industry]
            portfolio_returns.append(daily_return)

        portfolio_returns = pd.Series(portfolio_returns)

        # 计算VaR
        var = portfolio_returns.quantile(1 - confidence)

        print(f"✅ 计算 VaR ({confidence*100:.0f}%): {var:.2%}")

        return var


# ============================================================
# 示例函数
# ============================================================

def generate_sample_portfolio() -> Tuple[pd.DataFrame, Dict[str, str]]:
    """生成示例投资组合"""
    print("📊 生成示例投资组合...")

    # 示例股票
    stock_list = [f"{i:06d}.SZ" for i in range(1, 51)]

    # 生成持仓
    holdings = []
    remaining_weight = 1.0

    for i, stock in enumerate(stock_list):
        weight = remaining_weight * (0.5 ** (i + 1))  # 递减权重
        holdings.append({
            'stock_code': stock,
            'weight': weight
        })
        remaining_weight -= weight
        if remaining_weight <= 0:
            break

    holdings_df = pd.DataFrame(holdings)

    # 归一化
    holdings_df['weight'] = holdings_df['weight'] / holdings_df['weight'].sum()

    # 行业映射
    industries = ['银行', '地产', '医药', '科技', '消费', '制造', '金融', '能源']
    industry_map = {stock: np.random.choice(industries) for stock in stock_list}

    print(f"   生成 {len(holdings_df)} 只股票的组合")

    return holdings_df, industry_map


def example_1_concentration_check():
    """示例1: 行业集中度检查"""
    print("\n" + "="*80)
    print("示例1: 行业集中度检查")
    print("="*80)

    # 生成示例组合
    holdings, industry_map = generate_sample_portfolio()

    # 创建风险控制对象
    risk_control = IndustryConcentrationRisk(max_industry_weight=0.3)

    # 检查集中度
    print("\n📊 检查行业集中度...")
    passed, warnings = risk_control.check_concentration(holdings, industry_map)

    for warning in warnings:
        print(warning)

    # 显示行业权重
    industry_weights, metrics = risk_control.calculate_concentration(holdings, industry_map)
    print("\n行业权重分布:")
    print(industry_weights.head(10).to_string(index=False))


def example_2_portfolio_adjustment():
    """示例2: 投资组合调整"""
    print("\n" + "="*80)
    print("示例2: 投资组合调整")
    print("="*80)

    # 生成示例组合
    holdings, industry_map = generate_sample_portfolio()

    # 创建风险控制对象
    risk_control = IndustryConcentrationRisk(max_industry_weight=0.2)

    # 调整组合
    print("\n📊 调整投资组合...")
    adjusted_holdings = risk_control.adjust_portfolio(
        holdings,
        industry_map,
        method="capping"
    )

    # 再次检查
    print("\n📊 调整后检查...")
    passed, warnings = risk_control.check_concentration(adjusted_holdings, industry_map)

    for warning in warnings:
        print(warning)


def example_3_exposure_analysis():
    """示例3: 行业暴露分析"""
    print("\n" + "="*80)
    print("示例3: 行业暴露分析")
    print("="*80)

    # 生成组合和基准
    portfolio, industry_map = generate_sample_portfolio()
    benchmark, _ = generate_sample_portfolio()

    # 创建暴露分析对象
    exposure_analysis = IndustryExposureAnalysis()

    # 计算暴露
    print("\n📊 计算相对基准的行业暴露...")
    exposure = exposure_analysis.calculate_exposure(portfolio, benchmark, industry_map)

    print("\n行业暴露 (前10个):")
    print(exposure.head(10).to_string(index=False))

    # 分析风险因子
    print("\n📊 分析风险因子...")
    risk_metrics = exposure_analysis.analyze_risk_factors(exposure)


def example_4_stress_test():
    """示例4: 压力测试"""
    print("\n" + "="*80)
    print("示例4: 压力测试")
    print("="*80)

    # 生成组合
    holdings, industry_map = generate_sample_portfolio()

    # 创建压力测试对象
    stress_test = IndustryStressTest()

    # 定义情景
    scenarios = {
        "牛市": {
            "银行": 0.10, "地产": 0.15, "科技": 0.20,
            "医药": 0.08, "消费": 0.12, "制造": 0.10
        },
        "熊市": {
            "银行": -0.08, "地产": -0.12, "科技": -0.15,
            "医药": -0.05, "消费": -0.07, "制造": -0.08
        },
        "行业轮动(科技强)": {
            "科技": 0.25, "银行": -0.05, "地产": -0.05,
            "医药": 0.10, "消费": 0.05
        }
    }

    # 执行情景分析
    print("\n📊 执行情景分析...")
    results = stress_test.scenario_analysis(holdings, industry_map, scenarios)

    print("\n情景分析结果:")
    print(results.to_string(index=False))


# ============================================================
# 主函数
# ============================================================

def main():
    """主函数 - 运行所有示例"""
    print("\n🎯 行业风险管理示例")
    print("="*80)
    print("本示例演示如何使用行业数据进行风险控制")
    print("="*80)

    try:
        # 示例1: 行业集中度检查
        example_1_concentration_check()

        # 示例2: 投资组合调整
        example_2_portfolio_adjustment()

        # 示例3: 行业暴露分析
        example_3_exposure_analysis()

        # 示例4: 压力测试
        example_4_stress_test()

        print("\n" + "="*80)
        print("✅ 所有示例运行完成！")
        print("="*80)

        print("\n💡 使用建议:")
        print("   1. 根据实际风险偏好设置集中度限制")
        print("   2. 定期监控行业暴露度")
        print("   3. 设计多种压力情景进行测试")
        print("   4. 结合市场环境调整风险控制参数")

        print("\n📝 风险管理最佳实践:")
        print("   1. 设置单行业权重上限 (如30%)")
        print("   2. 控制前N大行业总权重")
        print("   3. 定期进行压力测试")
        print("   4. 监控相对基准的偏离度")
        print("   5. 建立风险预警机制")

    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
