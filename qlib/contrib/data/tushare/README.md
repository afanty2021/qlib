# Qlib TuShare数据源

为Qlib量化投资平台提供TuShare数据源集成，支持A股市场实时数据获取和处理。

## 🚀 功能特性

### 核心功能
- **统一数据接口**：与Qlib原生数据接口完全兼容
- **多层缓存机制**：内存缓存 + 磁盘缓存提升性能
- **企业级稳定性**：完善的错误处理、重试机制、降级策略
- **灵活配置管理**：支持环境变量、配置文件、代码配置
- **实时数据获取**：支持A股日线、分钟线等实时数据
- **自动字段映射**：TuShare字段到Qlib标准字段自动转换

### 数据支持
- **股票行情数据**：OHLCV基础行情数据
- **交易日历数据**：完整的交易日历信息
- **股票基本信息**：股票名称、行业、上市日期等
- **复权数据处理**：前复权、后复权支持
- **技术指标计算**：常用技术指标自动计算

## 📦 安装依赖

```bash
# 安装TuShare
pip install tushare

# 安装Qlib（如果还未安装）
pip install pyqlib
```

## 🔧 快速开始

### 1. 环境配置

设置TuShare Token（推荐方式）：

```bash
export TUSHARE_TOKEN="your_token_here"
```

或通过配置文件：

```yaml
# ~/.qlib/tushare_config.yaml
token: "your_token_here"
enable_cache: true
cache_ttl: 86400
max_retries: 3
```

### 2. 基本使用

```python
from qlib import init
from qlib.data import D
from qlib.contrib.data.tushare import TuShareConfig, TuShareProvider

# 初始化配置
config = TuShareConfig.from_env()  # 从环境变量加载

# 使用TuShare数据源初始化Qlib
init(provider_uri="tushare", default_conf={"tushare": config})

# 或者直接使用数据提供者
provider = TuShareProvider(config)

# 获取交易日历
calendar = D.calendar(start_time="2024-01-01", end_time="2024-12-31")
print(f"2024年共有 {len(calendar)} 个交易日")

# 获取股票列表
instruments = D.instruments("csi300")
print(f"CIS300成分股数量: {len(instruments)}")

# 获取股票数据
data = D.features(
    instruments=["000001.SZ", "600000.SH"],
    fields=["close", "volume", "open"],
    start_time="2024-01-01",
    end_time="2024-12-31"
)
print(data.head())

# 获取单只股票数据
single_data = D.features(
    instruments=["000001.SZ"],
    fields=["close"],
    start_time="2024-01-01",
    end_time="2024-01-31"
)
print(single_data)
```

### 3. 高级使用

```python
from qlib.contrib.data.tushare import TuShareProvider, TuShareConfig
import pandas as pd

# 自定义配置
config = TuShareConfig(
    token="your_token_here",
    enable_cache=True,
    cache_ttl=7200,  # 2小时缓存
    max_retries=5,
    rate_limit=180,  # 降低请求频率
    validate_data=True,
    adjust_price=True  # 启用复权
)

# 使用上下文管理器
with TuShareProvider(config) as provider:
    # 获取交易日历
    calendar = provider.calendar(
        start_time="2024-01-01",
        end_time="2024-12-31"
    )

    # 获取股票信息
    instruments = provider.instruments(market="all")
    print(f"总股票数量: {len(instruments)}")

    # 获取特征数据
    features = provider.features(
        instruments=["000001.SZ", "600000.SH"],
        fields=["open", "high", "low", "close", "volume"],
        start_time="2024-01-01",
        end_time="2024-12-31"
    )

    # 获取缓存统计
    cache_stats = provider.get_cache_stats()
    print(f"缓存统计: {cache_stats}")
```

## 📋 配置选项

### 完整配置参数

```python
config = TuShareConfig(
    # TuShare API配置
    token="your_token_here",              # TuShare API Token
    api_url="http://api.tushare.pro",    # API地址

    # 缓存配置
    enable_cache=True,                   # 启用缓存
    cache_dir="~/.qlib/cache/tushare",  # 缓存目录
    cache_ttl=86400,                    # 缓存生存时间（秒）
    max_cache_size=1024*1024*1024,      # 最大缓存大小（字节）

    # 重试和超时配置
    max_retries=3,                      # 最大重试次数
    retry_delay=1.0,                    # 重试延迟（秒）
    retry_backoff=2.0,                  # 退避因子
    timeout=30.0,                       # 请求超时（秒）

    # 频率限制配置
    rate_limit=200,                     # 每分钟最大请求数
    rate_limit_window=60,               # 频率限制窗口（秒）

    # 数据获取配置
    batch_size=5000,                    # 批量获取大小
    default_fields=[                    # 默认字段
        "open", "high", "low", "close", "volume", "amount"
    ],

    # 日志配置
    log_level="INFO",                   # 日志级别
    enable_api_logging=False,           # 启用API调用日志

    # 数据验证配置
    validate_data=True,                 # 验证数据
    remove_holidays=True,               # 移除节假日
    adjust_price=True,                  # 是否复权
)
```

