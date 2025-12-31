# ETF数据自动更新系统

> 自动从TuShare获取ETF日线行情数据，并转换为Qlib格式的完整解决方案。

## 功能特性

- ✅ **自动数据获取**：从TuShare API获取ETF日线行情数据
- ✅ **增量更新**：智能检测本地数据最新日期，仅下载新数据
- ✅ **全量下载**：支持一次性下载全部历史数据
- ✅ **Qlib格式转换**：自动转换为Qlib二进制格式
- ✅ **定时任务**：支持cron定时自动执行
- ✅ **错误处理**：完善的错误处理和重试机制
- ✅ **日志记录**：详细的日志记录和进度跟踪

## 文件说明

| 文件 | 功能描述 |
|------|---------|
| `etf_auto_download.py` | ETF数据下载脚本 |
| `etf_convert_qlib.py` | Qlib格式转换脚本 |
| `etf_daily_update.sh` | 完整的每日更新脚本 |
| `install_etf_cron.sh` | Cron定时任务安装脚本 |
| `etf_config.yaml` | 配置文件 |

## 快速开始

### 1. 环境准备

```bash
# 设置TuShare Token
export TUSHARE_TOKEN='your_token_here'

# 确保已安装依赖
pip install qlib tushare pandas numpy pyyaml tqdm
```

### 2. 首次使用 - 全量下载

```bash
# 下载配置文件中ETF的历史数据
python scripts/etf_auto_download.py --full-download --convert-qlib
```

### 3. 日常使用 - 增量更新

```bash
# 增量更新今日数据
python scripts/etf_auto_download.py --convert-qlib
```

### 4. 安装定时任务

```bash
# 安装cron定时任务（每个工作日16:00执行）
bash scripts/install_etf_cron.sh
```

## 详细使用说明

### etf_auto_download.py - 数据下载脚本

**基础用法**：
```bash
# 使用配置文件中的ETF列表下载
python scripts/etf_auto_download.py

# 下载指定ETF
python scripts/etf_auto_download.py --etf-codes 510300.SH,510500.SH

# 全量下载历史数据
python scripts/etf_auto_download.py --full-download

# 下载数据并转换为Qlib格式
python scripts/etf_auto_download.py --convert-qlib
```

**参数说明**：
| 参数 | 说明 |
|------|------|
| `--config` | 配置文件路径（默认: scripts/etf_config.yaml） |
| `--etf-codes` | ETF代码列表，逗号分隔（覆盖配置文件） |
| `--full-download` | 全量下载历史数据 |
| `--convert-qlib` | 转换为Qlib格式 |
| `--data-dir` | 原始数据存储目录 |
| `--qlib-dir` | Qlib格式数据目录 |

**示例**：
```bash
# 下载沪深300ETF和上证50ETF
python scripts/etf_auto_download.py \
    --etf-codes 510300.SH,510050.SH \
    --convert-qlib
```

### etf_convert_qlib.py - 格式转换脚本

**用法**：
```bash
# 将下载的CSV数据转换为Qlib格式
python scripts/etf_convert_qlib.py \
    --source-dir ~/.qlib/qlib_data/cn_data/etf_raw \
    --qlib-dir ~/.qlib/qlib_data/cn_data/etf
```

### etf_daily_update.sh - 完整更新脚本

**用法**：
```bash
# 使用默认配置
python scripts/etf_daily_update.sh

# 使用配置文件
python scripts/etf_daily_update.sh --config etf_config.yaml

# 全量下载
python scripts/etf_daily_update.sh --full-download
```

### install_etf_cron.sh - 定时任务安装

**用法**：
```bash
# 安装定时任务
bash scripts/install_etf_cron.sh

# 查看定时任务
crontab -l

# 查看执行日志
tail -f ~/.qlib/qlib_data/cn_data/etf/cron_$(date +%Y%m%d).log

# 手动测试运行
~/.qlib/qlib_data/cn_data/etf/etf_update_wrapper.sh
```

## 数据目录结构

```
~/.qlib/qlib_data/cn_data/
├── etf_raw/                      # 原始CSV数据
│   ├── 510300.SH.csv            # 沪深300ETF数据
│   ├── 510500.SH.csv            # 中证500ETF数据
│   └── update_YYYYMMDD.log      # 更新日志
│
└── etf/                          # Qlib格式数据
    ├── calendars/
    │   └── day.txt              # 交易日历
    ├── features/
    │   ├── 510300.sh/
    │   │   ├── close.day.bin
    │   │   ├── open.day.bin
    │   │   ├── high.day.bin
    │   │   ├── low.day.bin
    │   │   ├── volume.day.bin
    │   │   └── factor.day.bin
    │   └── 510500.sh/
    │       └── ...
    ├── instruments/
    │   └── all.txt              # ETF列表
    └── convert.log              # 转换日志
```

