# A股财务数据下载指南 (2000-2025)

> **项目**: 下载2000-2025年全部A股财务数据，支持长期回测
> **开始时间**: 2025-12-29 13:15
> **预计完成**: 2-3小时

## 📊 项目概述

### 数据规模

- **时间跨度**: 2000-2025年（26年）
- **股票数量**: 5,466只A股
- **季度数据**: 约104个季度
- **预计记录**: ~500,000条
- **数据字段**: 108个财务指标
- **预计大小**: ~300-500 MB

### 下载阶段

数据分为6个阶段下载：

1. **2020-2022** (12季度) - ✅ 已完成
2. **2015-2019** (20季度) - ⏳ 进行中
3. **2010-2014** (20季度) - ⏳ 待下载
4. **2005-2009** (20季度) - ⏳ 待下载
5. **2000-2004** (20季度) - ⏳ 待下载
6. **2025最新** (已公告数据) - ⏳ 待下载

## 🚀 快速开始

### 1. 检查下载进度

```bash
# 运行监控脚本
python3 qlib/contrib/data/tushare/check_download_progress.py

# 或查看实时日志
tail -f /tmp/financial_extended_force.log
```

### 2. 查看进程状态

```bash
# 检查下载进程
ps -p 51049

# 查看CPU和内存使用
top -pid 51049
```

### 3. 下载完成后的操作

```bash
# 验证和合并数据
python3 qlib/contrib/data/tushare/validate_and_merge_financial_data.py
```

## 📁 文件结构

### 下载脚本

```
qlib/contrib/data/tushare/
├── download_extended_force.py          # 强制下载脚本（运行中）
├── download_extended_test.py           # 测试下载脚本
├── download_extended_financial.py      # 标准下载脚本
├── check_download_progress.py          # 进度监控工具 ✨
└── validate_and_merge_financial_data.py # 数据验证合并工具 ✨
```

### 数据文件

```
~/.qlib/qlib_data/cn_data/financial_data/
├── phase_2020_2022.csv                # 2020-2022阶段数据 ✅
├── phase_2015_2019.csv                # 2015-2019阶段数据 ⏳
├── phase_2010_2014.csv                # 2010-2014阶段数据 ⏳
├── phase_2005_2009.csv                # 2005-2009阶段数据 ⏳
├── phase_2000_2004.csv                # 2000-2004阶段数据 ⏳
├── phase_2025_latest.csv               # 2025最新数据 ⏳
├── a_share_financial_latest.csv       # 最新完整数据（2023-2024）
└── a_share_financial_2000_2025_*.csv  # 最终合并数据（待生成）
```

## 📊 数据字段

### 基本信息
- `ts_code`: 股票代码
- `ann_date`: 公告日期
- `end_date`: 报告期

### 每股指标
- `eps`: 每股收益
- `bps`: 每股净资产
- `ocfps`: 每股经营现金流
- `cfps`: 每股现金流

### 盈利能力
- `roe`: 净资产收益率
- `roa`: 总资产收益率
- `grossprofit_margin`: 毛利率
- `netprofit_margin`: 净利率

### 成长能力
- `or_yoy`: 营收同比增长率
- `op_yoy`: 营业利润同比增长率
- `netprofit_yoy`: 净利润同比增长率

### 估值指标
- `pe`: 市盈率
- `pb`: 市净率
- `ps`: 市销率

### 偿债能力
- `debt_to_assets`: 资产负债率
- `current_ratio`: 流动比率
- `quick_ratio`: 速动比率

## ⏱️ 下载进度监控

### 实时监控

```bash
# 方法1: 使用监控脚本（推荐）
python3 qlib/contrib/data/tushare/check_download_progress.py

# 方法2: 查看日志
tail -f /tmp/financial_extended_force.log

# 方法3: 检查进程
ps -p 51049 && echo "运行中" || echo "已结束"
```

### 监控输出说明

```
1️⃣ 进程状态
   ✅ 运行中 / ❌ 已结束
   CPU使用率、内存占用、运行时间

2️⃣ 下载进度
   当前进度: XXX/5466 (XX.X%)
   下载速度: X.XX 只/秒
   预计剩余: X小时X分

3️⃣ 阶段文件
   已完成的阶段统计
   每阶段的记录数、股票数、时间范围

4️⃣ 数据验证
   现有数据统计
   年份范围、字段数量
```

## 🔍 数据质量验证

### 自动验证

下载完成后运行验证脚本：

```bash
python3 qlib/contrib/data/tushare/validate_and_merge_financial_data.py
```

### 验证项目

1. **完整性检查**
   - 所有6个阶段是否完成
   - 记录数是否符合预期
   - 股票覆盖率

2. **质量检查**
   - 缺失值统计
   - 重复记录检测
   - 数据范围验证

3. **合并处理**
   - 去除重复记录
   - 保留最新公告
   - 生成最终数据集

## 💾 数据使用

### 方法1: pandas直接读取

```python
import pandas as pd
from pathlib import Path

# 读取最新数据
data_file = Path("~/.qlib/qlib_data/cn_data/financial_data/a_share_financial_latest.csv")
df = pd.read_csv(data_file)

# 查看2020-2022数据
df_2020_2022 = df[df['end_date'].astype(str).str[:4].between('2020', '2022')]

# 查看特定股票
ping_an = df[df['ts_code'] == '000001.SZ']
print(ping_an[['end_date', 'roe', 'or_yoy', 'pe']].tail(10))
```

### 方法2: Qlib集成