### 环境变量配置

```bash
# TuShare Token
export TUSHARE_TOKEN="your_token_here"

# 缓存配置
export TUSHARE_ENABLE_CACHE=true
export TUSHARE_CACHE_DIR="~/.qlib/cache/tushare"
export TUSHARE_CACHE_TTL=86400

# 重试配置
export TUSHARE_MAX_RETRIES=3
export TUSHARE_RETRY_DELAY=1.0
export TUSHARE_TIMEOUT=30.0

# 频率限制
export TUSHARE_RATE_LIMIT=200

# 日志配置
export TUSHARE_LOG_LEVEL=INFO
export TUSHARE_ENABLE_API_LOGGING=false

# 数据配置
export TUSHARE_VALIDATE_DATA=true
export TUSHARE_ADJUST_PRICE=true
```

### 配置文件支持

支持JSON和YAML格式的配置文件：

```yaml
# tushare_config.yaml
token: "your_token_here"
enable_cache: true
cache_ttl: 86400
max_retries: 3
rate_limit: 180
validate_data: true
adjust_price: true
log_level: "INFO"
```

```python
# 从文件加载配置
config = TuShareConfig.from_file("tushare_config.yaml")
```

## 🔍 字段映射

TuShare字段与Qlib标准字段自动映射：

| TuShare字段 | Qlib字段 | 说明 |
|------------|----------|------|
| ts_code | instrument | 股票代码 |
| trade_date | date | 交易日期 |
| open | open | 开盘价 |
| high | high | 最高价 |
| low | low | 最低价 |
| close | close | 收盘价 |
| vol | volume | 成交量（手） |
| amount | amount | 成交额（千元） |
| pct_chg | pct_change | 涨跌幅 |

### 查看字段映射

```python
from qlib.contrib.data.tushare.field_mapping import TuShareFieldMapping

# 查看所有映射
mappings = TuShareFieldMapping.get_all_mappings()
print(mappings)

# 获取特定字段映射
qlib_field = TuShareFieldMapping.get_qlib_field("close")
print(f"TuShare 'close' -> Qlib '{qlib_field}'")

# 导出字段映射
TuShareFieldMapping.export_field_mappings("field_mappings.json")
```

## 📊 数据处理工具

### 代码转换工具

```python
from qlib.contrib.data.tushare.utils import TuShareCodeConverter

# 转换代码格式
tushare_code = TuShareCodeConverter.to_tushare_format("000001")  # -> "000001.SZ"
qlib_code = TuShareCodeConverter.to_qlib_format("000001.SZ")     # -> "SZ000001"
raw_code = TuShareCodeConverter.normalize_code("000001.SZ", "raw")  # -> "000001"
```

### 数据处理工具

```python
from qlib.contrib.data.tushare.utils import TuShareDataProcessor

# 验证交易数据
is_valid, errors = TuShareDataProcessor.validate_trading_data(df)
if not is_valid:
    print(f"数据验证失败: {errors}")

# 清洗数据
cleaned_data = TuShareDataProcessor.clean_trading_data(raw_data)

# 价格复权
adjusted_data = TuShareDataProcessor.adjust_price(df, method="qfq")

# 计算技术指标
indicators_data = TuShareDataProcessor.calculate_technical_indicators(df)
print(indicators_data[["ma_5", "ma_20", "rsi", "macd"]].head())
```

### 日期处理工具

```python
from qlib.contrib.data.tushare.utils import TuShareDateUtils

# 日期格式转换
tushare_date = TuShareDateUtils.to_tushare_date("2024-01-01")  # -> "20240101"
dt_object = TuShareDateUtils.from_tushare_date("20240101")    # -> datetime(2024, 1, 1)

# 获取日期范围
date_range = TuShareDateUtils.get_date_range("20240101", "20240107")
# -> ["20240101", "20240102", "20240103", "20240104", "20240105", "20240106", "20240107"]
```

## 🛠 缓存管理

### 查看缓存统计

```python
with TuShareProvider(config) as provider:
    stats = provider.get_cache_stats()
    print("缓存统计:")
    print(f"- 启用状态: {stats['enabled']}")
    print(f"- 内存缓存: {stats.get('memory', {})}")
    print(f"- 磁盘缓存: {stats.get('disk', {})}")
```

### 缓存操作

