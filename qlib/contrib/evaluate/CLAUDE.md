[根目录](../../../CLAUDE.md) > [qlib](../../CLAUDE.md) > [contrib](../CLAUDE.md) > **evaluate**

# 评估分析模块

> Qlib 的策略评估和风险分析框架，提供完整的量化策略绩效评估工具。

## 模块职责

评估分析模块专注于量化策略的综合评估：
- 风险指标计算和分析
- 策略绩效评估
- 交易指标分析
- 回测结果可视化

## 核心功能组件

### 风险分析 (risk_analysis)

#### 核心算法
```python
def risk_analysis(r, N: int = None, freq: str = "day", mode: Literal["sum", "product"] = "sum"):
    """
    风险分析计算

    参数:
        r: 日收益率序列
        N: 年化因子 (day: 252, week: 50, month: 12)
        freq: 分析频率
        mode: 累积模式
            - "sum": 算术累积 (线性收益)
            - "product": 几何累积 (复利收益)

    返回:
        包含风险指标的DataFrame
    """
```

#### 风险指标体系
- **基础收益指标**：
  - mean: 平均收益率
  - std: 收益率标准差
  - annualized_return: 年化收益率

- **风险调整收益**：
  - information_ratio: 信息比率
  - max_drawdown: 最大回撤

- **计算模式**：
  - 算术累积：Qlib默认模式，避免指数偏斜
  - 几何累积：传统复利计算模式

#### 计算示例
```python
# 算术累积模式 (默认)
risk_metrics = risk_analysis(returns, freq="day", mode="sum")

# 几何累积模式
risk_metrics_compound = risk_analysis(returns, freq="day", mode="product")

# 不同频率分析
daily_metrics = risk_analysis(returns, N=252)
weekly_metrics = risk_analysis(returns, N=50)
monthly_metrics = risk_analysis(returns, N=12)
```

### 交易指标分析 (indicator_analysis)

#### 交易质量指标
```python
def indicator_analysis(df, method="mean"):
    """
    交易指标统计分析

    参数:
        df: 包含交易指标的DataFrame
            必需字段: 'pa'(价格优势), 'pos'(正向率), 'ffr'(成效率)
            可选字段: 'deal_amount'(成交量), 'value'(交易价值)
        method: 统计方法
            - "mean": 简单平均
            - "amount_weighted": 成交量加权
            - "value_weighted": 交易价值加权

    返回:
        交易指标统计结果
    """
```

#### 指标说明
- **价格优势 (PA)**：交易价格相对基准价格的改善程度
- **正向率 (Pos)**：盈利交易的比例
- **成效率 (FFR)**：订单完成的效率

#### 加权方法
```python
# 简单平均
simple_stats = indicator_analysis(trade_df, method="mean")

# 成交量加权
volume_weighted = indicator_analysis(trade_df, method="amount_weighted")

# 交易价值加权
value_weighted = indicator_analysis(trade_df, method="value_weighted")
```

### 回测接口 (backtest_daily)

#### 统一回测接口
```python
def backtest_daily(
    start_time: Union[str, pd.Timestamp],
    end_time: Union[str, pd.Timestamp],
    strategy: Union[str, dict, BaseStrategy],
    executor: Union[str, dict, BaseExecutor] = None,
    account: Union[float, int, Position] = 1e8,
    benchmark: str = "SH000300",
    exchange_kwargs: dict = None,
    pos_type: str = "Position"
):
    """
    日频回测接口

    提供统一的日频回测执行接口，简化回测流程。
    """
```

#### 使用示例
```python
# 使用配置字典
strategy_config = {
    "class": "TopkDropoutStrategy",
    "module_path": "qlib.contrib.strategy.signal_strategy",
    "kwargs": {
        "signal": (model, dataset),
        "topk": 50,
        "n_drop": 5
    }
}

# 执行回测
report_df, positions = backtest_daily(
    start_time="2020-01-01",
    end_time="2020-12-31",
    strategy=strategy_config,
    benchmark="SH000300"
)
```

