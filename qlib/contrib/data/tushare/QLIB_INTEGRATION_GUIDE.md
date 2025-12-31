# Qlib行业数据集成指南

> 将行业板块数据集成到Qlib量化投资平台

## 📁 数据位置

行业板块数据已复制到Qlib标准数据目录:
```
~/.qlib/qlib_data/cn_data/industry_data/
```

## 📊 数据文件清单

### 行业分类数据 (9个分类体系)

| 文件名 | 数据量 | 说明 |
|-------|--------|------|
| `industry_SW2021_L1__latest.csv` | 28条 | 申万2021一级行业 |
| `industry_SW2021_L2__latest.csv` | 104条 | 申万2021二级行业 |
| `industry_SW2021_L3__latest.csv` | 227条 | 申万2021三级行业 |
| `industry_ZJH_L1__latest.csv` | 28条 | 证监会一级行业 |
| `industry_ZJH_L2__latest.csv` | 104条 | 证监会二级行业 |
| `industry_ZJH_L3__latest.csv` | 227条 | 证监会三级行业 |
| `industry_CITIC_L1__latest.csv` | 28条 | 中信一级行业 |
| `industry_CITIC_L2__latest.csv` | 104条 | 中信二级行业 |
| `industry_CITIC_L3__latest.csv` | 227条 | 中信三级行业 |

### 概念板块数据

| 文件名 | 数据量 | 说明 |
|-------|--------|------|
| `concept__latest.csv` | 879条 | 概念板块列表 |

### 指数行业分类

| 文件名 | 数据量 | 说明 |
|-------|--------|------|
| `index_classify_SW2021_L1__latest.csv` | 28条 | 指数申万一级分类 |
| `index_classify_SW2021_L2__latest.csv` | 104条 | 指数申万二级分类 |

## 💡 使用方法

### 方法1: 使用IndustryDataManager (推荐)

```python
import sys
sys.path.append('/Users/berton/Github/qlib')

from qlib.contrib.data.tushare.examples.data_loading_example import IndustryDataManager

# 初始化数据管理器
manager = IndustryDataManager(
    data_dir="~/.qlib/qlib_data/cn_data/industry_data"
)

# 加载申万一级行业
industry_l1 = manager.load_industry_classification("SW2021", "L1")

# 加载概念板块
concept = manager.load_concept_data()

# 创建行业映射
industry_map = manager.get_industry_mapping("SW2021", "L1")

# 搜索特定行业
banks = manager.search_industries("银行", "SW2021", "L1")
```

### 方法2: 直接使用pandas读取

```python
import pandas as pd
from pathlib import Path

# 数据目录
data_dir = Path("~/.qlib/qlib_data/cn_data/industry_data").expanduser()

# 读取申万一级行业
industry_l1 = pd.read_csv(data_dir / "industry_SW2021_L1__latest.csv")

# 读取概念板块
concept = pd.read_csv(data_dir / "concept__latest.csv")

# 查看数据
print(industry_l1.head())
print(concept.head())
```

### 方法3: 集成到Qlib工作流

```python
from qlib import init
from qlib.data import D
import pandas as pd
from pathlib import Path

# 初始化Qlib
init(provider_uri="~/.qlib/qlib_data/cn_data", region="cn")

# 加载行业数据
data_dir = Path("~/.qlib/qlib_data/cn_data/industry_data").expanduser()
industry_l1 = pd.read_csv(data_dir / "industry_SW2021_L1__latest.csv")

# 创建行业映射字典
industry_map = dict(zip(
    industry_l1['industry_code'],
    industry_l1['industry_name']
))

# 获取股票数据
instruments = D.instruments('csi300')
prices = D.features(
    instruments,
    ['close', 'volume'],
    start_time='2024-01-01',
    end_time='2024-12-31'
)

# 将行业信息添加到价格数据
# (需要先获取股票的行业分类)
```

## 🔧 构建股票-行业映射

### 从TuShare获取股票行业分类