```python
# 清空所有缓存
provider.clear_cache(level="all")

# 只清空内存缓存
provider.clear_cache(level="memory")

# 只清空磁盘缓存
provider.clear_cache(level="disk")
```

### 手动缓存控制

```python
from qlib.contrib.data.tushare.cache import TuShareCacheManager

cache_manager = TuShareCacheManager(config)

# 生成缓存键
cache_key = cache_manager.generate_key("feature", "000001.SZ", "close", "20240101", "20240131")

# 手动设置缓存
cache_manager.set(cache_key, data, level="all")

# 手动获取缓存
cached_data = cache_manager.get(cache_key)

# 删除特定缓存
cache_manager.delete(cache_key)
```

## 🚨 错误处理

### 常见错误类型

```python
from qlib.contrib.data.tushare.exceptions import (
    TuShareError,
    TuShareConfigError,
    TuShareAPIError,
    TuShareDataError,
    TuShareCacheError
)

try:
    data = provider.features(instruments, fields, start_time, end_time)
except TuShareConfigError as e:
    print(f"配置错误: {e}")
except TuShareAPIError as e:
    print(f"API调用错误: {e}, 状态码: {e.status_code}")
except TuShareDataError as e:
    print(f"数据错误: {e}, 股票: {e.symbol}, 字段: {e.field}")
except TuShareCacheError as e:
    print(f"缓存错误: {e}, 缓存键: {e.cache_key}")
except TuShareError as e:
    print(f"TuShare通用错误: {e}")
```

### 错误处理装饰器

```python
from qlib.contrib.data.tushare.exceptions import handle_tushare_error

@handle_tushare_error
def safe_data_fetch(symbol, start_date, end_date):
    return api_client.get_daily_data(symbol, start_date, end_date)

# 自动处理异常并转换为TuShareError
data = safe_data_fetch("000001.SZ", "20240101", "20240131")
```

## 📈 性能优化建议

### 1. 缓存策略优化

```python
# 针对高频数据使用更长的TTL
config = TuShareConfig(
    cache_ttl=7200,  # 2小时缓存
    max_cache_size=2*1024*1024*1024,  # 2GB缓存
)
```

### 2. 批量请求优化

```python
# 使用批量请求减少API调用
symbols = ["000001.SZ", "000002.SZ", "600000.SH", "600036.SH"]
data = provider.features(
    instruments=symbols,
    fields=["close", "volume"],
    start_time="2024-01-01",
    end_time="2024-12-31"
)
```

### 3. 频率限制管理

```python
# 针对高级账户调整频率限制
config = TuShareConfig(
    rate_limit=500,  # 增加请求频率
    max_retries=5,   # 增加重试次数
)
```

## 🔍 监控和日志

### API调用监控

```python
# 启用详细的API调用日志
config = TuShareConfig(
    enable_api_logging=True,
    log_level="DEBUG"
)

# 监控请求延迟和成功率
with TuShareProvider(config) as provider:
    start_time = time.time()
    data = provider.features(instruments, fields, start_time, end_time)
    elapsed_time = time.time() - start_time
    print(f"数据获取耗时: {elapsed_time:.2f}秒")
```

### 缓存性能监控

```python
# 定期检查缓存命中率
cache_stats = provider.get_cache_stats()
memory_stats = cache_stats.get("memory", {})
disk_stats = cache_stats.get("disk", {})

print(f"内存缓存命中率: {memory_stats.get('hit_rate', 0):.2%}")
print(f"磁盘缓存大小: {disk_stats.get('total_size', 0) / 1024 / 1024:.2f}MB")
```

## 🤝 贡献指南

欢迎提交Issue和Pull Request来改进这个项目。

### 开发环境设置

```bash
# 克隆项目
git clone https://github.com/microsoft/qlib.git
cd qlib

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
python -m pytest qlib/contrib/data/tushare/tests/
```

## 📄 许可证

本项目遵循Qlib的许可证协议。

## 🆘 故障排除

### 常见问题

**Q: Token无效或过期**
A: 请检查TuShare Token是否正确，或联系TuShare客服续费。

**Q: 频率限制错误**
A: 调整`rate_limit`配置或升级TuShare账户。

**Q: 数据为空**
A: 检查股票代码格式和日期范围是否正确。

**Q: 缓存问题**
A: 使用`provider.clear_cache()`清空缓存重试。

### 日志调试

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 查看详细的调试信息
config = TuShareConfig(
    log_level="DEBUG",
    enable_api_logging=True
)
```

## 📞 支持

- 📧 邮箱：qlib@example.com
- 💬 讨论：[GitHub Discussions](https://github.com/microsoft/qlib/discussions)
- 🐛 问题：[GitHub Issues](https://github.com/microsoft/qlib/issues)
- 📖 文档：[Qlib官方文档](https://qlib.readthedocs.io/)