```python
from qlib import init
from qlib.data import D
import pandas as pd

# 初始化Qlib
init(provider_uri="~/.qlib/qlib_data/cn_data", region="cn")

# 加载财务数据
financial_file = "~/.qlib/qlib_data/cn_data/financial_data/a_share_financial_latest.csv"
financial_df = pd.read_csv(financial_file)

# 计算财务因子
latest_financial = financial_df.sort_values('end_date').groupby('ts_code').last()

# 创建ROE因子
roe_factor = latest_financial['roe']
print(f"ROE因子: {len(roe_factor)} 只股票")
```

### 方法3: 回测应用

```python
# 使用2020年财务数据选股，在2021年回测
df_2020 = df[df['end_date'] == '20201231'].copy()

# 选股条件：高ROE、高增长、低估值
selected_stocks = df_2020[
    (df_2020['roe'] > 15) &
    (df_2020['or_yoy'] > 10) &
    (df_2020['pe'] < 20)
]['ts_code'].tolist()

print(f"选出 {len(selected_stocks)} 只股票")

# 使用Qlib回测
# ...
```

## 📈 数据应用场景

### 1. 长期回测

**26年数据可用于**:
- 多周期策略验证
- 牛熊市表现分析
- 长期因子有效性研究
- 经济周期影响分析

**示例**:
```python
# 2000-2025分时段回测
periods = [
    ('2000-2010', '20000101', '20101231'),
    ('2010-2020', '20100101', '20201231'),
    ('2020-2025', '20200101', '20251231')
]

for period_name, start, end in periods:
    # 回测该时期表现
    backtest_results = run_backtest(start, end)
    print(f"{period_name}: {backtest_results['return']}")
```

### 2. 财务因子分析

**研究内容**:
- ROE长期分布特征
- 营收增长的持续性
- 估值因子历史表现
- 质量因子有效性

**示例**:
```python
# ROE历史分布
df['year'] = df['end_date'].astype(str).str[:4]
roe_by_year = df.groupby('year')['roe'].mean()

print("各年平均ROE:")
print(roe_by_year)
```

### 3. 行业对比

**跨行业分析**:
- 行业盈利能力对比
- 行业成长性分析
- 行业估值水平
- 行业周期性研究

### 4. 个股深度分析

**个股案例**:
- 长期财务表现
- 竞争优势持续性
- 管理层能力评估
- 风险因素识别

## ⚠️ 注意事项

### 1. API限流

- TuShare免费账户: 200次/分钟
- 下载间隔: 0.2秒/请求
- 请勿频繁中断和重启

### 2. 数据完整性

- 早期数据(2000-2005)可能不完整
- 部分股票缺少某些字段
- ST股票数据可能异常
- 建议使用前验证数据

### 3. 时间成本

- 总耗时: 2-3小时
- 请在稳定网络环境下运行
- 建议使用nohup后台运行
- 避免终端关闭导致中断

### 4. 存储空间

- 预计占用: 300-500 MB
- 确保磁盘空间充足
- 定期清理临时文件

## 🛠️ 故障排除

### 问题1: 进程中断

**现象**: 下载进程意外终止

**解决方案**:
```bash
# 检查进程状态
ps -p 51049

# 如果已结束，查看日志
tail -100 /tmp/financial_extended_force.log

# 重新启动下载
cd /Users/berton/Github/qlib
nohup python3 -u qlib/contrib/data/tushare/download_extended_force.py > /tmp/financial_extended_force.log 2>&1 &
```

### 问题2: 数据不完整

**现象**: 某些阶段数据缺失

**解决方案**:
```bash
# 检查阶段文件
ls -lh ~/.qlib/qlib_data/cn_data/financial_data/phase_*.csv

# 如果缺少某些阶段，单独重新下载
python3 -c "
from qlib.contrib.data.tushare.download_extended_force import download_specific_phase
download_specific_phase('2015-2019', '20150101', '20191231')
"
```

### 问题3: 内存不足

**现象**: 下载脚本内存占用过高

**解决方案**:
- 脚本已实现分批保存（每200只股票）
- 确保系统有足够可用内存
- 关闭其他占用内存的程序

### 问题4: 网络超时

**现象**: API请求频繁超时

**解决方案**:
- 检查网络连接
- 增加请求间隔（修改脚本中的DELAY参数）
- 使用更稳定的网络环境

## 📞 技术支持

### 日志位置

- 下载日志: `/tmp/financial_extended_force.log`
- 错误信息: 查看日志最后100行

### 相关文档

- TuShare API文档: https://tushare.pro/document/2
- Qlib文档: https://qlib.readthedocs.io/
- 财务数据指南: `FINANCIAL_DATA_README.md`

## 🎯 预期成果

### 下载完成后

1. **数据文件**
   - `a_share_financial_2000_2025_*.csv`: 完整26年数据
   - `a_share_financial_latest.csv`: 最新版本（含历史数据）
   - `FINANCIAL_DATA_2000_2025_SUMMARY.md`: 数据汇总报告

2. **数据统计**
   - 总记录: ~500,000条
   - 股票数: 5,466只
   - 年份范围: 2000-2025（26年）
   - 季度数: ~104个

3. **应用价值**
   - 支持长期回测（10年+）
   - 多市场周期验证
   - 财务因子深度分析
   - 价值投资策略研究

## 📝 更新日志

### 2025-12-29 13:15
- ✨ 启动2000-2025财务数据下载
- ✅ 完成2020-2022阶段下载
- 📊 创建进度监控工具
- 🔧 创建数据验证合并工具
- 📚 完善使用文档

---

**开始时间**: 2025-12-29 13:15
**预计完成**: 2025-12-29 15:30-16:30
**当前状态**: ⏳ 下载进行中 (进程 PID: 51049)
