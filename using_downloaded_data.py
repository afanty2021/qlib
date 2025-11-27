#!/usr/bin/env python3
"""
演示如何在qlib中使用下载的上证指数和沪深300数据

下载的数据包括：
1. 上证指数(000001.SH)近5年日线数据
2. 沪深300成分股近5年日线数据
3. 已转换为qlib标准格式的数据
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

# 添加Qlib路径
sys.path.insert(0, os.path.dirname(__file__))

def load_and_inspect_data():
    """加载并检查下载的数据"""
    print("=" * 80)
    print("📊 加载并检查下载的数据")
    print("=" * 80)

    # 文件列表
    files = {
        "上证指数原始数据": "shanghai_index_5years.csv",
        "上证指数Qlib格式": "shanghai_index_5years_qlib_format.csv",
        "沪深300原始数据": "csi300_stocks_5years.csv",
        "沪深300Qlib格式": "csi300_stocks_5years_qlib_format.csv"
    }

    loaded_data = {}

    for name, filename in files.items():
        if os.path.exists(filename):
            print(f"\n📁 加载 {name}: {filename}")
            try:
                df = pd.read_csv(filename)
                loaded_data[name] = df
                print(f"   ✅ 数据形状: {df.shape}")
                print(f"   📅 日期范围: {df.iloc[0]['date'] if 'date' in df.columns else df.index[0]} 至 {df.iloc[-1]['date'] if 'date' in df.columns else df.index[-1]}")
                print(f"   📊 列名: {list(df.columns)}")

                # 显示前几行数据
                if len(df) > 0:
                    print(f"   📋 数据示例:")
                    print(f"      {df.head(2).to_string()}")
            except Exception as e:
                print(f"   ❌ 加载失败: {e}")
        else:
            print(f"\n⚠️ 文件不存在: {filename}")

    return loaded_data

def analyze_shanghai_index(data):
    """分析上证指数数据"""
    print("\n" + "=" * 80)
    print("📈 上证指数数据分析")
    print("=" * 80)

    if "上证指数Qlib格式" not in data:
        print("❌ 未找到上证指数数据")
        return

    df = data["上证指数Qlib格式"].copy()

    # 转换日期列
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')

    print(f"📊 数据统计:")
    print(f"   📅 数据时间范围: {df['date'].min().strftime('%Y-%m-%d')} 至 {df['date'].max().strftime('%Y-%m-%d')}")
    print(f"   📈 总交易日: {len(df)} 天")
    print(f"   💰 最新收盘价: {df['close'].iloc[-1]:.2f}")
    print(f"   📊 期间最高价: {df['high'].max():.2f}")
    print(f"   📊 期间最低价: {df['low'].min():.2f}")
    print(f"   📊 平均成交量: {df['volume'].mean():,.0f}")

    # 计算收益率
    df['returns'] = df['close'].pct_change()
    df['cumulative_returns'] = (1 + df['returns']).cumprod()

    print(f"\n📈 收益率分析:")
    total_return = (df['close'].iloc[-1]/df['close'].iloc[0] - 1) * 100
    annual_return = ((df['close'].iloc[-1]/df['close'].iloc[0])**(252/len(df)) - 1) * 100
    annual_volatility = df['returns'].std() * np.sqrt(252) * 100
    max_dd = calculate_max_drawdown(df['close'])

    print(f"   📊 期间总收益率: {total_return:.2f}%")
    print(f"   📊 年化收益率: {annual_return:.2f}%")
    print(f"   📊 年化波动率: {annual_volatility:.2f}%")
    print(f"   📊 最大回撤: {max_dd:.2f}%")

    # 尝试创建简单的图表
    try:
        plt.figure(figsize=(12, 8))

        # 价格走势图
        plt.subplot(2, 2, 1)
        plt.plot(df['date'], df['close'], linewidth=1)
        plt.title('上证指数收盘价走势')
        plt.xlabel('日期')
        plt.ylabel('收盘价')
        plt.xticks(rotation=45)

        # 成交量图
        plt.subplot(2, 2, 2)
        plt.plot(df['date'], df['volume']/1e8, linewidth=1, color='orange')
        plt.title('上证指数成交量')
        plt.xlabel('日期')
        plt.ylabel('成交量(亿手)')
        plt.xticks(rotation=45)

        # 累积收益率图
        plt.subplot(2, 2, 3)
        plt.plot(df['date'], (df['cumulative_returns'] - 1) * 100, linewidth=1, color='green')
        plt.title('上证指数累积收益率')
        plt.xlabel('日期')
        plt.ylabel('累积收益率(%)')
        plt.xticks(rotation=45)

        # 收益率分布
        plt.subplot(2, 2, 4)
        plt.hist(df['returns'].dropna() * 100, bins=50, alpha=0.7, color='red')
        plt.title('日收益率分布')
        plt.xlabel('日收益率(%)')
        plt.ylabel('频数')

        plt.tight_layout()
        chart_file = "shanghai_index_analysis.png"
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()

        print(f"\n📊 图表已保存: {chart_file}")

    except Exception as e:
        print(f"\n⚠️ 图表生成失败: {e}")

def analyze_csi300_stocks(data):
    """分析沪深300成分股数据"""
    print("\n" + "=" * 80)
    print("🏢 沪深300成分股数据分析")
    print("=" * 80)

    if "沪深300Qlib格式" not in data:
        print("❌ 未找到沪深300数据")
        return

    df = data["沪深300Qlib格式"].copy()

    # 转换日期列
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(['instrument', 'date'])

    print(f"📊 数据统计:")
    print(f"   🏢 股票数量: {df['instrument'].nunique()}")
    print(f"   📅 交易日期: {df['date'].nunique()} 天")
    print(f"   📈 总数据点: {len(df):,}")

    # 按股票分组统计
    stock_stats = df.groupby('instrument').agg({
        'close': ['first', 'last', 'mean', 'std'],
        'volume': 'mean'
    }).round(2)

    stock_stats.columns = ['期初价', '期末价', '平均价', '价格标准差', '平均成交量']
    stock_stats['期间收益率(%)'] = ((stock_stats['期末价'] / stock_stats['期初价'] - 1) * 100).round(2)

    print(f"\n📈 股票表现排名 (前10):")
    top_performers = stock_stats.sort_values('期间收益率(%)', ascending=False).head(10)
    print(top_performers.to_string())

    print(f"\n📉 股票表现排名 (后10):")
    bottom_performers = stock_stats.sort_values('期间收益率(%)', ascending=True).head(10)
    print(bottom_performers.to_string())

    # 计算整体统计
    print(f"\n📊 整体统计:")
    print(f"   📈 平均收益率: {stock_stats['期间收益率(%)'].mean():.2f}%")
    print(f"   📊 收益率中位数: {stock_stats['期间收益率(%)'].median():.2f}%")
    positive_count = (stock_stats['期间收益率(%)'] > 0).sum()
    negative_count = (stock_stats['期间收益率(%)'] <= 0).sum()
    positive_pct = (stock_stats['期间收益率(%)'] > 0).mean() * 100
    negative_pct = (stock_stats['期间收益率(%)'] <= 0).mean() * 100

    print(f"   📈 正收益股票数: {positive_count} 只 ({positive_pct:.1f}%)")
    print(f"   📉 负收益股票数: {negative_count} 只 ({negative_pct:.1f}%)")
    print(f"   📊 收益率标准差: {stock_stats['期间收益率(%)'].std():.2f}%")

def calculate_max_drawdown(prices):
    """计算最大回撤"""
    peak = pd.Series(prices).expanding().max()
    drawdown = (pd.Series(prices) - peak) / peak
    return drawdown.min() * 100

def demonstrate_qlib_usage():
    """演示如何在qlib中使用这些数据"""
    print("\n" + "=" * 80)
    print("🎯 Qlib数据使用演示")
    print("=" * 80)

    print("""
