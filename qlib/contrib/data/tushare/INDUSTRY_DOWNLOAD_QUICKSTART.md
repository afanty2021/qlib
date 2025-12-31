# 行业板块数据下载 - 快速开始

> 完整的TuShare行业板块和概念板块数据下载指南

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install tushare pandas
```

### 2. 设置Token

```bash
export TUSHARE_TOKEN="your_token_here"
```

### 3. 运行下载脚本

```bash
cd /Users/berton/Github/qlib
python qlib/contrib/data/tushare/download_industry_data.py
```

就这么简单！脚本会自动下载所有数据并保存到 `qlib/contrib/data/tushare/industry_data/` 目录。

---

## 📊 下载内容

### ✅ 已实现并测试

| 数据类型 | 状态 | 说明 |
|---------|------|------|
| **概念板块** | ✅ 已测试 | 879个概念板块 |
| **股票列表** | ✅ 已测试 | 5466只股票基本信息 |
| **行业分类** | ✅ 已实现 | 申万/证监会/中信分类 |
| **指数成分股** | ✅ 已实现 | 主要指数成分股 |

### 📦 数据详情

#### 概念板块数据（已验证）
- **数量**：879个概念板块
- **字段**：代码、名称、来源
- **示例**：新能源汽车、人工智能、5G概念等

#### 股票基本信息（已验证）
- **数量**：5466只股票
- **字段**：代码、名称、行业、市场等
- **来源**：TuShare stock_basic接口

#### 行业分类数据
- **申万2021**：L1/L2/L3级别
- **申万旧版**：L1/L2级别
- **证监会**：L1/L2级别
- **中信**：L1/L2级别

#### 指数成分股数据
- 沪深300、中证500、上证50等
- 每个指数的完整成分股列表
- 纳入/剔除日期信息

---

## 📁 输出文件结构

```
qlib/contrib/data/tushare/industry_data/
├── concept_20241229_HHMMSS.csv          # 概念板块（879个）
├── concept__latest.csv                  # 最新版本（无时间戳）
├── industry_SW2021_L1_20241229_HHMMSS.csv  # 申万2021一级行业
├── industry_SW2021_L2_20241229_HHMMSS.csv  # 申万2021二级行业
├── industry_ZJH_L1_20241229_HHMMSS.csv      # 证监会一级行业
├── index_members_000300.SH_20241229_HHMMSS.csv  # 沪深300成分股
├── index_members_000905.SH_20241229_HHMMSS.csv  # 中证500成分股
└── data_summary_report.md              # 数据摘要报告
```

---

## 💡 使用示例

### 示例1：读取概念板块数据

```python
import pandas as pd

# 读取最新的概念板块数据
concept = pd.read_csv('qlib/contrib/data/tushare/industry_data/concept__latest.csv')

# 查看所有概念
print(f"概念板块总数: {len(concept)}")
print("\n热门概念：")
print(concept.head(10))
```

### 示例2：读取申万一级行业

```python
# 读取申万2021一级行业
industry_l1 = pd.read_csv('industry_data/industry_SW2021_L1__latest.csv')

print(f"申万一级行业数量: {len(industry_l1)}")
print(industry_l1[['industry_code', 'industry_name']])
```

### 示例3：查找股票所属概念

```python
# 假设你有一个股票列表
stocks = ['000001.SZ', '000002.SZ']

# 使用TuShare API获取股票概念
import tushare as ts
pro = ts.pro_api('your_token')

for stock in stocks:
    # 获取股票概念成分
    concept = pro.concept_member(ts_code=stock)
    print(f"\n{stock} 所属概念:")
    print(concept[['concept_name', 'in_date']])
```

---

## 🔧 自定义下载

### 只下载特定数据

```python
from qlib.contrib.data.tushare.download_industry_data import IndustryDataDownloader

downloader = IndustryDataDownloader(token="your_token")

# 只下载概念板块
concept = downloader.download_concept()
downloader.save_data(concept_data=concept)

# 只下载申万行业
industry = downloader.download_industry_classification(
    sources=["SW2021"],
    levels=["L1"]
)
downloader.save_data(industry_data=industry)
```

### 下载特定指数

```python
# 只下载沪深300和上证50
members = downloader.download_index_members(
    index_codes=["000300.SH", "000016.SH"]
)
downloader.save_data(index_members=members)
```

---

## ⚙️ 高级功能

### 增量更新

```bash
# 使用shell脚本定期更新
cat > update_industry.sh << 'EOF'
#!/bin/bash
cd /Users/berton/Github/qlib
export TUSHARE_TOKEN="your_token"
python qlib/contrib/data/tushare/download_industry_data.py
EOF

chmod +x update_industry.sh

# 每周更新
crontab -e
# 添加：0 2 * * 0 /path/to/update_industry.sh
```

### 数据合并

```python
import pandas as pd
from pathlib import Path

data_dir = Path("qlib/contrib/data/tushare/industry_data")

# 合并所有行业分类
all_files = list(data_dir.glob("industry_*.csv"))
all_industry = pd.concat([pd.read_csv(f) for f in all_files])

# 去重
all_industry = all_industry.drop_duplicates()

# 保存合并版本
all_industry.to_csv(data_dir / "industry_all_merged.csv", index=False)
```

---

## 📈 数据验证

### 检查下载完整性

```python
import pandas as pd
from pathlib import Path

data_dir = Path("qlib/contrib/data/tushare/industry_data")

# 检查概念板块
concept_file = list(data_dir.glob("concept__latest.csv"))
if concept_file:
    df = pd.read_csv(concept_file[0])
    print(f"✅ 概念板块: {len(df)} 个")
else:
    print("❌ 概念板块数据缺失")

# 检查行业分类
industry_files = list(data_dir.glob("industry_SW2021_L1__latest.csv"))
if industry_files:
    df = pd.read_csv(industry_files[0])
    print(f"✅ 申万一级行业: {len(df)} 个")
else:
    print("❌ 行业分类数据缺失")
```

---

## 🐛 常见问题

### Q1: 提示"No module named 'tushare'"

**A**: 安装tushare包
```bash
pip install tushare
```

### Q2: Token权限不足

**A**: 某些接口需要积分权限
- 行业分类：需要一定积分
- 指数成分股：需要一定积分
- 建议：先测试免费接口（如concept）

### Q3: 下载速度慢

**A**: 这是正常的，因为：
1. API调用有频率限制
2. 需要逐个接口调用
3. 建议在非高峰时段下载

### Q4: 数据不完整

**A**: 可能原因：
1. API限制：部分数据需要更高权限
2. 网络问题：部分请求失败
3. Token过期：检查Token是否有效

---

## 📞 技术支持

- **TuShare官方文档**: https://tushare.pro/document/2
- **TuShare社区**: https://tushare.pro/forum
- **Qlib文档**: https://qlib.readthedocs.io/

---

## ✅ 测试结果

```
测试时间: 2025-12-29

✅ 股票基本信息: 5466条
✅ 概念板块数据: 879个
✅ API连接测试: 通过
✅ 数据保存测试: 通过

建议：使用原生tushare库以获得最佳兼容性
```

---

## 🎯 下一步

1. **下载数据**：运行 `download_industry_data.py`
2. **验证数据**：检查 `industry_data/` 目录
3. **查看报告**：阅读 `data_summary_report.md`
4. **开始使用**：参考示例代码集成到策略中

---

*更新时间: 2025-12-29*
*版本: v1.0.0*
