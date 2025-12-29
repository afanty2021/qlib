# 行业板块数据下载指南

> 使用TuShare API下载完整的行业板块和概念板块数据

## 快速开始

### 1. 设置Token

```bash
export TUSHARE_TOKEN="your_token_here"
```

### 2. 运行下载脚本

```bash
# 方法1：完整下载（推荐）
cd /Users/berton/Github/qlib
python qlib/contrib/data/tushare/download_industry_data.py

# 方法2：使用Python模块
python -m qlib.contrib.data.tushare.download_industry_data
```

## 下载内容

### 行业分类数据

| 分类标准 | 来源代码 | 级别 | 说明 |
|---------|---------|------|------|
| 申万2021 | SW2021 | L1, L2, L3 | 最新申万行业分类（推荐） |
| 申万旧版 | SW | L1, L2 | 旧版申万行业分类 |
| 证监会 | ZJH | L1, L2 | 证监会行业分类 |
| 中信 | CITIC | L1, L2 | 中信行业分类 |

### 概念板块数据

- 所有概念板块列表
- 概念板块基本信息
- 概念板块分类

### 指数成分股数据

| 指数代码 | 指数名称 | 说明 |
|---------|---------|------|
| 000001.SH | 上证综指 | 上海证券交易所综合指数 |
| 399001.SZ | 深证成指 | 深圳证券交易所成份指数 |
| 000300.SH | 沪深300 | 沪深300指数 |
| 000905.SH | 中证500 | 中证500指数 |
| 000016.SH | 上证50 | 上证50指数 |
| 399006.SZ | 创业板指 | 创业板指数 |
| 000688.SH | 科创50 | 科创50指数 |
| 000903.SH | 中证100 | 中证100指数 |
| 000852.SH | 中证1000 | 中证1000指数 |

### 指数行业分类数据

- 指数与行业的映射关系
- 申万行业分类的指数行业分类

## 输出文件

### 文件命名规则

```
[类型]_[来源]_[级别]_[时间戳].csv
```

例如：
- `industry_SW2021_L1_20241229_120000.csv` - 申万2021一级行业
- `concept_20241229_120000.csv` - 概念板块
- `index_members_all_20241229_120000.csv` - 所有指数成分股

### 最新版本文件

每次下载后会创建不带时间戳的`_latest`文件：
- `industry__latest.csv`
- `concept__latest.csv`
- `index_members_all__latest.csv`

### 输出目录

```
qlib/contrib/data/tushare/industry_data/
├── industry_SW2021_L1_20241229_120000.csv
├── industry_SW2021_L2_20241229_120000.csv
├── industry_SW2021_L3_20241229_120000.csv
├── industry_ZJH_L1_20241229_120000.csv
├── industry_CITIC_L1_20241229_120000.csv
├── concept_20241229_120000.csv
├── index_members_all_20241229_120000.csv
├── index_members_000300.SH_20241229_120000.csv
├── index_members_000905.SH_20241229_120000.csv
├── index_classify_SW2021_L1_20241229_120000.csv
└── data_summary_report.md
```

## 数据格式

### 行业分类数据格式

```csv
industry_code,industry_name,level,is_parent
801010,农林牧渔,L1,Y
801010.SW,农林牧渔,L1,Y
801020,采掘,L1,Y
```

### 概念板块数据格式

```csv
id,concept_name,concept_type
TS001,新能源汽车,主题
TS002,人工智能,主题
```

### 指数成分股数据格式

```csv
index_code,con_code,in_date,out_date,is_new
000300.SH,600000.SH,20100101,,N
000300.SH,600004.SH,20100101,,N
```

## 高级用法

### 自定义下载

```python
from qlib.contrib.data.tushare.download_industry_data import IndustryDataDownloader

# 创建下载器
downloader = IndustryDataDownloader(
    token="your_token",
    output_dir="./my_industry_data"
)

# 只下载申万行业分类
industry_data = downloader.download_industry_classification(
    sources=["SW2021"],
    levels=["L1", "L2"]
)

# 只下载特定指数
index_members = downloader.download_index_members(
    index_codes=["000300.SH", "000905.SH"]
)

# 保存数据
downloader.save_data(
    industry_data=industry_data,
    index_members=index_members
)
```

### 增量更新

```bash
# 定期更新（建议每周一次）
crontab -e

# 每周日凌晨2点更新
0 2 * * 0 cd /Users/berton/Github/qlib && python qlib/contrib/data/tushare/download_industry_data.py
```

## 数据使用示例

### 读取行业分类

```python
import pandas as pd

# 读取最新的申万一级行业
industry_l1 = pd.read_csv('industry_data/industry__latest.csv')

# 筛选申万2021一级行业
sw2021_l1 = industry_l1[
    (industry_l1['industry_code'].str.startswith('80')) &
    (industry_l1['level'] == 'L1')
]

print(f"申万一级行业数量: {len(sw2021_l1)}")
print(sw2021_l1[['industry_code', 'industry_name']])
```

### 读取指数成分股

```python
# 读取沪深300成分股
hs300 = pd.read_csv('industry_data/index_members_000300.SH__latest.csv')

print(f"沪深300成分股数量: {len(hs300)}")
print(hs300.head())
```

### 合并到Qlib使用

```python
from qlib import init
from qlib.data import D

# 初始化Qlib
init(provider_uri="tushare")

# 读取行业分类
industry_df = pd.read_csv('industry_data/industry_SW2021_L1__latest.csv')

# 创建行业映射
industry_map = dict(zip(
    industry_df['industry_code'],
    industry_df['industry_name']
))

# 获取股票数据
instruments = D.instruments('csi300')
data = D.features(instruments, ['close', 'volume'])

# 添加行业信息
data_with_industry = data.reset_index()
data_with_industry['industry'] = data_with_industry['instrument'].map(industry_map)
```

## 常见问题

### Q1: Token如何获取？

A: 访问 [TuShare官网](https://tushare.pro) 注册账号，然后在个人中心获取API Token。

### Q2: 下载需要多长时间？

A: 取决于网络速度和API限制，通常需要1-5分钟。

### Q3: 数据多久更新一次？

A: 建议：
- 行业分类：每月更新（申万通常季度调整）
- 概念板块：每周更新
- 指数成分股：每月更新

### Q4: 下载失败怎么办？

A: 检查：
1. Token是否正确
2. 网络连接是否正常
3. API调用次数是否超限
4. 查看错误信息进行针对性处理

### Q5: 如何获取更多指数？

A: 修改脚本中的`index_codes`列表，添加需要的指数代码。

## 技术支持

- **TuShare文档**: https://tushare.pro/document/2
- **Qlib文档**: https://qlib.readthedocs.io/
- **GitHub Issues**: https://github.com/microsoft/qlib/issues

## 更新日志

### v1.0.0 (2025-12-29)

**初始版本**：
- ✅ 支持申万、证监会、中信行业分类下载
- ✅ 支持概念板块下载
- ✅ 支持主要指数成分股下载
- ✅ 支持指数行业分类下载
- ✅ 自动生成数据摘要报告
- ✅ 创建最新版本链接
