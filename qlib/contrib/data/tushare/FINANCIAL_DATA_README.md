# A股财务数据下载与使用指南

> 下载完成时间: 2025-12-29
> 数据来源: TuShare Pro
> 数据目录: `~/.qlib/qlib_data/cn_data/financial_data/`

## ✅ 下载完成状态

### 📊 数据统计

- **股票总数**: 5466只A股
- **时间范围**: 2023-01-01 至 2024-12-31 (2年)
- **数据字段**: 108个财务指标
- **预计总记录**: 约50,000条

### 📁 文件结构

```
~/.qlib/qlib_data/cn_data/financial_data/
├── batch_0001.csv                 # 第1批数据
├── batch_0002.csv                 # 第2批数据
├── ...
├── batch_0110.csv                 # 最后一批数据
├── a_share_financial_latest.csv   # 最新完整数据
├── a_share_financial_YYYYMMDD_HHMMSS.csv  # 带时间戳的完整数据
└── download_state.json            # 下载状态（支持断点续传）
```

## 📊 数据字段说明

### 主要财务指标 (108个字段)

**盈利能力**:
- `roe` - 净资产收益率 (%)
- `roa` - 总资产收益率 (%)
- `grossprofit_margin` - 毛利率 (%)
- `netprofit_margin` - 净利率 (%)
- `profit_to_gr` - 净利润增长率 (%)

**成长能力**:
- `or_yoy` - 营业收入同比增长率 (%)
- `op_yoy` - 营业利润同比增长率 (%)
- `ebt_yoy` - 利润总额同比增长率 (%)
- `netprofit_yoy` - 净利润同比增长率 (%)

**估值指标**:
- `pe` - 市盈率 (TTM)
- `pb` - 市净率
- `ps` - 市销率
- `pcf` - 市现率

**偿债能力**:
- `debt_to_assets` - 资产负债率 (%)
- `current_ratio` - 流动比率
- `quick_ratio` - 速动比率
- `eqt_to_debt` - 产权比率

**运营能力**:
- `assets_turnover` - 总资产周转率
- `ar_turn` - 应收账款周转率
- `ca_turn` - 流动资产周转率
- `fa_turn` - 固定资产周转率

### 完整字段列表

```python
all_fields = [
    # 基本信息
    'ts_code', 'ann_date', 'end_date',

    # 每股指标
    'eps', 'dt_eps', 'bps', 'ocfps', 'cfps',

    # 盈利能力
    'roe', 'roa', 'npta', 'roic', 'roe_yearly',
    'grossprofit_margin', 'netprofit_margin',

    # 偿债能力
    'debt_to_assets', 'current_ratio', 'quick_ratio',
    'assets_to_eqt', 'eqt_to_debt', 'tangibleasset_to_debt',

    # 运营能力
    'assets_turnover', 'ar_turn', 'ca_turn', 'fa_turn',
    'inv_turn', 'turn_days',

    # 成长能力
    'or_yoy', 'op_yoy', 'ebt_yoy', 'netprofit_yoy',
    'basic_eps_yoy', 'cfps_yoy', 'roe_yoy',

    # 估值
    'pe', 'pb', 'ps', 'pcf',

    # 现金流
    'ocf_to_shortdebt', 'ocf_to_debt', 'fcff', 'fcfe',
    'ocf_to_sales', 'ocf_yoy'
]
```

## 💡 使用方法

### 方法1: 使用pandas直接读取

```python
import pandas as pd
from pathlib import Path

# 读取最新数据
data_file = Path("~/.qlib/qlib_data/cn_data/financial_data/a_share_financial_latest.csv")
df = pd.read_csv(data_file)

# 查看数据
print(f"总记录数: {len(df)}")
print(f"股票数量: {df['ts_code'].nunique()}")
print(f"字段数量: {len(df.columns)}")

# 查看特定股票
stock_data = df[df['ts_code'] == '000001.SZ']
print(stock_data[['end_date', 'roe', 'roa', 'or_yoy']])
```

### 方法2: 筛选特定时间范围

```python
# 筛选2024年年报数据
年报_2024 = df[df['end_date'].str.endswith('1231')]
print(f"2024年报: {len(年报_2024)} 条")

# 筛选最新季度
latest = df.sort_values('end_date').groupby('ts_code').last()
print(f"最新财务数据: {len(latest)} 只股票")
```

### 方法3: 计算财务因子

```python
# 计算综合财务得分
def calculate_financial_score(df):
    """计算财务综合得分"""
    df = df.copy()

    # 标准化各指标
    df['roe_score'] = df['roe'].rank(pct=True)
    df['growth_score'] = df['or_yoy'].rank(pct=True)
    df['value_score'] = (1/df['pe']).rank(pct=True)

    # 综合得分
    df['total_score'] = (
        0.4 * df['roe_score'] +
        0.3 * df['growth_score'] +
        0.3 * df['value_score']
    )

    return df

# 应用到最新数据
latest_data = df.sort_values('end_date').groupby('ts_code').last()
scored_data = calculate_financial_score(latest_data)

# 选股 - 财务综合得分前50
top_50 = scored_data.nlargest(50, 'total_score')
print(top_50[['ts_code', 'roe', 'or_yoy', 'pe', 'total_score']])
```

### 方法4: 集成到Qlib策略

