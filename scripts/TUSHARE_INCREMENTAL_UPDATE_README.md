# TuShare A股数据增量更新工具

> 借鉴 [investment_data](https://github.com/chenditc/investment_data) 项目的增量更新思路，
> 结合 Qlib 的 TuShare 集成，实现本地 A股行情数据的增量更新功能。

## 📋 目录

- [功能特点](#功能特点)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [使用方法](#使用方法)
- [数据格式](#数据格式)
- [与 investment_data 的对比](#与-investment_data-的对比)
- [常见问题](#常见问题)

## ✨ 功能特点

### 核心功能

1. **智能增量更新**
   - 自动检测本地数据的最新日期
   - 仅下载自最新日期后的新数据
   - 避免重复下载已有数据，节省 API 调用次数

2. **多数据类型支持**
   - 股票日线数据（全市场）
   - 指数日线数据（主流指数）
   - 指数权重数据（成分股权重）

3. **数据质量控制**
   - 数据验证和完整性检查
   - 自动去重和排序
   - 错误处理和重试机制

4. **完善的日志系统**
   - 详细的更新日志
   - 进度跟踪和统计信息
   - 错误记录和诊断信息

### 与 investment_data 的区别

| 特性 | investment_data | 本工具 |
|------|----------------|--------|
| 数据库 | Dolt（版本控制数据库） | 本地文件系统（CSV） |
| 部署复杂度 | 需要 Docker + Dolt | 纯 Python，无需额外依赖 |
| 数据导出 | 需要额外导出步骤 | 直接保存为 Qlib 格式 |
| 版本控制 | Dolt Git 版本控制 | 无（可用 Git 管理配置） |
| 适用场景 | 多人协作、数据版本管理 | 个人使用、快速部署 |

### 技术优势

- **零依赖数据库**：无需安装 Dolt 或 MySQL，使用简单的 CSV 文件
- **Qlib 原生集成**：直接利用 Qlib 的 TuShare API 客户端和缓存系统
- **轻量级部署**：单个 Python 脚本，易于维护和扩展
- **企业级稳定性**：继承 Qlib 的错误处理、重试机制、频率限制

## 🚀 快速开始

### 1. 环境准备

```bash
# 确保 Qlib 已安装
pip install qlib

# 确保 TuShare 已安装（Qlib 依赖）
pip install tushare pyyaml
```

### 2. 设置 TuShare Token

```bash
# 设置环境变量
export TUSHARE_TOKEN="your_token_here"

# 或在 ~/.bashrc 或 ~/.zshrc 中添加
echo 'export TUSHARE_TOKEN="your_token_here"' >> ~/.bashrc
source ~/.bashrc
```

> 💡 **如何获取 Token**：访问 [TuShare 官网](https://tushare.pro) 注册账号并申请 API Token

### 3. 运行增量更新

```bash
# 进入 Qlib 目录
cd /path/to/qlib

# 运行更新脚本
python scripts/tushare_incremental_update.py
```

### 4. 查看更新结果

```bash
# 查看日志
tail -f ~/.qlib/qlib_data/cn_data/incremental_update.log

# 查看更新后的数据
ls -lh ~/.qlib/qlib_data/cn_data/*.csv
```

## ⚙️ 配置说明

### 配置文件位置

默认配置文件：`scripts/tushare_incremental_config.yaml`

### 主要配置项

#### 基础配置

```yaml
# 数据存储目录
data_dir: "~/.qlib/qlib_data/cn_data"

# API 调用配置
max_retries: 3           # 最大重试次数
retry_delay: 1.0         # 重试延迟（秒）
rate_limit: 200          # API 频率限制
```

#### 数据更新控制

```yaml
# 是否更新各类数据
update_stock: true        # 股票日线数据
update_index: true        # 指数数据
update_index_weight: true # 指数权重数据
validate_data: true       # 数据验证
```

#### 数据范围配置

```yaml
# 历史数据起始日期（首次运行时使用）
stock_start_date: "20200101"
index_start_date: "20200101"

# 需要更新的指数
index_list:
  - "399300.SZ"  # 沪深300
  - "000905.SH"  # 中证500
  # ... 更多指数
```

### 自定义配置

#### 方法1：修改默认配置文件

```bash
# 编辑配置文件
vim scripts/tushare_incremental_config.yaml
```

#### 方法2：使用自定义配置文件

```bash
# 复制默认配置
cp scripts/tushare_incremental_config.yaml scripts/my_config.yaml

# 使用自定义配置运行
python scripts/tushare_incremental_update.py --config scripts/my_config.yaml
```

## 📖 使用方法

### 基本使用

```bash
# 运行完整更新（股票 + 指数 + 权重）
python scripts/tushare_incremental_update.py
```

### 高级使用

#### 仅更新股票数据

编辑配置文件：
```yaml
update_stock: true
update_index: false
update_index_weight: false
```

#### 仅更新特定指数

编辑配置文件：
```yaml
index_list:
  - "399300.SZ"  # 只更新沪深300
  - "000905.SH"  # 只更新中证500
```

#### 设置日志级别

编辑配置文件：
```yaml
log_level: "DEBUG"  # 输出详细调试信息
```

### 定时任务设置

#### Linux/macOS (crontab)

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天 18:00 执行）
0 18 * * * cd /path/to/qlib && /usr/bin/python3 scripts/tushare_incremental_update.py >> /var/log/tushare_update.log 2>&1
```

#### Windows (任务计划程序)

1. 打开"任务计划程序"
2. 创建基本任务
3. 设置触发器（每天特定时间）
4. 设置操作：运行 Python 脚本

```powershell
# 程序或脚本
python.exe

# 添加参数
C:\path\to\qlib\scripts\tushare_incremental_update.py

# 起始于
C:\path\to\qlib
```

## 📊 数据格式

### 股票数据 (stock_data.csv)

```csv
tradedate,symbol,open,high,low,close,volume,amount
20240101,000001.SZ,10.50,10.80,10.30,10.75,1234567.89,12345678.90
20240101,000002.SZ,15.20,15.50,15.00,15.40,2345678.90,23456789.01
...
```

**字段说明**：
- `tradedate`: 交易日期（YYYYMMDD）
- `symbol`: 股票代码（TuShare 格式：000001.SZ）
- `open`: 开盘价
- `high`: 最高价
- `low`: 最低价
- `close`: 收盘价
- `volume`: 成交量
- `amount`: 成交额

### 指数数据 (index_data.csv)

```csv
tradedate,symbol,open,high,low,close,volume,amount
20240101,399300.SZ,3800.50,3850.80,3780.30,3820.75,123456789.01,123456789.01
...
```

**字段说明**：与股票数据相同

### 指数权重数据 (index_weight.csv)

```csv
tradedate,symbol,stock_code,weight
20240101,399300.SZ,000001.SZ,0.85
20240101,399300.SZ,000002.SZ,0.75
...
```

**字段说明**：
- `tradedate`: 交易日期（YYYYMMDD）
- `symbol`: 指数代码
- `stock_code`: 成分股代码
- `weight`: 权重（百分比）

## 🔍 与 investment_data 的对比

### investment_data 的优势

1. **版本控制**：Dolt 数据库提供 Git 风格的版本控制
2. **多人协作**：支持分支、合并、冲突解决
3. **数据质量**：多数据源交叉验证
4. **社区贡献**：众包数据更新模式

### 本工具的优势

1. **零依赖数据库**：无需安装 Dolt，部署更简单
2. **轻量级**：单个 Python 脚本，易于维护
3. **Qlib 集成**：直接利用 Qlib 的 API 客户端和缓存
4. **快速上手**：配置简单，开箱即用

### 选择建议

- **使用 investment_data 如果你需要**：
  - 多人协作的数据更新
  - 完整的数据版本控制
  - 多数据源交叉验证
  - 参与社区数据贡献

- **使用本工具如果你需要**：
  - 个人或小团队使用
  - 快速部署和简单维护
  - 直接集成到 Qlib 工作流
  - 轻量级的解决方案

## ❓ 常见问题

### Q1: 如何查看更新进度？

A: 查看日志文件：
```bash
tail -f ~/.qlib/qlib_data/cn_data/incremental_update.log
```

### Q2: 更新失败怎么办？

A: 检查以下几点：
1. 确认 TUSHARE_TOKEN 环境变量已设置
2. 检查网络连接
3. 查看 API 配额是否用完
4. 检查日志文件中的错误信息

### Q3: 如何首次运行获取历史数据？

A: 首次运行时，脚本会自动下载配置文件中 `stock_start_date` 和 `index_start_date` 之后的所有数据。

### Q4: 数据更新频率建议？

A: 建议每个交易日收盘后（18:00-20:00）运行一次，获取当日最新数据。

### Q5: 如何仅更新特定时间段的数据？

A: 可以删除本地数据文件，修改配置文件中的起始日期，然后重新运行。

### Q6: API 频率限制如何处理？

A: 脚本内置了频率限制控制，会自动处理 API 限制。如需调整，可修改配置文件中的 `rate_limit` 参数。

### Q7: 数据存储空间需求？

A: 大约估算：
- 全市场股票日线数据（1年）：约 500MB - 1GB
- 指数数据（1年）：约 10MB
- 指数权重数据（1年）：约 50MB

### Q8: 如何备份数据？

A: 直接复制数据目录：
```bash
cp -r ~/.qlib/qlib_data/cn_data ~/.qlib/qlib_data/cn_data_backup
```

### Q9: 如何与 Qlib 集成使用？

A: 更新的数据可以直接在 Qlib 中使用：
```python
from qlib import init
from qlib.data import D

# 初始化 Qlib
init(provider_uri="~/.qlib/qlib_data/cn_data")

# 使用数据
instruments = D.instruments("csi300")
features = D.features(instruments, ["close", "volume"])
```

### Q10: 错误 "没有新的交易日" 是什么意思？

A: 这表示本地数据已经是最新的，没有新的交易日需要更新。这是正常情况。

## 📚 参考资料

- [investment_data 项目](https://github.com/chenditc/investment_data)
- [TuShare 官方文档](https://tushare.pro/document/2)
- [Qlib 官方文档](https://qlib.readthedocs.io/)

## 📝 更新日志

### v1.0.0 (2025-01-19)

- ✨ 初始版本发布
- 🚀 实现增量更新功能
- 📊 支持股票、指数、权重数据更新
- 🛡️ 完善的错误处理和重试机制
- 📚 详细的文档和配置说明

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目遵循 Qlib 项目的许可证协议。