```python
import tushare as ts
import pandas as pd

# 初始化TuShare
pro = ts.pro_api('your_token')

# 获取股票基本信息(包含行业)
stock_basic = pro.stock_basic(
    exchange='',
    list_status='L',
    fields='ts_code,name,industry'
)

# 获取更详细的行业分类
stock_industry = pro.index_classify(
    level='L1',
    source='SW2021'
)

print(stock_basic.head())
print(stock_industry.head())
```

### 保存股票-行业映射

```python
# 构建完整映射
stock_industry_map = dict(zip(
    stock_basic['ts_code'],
    stock_basic['industry']
))

# 保存为JSON
import json
with open('~/.qlib/qlib_data/cn_data/industry_data/stock_industry_map.json', 'w') as f:
    json.dump(stock_industry_map, f, ensure_ascii=False, indent=2)
```

## 📈 应用场景

### 1. 行业轮动策略

```python
from qlib.contrib.data.tushare.examples.stock_selection_strategy import IndustryRotationStrategy

# 创建策略
strategy = IndustryRotationStrategy(
    price_data=price_df,
    industry_map=industry_map
)

# 选股
selected_stocks = strategy.select_stocks(
    date='2024-12-31',
    top_industries=3,
    stocks_per_industry=5
)
```

### 2. 行业中性策略

```python
from qlib.contrib.data.tushare.examples.stock_selection_strategy import IndustryNeutralStrategy

strategy = IndustryNeutralStrategy(
    price_data=price_df,
    industry_map=industry_map
)

selected_stocks = strategy.select_stocks(
    date='2024-12-31',
    stocks_per_industry=2
)
```

### 3. 行业风险控制

```python
from qlib.contrib.data.tushare.examples.risk_management import IndustryConcentrationRisk

risk_control = IndustryConcentrationRisk(max_industry_weight=0.3)

# 检查集中度
passed, warnings = risk_control.check_concentration(
    holdings=portfolio_df,
    industry_map=industry_map
)

# 调整组合
adjusted_portfolio = risk_control.adjust_portfolio(
    holdings=portfolio_df,
    industry_map=industry_map
)
```

## 🔄 数据更新

### 定期更新行业分类

```bash
# 每季度更新一次
cd /Users/berton/Github/qlib
python qlib/contrib/data/tushare/download_industry_data.py

# 复制到Qlib数据目录
cp -r qlib/contrib/data/tushare/industry_data/* \
    ~/.qlib/qlib_data/cn_data/industry_data/
```

### 使用脚本自动更新

```bash
#!/bin/bash
# update_industry_data.sh

# 1. 下载最新数据
cd /Users/berton/Github/qlib
python qlib/contrib/data/tushare/download_industry_data.py

# 2. 备份旧数据
mv ~/.qlib/qlib_data/cn_data/industry_data \
   ~/.qlib/qlib_data/cn_data/industry_data.bak.$(date +%Y%m%d)

# 3. 复制新数据
mkdir -p ~/.qlib/qlib_data/cn_data/industry_data
cp -r qlib/contrib/data/tushare/industry_data/* \
    ~/.qlib/qlib_data/cn_data/industry_data/

# 4. 清理旧备份(保留最近3次)
find ~/.qlib/qlib_data/cn_data/ -name "industry_data.bak.*" -mtime +90 -delete

echo "行业数据更新完成"
```

## 📊 数据验证

### 验证数据完整性

```python
import pandas as pd
from pathlib import Path

data_dir = Path("~/.qlib/qlib_data/cn_data/industry_data").expanduser()

# 检查必要文件是否存在
required_files = [
    "industry_SW2021_L1__latest.csv",
    "industry_ZJH_L1__latest.csv",
    "industry_CITIC_L1__latest.csv",
    "concept__latest.csv"
]

for file in required_files:
    file_path = data_dir / file
    if file_path.exists():
        df = pd.read_csv(file_path)
        print(f"✅ {file}: {len(df)} 条记录")
    else:
        print(f"❌ {file}: 文件不存在")
```

## 🎯 最佳实践

### 1. 缓存行业映射