### 多空回测 (long_short_backtest)

#### 多空策略回测
```python
def long_short_backtest(
    pred,
    topk=50,
    deal_price=None,
    shift=1,
    open_cost=0,
    close_cost=0,
    trade_unit=None,
    limit_threshold=None,
    min_cost=5,
    subscribe_fields=[],
    extract_codes=False
):
    """
    多空策略回测

    实现经典的多空对冲策略回测，适合alpha因子测试。
    """
```

#### 策略逻辑
1. **选股逻辑**：每日选择topk股票做多，bottomk股票做空
2. **风险对冲**：通过多空组合对冲市场风险
3. **收益计算**：计算多头、空头和多空组合的相对收益

#### 使用示例
```python
# 多空回测
ls_results = long_short_backtest(
    pred=score_df,
    topk=50,
    shift=1,
    open_cost=0.0005,
    close_cost=0.0015
)

# 结果包含三部分
long_returns = ls_results["long"]      # 多头相对收益
short_returns = ls_results["short"]    # 空头相对收益
ls_returns = ls_results["long_short"]  # 多空组合收益
```

## 风险指标详解

### 年化收益率计算
```python
# 算术累积模式 (Qlib默认)
annualized_return = mean * N

# 几何累积模式
cumulative_return = (1 + r).cumprod().iloc[-1] - 1
annualized_return = (1 + cumulative_return) ** (N / len(r)) - 1
```

### 最大回撤计算
```python
# 算术累积模式
max_drawdown = (r.cumsum() - r.cumsum().cummax()).min()

# 几何累积模式
cumulative_curve = (1 + r).cumprod()
max_drawdown = (cumulative_curve / cumulative_curve.cummax() - 1).min()
```

### 信息比率计算
```python
information_ratio = mean / std * np.sqrt(N)
```

## 数据格式规范

### 风险分析数据格式
```python
# 收益率序列
returns = pd.Series([
    0.01, -0.005, 0.02, 0.015, -0.01
], index=pd.date_range("2020-01-01", periods=5))
```

### 交易指标数据格式
```python
# 交易指标DataFrame
trade_df = pd.DataFrame({
    'pa': [0.001, 0.002, -0.001],       # 价格优势
    'pos': [0.6, 0.55, 0.65],           # 正向率
    'ffr': [0.95, 0.92, 0.98],          # 成效率
    'deal_amount': [1000, 1500, 800],   # 成交量
    'value': [100000, 150000, 80000]    # 交易价值
}, index=pd.date_range("2020-01-01", periods=3))
```

### 多空回测数据格式
```python
# 预测评分DataFrame
score_df = pd.DataFrame({
    'score': [0.8, 0.6, 0.4, 0.2, 0.1]
}, index=pd.MultiIndex.from_tuples([
    ('SH600000', '2020-01-01'),
    ('SH600001', '2020-01-01'),
    ('SH600002', '2020-01-01'),
    ('SH600003', '2020-01-01'),
    ('SH600004', '2020-01-01')
], names=['instrument', 'datetime']))
```

## 高级分析功能

### 多时间尺度分析
```python
# 不同频率的风险分析
daily_risk = risk_analysis(daily_returns, freq="day")
weekly_risk = risk_analysis(weekly_returns, freq="week")
monthly_risk = risk_analysis(monthly_returns, freq="month")

# 频率对比分析
risk_comparison = pd.DataFrame({
    'daily': daily_risk['risk'],
    'weekly': weekly_risk['risk'],
    'monthly': monthly_risk['risk']
})
```

### 滚动窗口分析
```python
def rolling_risk_analysis(returns, window=252):
    """滚动窗口风险分析"""
    rolling_metrics = []

    for i in range(window, len(returns)):
        window_returns = returns.iloc[i-window:i]
        metrics = risk_analysis(window_returns)
        rolling_metrics.append(metrics)

    return pd.concat(rolling_metrics, axis=1).T
```