```python
from qlib import init
from qlib.data import D
import pandas as pd
from pathlib import Path

# 初始化Qlib
init(provider_uri="~/.qlib/qlib_data/cn_data", region="cn")

# 加载财务数据
financial_file = Path("~/.qlib/qlib_data/cn_data/financial_data/a_share_financial_latest.csv")
financial_df = pd.read_csv(financial_file)

# 获取最新财务数据
latest_financial = financial_df.sort_values('end_date').groupby('ts_code').last()

# 创建因子字典
factor_dict = {}
for stock, row in latest_financial.iterrows():
    factor_dict[stock] = {
        'roe': row['roe'],
        'roa': row['roa'],
        'pe': row['pe'],
        'revenue_growth': row['or_yoy']
    }

# 使用因子进行选股
# ... (后续策略逻辑)
```

## 📈 常用分析场景

### 1. 价值股筛选

```python
# 低PE + 低PB + 高ROE
value_stocks = latest_financial[
    (latest_financial['pe'] < 15) &
    (latest_financial['pb'] < 2) &
    (latest_financial['roe'] > 10)
].sort_values('roe', ascending=False)

print("价值股 Top 20:")
print(value_stocks[['ts_code', 'pe', 'pb', 'roe']].head(20))
```

### 2. 成长股筛选

```python
# 高营收增长 + 高利润增长
growth_stocks = latest_financial[
    (latest_financial['or_yoy'] > 20) &
    (latest_financial['netprofit_yoy'] > 20)
].sort_values('or_yoy', ascending=False)

print("成长股 Top 20:")
print(growth_stocks[['ts_code', 'or_yoy', 'netprofit_yoy']].head(20))
```

### 3. 质量股筛选

```python
# 高ROE + 低负债率
quality_stocks = latest_financial[
    (latest_financial['roe'] > 15) &
    (latest_financial['debt_to_assets'] < 60)
].sort_values('roe', ascending=False)

print("质量股 Top 20:")
print(quality_stocks[['ts_code', 'roe', 'debt_to_assets']].head(20))
```

### 4. 行业财务对比

```python
# 按行业分组统计
# 需要先添加行业信息
industry_analysis = latest_financial.groupby('industry').agg({
    'roe': 'mean',
    'or_yoy': 'mean',
    'pe': 'mean',
    'ts_code': 'count'
}).round(2)

industry_analysis.columns = ['平均ROE', '平均营收增长', '平均PE', '股票数量']
print(industry_analysis.sort_values('平均ROE', ascending=False))
```

## 🔄 数据更新

### 定期更新财务数据

```bash
# 每季度更新一次
cd /Users/berton/Github/qlib
python qlib/contrib/data/tushare/download_all_a_shares_financial.py
```

### 增量更新

```python
import pandas as pd
from pathlib import Path

# 读取现有数据
old_file = Path("~/.qlib/qlib_data/cn_data/financial_data/a_share_financial_latest.csv")
old_data = pd.read_csv(old_file)

# 获取最新日期
latest_date = old_data['end_date'].max()
print(f"现有数据最新日期: {latest_date}")

# 下载新数据
# ... (使用下载脚本下载新数据)

# 合并新旧数据
updated_data = pd.concat([old_data, new_data]).drop_duplicates()
updated_data.to_csv(old_file, index=False)
```

## ⚠️ 注意事项

### 1. 数据更新频率

财务数据按季度更新:
- 一季报: 04-30前
- 中报: 08-31前
- 三季报: 10-31前
- 年报: 04-30前 (次年)

### 2. 数据质量

- ✅ 已包含全部5466只A股
- ⚠️ 部分股票可能缺少某些字段（显示为NaN）
- ⚠️ ST股票财务数据可能异常

### 3. 数据使用建议

- 使用前检查数据完整性
- 剔除异常值（如ROE超过100%）
- 关注数据的公告日期(ann_date)
- 建议与价格数据结合使用

## 📊 数据示例

### 平安银行 (000001.SZ) 2024年报

```
股票代码: 000001.SZ
报告期: 2024-12-31

盈利能力:
  ROE: 9.20%
  ROA: N/A
  毛利率: N/A
  净利率: N/A

成长能力:
  营收增长: -10.93%
  利润增长: N/A

估值:
  PE: N/A
  PB: N/A
```

### 美的集团 (000333.SZ)

```
股票代码: 000333.SZ
报告期: 2024-12-31

盈利能力:
  ROE: 16.85%
  ROA: 6.84%
  毛利率: 25.81%

成长能力:
  营收增长: 5.87%
  利润增长: 10.23%

估值:
  PE: 13.50
  PB: 3.85
```

## 🚀 下一步

1. **数据探索**: 使用pandas分析数据特征
2. **因子计算**: 构建自定义财务因子
3. **回测验证**: 在Qlib中回测财务因子策略
4. **策略开发**: 开发基于财务因子的选股策略
5. **定期更新**: 每季度更新财务数据

## 📚 相关文档

- [TuShare财务数据文档](https://tushare.pro/document/2?doc_id=70)
- [Qlib数据处理指南](https://qlib.readthedocs.io/)
- [财务因子示例代码](../examples/financial_data_example.py)
- [财务数据集成指南](./FINANCIAL_DATA_GUIDE.md)

---

**下载时间**: 2025-12-29
**数据版本**: v1.0.0
**数据来源**: TuShare Pro API