```python
import pickle
from pathlib import Path

cache_file = Path("~/.qlib/qlib_data/cn_data/industry_data/industry_map.pkl")

def get_industry_map():
    """加载或创建行业映射缓存"""
    if cache_file.exists():
        with open(cache_file, 'rb') as f:
            return pickle.load(f)
    else:
        # 从TuShare获取并保存
        industry_map = fetch_industry_map_from_tushare()
        with open(cache_file, 'wb') as f:
            pickle.dump(industry_map, f)
        return industry_map
```

### 2. 使用__latest文件

优先使用带`__latest`后缀的文件,这些文件指向最新的数据版本,方便代码维护:

```python
# ✅ 推荐
industry_l1 = pd.read_csv(data_dir / "industry_SW2021_L1__latest.csv")

# ❌ 不推荐(需要经常修改文件名)
industry_l1 = pd.read_csv(data_dir / "industry_SW2021_L1_20251229_112014.csv")
```

### 3. 数据版本管理

```python
import yaml

version_file = data_dir / "data_version.yaml"

def save_data_version():
    """记录数据版本信息"""
    version_info = {
        'update_date': '2025-12-29',
        'source': 'TuShare',
        'files': {
            'industry_SW2021_L1': '20251229_112014',
            'concept': '20251229_112014'
        }
    }

    with open(version_file, 'w') as f:
        yaml.dump(version_info, f)

def check_data_version():
    """检查数据是否需要更新"""
    if version_file.exists():
        with open(version_file) as f:
            version_info = yaml.safe_load(f)
        # 检查是否超过3个月
        from datetime import datetime, timedelta
        update_date = datetime.strptime(version_info['update_date'], '%Y-%m-%d')
        if datetime.now() - update_date > timedelta(days=90):
            print("⚠️ 行业数据可能需要更新")
    else:
        print("⚠️ 未找到版本信息,建议更新数据")
```

## 📞 常见问题

### Q1: 数据文件很大,如何优化加载速度?

A: 使用缓存和增量加载:

```python
# 只加载需要的字段
industry_l1 = pd.read_csv(
    data_dir / "industry_SW2021_L1__latest.csv",
    usecols=['industry_code', 'industry_name']
)

# 使用低内存数据类型
industry_l1 = pd.read_csv(
    data_dir / "industry_SW2021_L1__latest.csv",
    dtype={'industry_code': 'category', 'industry_name': 'category'}
)
```

### Q2: 如何处理行业分类变更?

A: 记录历史分类变更:

```python
# 保存不同时期的分类
industry_2024 = pd.read_csv('industry_SW2021_L1_20241231.csv')
industry_2023 = pd.read_csv('industry_SW2021_L1_20231231.csv')

# 比较变更
changes = industry_2024.merge(
    industry_2023,
    on='industry_code',
    how='outer',
    indicator=True
)
```

### Q3: 如何获取更多历史数据?

A: 使用TuShare的时间序列接口:

```python
import tushare as ts
pro = ts.pro_api('your_token')

# 获取历史成分股变更
index_member = pro.index_member(
    index_code='000300.SH',  # 沪深300
    start_date='20200101',
    end_date='20241231'
)
```

## ✅ 数据集成检查清单

- [x] 数据文件已复制到 `~/.qlib/qlib_data/cn_data/industry_data/`
- [x] 包含16个CSV文件和4个JSON文件
- [x] 数据总量: 784KB
- [x] 涵盖3种行业分类体系 (申万/证监会/中信)
- [x] 包含879个概念板块
- [x] 数据更新日期: 2025-12-29

## 🚀 下一步

1. **运行示例代码**:
   ```bash
   cd /Users/berton/Github/qlib
   python qlib/contrib/data/tushare/examples/data_loading_example.py
   python qlib/contrib/data/tushare/examples/stock_selection_strategy.py
   python qlib/contrib/data/tushare/examples/risk_management.py
   ```

2. **构建股票-行业映射**: 使用TuShare API获取真实映射

3. **集成到策略**: 在您的量化策略中使用行业数据

4. **定期更新**: 设置定时任务每季度更新数据

---

**更新时间**: 2025-12-29
**数据版本**: v1.0.0
**数据来源**: TuShare Pro