### 风险归因分析
```python
def risk_attribution(portfolio_returns, factor_returns):
    """风险归因分析"""
    # 计算因子暴露
    factor_exposure = np.linalg.lstsq(factor_returns, portfolio_returns, rcond=None)[0]

    # 计算因子贡献
    factor_contribution = factor_returns @ factor_exposure

    # 计算特异性风险
    specific_return = portfolio_returns - factor_contribution

    return {
        'factor_exposure': factor_exposure,
        'factor_contribution': factor_contribution,
        'specific_return': specific_return
    }
```

## 性能基准对比

### 基准收益率计算
```python
def benchmark_analysis(strategy_returns, benchmark_returns):
    """基准对比分析"""
    # 超额收益
    excess_returns = strategy_returns - benchmark_returns

    # 相对风险指标
    tracking_error = excess_returns.std()
    information_ratio = excess_returns.mean() / tracking_error * np.sqrt(252)

    # Beta计算
    beta = np.cov(strategy_returns, benchmark_returns)[0,1] / np.var(benchmark_returns)

    # Alpha计算
    alpha = strategy_returns.mean() - beta * benchmark_returns.mean()

    return {
        'excess_return': excess_returns.mean(),
        'tracking_error': tracking_error,
        'information_ratio': information_ratio,
        'beta': beta,
        'alpha': alpha
    }
```

## 扩展开发

### 自定义风险指标
```python
def custom_risk_metric(returns):
    """自定义风险指标"""
    # 计算下行风险
    negative_returns = returns[returns < 0]
    downside_deviation = np.sqrt((negative_returns ** 2).mean())

    # 计算VaR
    var_95 = returns.quantile(0.05)

    # 计算CVaR (Expected Shortfall)
    cvar_95 = returns[returns <= var_95].mean()

    return {
        'downside_deviation': downside_deviation,
        'var_95': var_95,
        'cvar_95': cvar_95
    }
```

### 增强的风险分析
```python
def enhanced_risk_analysis(returns, benchmark=None):
    """增强版风险分析"""
    # 基础风险指标
    basic_metrics = risk_analysis(returns)

    # 自定义指标
    custom_metrics = custom_risk_metric(returns)

    # 基准对比
    if benchmark is not None:
        benchmark_metrics = benchmark_analysis(returns, benchmark)
    else:
        benchmark_metrics = {}

    # 合并结果
    all_metrics = {**basic_metrics, **custom_metrics, **benchmark_metrics}

    return pd.DataFrame(all_metrics)
```

## 常见问题 (FAQ)

### Q1: 为什么Qlib使用算术累积而不是几何累积？
算术累积避免了指数级偏斜，更适合量化投资的收益计算，特别是在进行收益分解和归因分析时。

### Q2: 如何处理不同交易日的收益率数据？
确保收益率序列的时间索引是交易日历，使用D.calendar()获取正确的交易日序列。

### Q3: 多空回测中的shift参数有什么作用？
shift=1表示T日预测，T+1日交易，避免未来信息泄漏。

## 相关文件清单

### 核心文件
- `evaluate.py` - 评估分析主模块

### 依赖模块
- `../report/analysis_position/` - 持仓分析工具
- `../strategy/` - 策略实现
- `../../backtest/` - 回测引擎

## 变更记录 (Changelog)

### 2025-11-17 12:53:01 - 第四次增量更新
- ✨ **新增评估分析模块详细文档**：
  - 完整的风险指标计算体系
  - 交易指标分析和回测接口
  - 多空策略回测实现
- 📊 **深度分析核心算法**：
  - 算术累积vs几何累积模式
  - 风险指标计算原理
  - 交易质量评估方法
- 🔗 **完善高级分析功能**：
  - 多时间尺度和滚动分析
  - 风险归因和基准对比
  - 自定义指标扩展指南