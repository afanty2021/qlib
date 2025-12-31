# 股票复权处理完整指南

> 详细说明股票分红、送股、配股等除权除息事件的处理方法

## 📋 目录

- [除权除息基础知识](#除权除息基础知识)
- [复权类型详解](#复权类型详解)
- [复权计算原理](#复权计算原理)
- [使用方法](#使用方法)
- [代码示例](#代码示例)
- [常见问题](#常见问题)

## 🎯 除权除息基础知识

### 什么是除权除息？

**除权除息** 是上市公司向股东分配利润或进行股本变动时，对股票价格进行的调整。

### 常见事件类型

| 事件类型 | 说明 | 对股价的影响 | 例子 |
|---------|------|-------------|------|
| **现金分红** | 以现金形式分配利润 | 股价扣除分红金额 | 每股分红 0.5 元，股价 10元→9.5元 |
| **送股** | 以股票形式分配利润 | 股价按比例降低 | 10送10，股价 10元→5元 |
| **转增** | 公积金转增股本 | 股价按比例降低 | 10转10，股价 10元→5元 |
| **配股** | 向原股东配售新股 | 股价综合调整 | 10配3，配股价8元 |
| **拆股** | 一股拆分成多股 | 股价按比例降低 | 1拆2，股价 10元→5元 |

### 为什么需要复权？

**问题**：如果不进行复权，价格数据会出现断层，无法进行准确的分析。

**例子**：
```
股票 A 的历史价格：
2024-06-10: 20.00 元 (除权日)
2024-06-09: 40.00 元 (10送10)

看起来股价跌了 50%，但实际上是送股导致的除权！
```

**解决**：通过复权因子调整历史价格，使价格数据具有可比性。

## 🔍 复权类型详解

### 1. 前复权 (QFQ - Quote Forward Adjustment)

**原理**：保持当前价格不变，调整历史价格

**计算公式**：
```
复权价格 = 原始价格 × 当日复权因子
```

**TuShare 字段**：
- `adj_factor`: 复权因子
- `adj_close`: 前复权收盘价 = `close × adj_factor`

**适用场景**：
- ✅ 技术分析（K线图、技术指标）
- ✅ 短线交易
- ✅ 趋势判断
- ✅ 回测系统

**优点**：
- 当前价格真实，与市场一致
- 方便进行实时分析

**缺点**：
- 历史价格会变化，与当时实际不符
- 随时间推移，早期价格可能变得很小

**示例**：
```
日期          原始价格    复权因子    前复权价格
2024-06-09    40.00      0.5000     20.00  (送股前)
2024-06-10    20.00      1.0000     20.00  (送股后，当前价格不变)
```

### 2. 后复权 (HFQ - Quote Backward Adjustment)

**原理**：保持最早价格不变，调整当前价格

**计算公式**：
```
归一化因子 = 当日复权因子 / 首日复权因子
复权价格 = 原始价格 × 归一化因子
```

**适用场景**：
- ✅ 长期投资分析
- ✅ 收益率计算
- ✅ 历史走势研究

**优点**：
- 历史价格真实，反映当时实际情况
- 长期趋势清晰

**缺点**：
- 当前价格可能与实际市场价差距较大
- 不适合实时分析

**示例**：
```
日期          原始价格    复权因子    归一化因子    后复权价格
2024-06-09    40.00      0.5000     1.0000       40.00  (最早价格不变)
2024-06-10    20.00      1.0000     2.0000       40.00  (当前价格调整)
```

### 3. 不复权 (None)

**原理**：保持原始价格，不做任何调整

**适用场景**：
- ✅ 当日交易分析
- ✅ 事件研究
- ✅ 历史数据查询

**优点**：
- 完全真实的历史价格

**缺点**：
- 不同时期价格不可比
- 除权除息日会有价格跳空

## 🧮 复权计算原理

### TuShare 复权因子机制

**复权因子定义**：
```
adj_factor = 当日调整后的价格 / 当日原始价格
```

**累积计算**：
```
adj_factor[n] = adj_factor[n-1] × (1 + 股本变动比例) × (1 - 现金分红比例)
```

### 前复权计算示例

假设股票 A 发生了以下事件：

```
日期          事件          原始收盘价    复权因子
2024-01-01    -            10.00        1.0000
2024-06-01    10送5        15.00        0.6667  (10/15)
2024-12-01    现金分红      12.00        0.6400  (12 × 0.6667 / 12.5)
```

**前复权价格**：
```
2024-01-01: 10.00 × 0.6400 = 6.40 元
2024-06-01: 15.00 × 0.6667 = 10.00 元 (除权后当前价)
2024-12-01: 12.00 × 0.6400 = 7.68 元 (除权后当前价)
```

### 后复权计算示例

**归一化因子**：
```
归一化因子 = 当日复权因子 / 首日复权因子
首日归一化因子 = 1.0000

2024-01-01: 1.0000 / 1.0000 = 1.0000
2024-06-01: 0.6667 / 1.0000 = 0.6667
2024-12-01: 0.6400 / 1.0000 = 0.6400
```

**后复权价格**：
```
2024-01-01: 10.00 × 1.0000 = 10.00 元 (保持首日价格不变)
2024-06-01: 15.00 × 0.6667 = 10.00 元
2024-12-01: 12.00 × 0.6400 = 7.68 元
```

## 📖 使用方法

### 1. 可视化复权效果

```bash
# 运行复权演示脚本
python scripts/adjust_factor_handler.py

# 生成图表展示不同复权类型的效果
```

输出：
```
除权除息事件类型说明
============================

📌 现金分红
   说明: 公司以现金形式向股东分配利润
   影响: 股价需要扣除分红金额
   ...
```

### 2. 下载复权数据

```python
from scripts.adjust_factor_handler import AdjustFactorHandler

# 创建处理器
handler = AdjustFactorHandler()

# 下载前复权数据
handler.download_and_save_adjusted_data(
    symbols=["000001.SZ", "000002.SZ"],
    start_date="20200101",
    end_date="20241231",
    adjust_type="qfq"  # qfq, hfq, none
)

# 输出文件
# ~/.qlib/qlib_data/cn_data/stock_data_qfq.csv  (前复权)
# ~/.qlib/qlib_data/cn_data/stock_data_hfq.csv  (后复权)
# ~/.qlib/qlib_data/cn_data/stock_data_none.csv (不复权)
```

### 3. 计算复权价格

```python
# 获取价格数据
price_df = pd.DataFrame({
    "tradedate": ["20241201", "20241202"],
    "symbol": ["000001.SZ", "000001.SZ"],
    "close": [10.0, 10.5]
})

# 获取复权因子
adj_factor_df = handler.get_adj_factor(
    ts_code="000001.SZ",
    start_date="20241201",
    end_date="20241202"
)

# 计算前复权价格
adjusted_df = handler.calculate_adjusted_price(
    price_df=price_df,
    adj_factor_df=adj_factor_df,
    adjust_type="qfq"
)

print(adjusted_df[["tradedate", "symbol", "close", "adj_close"]])
```

### 4. 可视化对比

```python
# 生成复权对比图
handler.visualize_adjustment(
    symbol="000001.SZ",
    start_date="20240101",
    end_date="20241231"
)

# 图表保存路径
# ~/.qlib/qlib_data/cn_data/adjustment_charts/000001.SZ_adjustment_comparison.png
```

## 💻 代码示例

### 示例 1: 获取复权因子

```python
import os
os.environ["TUSHARE_TOKEN"] = "your_token"

from qlib.contrib.data.tushare.api_client import TuShareAPIClient
from qlib.contrib.data.tushare.config import TuShareConfig

# 初始化客户端
config = TuShareConfig(token=os.getenv("TUSHARE_TOKEN"))
client = TuShareAPIClient(config)

# 获取复权因子
data = client._make_request("adj_factor", {
    "ts_code": "000001.SZ",
    "start_date": "20240101",
    "end_date": "20241231"
})

# 转换为 DataFrame
import pandas as pd
adj_factor_df = pd.DataFrame(data["items"], columns=data["fields"])

print(adj_factor_df.head())
```

### 示例 2: 计算前复权价格

```python
# 原始价格
price = 10.0  # 元
adj_factor = 0.8  # 复权因子

# 前复权价格
adj_price = price * adj_factor
print(f"前复权价格: {adj_price:.2f} 元")
```

### 示例 3: 计算后复权价格

```python
# 获取一段时间的数据
adj_factors = [1.0, 0.9, 0.8, 0.75, 0.7]  # 复权因子序列
first_factor = adj_factors[0]  # 首日因子

# 归一化因子
normalized_factors = [f / first_factor for f in adj_factors]

# 原始价格
prices = [10.0, 10.5, 11.0, 10.8, 11.2]

# 后复权价格
adj_prices = [p * n for p, n in zip(prices, normalized_factors)]

print(f"后复权价格: {adj_prices}")
```

### 示例 4: 检测除权事件

```python
import pandas as pd

# 读取复权因子数据
adj_factor_df = pd.read_csv("adj_factors.csv")

# 计算复权因子变化
adj_factor_df["factor_change"] = adj_factor_df["adj_factor"].pct_change()

# 找出变化超过 5% 的日期（可能有除权事件）
events = adj_factor_df[abs(adj_factor_df["factor_change"]) > 0.05]

print("除权事件日期:")
print(events[["tradedate", "adj_factor", "factor_change"]])
```

## 📊 常见问题

### Q1: 什么时候使用前复权，什么时候使用后复权？

**A**:
- **技术分析、短线交易**：使用前复权，当前价格真实
- **长期投资、收益率计算**：使用后复权，历史趋势清晰
- **当日交易、事件研究**：使用不复权，完全真实

### Q2: TuShare 的复权因子准确吗？

**A**: TuShare 的复权因子由专业团队维护，综合考虑了各种除权除息事件，准确度较高。但仍建议：
- 定期检查复权因子的合理性
- 对比多个数据源验证
- 关注特殊事件（如借壳上市）

### Q3: 如何验证复权是否正确？

**A**: 可以通过以下方式验证：
1. **对比除权日前后的价格**
2. **检查复权因子的变化趋势**
3. **可视化复权前后的价格走势**
4. **对比官方数据（如交易所公告）**

### Q4: 复权数据多久更新一次？

**A**:
- **复权因子**：每次除权除息事件后更新
- **建议更新频率**：每日收盘后更新一次
- **全量更新**：每月一次，确保历史数据正确

### Q5: 配股如何复权？

**A**: 配股的复权计算比较复杂：
```
配股复权因子 = (原收盘价 + 配股比例 × 配股价) / (1 + 配股比例) / 原收盘价
```

TuShare 已经处理了配股的复权因子，直接使用即可。

### Q6: 为什么有些股票没有复权因子？

**A**: 可能的原因：
1. **新上市股票**：还没有除权除息记录
2. **数据缺失**：TuShare 数据缺失
3. **特殊股票**：如 ST 股票、退市股票

处理方法：
- 使用原始价格（不复权）
- 标记数据缺失，谨慎使用

### Q7: 复权因子会变吗？

**A**: **会！**
- **未来除权**：未发生的除权事件，复权因子可能变化
- **数据修正**：TuShare 可能修正历史复权因子
- **建议**：定期更新复权因子数据

### Q8: 如何在回测中使用复权数据？

**A**:
```python
# 回测时使用前复权数据
from qlib import init
from qlib.data import D

# 初始化（使用前复权数据）
init(provider_uri="~/.qlib/qlib_data/cn_data_qfq")

# 获取前复权价格
instruments = D.instruments("csi300")
features = D.features(
    instruments,
    ["close", "volume"],  # 这些价格已是前复权价格
    start_time="2020-01-01",
    end_time="2024-12-31"
)

# 进行回测...
```

## 📚 参考资料

- [TuShare 官方文档 - 复权因子](https://tushare.pro/document/2?doc_id=170)
- [Qlib 数据处理文档](https://qlib.readthedocs.io/)
- [investment_data 项目](https://github.com/chenditc/investment_data)

## 🔄 更新日志

### v1.0.0 (2025-01-19)
- ✨ 初始版本发布
- 📊 支持前复权、后复权、不复权
- 🎨 复权效果可视化
- 📚 详细的文档和示例
