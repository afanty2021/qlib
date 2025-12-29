"""
行业板块数据使用示例

演示如何使用TuShare数据源的行业板块功能，包括：
1. 获取行业分类数据
2. 计算行业动量因子
3. 计算行业相对强度
4. 分析行业轮动
5. 构建行业暴露度因子

使用前准备：
- 确保已设置TUSHARE_TOKEN环境变量
- 或在代码中直接配置token
"""

import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

# 导入Qlib和TuShare相关模块
try:
    from qlib import init
    from qlib.data import D
    from qlib.contrib.data.tushare import (
        TuShareConfig,
        TuShareProvider,
        TuShareAPIClient
    )
    from qlib.contrib.data.tushare.industry_factors import (
        IndustryFactorCalculator,
        calculate_industry_exposure,
        normalize_industry_factors
    )
    QLIB_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Qlib未安装: {e}")
    print("请先安装Qlib: pip install pyqlib")
    QLIB_AVAILABLE = False


def example_1_get_industry_classification():
    """
    示例1：获取行业分类数据
    """
    print("\n" + "="*80)
    print("示例1：获取行业分类数据")
    print("="*80)

    if not QLIB_AVAILABLE:
        return

    try:
        # 初始化配置
        config = TuShareConfig.from_env()

        # 创建数据提供者
        with TuShareProvider(config) as provider:

            # 获取申万2021一级行业分类
            print("\n📊 获取申万2021一级行业分类...")
            industry_l1 = provider.get_industry_classification(src="SW2021", level="L1")

            if not industry_l1.empty:
                print(f"✅ 成功获取 {len(industry_l1)} 个一级行业")
                print("\n行业列表（前10个）：")
                print(industry_l1.head(10).to_string(index=False))

                # 统计分析
                print(f"\n📈 行业分类统计：")
                print(f"- 一级行业总数：{len(industry_l1)}")

            # 获取申万2021二级行业分类
            print("\n📊 获取申万2021二级行业分类...")
            industry_l2 = provider.get_industry_classification(src="SW2021", level="L2")

            if not industry_l2.empty:
                print(f"✅ 成功获取 {len(industry_l2)} 个二级行业")
                print("\n二级行业列表（前10个）：")
                print(industry_l2.head(10).to_string(index=False))

                # 统计分析
                print(f"\n📈 行业分类统计：")
                print(f"- 二级行业总数：{len(industry_l2)}")

    except Exception as e:
        print(f"❌ 获取行业分类失败: {e}")


def example_2_calculate_industry_momentum():
    """
    示例2：计算行业动量因子
    """
    print("\n" + "="*80)
    print("示例2：计算行业动量因子")
    print("="*80)

    if not QLIB_AVAILABLE:
        return

    try:
        # 初始化配置
        config = TuShareConfig.from_env()

        # 创建数据提供者
        with TuShareProvider(config) as provider:

            # 获取沪深300成分股
            print("\n📊 获取沪深300成分股...")
            instruments = D.instruments('csi300')
            print(f"✅ 获取 {len(instruments)} 只股票")

            # 获取最近3个月的数据
            from datetime import datetime, timedelta
            end_time = datetime.now()
            start_time = end_time - timedelta(days=90)

            # 计算行业动量因子
            print(f"\n📈 计算行业动量因子（{start_time.date()} 到 {end_time.date()}）...")
            momentum_df = provider.get_industry_factors(
                instruments=list(instruments)[:50],  # 限制数量加快演示
                factor_type="momentum",
                start_time=start_time.strftime("%Y-%m-%d"),
                end_time=end_time.strftime("%Y-%m-%d"),
                window=20,
                method="return"
            )

            if not momentum_df.empty:
                print(f"✅ 成功计算行业动量因子")
                print("\n最新行业动量排名（Top 10）：")

                # 获取最新一期的数据
                latest_momentum = momentum_df.groupby('industry_code').last().reset_index()
                latest_momentum = latest_momentum.sort_values('momentum', ascending=False)

                print(latest_momentum.head(10)[['industry_name', 'momentum']].to_string(index=False))

                # 可视化（可选）
                try:
                    plt.figure(figsize=(12, 6))
                    top_industries = latest_momentum.head(10)
                    plt.barh(top_industries['industry_name'], top_industries['momentum'])
                    plt.xlabel('动量值')
                    plt.ylabel('行业')
                    plt.title('行业动量因子排名（Top 10）')
                    plt.tight_layout()
                    plt.savefig('industry_momentum.png', dpi=100, bbox_inches='tight')
                    print(f"\n📊 图表已保存：industry_momentum.png")
                except Exception as plot_err:
                    print(f"\n⚠️ 图表生成失败: {plot_err}")

    except Exception as e:
        print(f"❌ 计算行业动量失败: {e}")