## 在Qlib中使用ETF数据

```python
import qlib
from qlib.data import D

# 初始化Qlib（使用ETF数据）
qlib.init(
    provider_uri="~/.qlib/qlib_data/cn_data/etf",
    region="cn"
)

# 获取ETF列表
etf_list = D.instruments(market="all")
print(f"可用ETF数量: {len(etf_list)}")

# 获取ETF数据
etf_codes = ["510300.SH", "510500.SH"]
features = D.features(
    etf_codes,
    fields=["$close", "$volume", "$open"],
    start_time="2020-01-01",
    end_time="2024-12-31"
)

print(features.head())
```

## 配置文件

修改 `etf_config.yaml` 来自定义行为：

```yaml
# 添加或删除ETF
etf_list:
  - 510300.SH
  - 510500.SH
  # 添加更多...

# 调整下载间隔
download_interval: 0.2  # 秒

# 调整重试次数
max_retries: 3

# 启用/禁用自动转换
convert_to_qlib: true

# 日志级别
log_level: INFO  # DEBUG, INFO, WARNING, ERROR
```

## 主流ETF列表

默认配置文件包含以下ETF（详见 `etf_config.yaml`）：

### 宽基指数ETF
- `510300.SH` - 沪深300ETF
- `510500.SH` - 中证500ETF
- `510050.SH` - 上证50ETF
- `159915.SZ` - 深证300ETF
- `159919.SZ` - 沪深300ETF（深）
- `159901.SZ` - 深100ETF
- `159949.SZ` - 创业板50ETF
- `159934.SZ` - 创业板ETF
- `512100.SH` - 中证1000ETF
- `159338.SZ` - 中证A500ETF

### 行业/主题ETF
- `512000.SH` - 券商ETF
- `512480.SH` - 计算机ETF
- `512170.SH` - 医疗ETF
- `512010.SH` - 医药ETF
- `512890.SH` - 红利低波ETF

### 海外ETF
- `513180.SH` - 恒生科技指数ETF
- `513330.SH` - 恒生互联网ETF
- `159941.SZ` - 纳指ETF
- `513500.SH` - 标普500ETF

### 商品ETF
- `518880.SH` - 黄金ETF

> 💡 提示：可以通过修改 `etf_config.yaml` 添加或删除ETF

## 故障排除

### 问题1：TuShare API错误

```bash
# 检查Token是否设置
echo $TUSHARE_TOKEN

# 检查Token是否有效
python -c "import tushare as ts; ts.set_token('$TUSHARE_TOKEN'); print(ts.pro_api().trade_cal(exchange='SSE', start_date='20240101', end_date='20240105'))"
```

### 问题2：数据转换失败

```bash
# 检查原始数据是否存在
ls -lh ~/.qlib/qlib_data/cn_data/etf_raw/

# 查看转换日志
cat ~/.qlib/qlib_data/cn_data/etf/convert.log
```

### 问题3：定时任务未执行

```bash
# 检查cron服务状态
sudo systemctl status cron  # Linux
launchctl list | grep cron  # macOS

# 查看cron日志
grep CRON /var/log/syslog  # Linux
log show --predicate 'eventMessage contains "cron"' --info  # macOS

# 手动测试定时任务脚本
~/.qlib/qlib_data/cn_data/etf/etf_update_wrapper.sh
```

## 性能优化建议

1. **批量下载**：首次使用时使用 `--full-download` 一次性下载所有历史数据
2. **增量更新**：日常使用增量更新，仅下载新数据
3. **调整间隔**：根据TuShare积分限制调整 `download_interval`
4. **并行处理**：对于大量ETF，可以分批并行下载

## 常见问题 (FAQ)

### Q1: 支持哪些ETF？
A: 支持所有TuShare fund_daily接口覆盖的ETF，包括宽基指数ETF、行业ETF、主题ETF等。

### Q2: 数据更新频率？
A: 每个交易日16:00左右自动更新（通过cron定时任务）。

### Q3: 如何添加新的ETF？
A: 在配置文件 `etf_config.yaml` 中添加ETF代码，或使用 `--etf-codes` 参数指定。

### Q4: 如何回测ETF策略？
A: 参考"在Qlib中使用ETF数据"部分初始化Qlib，然后使用Qlib的回测引擎。

### Q5: 数据存储空间？
A: 每个ETF约1-2MB/年（日线数据），20个ETF约10年历史数据约200MB。

## 许可证

MIT License
