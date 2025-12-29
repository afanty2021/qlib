# TuShare财务数据与Qlib集成指南

> 完整的财务数据获取、因子计算和Qlib集成方案

## 📊 TuShare财务数据接口概览

### ✅ 支持的财务数据类型

TuShare提供了丰富的财务数据接口：

| 数据类型 | 接口名称 | 主要字段 | 说明 |
|---------|---------|---------|------|
| **利润表** | `income` | 营业收入、营业成本、净利润等 | 公司盈利情况 |
| **资产负债表** | `balancesheet` | 总资产、总负债、股东权益等 | 资产负债结构 |
| **现金流量表** | `cashflow` | 经营现金流、投资现金流等 | 现金流动情况 |
| **财务指标** | `fina_indicator` | ROE、ROA、毛利率等 | **最常用** |
| **分红送股** | `dividend` | 分红、送股、转增等 | 股东回报 |
| **业绩预告** | `forecast` | 预告净利润、增长率等 | 业绩前瞻 |
| **业绩快报** | `expression` | 快报财务数据 | 业绩速览 |

### 🔑 关键财务指标

**盈利能力指标**:
- `roe` - 净资产收益率
- `roa` - 总资产收益率
- `grossprofit_margin` - 毛利率
- `netprofit_margin` - 净利率

**成长能力指标**:
- `or_yoy` - 营业收入同比增长率
- `op_yoy` - 营业利润同比增长率

**估值指标**:
- `pe` - 市盈率
- `pb` - 市净率
- `ps` - 市销率

**偿债能力指标**:
- `debt_to_assets` - 资产负债率
- `current_ratio` - 流动比率
- `quick_ratio` - 速动比率

**运营能力指标**:
- `assets_turnover` - 总资产周转率
- `ar_turnover` - 应收账款周转率
- `inv_turnover` - 存货周转率

## 🚀 快速开始

### 1. 下载财务数据

```python
import tushare as ts

# 初始化
pro = ts.pro_api('your_token')

# 下载财务指标 (最常用)
df = pro.fina_indicator(
    ts_code='000001.SZ',    # 股票代码
    start_date='20200101',  # 开始日期
    end_date='20241231'     # 结束日期
)

print(df.head())
```

**输出示例**:
```
     ts_code  end_date    ann_date  roe   roa  grossprofit_margin  ...
0  000001.SZ  20241231  2025-03-31  12.5  1.2              45.2  ...
1  000001.SZ  20240930  2024-10-25  13.2  1.3              46.1  ...
2  000001.SZ  20240630  2024-08-20  11.8  1.1              44.8  ...
```

### 2. 批量下载多只股票

```python
# 获取股票列表
stocks = pro.stock_basic(
    exchange='',
    list_status='L',
    fields='ts_code,name'
)

# 批量下载财务指标
all_financial_data = []

for stock in stocks['ts_code'].head(100):  # 先下载100只
    try:
        df = pro.fina_indicator(
            ts_code=stock,
            start_date='20240101',
            end_date='20241231'
        )
        all_financial_data.append(df)
    except Exception as e:
        print(f"❌ {stock} 下载失败: {e}")

# 合并数据
financial_df = pd.concat(all_financial_data, ignore_index=True)
```

## 🔧 Qlib集成方案

### 方案1: 通过DataLoader集成

Qlib支持自定义DataLoader来加载财务数据：

```python
from qlib.data.dataset import DataLoader
from qlib.data.dataset.handler import DataHandlerLP

class FinancialDataLoader(DataLoader):
    """财务数据加载器"""

    def load(self, instruments, start_time, end_time):
        """加载财务数据"""
        # 1. 从TuShare下载财务数据
        financial_data = self._download_financial_data(instruments)

        # 2. 转换为Qlib格式
        qlib_data = self._to_qlib_format(financial_data)

        return qlib_data

    def _download_financial_data(self, instruments):
        """从TuShare下载财务数据"""
        import tushare as ts
        pro = ts.pro_api('your_token')

        all_data = []
        for stock in instruments:
            df = pro.fina_indicator(
                ts_code=stock,
                start_date=start_time.replace('-', ''),
                end_date=end_time.replace('-', '')
            )
            all_data.append(df)

        return pd.concat(all_data, ignore_index=True)

    def _to_qlib_format(self, data):
        """转换为Qlib格式"""
        # Qlib期望格式: (date, instrument, feature)
        data['date'] = pd.to_datetime(data['end_date'])
        data['instrument'] = data['ts_code']

        # 选择需要的因子
        factors = data[['date', 'instrument', 'roe', 'roa', 'pe', 'pb']]

        return factors
```

### 方案2: 直接在Handler中定义

```python
from qlib.contrib.data.handler import Alpha158

class FinancialAlpha158(Alpha158):
    """带财务因子的Alpha158"""

    def get_feature_config(self):
        """获取特征配置"""
        # 获取基础Alpha158特征
        base_config = super().get_feature_config()

        # 添加财务因子
        financial_config = {
            "financial": (
                ["$roe", "$roa", "$pe", "$pb", "$debt_ratio"],
                ["roe", "roa", "pe", "pb", "debt_ratio"]
            )
        }

        # 合并配置
        base_config.update(financial_config)

        return base_config
```