def example_3_calculate_relative_strength():
    """
    示例3：计算行业相对强度
    """
    print("\n" + "="*80)
    print("示例3：计算行业相对强度")
    print("="*80)

    if not QLIB_AVAILABLE:
        return

    try:
        # 初始化配置
        config = TuShareConfig.from_env()

        # 创建数据提供者
        with TuShareProvider(config) as provider:

            # 获取中证500成分股
            print("\n📊 获取中证500成分股...")
            instruments = D.instruments('csi500')
            print(f"✅ 获取 {len(instruments)} 只股票")

            # 计算行业相对强度
            from datetime import datetime, timedelta
            end_time = datetime.now()
            start_time = end_time - timedelta(days=60)

            print(f"\n📈 计算行业相对强度（相对市场基准）...")
            relative_strength_df = provider.get_industry_factors(
                instruments=list(instruments)[:50],
                factor_type="relative_strength",
                start_time=start_time.strftime("%Y-%m-%d"),
                end_time=end_time.strftime("%Y-%m-%d"),
                benchmark="market",
                window=20
            )

            if not relative_strength_df.empty:
                print(f"✅ 成功计算行业相对强度")
                print("\n最新行业相对强度排名（Top 10）：")

                # 获取最新一期的数据
                latest_rs = relative_strength_df.groupby('industry_code').last().reset_index()
                latest_rs = latest_rs.sort_values('relative_strength', ascending=False)

                print(latest_rs.head(10)[['industry_name', 'relative_strength']].to_string(index=False))

                # 分析
                print(f"\n📊 相对强度统计：")
                print(f"- 强势行业（相对强度>0）：{len(latest_rs[latest_rs['relative_strength'] > 0])}")
                print(f"- 弱势行业（相对强度<0）：{len(latest_rs[latest_rs['relative_strength'] < 0])}")
                print(f"- 平均相对强度：{latest_rs['relative_strength'].mean():.4f}")

    except Exception as e:
        print(f"❌ 计算相对强度失败: {e}")


