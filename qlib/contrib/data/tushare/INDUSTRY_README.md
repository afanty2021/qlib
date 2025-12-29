# TuShare 行业板块数据扩展

> 为 Qlib 量化投资平台添加完整的行业板块数据支持，提供行业因子计算和分析功能。

## 📋 目录

- [功能概览](#功能概览)
- [快速开始](#快速开始)
- [API 参考](#api-参考)
- [行业因子库](#行业因子库)
- [使用示例](#使用示例)
- [最佳实践](#最佳实践)
- [常见问题](#常见问题)

## 功能概览

### ✨ 新增功能

**1. 行业分类数据接口**
- 支持申万2021、申万旧版、证监会、中信等多种行业分类标准
- 提供一级行业、二级行业、三级行业数据
- 完整的板块成分股信息

**2. 概念板块数据接口**
- 热点概念板块分类
- 概念成分股列表
- 概念板块行情数据

**3. 行业因子计算库**
- **行业动量因子**：捕捉行业趋势
- **行业相对强度因子**：相对市场表现
- **行业集中度因子**：持仓行业集中度
- **行业估值因子**：行业PE/PB估值
- **行业轮动因子**：板块轮动识别
- **跨行业配置因子**：配置偏离度分析

**4. 统一数据接口**
- 与 Qlib 原生接口完全兼容
- 支持行业信息自动标注
- 内置缓存机制提升性能

## 快速开始

### 1. 环境准备

```bash
# 安装 Qlib 和 TuShare
pip install pyqlib tushare

# 设置 TuShare Token
export TUSHARE_TOKEN="your_token_here"
```

### 2. 初始化 Qlib

```python
from qlib import init
from qlib.contrib.data.tushare import TuShareConfig, TuShareProvider

# 配置 TuShare 数据源
config = TuShareConfig.from_env()

# 初始化 Qlib
init(provider_uri="tushare", default_conf={"tushare": config})
```

### 3. 获取行业分类

```python
from qlib.data import D
from qlib.contrib.data.tushare import TuShareProvider

# 创建数据提供者
provider = TuShareProvider(config)

# 获取申万2021一级行业
industry_l1 = provider.get_industry_classification(src="SW2021", level="L1")
print(industry_l1)

# 获取二级行业
industry_l2 = provider.get_industry_classification(src="SW2021", level="L2")
print(industry_l2)
```

### 4. 计算行业因子

```python
# 获取股票列表
instruments = D.instruments('csi300')

# 计算行业动量因子
momentum = provider.get_industry_factors(
    instruments=instruments,
    factor_type="momentum",
    start_time="2024-01-01",
    end_time="2024-12-31",
    window=20
)
print(momentum)
```

## API 参考

### TuShareProvider 新增方法

#### get_industry_classification()

获取行业分类数据

```python
provider.get_industry_classification(
    src="SW2021",    # 行业分类来源: SW2021, SW, ZJH, CITIC
    level="L1"       # 行业级别: L1, L2, L3
) -> pd.DataFrame
```

**返回字段**：
- `industry_code`: 行业代码
- `industry_name`: 行业名称
- `level`: 行业级别
- `is_parent`: 是否为父类

#### get_concept_classification()

获取概念板块分类数据

```python
provider.get_concept_classification(
    id=None  # 概念板块ID（可选）
) -> pd.DataFrame
```

**返回字段**：
- `id`: 概念ID
- `concept_name`: 概念名称
- `concept_type`: 概念类型

#### get_industry_members()

获取指数成分股数据

```python
provider.get_industry_members(
    index_code="000300.SH"  # 指数代码
) -> pd.DataFrame
```

**返回字段**：
- `index_code`: 指数代码
- `con_code`: 成分股代码
- `in_date`: 纳入日期
- `out_date`: 剔除日期

#### get_industry_factors()

计算行业因子

```python
provider.get_industry_factors(
    instruments=["sh600000", ...],  # 股票列表
    factor_type="momentum",          # 因子类型
    start_time="2024-01-01",        # 开始时间
    end_time="2024-12-31",          # 结束时间
    **kwargs                        # 因子参数
) -> pd.DataFrame
```

**支持的因子类型**：
- `"momentum"`: 行业动量因子
  - `window`: 时间窗口（默认20天）
  - `method`: 计算方法（"return", "log_return", "volatility_adjusted"）

- `"relative_strength"`: 行业相对强度因子
  - `benchmark`: 基准类型（"market", "index", "industry_median"）
  - `window`: 时间窗口（默认20天）

- `"concentration"`: 行业集中度因子
  - `holdings`: 持仓数据（必需）

- `"pe_ratio"`: 行业市盈率因子
  - `fundamental_data`: 基本面数据（必需）
  - `method`: 计算方法（"mean", "median", "weighted"）

#### features_with_industry()

获取包含行业信息的特征数据

```python
provider.features_with_industry(
    instruments=["sh600000", ...],
    fields=["close", "volume"],
    start_time="2024-01-01",
    end_time="2024-12-31",
    include_industry=True  # 是否包含行业信息
) -> pd.DataFrame
```

## 行业因子库

### IndustryFactorCalculator

核心因子计算器，提供各类行业因子的计算功能。

#### 初始化

```python
from qlib.contrib.data.tushare.industry_factors import IndustryFactorCalculator

calculator = IndustryFactorCalculator(
    industry_data=industry_df,      # 行业分类数据
    price_data=price_df,            # 价格数据
    index_data=index_df,            # 指数数据（可选）
    industry_classification="SW2021"
)
```

#### 主要方法

**1. calculate_industry_momentum()**

计算行业动量因子

```python
momentum_df = calculator.calculate_industry_momentum(
    window=20,              # 时间窗口
    method="return"         # 计算方法
)
```

**2. calculate_industry_relative_strength()**

计算行业相对强度因子

```python
relative_strength_df = calculator.calculate_industry_relative_strength(
    benchmark="market",     # 基准类型
    window=20              # 时间窗口
)
```

**3. calculate_industry_concentration()**

计算行业集中度因子

```python
concentration_df = calculator.calculate_industry_concentration(
    holdings=holdings_df,  # 持仓数据
    weights=None           # 权重（可选）
)
```

**4. calculate_industry_pe_ratio()**

计算行业市盈率因子

```python
pe_df = calculator.calculate_industry_pe_ratio(
    fundamental_data=fundamental_df,  # 基本面数据
    method="median"                   # 计算方法
)
```

**5. calculate_industry_momentum_rank()**

计算行业动量排名

```python
rank_df = calculator.calculate_industry_momentum_rank(
    window=20,
    rank_method="dense"  # 排名方法
)
```

**6. calculate_industry_rotation()**

计算行业轮动因子

```python
rotation_df = calculator.calculate_industry_rotation(
    lookback=5,        # 回溯期数
    threshold=0.3      # 强势行业阈值
)
```

### 辅助函数

**calculate_industry_exposure()**

计算股票对目标行业的暴露度

```python
from qlib.contrib.data.tushare.industry_factors import calculate_industry_exposure

exposure_df = calculate_industry_exposure(
    stock_industry_map=industry_df,
    target_industries=['电气设备', '电子', '计算机']
)
```

**normalize_industry_factors()**

标准化行业因子

```python
from qlib.contrib.data.tushare.industry_factors import normalize_industry_factors

normalized_df = normalize_industry_factors(
    factor_df=momentum_df,
    method="zscore",      # 标准化方法
    group_by="date"
)
```

## 使用示例

### 示例1：行业动量策略

```python
from qlib import init
from qlib.data import D
from qlib.contrib.data.tushare import TuShareConfig, TuShareProvider

# 初始化
config = TuShareConfig.from_env()
init(provider_uri="tushare", default_conf={"tushare": config})

# 创建提供者
provider = TuShareProvider(config)

# 获取股票列表
instruments = D.instruments('csi300')

# 计算行业动量
momentum = provider.get_industry_factors(
    instruments=instruments,
    factor_type="momentum",
    start_time="2024-01-01",
    end_time="2024-12-31",
    window=20
)

# 选择强势行业
latest_momentum = momentum.groupby('industry_code').last()
strong_industries = latest_momentum.nlargest(5, 'momentum')
print(f"强势行业：\n{strong_industries[['industry_name', 'momentum']]}")
```

### 示例2：行业轮动识别

```python
from qlib.contrib.data.tushare.industry_factors import IndustryFactorCalculator

# 准备数据
industry_data = provider.get_industry_classification()
price_df = provider.features(instruments, ["close"], start_time, end_time)

# 创建计算器
calculator = IndustryFactorCalculator(
    industry_data=industry_data,
    price_data=price_df.reset_index()
)

# 计算轮动
rotation_df = calculator.calculate_industry_rotation(
    lookback=5,
    threshold=0.3
)

# 判断轮动强度
latest_rotation = rotation_df['rotation'].iloc[-1]
if latest_rotation > 0.05:
    print("🔥 高轮动：关注行业轮动策略")
else:
    print("💡 低轮动：坚守主线投资")
```

### 示例3：行业暴露度分析

```python
from qlib.contrib.data.tushare.industry_factors import calculate_industry_exposure

# 获取行业分类
industry_data = provider.get_industry_classification()

# 定义目标行业
target_industries = ['电气设备', '电子', '计算机', '通信']

# 计算暴露度
exposure = calculate_industry_exposure(industry_data, target_industries)

# 分析组合暴露度
total_exposure = exposure['exposure'].mean()
print(f"组合对科技行业的暴露度：{total_exposure:.2%}")
```

## 最佳实践

### 1. 数据缓存策略

```python
# 配置缓存
config = TuShareConfig(
    token="your_token",
    enable_cache=True,
    cache_ttl=86400,  # 24小时
    max_cache_size=10737418240  # 10GB
)
```

### 2. 批量数据获取

```python
# 批量获取行业分类
industry_levels = ["L1", "L2", "L3"]
industry_data = {}

for level in industry_levels:
    industry_data[level] = provider.get_industry_classification(
        src="SW2021",
        level=level
    )
```

### 3. 因子组合使用

```python
# 计算多个因子
factors = {}

# 动量因子
factors['momentum'] = provider.get_industry_factors(
    instruments, "momentum", start_time, end_time, window=20
)

# 相对强度因子
factors['relative_strength'] = provider.get_industry_factors(
    instruments, "relative_strength", start_time, end_time
)

# 因子融合
for factor_name, factor_df in factors.items():
    # 标准化
    factor_df['norm'] = normalize_industry_factors(
        factor_df,
        method="zscore"
    )['factor_norm']
```

### 4. 性能优化

```python
# 限制数据范围
instruments = D.instruments('csi300')[:100]  # 先用少量数据测试

# 使用缓存
# 第一次调用会从API获取，后续调用从缓存读取
industry_data = provider.get_industry_classification()

# 批量处理
batch_size = 50
for i in range(0, len(instruments), batch_size):
    batch = instruments[i:i+batch_size]
    factors = provider.get_industry_factors(batch, "momentum", ...)
```

## 常见问题

### Q1: 如何获取 TuShare Token？

A: 访问 [TuShare 官网](https://tushare.pro) 注册账号并申请 API Token。

### Q2: 支持哪些行业分类标准？

A: 支持：
- **SW2021**: 申万2021行业分类（推荐）
- **SW**: 申万行业分类（旧版）
- **ZJH**: 证监会行业分类
- **CITIC**: 中信行业分类

### Q3: 行业因子如何应用到选股策略？

A: 典型流程：
1. 计算行业动量因子
2. 选择强势行业
3. 在强势行业内筛选个股
4. 构建组合

```python
# 选择强势行业
strong_industries = momentum.nlargest(3, 'momentum')['industry_code']

# 获取行业内股票
industry_stocks = industry_data[
    industry_data['industry_code'].isin(strong_industries)
]['instrument']

# 在这些股票中应用选股策略
selected = your_selection_strategy(industry_stocks)
```

### Q4: 数据更新频率如何？

A: TuShare 提供实时和历史数据：
- 行业分类：季度更新
- 行业成分股：月度更新
- 行业指数：每日更新

### Q5: 如何处理 API 频率限制？

A: 系统内置频率限制控制：
- 默认：200请求/分钟
- 自动退避和重试
- 建议使用缓存减少请求

## 更新日志

### v1.0.0 (2025-12-29)

**新增功能**：
- ✨ 添加5个行业板块API接口
- ✨ 实现完整的行业因子计算库
- ✨ 集成到TuShareProvider统一接口
- ✨ 创建详细的使用示例和文档

**API接口**：
- `get_industry()` - 获取行业分类
- `get_concept()` - 获取概念板块
- `get_index_member()` - 获取指数成分股
- `get_index_classify()` - 获取指数行业分类
- `get_industry_detail()` - 获取行业详细信息

**因子类型**：
- 行业动量因子
- 行业相对强度因子
- 行业集中度因子
- 行业市盈率因子
- 行业轮动因子
- 跨行业配置因子

## 贡献指南

欢迎贡献代码和提出建议！

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 创建 Pull Request

## 许可证

本项目遵循 Qlib 项目的许可证协议。

## 联系方式

- **项目地址**: https://github.com/microsoft/qlib
- **问题反馈**: GitHub Issues
- **技术交流**: GitHub Discussions