### 方案3: 自定义操作符 (推荐)

创建自定义操作符来计算财务因子：

```python
from qlib.data.ops import register_ops

@register_ops
class ROE_Operator:
    """ROE因子操作符"""

    def __init__(self, period=20):
        self.period = period

    def __call__(self, data):
        """
        计算ROE因子

        Args:
            data: 包含财务数据的DataFrame

        Returns:
            ROE因子序列
        """
        # 从预加载的财务数据中获取ROE
        roe_data = self._load_roe_data()

        # 对齐日期
        aligned_roe = self._align_date(data, roe_data)

        return aligned_roe

    def _load_roe_data(self):
        """加载ROE数据"""
        import tushare as ts
        pro = ts.pro_api('your_token')

        # 获取最新的ROE数据
        df = pro.fina_indicator(
            fields='ts_code,end_date,roe'
        )

        return df
```

## 📈 完整集成示例

### 示例: 财务因子选股策略

```python
from qlib import init
from qlib.data import D
from qlib.backtest import backtest
from qlib.contrib.strategy import TopkDropoutStrategy
import pandas as pd

# 1. 初始化Qlib
init(provider_uri="~/.qlib/qlib_data/cn_data", region="cn")

# 2. 下载财务数据
import tushare as ts
pro = ts.pro_api('your_token')

# 获取沪深300股票
instruments = D.instruments('csi300')

# 下载财务指标
financial_data = []
for stock in instruments[:50]:  # 示例: 只处理50只
    df = pro.fina_indicator(
        ts_code=stock,
        start_date='20240101',
        end_date='20241231'
    )
    financial_data.append(df)

financial_df = pd.concat(financial_data, ignore_index=True)

# 3. 计算财务因子
def calculate_financial_score(df):
    """计算综合财务得分"""
    df = df.copy()

    # 标准化各指标
    df['roe_score'] = (df['roe'] - df['roe'].mean()) / df['roe'].std()
    df['roa_score'] = (df['roa'] - df['roa'].mean()) / df['roa'].std()
    df['growth_score'] = (df['or_yoy'] - df['or_yoy'].mean()) / df['or_yoy'].std()

    # 综合得分 (可调整权重)
    df['financial_score'] = (
        0.4 * df['roe_score'] +
        0.3 * df['roa_score'] +
        0.3 * df['growth_score']
    )

    return df

# 计算得分
financial_df = calculate_financial_score(financial_df)

# 4. 获取最新得分作为预测
latest_scores = financial_df.groupby('ts_code').last().reset_index()

# 5. 构建预测序列 (Qlib格式)
predictions = {}
for stock in instruments:
    if stock in latest_scores['ts_code'].values:
        score = latest_scores[latest_scores['ts_code'] == stock]['financial_score'].values[0]
        predictions[stock] = score

# 6. 运行策略
strategy = TopkDropoutStrategy(
    topk=30,
    n_drop=5
)

# 7. 执行回测
portfolio_metrics, indicator_metrics = backtest(
    start_time='2024-01-01',
    end_time='2024-12-31',
    strategy=strategy,
    predictions=predictions
)

print(f"年化收益率: {portfolio_metrics['annualized_return']:.2%}")
print(f"夏普比率: {portfolio_metrics['sharpe']:.2f}")
```

## 💡 最佳实践

### 1. 数据缓存

```python
import pickle
from pathlib import Path

cache_dir = Path("~/.qlib/qlib_data/cn_data/financial_cache").expanduser()
cache_dir.mkdir(parents=True, exist_ok=True)

def get_financial_data_with_cache(stock_code, days=30):
    """带缓存的财务数据获取"""

    cache_file = cache_dir / f"{stock_code}_financial.pkl"

    # 检查缓存
    if cache_file.exists():
        file_time = cache_file.stat().st_mtime
        current_time = time.time()

        # 缓存未过期 (30天)
        if (current_time - file_time) < (days * 24 * 3600):
            with open(cache_file, 'rb') as f:
                return pickle.load(f)

    # 下载新数据
    pro = ts.pro_api('your_token')
    df = pro.fina_indicator(ts_code=stock_code)

    # 保存缓存
    with open(cache_file, 'wb') as f:
        pickle.dump(df, f)

    return df
```

### 2. 增量更新

```python
def update_financial_data():
    """增量更新财务数据"""

    # 获取本地最新数据日期
    local_data = pd.read_csv('financial_data.csv')
    latest_date = local_data['end_date'].max()

    # 只下载新数据
    pro = ts.pro_api('your_token')
    new_data = pro.fina_indicator(
        start_date=latest_date.replace('-', '')
    )

    # 合并数据
    updated_data = pd.concat([local_data, new_data]).drop_duplicates()

    # 保存
    updated_data.to_csv('financial_data.csv', index=False)
```

### 3. 因子标准化