def example_4_industry_rotation_analysis():
    """
    示例4：行业轮动分析
    """
    print("\n" + "="*80)
    print("示例4：行业轮动分析")
    print("="*80)

    if not QLIB_AVAILABLE:
        return

    try:
        # 初始化配置
        config = TuShareConfig.from_env()

        # 创建数据提供者
        with TuShareProvider(config) as provider:

            # 获取数据
            from datetime import datetime, timedelta
            end_time = datetime.now()
            start_time = end_time - timedelta(days=120)

            print(f"\n📊 获取行业数据（{start_time.date()} 到 {end_time.date()}）...")

            # 获取行业分类
            industry_data = provider.get_industry_classification(src="SW2021", level="L1")

            # 获取价格数据
            instruments = D.instruments('csi300')
            price_df = provider.features(
                instruments=list(instruments)[:100],
                fields=["close", "volume"],
                start_time=start_time.strftime("%Y-%m-%d"),
                end_time=end_time.strftime("%Y-%m-%d"),
                freq="day"
            )

            if price_df.empty:
                print("⚠️ 价格数据为空")
                return

            # 转换格式
            price_df_reset = price_df.reset_index()
            price_df_reset.columns = ['instrument', 'date', 'close', 'volume']

            # 创建因子计算器
            calculator = IndustryFactorCalculator(
                industry_data=industry_data,
                price_data=price_df_reset,
                industry_classification="SW2021"
            )

            # 计算行业轮动
            print("\n📈 计算行业轮动因子...")
            rotation_df = calculator.calculate_industry_rotation(
                lookback=5,
                threshold=0.3
            )

            if not rotation_df.empty:
                print(f"✅ 成功计算行业轮动因子")
                print("\n行业轮动情况（最近10期）：")
                print(rotation_df.tail(10).to_string(index=False))

                # 分析
                print(f"\n📊 轮动统计：")
                print(f"- 轮动均值：{rotation_df['rotation'].mean():.4f}")
                print(f"- 轮动标准差：{rotation_df['rotation'].std():.4f}")
                print(f"- 最大轮动：{rotation_df['rotation'].max():.4f}")
                print(f"- 最小轮动：{rotation_df['rotation'].min():.4f}")

                # 判断轮动强度
                latest_rotation = rotation_df['rotation'].iloc[-1]
                if latest_rotation > 0.05:
                    print(f"\n🔥 当前轮动强度：高（{latest_rotation:.4f}）")
                    print("   建议：关注行业轮动策略")
                elif latest_rotation > 0:
                    print(f"\n⚖️ 当前轮动强度：中（{latest_rotation:.4f}）")
                    print("   建议：均衡配置")
                else:
                    print(f"\n❄️ 当前轮动强度：低（{latest_rotation:.4f}）")
                    print("   建议：坚守主线")

    except Exception as e:
        print(f"❌ 行业轮动分析失败: {e}")


def example_5_industry_exposure():
    """
    示例5：计算行业暴露度
    """
    print("\n" + "="*80)
    print("示例5：计算行业暴露度")
    print("="*80)

    if not QLIB_AVAILABLE:
        return

    try:
        # 初始化配置
        config = TuShareConfig.from_env()

        # 创建数据提供者
        with TuShareProvider(config) as provider:

            # 获取行业分类
            print("\n📊 获取行业分类...")
            industry_data = provider.get_industry_classification(src="SW2021", level="L1")

            if industry_data.empty:
                print("⚠️ 行业数据为空")
                return

            # 模拟持仓数据（实际使用时替换为真实持仓）
            print("\n📊 模拟持仓数据...")
            mock_holdings = pd.DataFrame({
                'instrument': [f"SH{i:06d}" for i in range(600000, 600010, 1)],
                'weight': [0.1] * 10
            })

            print("持仓股票：")
            print(mock_holdings.to_string(index=False))

            # 选择目标行业（示例：科技类行业）
            target_industries = ['电气设备', '电子', '计算机', '通信']

            print(f"\n🎯 目标行业：{', '.join(target_industries)}")

            # 计算行业暴露度
            print("\n📈 计算行业暴露度...")
            exposure_df = calculate_industry_exposure(
                industry_data,
                target_industries
            )

            if not exposure_df.empty:
                print(f"✅ 成功计算行业暴露度")
                print("\n行业暴露度详情：")
                print(exposure_df.head(10).to_string(index=False))

                # 计算组合总暴露度
                total_exposure = exposure_df['exposure'].mean()
                print(f"\n📊 组合对目标行业的暴露度：{total_exposure:.2%}")

                if total_exposure > 0.5:
                    print("⚠️ 高暴露：组合对目标行业暴露度较高")
                elif total_exposure > 0.2:
                    print("✅ 适中暴露：组合对目标行业暴露度适中")
                else:
                    print("💡 低暴露：组合对目标行业暴露度较低")

    except Exception as e:
        print(f"❌ 计算行业暴露度失败: {e}")