💡 在Qlib中使用下载的数据有几种方式：

1. 📁 直接加载CSV文件
   ```python
   import pandas as pd

   # 加载上证指数数据
   index_data = pd.read_csv('shanghai_index_5years_qlib_format.csv')
   index_data['date'] = pd.to_datetime(index_data['date'])

   # 加载沪深300数据
   stock_data = pd.read_csv('csi300_stocks_5years_qlib_format.csv')
   stock_data['date'] = pd.to_datetime(stock_data['date'])
   ```

2. 🔄 转换为Qlib数据格式
   ```python
   from qlib.data import D

   # 将数据设置为Qlib可用格式
   # 需要将数据放在正确的目录结构中
   # 并按Qlib要求的数据格式组织
   ```

3. 📊 数据分析和可视化
   ```python
   import matplotlib.pyplot as plt

   # 基本分析
   stock_returns = stock_data.groupby('instrument').apply(
       lambda x: (x['close'].iloc[-1] / x['close'].iloc[0] - 1) * 100
   )

   # 可视化
   plt.figure(figsize=(12, 6))
   plt.hist(stock_returns, bins=30, alpha=0.7)
   plt.title('沪深300成分股期间收益率分布')
   plt.xlabel('收益率(%)')
   plt.ylabel('股票数量')
   plt.show()
   ```

4. 🤖 机器学习模型训练
   ```python
   from qlib.data.dataset import DatasetH
   from qlib.contrib.model.gbdt import LGBModel

   # 创建数据集
   dataset = DatasetH(
       handler=data_handler,
       segments={'train': ('2020-11-27', '2023-11-27'),
                'test': ('2023-11-28', '2025-11-26')}
   )

   # 训练模型
   model = LGBModel(loss='mse', learning_rate=0.1)
   model.fit(dataset)
   ```

📋 数据格式说明：
- 所有数据已转换为Qlib标准格式
- 日期格式：YYYY-MM-DD
- 股票代码：SZ000001, SH600000 等
- 字段：open, high, low, close, volume, amount
- 数据已按日期排序

🔧 后续使用建议：
1. 可以根据需要筛选特定时间范围
2. 可以添加更多技术指标
3. 可以与其他数据源进行整合
4. 可以直接用于策略回测和模型训练
    """)

def main():
    """主函数"""
    print("🎯 上证指数和沪深300数据分析演示")
    print("=" * 80)

    # 加载数据
    loaded_data = load_and_inspect_data()

    # 分析上证指数
    analyze_shanghai_index(loaded_data)

    # 分析沪深300成分股
    analyze_csi300_stocks(loaded_data)

    # 演示Qlib使用方法
    demonstrate_qlib_usage()

    print("\n" + "=" * 80)
    print("🎉 数据分析演示完成！")
    print("=" * 80)
    print("\n💡 提示:")
    print("   📊 数据文件已保存在当前目录")
    print("   📈 可以直接用于量化分析和策略开发")
    print("   🤖 建议结合Qlib的机器学习模块进行深度分析")
    print("   📚 更多使用方法请参考Qlib官方文档")

if __name__ == "__main__":
    main()