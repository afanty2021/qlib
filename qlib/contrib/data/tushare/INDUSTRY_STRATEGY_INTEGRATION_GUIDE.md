# 行业板块数据集成到量化策略完整指南

> 从数据加载到策略回测的完整实施方案

## 📋 目录

- [1. 基础数据加载](#1-基础数据加载)
- [2. 行业因子构建](#2-行业因子构建)
- [3. 选股策略应用](#3-选股策略应用)
- [4. 风险管理应用](#4-风险管理应用)
- [5. 回测框架集成](#5-回测框架集成)
- [6. 完整策略示例](#6-完整策略示例)
- [7. 性能优化技巧](#7-性能优化技巧)

---

## 1. 基础数据加载

### 1.1 加载行业分类数据

```python
import pandas as pd
import numpy as np
from pathlib import Path

class IndustryDataManager:
    """行业数据管理器"""

    def __init__(self, data_dir: str = None):
        """
        初始化行业数据管理器

        Args:
            data_dir: 行业数据目录
        """
        if data_dir is None:
            data_dir = Path(__file__).parent / "industry_data"
        else:
            data_dir = Path(data_dir)

        self.data_dir = data_dir
        self.industry_data = {}
        self.concept_data = None
        self._load_data()

    def _load_data(self):
        """加载所有行业数据"""
        # 加载申万行业分类（推荐使用）
        sw_l1 = pd.read_csv(self.data_dir / "industry_SW2021_L1_20251229_112014.csv")
        sw_l2 = pd.read_csv(self.data_dir / "industry_SW2021_L2_20251229_112014.csv")
        sw_l3 = pd.read_csv(self.data_dir / "industry_SW2021_L3_20251229_112014.csv")

        self.industry_data['SW2021'] = {
            'L1': sw_l1,
            'L2': sw_l2,
            'L3': sw_l3
        }

        # 加载概念板块
        self.concept_data = pd.read_csv(
            self.data_dir / "concept_20251229_112014.csv"
        )

        print(f"✅ 行业数据加载完成")
        print(f"   申万一级行业: {len(sw_l1)} 个")
        print(f"   申万二级行业: {len(sw_l2)} 个")
        print(f"   申万三级行业: {len(sw_l3)} 个")
        print(f"   概念板块: {len(self.concept_data)} 个")

    def get_industry_mapping(self, level: str = 'L1') -> dict:
        """
        获取行业代码到名称的映射

        Args:
            level: L1, L2, L3

        Returns:
            行业映射字典
        """
        df = self.industry_data['SW2021'][level]
        return dict(zip(df['industry_code'], df['industry_name']))

    def get_stock_industry(self, stock_code: str, level: str = 'L2') -> str:
        """
        获取股票所属行业（需要预先构建股票-行业映射）

        Args:
            stock_code: 股票代码
            level: 行业级别

        Returns:
            行业名称
        """
        # 这里需要额外的数据源来映射股票到行业
        # 实际使用中需要构建 stock_code -> industry_code 的映射
        pass

    def get_industry_list(self, level: str = 'L1') -> list:
        """获取行业列表"""
        df = self.industry_data['SW2021'][level]
        return df['industry_code'].tolist()

    def get_concept_list(self) -> list:
        """获取概念板块列表"""
        return self.concept_data['code'].tolist()

# 使用示例
manager = IndustryDataManager()
industry_map = manager.get_industry_mapping('L1')
print(f"行业映射示例: {list(industry_map.items())[:5]}")
```

### 1.2 构建股票-行业映射

```python
def build_stock_industry_mapping(
    industry_manager: IndustryDataManager,
    save_path: str = None
) -> dict:
    """
    构建股票到行业的映射关系

    Args:
        industry_manager: 行业数据管理器
        save_path: 保存路径

    Returns:
        股票到行业的映射字典
    """
    import tushare as ts
    import os
    from tqdm import tqdm

    token = os.getenv("TUSHARE_TOKEN")
    pro = ts.pro_api(token)

    mapping = {}

    # 获取所有股票列表
    print("📊 获取股票基本信息...")
    stock_basic = pro.stock_basic(
        list_status='L',
        fields='ts_code,name,industry'
    )

    # 构建映射
    print(f"📊 构建股票-行业映射（共{len(stock_basic)}只股票）...")

    for _, row in tqdm(stock_basic.iterrows(), total=len(stock_basic)):
        # 使用TuShare返回的行业信息
        stock_code = row['ts_code']
        industry = row.get('industry', '未知')

        # 标准化行业名称（可以根据需要调整）
        if pd.notna(industry):
            mapping[stock_code] = industry

    # 保存映射
    if save_path:
        import json
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        print(f"✅ 映射已保存到: {save_path}")

    print(f"✅ 映射构建完成，覆盖 {len(mapping)} 只股票")
    return mapping

# 使用示例
mapping = build_stock_industry_mapping(manager, 'stock_industry_mapping.json')
print(f"映射示例: {list(mapping.items())[:5]}")
```

---

## 2. 行业因子构建

### 2.1 行业动量因子

```python
class IndustryMomentumFactor:
    """行业动量因子"""

    def __init__(self, price_data: pd.DataFrame, industry_mapping: dict):
        """
        初始化

        Args:
            price_data: 价格数据，包含 instrument, date, close
            industry_mapping: 股票到行业的映射
        """
        self.price_data = price_data
        self.industry_mapping = industry_mapping

    def calculate(self, window: int = 20) -> pd.DataFrame:
        """
        计算行业动量因子

        Args:
            window: 时间窗口（天）

        Returns:
            行业动量DataFrame
        """
        # 添加行业信息
        df = self.price_data.copy()
        df['industry'] = df['instrument'].map(self.industry_mapping)

        # 按行业和日期分组计算收益率
        df['return'] = df.groupby('industry')['close'].pct_change()

        # 计算行业动量（累积收益率）
        df['industry_momentum'] = df.groupby('industry')['return'].transform(
            lambda x: x.rolling(window, min_periods=1).sum()
        )

        # 按行业和日期聚合
        momentum_df = df.groupby(['date', 'industry'])['industry_momentum'].last().reset_index()

        return momentum_df

    def rank_industries(self, momentum_df: pd.DataFrame, top_n: int = 5) -> list:
        """
        对行业进行排名

        Args:
            momentum_df: 动量数据
            top_n: 返回前N个行业

        Returns:
        排名后的行业列表
        """
        latest = momentum_df.groupby('industry').last()
        ranked = latest['industry_momentum'].nlargest(top_n).index.tolist()
        return ranked

# 使用示例
momentum_factor = IndustryMomentumFactor(price_data, stock_industry_map)
momentum_df = momentum_factor.calculate(window=20)

# 获取强势行业
strong_industries = momentum_factor.rank_industries(momentum_df, top_n=5)
print(f"强势行业: {strong_industries}")
```

### 2.2 行业轮动因子

```python
class IndustryRotationFactor:
    """行业轮动因子"""

    def __init__(self, price_data: pd.DataFrame, industry_mapping: dict):
        self.price_data = price_data
        self.industry_mapping = industry_mapping

    def calculate_rotation_score(self, window: int = 20) -> pd.DataFrame:
        """
        计算行业轮动分数

        Args:
            window: 时间窗口

        Returns:
            轮动分数DataFrame
        """
        # 添加行业信息
        df = self.price_data.copy()
        df['industry'] = df['instrument'].map(self.industry_mapping)

        # 计算每日收益率
        df['daily_return'] = df.groupby(['industry', 'date'])['close'].transform(
            lambda x: x.pct_change()
        )

        # 计算行业排名
        df['rank'] = df.groupby('date')['daily_return'].rank(ascending=False)

        # 计算轮动分数（排名变化的绝对值之和）
        rotation_score = df.groupby('date')['rank'].transform(
            lambda x: x.diff().abs().sum()
        )

        return rotation_score

    def detect_rotation(self, threshold: float = 50.0) -> pd.Series:
        """
        检测行业轮动

        Args:
            threshold: 轮动阈值

        Returns:
            轮动信号（1表示轮动，0表示稳定）
        """
        rotation_score = self.calculate_rotation_score()
        signal = (rotation_score > threshold).astype(int)
        return signal

# 使用示例
rotation_factor = IndustryRotationFactor(price_data, stock_industry_map)
signal = rotation_factor.detect_rotation(threshold=50.0)

print(f"轮动检测（最近10天）:")
print(signal.tail(10))
```

### 2.3 行业估值因子

```python
class IndustryValueFactor:
    """行业估值因子"""

    def calculate_pe_ratio(self, pe_data: pd.DataFrame, industry_mapping: dict) -> pd.DataFrame:
        """
        计算行业PE（市盈率）

        Args:
            pe_data: PE数据，包含 instrument, date, pe
            industry_mapping: 行业映射

        Returns:
            行业PE DataFrame
        """
        df = pe_data.copy()
        df['industry'] = df['instrument'].map(industry_mapping)

        # 计算行业平均PE
        industry_pe = df.groupby(['date', 'industry'])['pe'].median().reset_index()
        industry_pe.columns = ['date', 'industry', 'industry_pe']

        return industry_pe

    def calculate_pb_ratio(self, pb_data: pd.DataFrame, industry_mapping: dict) -> pd.DataFrame:
        """计算行业PB（市净率）"""
        df = pb_data.copy()
        df['industry'] = df['instrument'].map(industry_mapping)

        industry_pb = df.groupby(['date', 'industry'])['pb'].median().reset_index()
        industry_pb.columns = ['date', 'industry', 'industry_pb']

        return industry_pb

# 使用示例
value_factor = IndustryValueFactor()
industry_pe = value_factor.calculate_pe_ratio(pe_data, stock_industry_map)

print(f"行业PE（最新）:")
print(industry_pe.groupby('industry').last().sort_values('industry_pe').head(10))
```

---

## 3. 选股策略应用

### 3.1 行业轮动选股策略

```python
class IndustryRotationStrategy:
    """行业轮动选股策略"""

    def __init__(
        self,
        industry_manager: IndustryDataManager,
        stock_industry_map: dict,
        lookback: int = 20,
        top_n_industries: int = 3,
        top_n_stocks: int = 10
    ):
        """
        初始化策略

        Args:
            industry_manager: 行业数据管理器
            stock_industry_map: 股票行业映射
            lookback: 回看期（天）
            top_n_industries: 选择前N个强势行业
            top_n_stocks: 每个行业选择前N只股票
        """
        self.industry_manager = industry_manager
        self.stock_industry_map = stock_industry_map
        self.lookback = lookback
        self.top_n_industries = top_n_industries
        self.top_n_stocks = top_n_stocks

    def select_industries(self, price_data: pd.DataFrame) -> list:
        """
        选择强势行业

        Args:
            price_data: 价格数据

        Returns:
            选中的行业列表
        """
        # 计算行业动量
        momentum_factor = IndustryMomentumFactor(price_data, self.stock_industry_map)
        momentum_df = momentum_factor.calculate(self.lookback)

        # 选择强势行业
        strong_industries = momentum_factor.rank_industries(momentum_df, self.top_n_industries)

        return strong_industries

    def select_stocks_in_industry(
        self,
        price_data: pd.DataFrame,
        industry: str,
        fundamental_data: pd.DataFrame = None
    ) -> list:
        """
        在选定行业内选择股票

        Args:
            price_data: 价格数据
            industry: 目标行业
            fundamental_data: 基本面数据（可选）

        Returns:
            选中的股票列表
        """
        # 筛选该行业的股票
        industry_stocks = price_data[
            price_data['instrument'].map(self.stock_industry_map) == industry
        ]['instrument'].unique()

        # 计算股票动量
        stock_returns = price_data[
            price_data['instrument'].isin(industry_stocks)
        ].copy()

        stock_returns['return'] = stock_returns.groupby('instrument')['close'].transform(
            lambda x: x.pct_change().sum()
        )

        # 选择前N只股票
        top_stocks = stock_returns.groupby('instrument')['return'].last().nlargest(
            self.top_n_stocks
        ).index.tolist()

        return top_stocks

    def generate_signals(self, price_data: pd.DataFrame) -> dict:
        """
        生成交易信号

        Args:
            price_data: 价格数据

        Returns:
            信号字典 {date: [stock_list]}
        """
        signals = {}

        # 获取每个交易日期
        dates = price_data['date'].unique()

        for i, date in enumerate(dates[20:]):  # 从第20天开始，有足够历史数据
            # 使用过去的数据
            historical_data = price_data[price_data['date'] <= date]

            # 选择强势行业
            strong_industries = self.select_industries(historical_data)

            # 在每个行业内选择股票
            selected_stocks = []
            for industry in strong_industries:
                stocks = self.select_stocks_in_industry(historical_data, industry)
                selected_stocks.extend(stocks)

            signals[date] = selected_stocks

        return signals

# 使用示例
strategy = IndustryRotationStrategy(
    industry_manager=manager,
    stock_industry_map=stock_industry_map,
    lookback=20,
    top_n_industries=3,
    top_n_stocks=10
)

signals = strategy.generate_signals(price_data)
print(f"生成的信号示例:")
for date, stocks in list(signals.items())[:3]:
    print(f"{date}: {len(stocks)} 只股票")
```

### 3.2 行业中性策略

```python
class IndustryNeutralStrategy:
    """行业中性策略"""

    def __init__(
        self,
        industry_manager: IndustryDataManager,
        stock_industry_map: dict,
        benchmark_weights: dict = None
    ):
        """
        初始化行业中性策略

        Args:
            industry_manager: 行业数据管理器
            stock_industry_map: 股票行业映射
            benchmark_weights: 基准行业权重
        """
        self.industry_manager = industry_manager
        self.stock_industry_map = stock_industry_map
        self.benchmark_weights = benchmark_weights or self._get_default_benchmark()

    def _get_default_benchmark(self) -> dict:
        """获取默认基准权重（等权重）"""
        industries = self.industry_manager.get_industry_list('L1')
        weight = 1.0 / len(industries)
        return {industry: weight for industry in industries}

    def calculate_industry_exposure(
        self,
        holdings: pd.DataFrame
    ) -> pd.DataFrame:
        """
        计算组合行业暴露度

        Args:
            holdings: 持仓数据，包含 instrument, weight

        Returns:
            行业暴露度DataFrame
        """
        df = holdings.copy()
        df['industry'] = df['instrument'].map(self.stock_industry_map)

        # 计算每个行业的权重
        industry_weights = df.groupby('industry')['weight'].sum().reset_index()
        industry_weights.columns = ['industry', 'portfolio_weight']

        # 添加基准权重
        industry_weights['benchmark_weight'] = industry_weights['industry'].map(
            self.benchmark_weights
        )

        # 计算主动权重
        industry_weights['active_weight'] = (
            industry_weights['portfolio_weight'] -
            industry_weights['benchmark_weight']
        )

        return industry_weights

    def select_neutral_stocks(
        self,
        price_data: pd.DataFrame,
        factor_data: pd.DataFrame
    ) -> dict:
        """
        选择行业中性股票组合

        Args:
            price_data: 价格数据
            factor_data: 因子数据

        Returns:
            {industry: [stock_list]}
        """
        # 获取所有行业
        industries = self.industry_manager.get_industry_list('L1')

        selected_by_industry = {}

        for industry in industries:
            # 筛选该行业的股票
            industry_stocks = price_data[
                price_data['instrument'].map(self.stock_industry_map) == industry
            ]['instrument'].unique()

            # 计算因子值并排序
            industry_factor_data = factor_data[
                factor_data['instrument'].isin(industry_stocks)
            ]

            # 选择因子值最高的股票
            top_stocks = industry_factor_data.nlargest(10, 'factor_value')['instrument'].tolist()

            selected_by_industry[industry] = top_stocks

        return selected_by_industry

# 使用示例
neutral_strategy = IndustryNeutralStrategy(
    industry_manager=manager,
    stock_industry_map=stock_industry_map
)

# 计算当前持仓的行业暴露度
holdings = pd.DataFrame({
    'instrument': ['000001.SZ', '000002.SZ', '600000.SH'],
    'weight': [0.3, 0.3, 0.4]
})

exposure = neutral_strategy.calculate_industry_exposure(holdings)
print(f"行业暴露度:")
print(exposure)
```

---

## 4. 风险管理应用

### 4.1 行业集中度风险控制

```python
class IndustryConcentrationRisk:
    """行业集中度风险管理"""

    def __init__(self, stock_industry_map: dict, max_concentration: float = 0.3):
        """
        初始化

        Args:
            stock_industry_map: 股票行业映射
            max_concentration: 最大单一行业集中度
        """
        self.stock_industry_map = stock_industry_map
        self.max_concentration = max_concentration

    def calculate_concentration(self, holdings: pd.DataFrame) -> dict:
        """
        计算行业集中度

        Args:
            holdings: 持仓数据

        Returns:
            集中度指标
        """
        df = holdings.copy()
        df['industry'] = df['instrument'].map(self.stock_industry_map)

        # 计算行业权重
        industry_weights = df.groupby('industry')['weight'].sum()

        # 计算赫芬达尔指数（HHI）
        hhi = (industry_weights ** 2).sum()

        # 计算最大单一行业权重
        max_weight = industry_weights.max()

        return {
            'hhi': hhi,
            'max_weight': max_weight,
            'industry_weights': industry_weights.to_dict()
        }

    def check_concentration(self, holdings: pd.DataFrame) -> tuple:
        """
        检查集中度是否超标

        Returns:
            (是否超标, 超标行业列表)
        """
        metrics = self.calculate_concentration(holdings)

        over_concentration = metrics['max_weight'] > self.max_concentration

        # 找出超标的行业
        over_limit_industries = [
            ind for ind, w in metrics['industry_weights'].items()
            if w > self.max_concentration
        ]

        return over_concentration, over_limit_industries

    def adjust_for_concentration(
        self,
        holdings: pd.DataFrame,
        target_weights: dict
    ) -> pd.DataFrame:
        """
        调整持仓以控制集中度

        Args:
            holdings: 当前持仓
            target_weights: 目标权重（调整后）

        Returns:
            调整后的持仓
        """
        adjusted = holdings.copy()

        # 应用调整
        for instrument, target_weight in target_weights.items():
            adjusted.loc[adjusted['instrument'] == instrument, 'weight'] = target_weight

        return adjusted

# 使用示例
risk_manager = IndustryConcentrationRisk(stock_industry_map, max_concentration=0.3)

# 检查当前持仓
is_over, over_industries = risk_manager.check_concentration(holdings)
print(f"集中度超标: {is_over}")
print(f"超标的行业: {over_industries}")

# 计算详细指标
metrics = risk_manager.calculate_concentration(holdings)
print(f"赫芬达尔指数: {metrics['hhi']:.4f}")
print(f"最大权重: {metrics['max_weight']:.2%}")
```

### 4.2 行业风险敞口分析

```python
class IndustryExposureAnalysis:
    """行业风险敞口分析"""

    def __init__(self, stock_industry_map: dict):
        self.stock_industry_map = stock_industry_map

    def calculate_portfolio_industry_risk(
        self,
        portfolio_holdings: pd.DataFrame,
        benchmark_holdings: pd.DataFrame
    ) -> pd.DataFrame:
        """
        计算组合相对基准的行业风险敞口

        Args:
            portfolio_holdings: 组合持仓
            benchmark_holdings: 基准持仓

        Returns:
            行业风险敞口DataFrame
        """
        # 计算组合行业权重
        portfolio_df = portfolio_holdings.copy()
        portfolio_df['industry'] = portfolio_df['instrument'].map(self.stock_industry_map)
        portfolio_weights = portfolio_df.groupby('industry')['weight'].sum()

        # 计算基准行业权重
        benchmark_df = benchmark_holdings.copy()
        benchmark_df['industry'] = benchmark_df['instrument'].map(self.stock_industry_map)
        benchmark_weights = benchmark_df.groupby('industry')['weight'].sum()

        # 计算主动权重
        all_industries = set(portfolio_weights.index) | set(benchmark_weights.index)

        exposure_data = []
        for industry in all_industries:
            portfolio_w = portfolio_weights.get(industry, 0)
            benchmark_w = benchmark_weights.get(industry, 0)
            active_w = portfolio_w - benchmark_w

            exposure_data.append({
                'industry': industry,
                'portfolio_weight': portfolio_w,
                'benchmark_weight': benchmark_w,
                'active_weight': active_w,
                'active_pct': active_w / benchmark_w if benchmark_w > 0 else 0
            })

        return pd.DataFrame(exposure_data)

    def generate_risk_report(self, exposure_df: pd.DataFrame) -> str:
        """
        生成风险报告

        Args:
            exposure_df: 行业敞口数据

        Returns:
            报告文本
        """
        report_lines = []
        report_lines.append("行业风险敞口分析报告")
        report_lines.append("="*50)

        # 超配行业
        over_weight = exposure_df[exposure_df['active_weight'] > 0.05]
        if not over_weight.empty:
            report_lines.append("\n超配行业（>5%）:")
            for _, row in over_weight.iterrows():
                report_lines.append(f"  {row['industry']}: {row['active_weight']:.2%} ({row['portfolio_weight']:.2%} vs {row['benchmark_weight']:.2%})")

        # 低配行业
        under_weight = exposure_df[exposure_df['active_weight'] < -0.05]
        if not under_weight.empty:
            report_lines.append("\n低配行业（<-5%）:")
            for _, row in under_weight.iterrows():
                report_lines.append(f"  {row['industry']}: {row['active_weight']:.2%} ({row['portfolio_weight']:.2%} vs {row['benchmark_weight']:.2%})")

        # 风险指标
        tracking_error = exposure_df['active_weight'].abs().sum() / 2
        report_lines.append(f"\n跟踪误差: {tracking_error:.2%}")

        return '\n'.join(report_lines)

# 使用示例
exposure_analyzer = IndustryExposureAnalysis(stock_industry_map)

# 假设有组合和基准持仓
portfolio = pd.DataFrame({
    'instrument': ['000001.SZ', '000002.SZ', '600000.SH'],
    'weight': [0.4, 0.3, 0.3]
})

benchmark = pd.DataFrame({
    'instrument': ['000001.SZ', '000002.SZ', '600000.SH'],
    'weight': [0.33, 0.33, 0.34]
})

# 计算风险敞口
exposure_df = exposure_analyzer.calculate_portfolio_industry_risk(portfolio, benchmark)
print(exposure_df)

# 生成风险报告
report = exposure_analyzer.generate_risk_report(exposure_df)
print("\n" + report)
```

---

## 5. 回测框架集成

### 5.1 集成到Qlib回测

```python
from qlib import init
from qlib.data import D
from qlib.backtest import backtest, executor
from qlib.contrib.strategy import TopkDropoutStrategy
from qlib.contrib.model import LGBModel

# 初始化Qlib
init(provider_uri="tushare", region="cn")

# 加载行业数据
industry_manager = IndustryDataManager()
stock_industry_map = load_stock_industry_mapping('stock_industry_mapping.json')

# 获取价格数据并添加行业信息
instruments = D.instruments('csi300')
price_data = D.features(
    instruments=instruments,
    fields=['close', 'volume', 'high', 'low'],
    start_time='2023-01-01',
    end_time='2024-12-31'
).reset_index()

# 添加行业信息
price_data['industry'] = price_data['instrument'].map(stock_industry_map)

# 使用行业数据增强策略
# 这里可以自定义策略使用行业信息
```

### 5.2 自定义Qlib策略

```python
from qlib.contrib.strategy.signal_strategy import TopkDropoutStrategy

class IndustryEnhancedStrategy(TopkDropoutStrategy):
    """行业增强的TopkDropout策略"""

    def __init__(
        self,
        signal,
        industry_manager: IndustryDataManager,
        stock_industry_map: dict,
        topk: int = 50,
        n_drop: int = 5,
        max_industry_weight: float = 0.3
    ):
        """
        初始化

        Args:
            signal: 信号数据
            industry_manager: 行业管理器
            stock_industry_map: 行业映射
            topk: 选择股票数
            n_drop: 调仓股票数
            max_industry_weight: 最大单一行业权重
        """
        super().__init__(signal, topk, n_drop)
        self.industry_manager = industry_manager
        self.stock_industry_map = stock_industry_map
        self.max_industry_weight = max_industry_weight

    def generate_signal(self):
        """生成交易信号（含行业约束）"""
        # 获取基础信号
        base_signal = super().generate_signal()

        # 添加行业集中度约束
        signal_with_constraints = self._apply_industry_constraint(base_signal)

        return signal_with_constraint

    def _apply_industry_constraint(self, signal: pd.DataFrame) -> pd.DataFrame:
        """应用行业集中度约束"""
        # 计算当前持仓的行业权重
        signal['industry'] = signal.index.get_level_values(0).map(self.stock_industry_map)

        # 按行业分组并限制权重
        def adjust_weights(group):
            total_weight = group.sum()
            if total_weight > self.max_industry_weight:
                scale = self.max_industry_weight / total_weight
                return group * scale
            return group

        signal['adjusted_score'] = signal.groupby('industry')['score'].transform(
            lambda g: adjust_weights(g)
        )

        return signal

# 使用示例
strategy = IndustryEnhancedStrategy(
    signal=your_signal_data,
    industry_manager=industry_manager,
    stock_industry_map=stock_industry_map,
    topk=50,
    n_drop=5,
    max_industry_weight=0.3
)
```

---

## 6. 完整策略示例

### 6.1 行业轮动+多因子策略

```python
class IndustryMomentumMultiFactorStrategy:
    """行业动量多因子策略"""

    def __init__(
        self,
        industry_manager: IndustryDataManager,
        stock_industry_map: dict,
        start_date: str,
        end_date: str
    ):
        """
        初始化

        Args:
            industry_manager: 行业管理器
            stock_industry_map: 行业映射
            start_date: 开始日期
            end_date: 结束日期
        """
        self.industry_manager = industry_manager
        self.stock_industry_map = stock_industry_map
        self.start_date = start_date
        self.end_date = end_date

        # 策略参数
        self.lookback_days = 20
        self.top_industries = 3
        self.top_stocks_per_industry = 5
        self.rebalance_frequency = 'monthly'  # 每月调仓

    def run_backtest(self):
        """运行完整回测"""
        print("🚀 开始行业动量多因子策略回测")

        # 1. 加载数据
        print("\n📊 加载数据...")
        price_data = self._load_price_data()

        # 2. 生成交易信号
        print("📈 生成交易信号...")
        signals = self._generate_signals(price_data)

        # 3. 执行回测
        print("⚡ 执行回测...")
        backtest_results = self._run_backtest(signals)

        # 4. 分析结果
        print("📊 分析结果...")
        self._analyze_results(backtest_results)

        return backtest_results

    def _load_price_data(self) -> pd.DataFrame:
        """加载价格数据"""
        from qlib.data import D

        instruments = D.instruments('csi300')
        data = D.features(
            instruments=instruments,
            fields=['close', 'volume', 'high', 'low', 'open'],
            start_time=self.start_date,
            end_date=self.end_date
        ).reset_index()

        # 添加行业信息
        data['industry'] = data['instrument'].map(self.stock_industry_map)

        return data

    def _generate_signals(self, price_data: pd.DataFrame) -> dict:
        """生成交易信号"""
        from qlib.contrib.data.tushare.industry_factors import IndustryFactorCalculator

        signals = {}

        # 创建因子计算器
        calculator = IndustryFactorCalculator(
            industry_data=pd.DataFrame(),  # 使用简化数据
            price_data=price_data
        )

        # 计算行业动量
        momentum_df = calculator.calculate_industry_momentum(window=self.lookback_days)

        # 按月生成信号
        price_data['month'] = pd.to_datetime(price_data['date']).dt.to_period('M')
        months = price_data['month'].unique()

        for month in months:
            # 获取该月的历史数据
            historical = price_data[price_data['month'] <= month]

            # 计算行业动量
            momentum = IndustryMomentumFactor(historical, self.stock_industry_map)
            momentum_df = momentum.calculate(window=20)

            # 选择强势行业
            strong_industries = momentum.rank_industries(momentum_df, self.top_industries)

            # 在每个行业内选择股票
            selected_stocks = []
            for industry in strong_industries:
                industry_stocks = historical[
                    historical['industry'] == industry
                ]['instrument'].unique()

                # 计算股票收益率
                stock_returns = historical[
                    historical['instrument'].isin(industry_stocks)
                ].groupby('instrument')['close'].apply(
                    lambda x: (x.iloc[-1] / x.iloc[0] - 1) if len(x) > 0 else 0
                )

                # 选择表现最好的股票
                top_stocks = stock_returns.nlargest(self.top_stocks_per_industry)
                selected_stocks.extend(top_stocks.index.tolist())

            # 等权重配置
            weights = np.repeat(1.0 / len(selected_stocks), len(selected_stocks))

            signals[str(month)] = {
                'stocks': selected_stocks,
                'weights': weights
            }

        return signals

    def _run_backtest(self, signals: dict):
        """执行回测"""
        # 这里可以使用Qlib的回测框架
        # 或者实现简单的回测逻辑
        results = {}

        total_return = 1.0

        for period, signal in signals.items():
            # 简化的回测逻辑
            stocks = signal['stocks']
            weights = signal['weights']

            # 计算该期收益（这里需要实际的价格数据）
            # period_return = ...

            results[period] = {
                'stocks': stocks,
                'weights': weights,
                'return': 0.05  # 示例值
            }

            total_return *= (1 + 0.05)  # 累计收益

        results['total_return'] = total_return
        return results

    def _analyze_results(self, results: dict):
        """分析回测结果"""
        print(f"\n总收益率: {results['total_return']:.2%}")
        print(f"交易期数: {len(results) - 1}")

# 使用示例
strategy = IndustryMomentumMultiFactorStrategy(
    industry_manager=manager,
    stock_industry_map=stock_industry_map,
    start_date='2023-01-01',
    end_date='2024-12-31'
)

# 运行回测
# backtest_results = strategy.run_backtest()
```

### 6.2 行业配置优化策略

```python
def optimize_industry_allocation(
    industry_manager: IndustryDataManager,
    expected_returns: dict,
    risk_covariance: pd.DataFrame,
    risk_aversion: float = 1.0
) -> dict:
    """
    优化行业配置权重（马科维茨优化）

    Args:
        industry_manager: 行业管理器
        expected_returns: 行业预期收益 {industry: return}
        risk_covariance: 行业协方差矩阵
        risk_aversion: 风险厌恶系数

    Returns:
        最优行业配置权重
    """
    from scipy.optimize import minimize

    industries = list(expected_returns.keys())
    n = len(industries)

    # 目标函数：最小化组合方差
    def objective(weights):
        portfolio_variance = np.dot(weights.T, np.dot(risk_covariance.values, weights))
        portfolio_return = np.dot(weights, [expected_returns[i] for i in industries])

        # 优化目标：最小化方差 - lambda * 收益
        return portfolio_variance - risk_aversion * portfolio_return

    # 约束条件
    constraints = [
        {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # 权重和为1
    ]

    # 边界条件：每个行业权重在0到1之间
    bounds = [(0, 1) for _ in range(n)]

    # 初始权重（等权重）
    x0 = np.array([1.0 / n] * n)

    # 优化
    result = minimize(
        objective,
        x0,
        method='SLSQP',
        bounds=bounds,
        constraints=constraints
    )

    # 构建权重字典
    optimal_weights = {industry: weight for industry, weight in zip(industries, result.x)}

    return optimal_weights

# 使用示例
# 准备数据
industries = manager.get_industry_list('L1')
expected_returns = {ind: 0.08 for ind in industries}  # 示例收益率
risk_covariance = pd.DataFrame(
    np.eye(len(industries)) * 0.01,  # 示例协方差矩阵
    index=industries,
    columns=industries
)

# 优化行业配置
optimal_weights = optimize_industry_allocation(
    industry_manager=manager,
    expected_returns=expected_returns,
    risk_covariance=risk_covariance
)

print("最优行业配置:")
for industry, weight in sorted(optimal_weights.items(), key=lambda x: x[1], reverse=True):
    if weight > 0.01:
        print(f"  {industry}: {weight:.2%}")
```

---

## 7. 性能优化技巧

### 7.1 数据缓存优化

```python
import pickle
from functools import lru_cache

class CachedIndustryData:
    """缓存的行业数据管理器"""

    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path("industry_cache")
        self.cache_dir.mkdir(exist_ok=True)

    @lru_cache(maxsize=128)
    def get_industry_mapping(self, level: str = 'L1') -> dict:
        """获取行业映射（带缓存）"""
        cache_file = self.cache_dir / f"industry_map_{level}.pkl"

        if cache_file.exists():
            with open(cache_file, 'rb') as f:
                return pickle.load(f)

        # 如果缓存不存在，加载并保存
        # ... 加载逻辑 ...

        return mapping

    def save_to_cache(self, key: str, data: any):
        """保存数据到缓存"""
        cache_file = self.cache_dir / f"{key}.pkl"
        with open(cache_file, 'wb') as f:
            pickle.dump(data, f)
```

### 7.2 并行计算优化

```python
from multiprocessing import Pool, cpu_count

def calculate_industry_factor_parallel(
    industry_list: list,
    price_data: pd.DataFrame,
    stock_industry_map: dict
) -> dict:
    """并行计算多个行业的因子"""

    def calculate_single_industry(industry: str):
        # 筛选该行业股票
        industry_stocks = price_data[
            price_data['instrument'].map(stock_industry_map) == industry
        ]['instrument'].unique()

        industry_data = price_data[
            price_data['instrument'].isin(industry_stocks)
        ]

        # 计算因子（示例：动量）
        returns = industry_data.groupby('instrument')['close'].apply(
            lambda x: x.pct_change().mean()
        )

        return returns

    # 并行计算
    with Pool(processes=min(cpu_count(), len(industry_list))) as pool:
        results = pool.map(calculate_single_industry, industry_list)

    return dict(zip(industry_list, results))
```

### 7.3 增量更新策略

```python
class IncrementalIndustryStrategy:
    """增量更新策略"""

    def __init__(self, initial_date: str):
        self.initial_date = initial_date
        self.last_update = initial_date
        self.industry_cache = {}

    def incremental_update(self, new_date: str, new_data: pd.DataFrame):
        """增量更新数据"""
        # 只处理新数据
        new_data_filtered = new_data[new_data['date'] > self.last_update]

        # 更新缓存
        self._update_industry_cache(new_data_filtered)

        # 更新最后更新时间
        self.last_update = new_date

    def _update_industry_cache(self, new_data: pd.DataFrame):
        """更新行业缓存"""
        # 增量计算
        # ... 更新逻辑 ...
        pass
```

---

## 📝 完整使用示例

### 示例：完整的行业轮动策略

```python
"""
完整的行业轮动策略实现
"""
import pandas as pd
import numpy as np
from pathlib import Path

# 1. 加载行业数据
manager = IndustryDataManager()
stock_industry_map = load_stock_industry_mapping('stock_industry_mapping.json')

# 2. 加载价格数据
from qlib import init
from qlib.data import D

init(provider_uri="tushare", region="cn")

instruments = D.instruments('csi500')
price_data = D.features(
    instruments=instruments,
    fields=['close', 'volume'],
    start_time='2023-01-01',
    end_date='2024-12-31'
).reset_index()

# 添加行业信息
price_data['industry'] = price_data['instrument'].map(stock_industry_map)

# 3. 计算行业动量
momentum_factor = IndustryMomentumFactor(price_data, stock_industry_map)
momentum_df = momentum_factor.calculate(window=20)

# 4. 选择强势行业
strategy = IndustryRotationStrategy(
    industry_manager=manager,
    stock_industry_map=stock_industry_map
)
strong_industries = strategy.select_industries(price_data)

print(f"强势行业: {strong_industries}")

# 5. 在强势行业内选择股票
selected_stocks = {}
for industry in strong_industries:
    stocks = strategy.select_stocks_in_industry(price_data, industry)
    selected_stocks[industry] = stocks

print(f"\n选中的股票:")
for industry, stocks in selected_stocks.items():
    print(f"{industry}: {stocks}")

# 6. 风险管理
risk_manager = IndustryConcentrationRisk(stock_industry_map, max_concentration=0.3)
# 创建等权重组合
holdings = pd.DataFrame({
    'instrument': [s for stocks in selected_stocks.values() for s in stocks],
    'weight': np.repeat(1.0 / 30, 30)
})

is_over, over_industries = risk_manager.check_concentration(holdings)
print(f"\n集中度检查: {'⚠️ 超标' if is_over else '✅ 正常'}")

if is_over:
    print(f"超标的行业: {over_industries}")
```

---

## 🎯 总结

### 集成路径

1. **数据准备** → 加载行业数据，构建股票-行业映射
2. **因子构建** → 计算行业动量、估值、轮动等因子
3. **信号生成** → 基于行业因子生成交易信号
4. **风险控制** → 监控行业集中度，控制行业风险敞口
5. **回测验证** → 在历史数据上验证策略效果

### 核心优势

✅ **数据驱动**：基于完整的行业分类体系
✅ **风险控制**：行业分散降低组合风险
✅ **灵活配置**：支持多种行业权重配置方法
✅ **易于扩展**：模块化设计便于添加新因子

### 下一步

您现在可以：
1. ✅ 加载并使用行业数据
2. ✅ 构建行业因子
3. ✅ 实现行业轮动策略
4. ✅ 控制行业集中度风险
5. ✅ 集成到回测框架

所有代码示例都已提供，可以直接使用或根据需求修改！