def example_6_features_with_industry():
    """
    示例6：获取包含行业信息的特征数据
    """
    print("\n" + "="*80)
    print("示例6：获取包含行业信息的特征数据")
    print("="*80)

    if not QLIB_AVAILABLE:
        return

    try:
        # 初始化配置
        config = TuShareConfig.from_env()

        # 创建数据提供者
        with TuShareProvider(config) as provider:

            # 获取股票列表
            print("\n📊 获取股票列表...")
            instruments = D.instruments('csi100')[:20]  # 取前20只
            print(f"✅ 获取 {len(instruments)} 只股票")

            # 获取包含行业信息的特征数据
            from datetime import datetime, timedelta
            end_time = datetime.now()
            start_time = end_time - timedelta(days=30)

            print(f"\n📈 获取特征数据（包含行业信息）...")

            features_with_industry = provider.features_with_industry(
                instruments=instruments,
                fields=["close", "volume"],
                start_time=start_time.strftime("%Y-%m-%d"),
                end_time=end_time.strftime("%Y-%m-%d"),
                freq="day",
                include_industry=True
            )

            if not features_with_industry.empty:
                print(f"✅ 成功获取特征数据")
                print(f"数据形状：{features_with_industry.shape}")

                # 显示行业分布
                if 'industry' in features_with_industry.columns:
                    print("\n📊 行业分布：")
                    industry_dist = features_with_industry['industry'].value_counts()
                    print(industry_dist.head(10))

                # 显示数据样例
                print("\n📋 数据样例（前5行）：")
                print(features_with_industry.head())

    except Exception as e:
        print(f"❌ 获取特征数据失败: {e}")


def run_all_examples():
    """
    运行所有示例
    """
    print("\n" + "="*80)
    print("TuShare 行业板块数据使用示例")
    print("="*80)

    # 检查环境
    if not QLIB_AVAILABLE:
        print("\n❌ Qlib未安装，请先安装：pip install pyqlib")
        return

    # 检查Token
    import os
    if not os.getenv("TUSHARE_TOKEN"):
        print("\n⚠️ 未设置TUSHARE_TOKEN环境变量")
        print("请设置：export TUSHARE_TOKEN='your_token_here'")
        print("或在代码中配置：config = TuShareConfig(token='your_token')")
        return

    print("\n✅ 环境检查通过")
    print(f"Token: {os.getenv('TUSHARE_TOKEN')[:10]}...")

    # 运行示例
    examples = [
        ("获取行业分类", example_1_get_industry_classification),
        ("计算行业动量", example_2_calculate_industry_momentum),
        ("计算相对强度", example_3_calculate_relative_strength),
        ("行业轮动分析", example_4_industry_rotation_analysis),
        ("计算行业暴露度", example_5_industry_exposure),
        ("行业特征数据", example_6_features_with_industry),
    ]

    print("\n请选择要运行的示例（输入数字，多个示例用空格分隔）：")
    print("0. 运行所有示例")
    for i, (name, _) in enumerate(examples, 1):
        print(f"{i}. {name}")

    try:
        choice = input("\n请选择：").strip()

        if choice == "0":
            # 运行所有示例
            for name, func in examples:
                try:
                    func()
                except Exception as e:
                    print(f"❌ 示例执行失败（{name}）：{e}")
        else:
            # 运行选定示例
            indices = [int(x) for x in choice.split()]
            for idx in indices:
                if 1 <= idx <= len(examples):
                    name, func = examples[idx - 1]
                    try:
                        func()
                    except Exception as e:
                        print(f"❌ 示例执行失败（{name}）：{e}")

    except (ValueError, KeyboardInterrupt):
        print("\n⚠️ 输入无效或已取消")


if __name__ == "__main__":
    run_all_examples()