```python
def standardize_factor(df, factor_col, method='zscore'):
    """因子标准化"""

    if method == 'zscore':
        # Z-score标准化
        df[f'{factor_col}_std'] = (
            df[factor_col] - df[factor_col].mean()
        ) / df[factor_col].std()

    elif method == 'rank':
        # 分位数标准化
        df[f'{factor_col}_std'] = df[factor_col].rank(pct=True)

    elif method == 'mad':
        # MAD去极值后标准化
        median = df[factor_col].median()
        mad = (df[factor_col] - median).abs().median()

        # 去极值 (3倍MAD)
        df[factor_col+'_clean'] = df[factor_col].clip(
            median - 3*mad,
            median + 3*mad
        )

        # 标准化
        df[f'{factor_col}_std'] = (
            df[f'{factor_col}_clean'] - median
        ) / mad

    return df
```

### 4. 因子有效性检验

```python
def test_factor_effectiveness(factor_data, return_data):
    """检验因子有效性"""

    from scipy.stats import spearmanr

    # 计算IC (Information Coefficient)
    ic, p_value = spearmanr(factor_data, return_data)

    # 计算ICIR (IC Information Ratio)
    ic_series = []
    for date in factor_data.index.unique():
        daily_factor = factor_data.loc[date]
        daily_return = return_data.loc[date]
        ic, _ = spearmanr(daily_factor, daily_return)
        ic_series.append(ic)

    icir = np.mean(ic_series) / np.std(ic_series)

    print(f"IC: {ic:.4f}")
    print(f"IC p-value: {p_value:.4f}")
    print(f"ICIR: {icir:.4f}")

    return ic, icir
```

## 📊 常用财务因子组合

### 价值因子组合

```python
def calculate_value_score(df):
    """计算价值得分"""
    df = df.copy()

    # PE、PB倒数 (低估值好)
    df['pe_inv'] = 1 / df['pe']
    df['pb_inv'] = 1 / df['pb']

    # 标准化
    df['pe_score'] = (df['pe_inv'] - df['pe_inv'].mean()) / df['pe_inv'].std()
    df['pb_score'] = (df['pb_inv'] - df['pb_inv'].mean()) / df['pb_inv'].std()

    # 价值得分
    df['value_score'] = 0.6 * df['pe_score'] + 0.4 * df['pb_score']

    return df
```

### 成长因子组合

```python
def calculate_growth_score(df):
    """计算成长得分"""
    df = df.copy()

    # 营收增长率、利润增长率
    df['revenue_growth_std'] = (
        df['or_yoy'] - df['or_yoy'].mean()
    ) / df['or_yoy'].std()

    df['profit_growth_std'] = (
        df['op_yoy'] - df['op_yoy'].mean()
    ) / df['op_yoy'].std()

    # 成长得分
    df['growth_score'] = (
        0.5 * df['revenue_growth_std'] +
        0.5 * df['profit_growth_std']
    )

    return df
```

### 质量因子组合

```python
def calculate_quality_score(df):
    """计算质量得分 (盈利质量)"""
    df = df.copy()

    # ROE、ROA、毛利率
    df['roe_std'] = (
        df['roe'] - df['roe'].mean()
    ) / df['roe'].std()

    df['roa_std'] = (
        df['roa'] - df['roa'].mean()
    ) / df['roa'].std()

    df['margin_std'] = (
        df['grossprofit_margin'] - df['grossprofit_margin'].mean()
    ) / df['grossprofit_margin'].std()

    # 质量得分
    df['quality_score'] = (
        0.4 * df['roe_std'] +
        0.3 * df['roa_std'] +
        0.3 * df['margin_std']
    )

    return df
```

## ⚠️ 注意事项

### 1. 数据更新频率

财务数据是**季度更新**的:
- 一季报: 04-30
- 半年报: 08-31
- 三季报: 10-31
- 年报: 04-30 (次年)

### 2. 数据滞后性

- 财务数据有1-2个月滞后
- 使用最新数据时注意实际发布日期
- 可以用`ann_date`字段确认公告日期

### 3. API频率限制

- TuShare对财务数据接口有频率限制
- 建议批量下载并缓存
- 使用积分获取更高额度

### 4. 数据质量

- 检查缺失值和异常值
- 剔除ST股票
- 注意停牌股票

## 🚀 完整工作流

```bash
# 1. 下载财务数据
cd /Users/berton/Github/qlib
python qlib/contrib/data/tushare/examples/financial_data_example.py

# 2. 计算财务因子
python scripts/calculate_financial_factors.py

# 3. 集成到Qlib策略
python strategies/financial_factor_strategy.py

# 4. 回测验证
python backtest/financial_factor_backtest.py
```

## 📚 相关文档

- [TuShare财务数据文档](https://tushare.pro/document/2?doc_id=70)
- [Qlib数据处理器文档](https://qlib.readthedocs.io/en/latest/component/data.html)
- [财务因子示例代码](../examples/financial_data_example.py)

---

**更新时间**: 2025-12-29
**版本**: v1.0.0
