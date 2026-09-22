# Qlib 数据包自动下载脚本使用指南（增强版）

## 脚本功能

智能检测 GitHub Releases 是否有最新交易日发布的 Qlib 数据包，如果存在则使用 aria2c 多线程下载，并自动更新 Qlib 数据目录。

### 核心特性

- ✅ **智能交易日检测**：自动识别交易日、周末、节假日
- ✅ **持续检测机制**：数据未上线持续检测，直到成功下载
- ✅ **节假日延迟处理**：支持节假日前数据延后发布场景
- ✅ **多线程下载**：使用 aria2c 实现高速下载（16连接/16分段）
- ✅ **安全备份**：更新前自动备份现有数据
- ✅ **原子更新**：失败自动回滚，保证数据一致性
- ✅ **数据验证**：解压后验证数据完整性和目标日期
- ✅ **去重下载**：已下载的数据不会重复下载
- ✅ **详细日志**：完整的操作日志记录

## 文件说明

- **auto_download_qlib_bin.sh** - 主执行脚本（增强版）
- **install_cron.sh** - 自动安装定时任务
- **README_auto_download.md** - 本说明文档

## 工作原理

### 智能检测逻辑

```
定时触发（每30分钟，16:00-23:30）
    ↓
检查时间窗口和交易日
    ↓
今天是否在16:00-23:30？
├─ 否 → 跳过检测
└─ 是 → 继续
    ↓
今天是否是交易日？
├─ 是 → 检测今天的数据
└─ 否 → 检查是否需要持续检测
         ↓
    最后成功日期的下一个交易日已过去？
    ├─ 是 → 继续检测（可能是延后发布）
    └─ 否 → 跳过检测
```

### 数据下载流程

```
确定目标日期
    ↓
检查是否已下载
├─ 是 → 跳过（去重）
└─ 否 → 继续
    ↓
探测 GitHub Release（curl -r 0-0 首字节探测 + 重试）
├─ 404 未上线 → 等待下次检测（exit 0）
├─ 探测失败（网络/5xx/超时）
│   ├─ 任一镜像探测到该 URL → 视为已发布，走镜像下载（镜像链救援）
│   └─ 直连与镜像均不可用 → 报错退出（exit 1，调度器可感知）
└─ 已上线 → 选镜像下载（镜像按序探测，全部失败回退直连；
            下载后 gzip 校验，损坏自动重试；每次重试重新选镜像）
    ↓
备份现有数据
    ↓
解压新数据（--strip-components=1）
    ↓
验证数据完整性
├─ 成功 → 记录状态 → 完成
└─ 失败 → 恢复备份 → 报错
```

> **退出码语义**（调度/告警依赖）：`0` = 正常（完成、或按规则跳过：不在时间窗、
> 未发布 404、已下载、锁冲突）；`1` = 异常（探测失败、下载失败、解压/验证失败）。
> 探测失败与"未发布"严格区分——前者若被静默吞掉，数据会持续陈旧而调度器毫无感知
> （2026-04~06 断更的教训）。

### 时间窗口和检测策略

| 时间段 | 行为 |
|--------|------|
| 00:00-15:59 | 不检测（数据未发布） |
| 16:00-23:30 | 检测窗口期（每30分钟） |
| 23:30-23:59 | 不检测（等待第二天） |

> `QDLIB_FORCE_CHECK=1` 可跳过时间窗与交易日判定（幂等性由状态文件保证），
> 供定时任务补偿与手动补跑使用。

### 交易日处理

| 日期类型 | 行为 |
|---------|------|
| 普通交易日 | 检测当日数据，未成功则持续检测 |
| 周末 | 不检测（除非前个交易日数据未下载） |
| 节假日 | 不检测（需要预先配置节假日列表） |
| 节假日前 | 延长检测期（数据可能延后发布） |

## 前置要求

### 必需工具

```bash
# macOS (Homebrew)
brew install aria2 curl

# Linux (Debian/Ubuntu)
sudo apt-get install aria2 curl

# Linux (CentOS/RHEL)
sudo yum install aria2 curl
```

### 验证安装

```bash
which aria2c
which curl
which tar
```

## 使用方法

### 方式一：自动安装（推荐）

```bash
cd /Users/berton/Github/qlib
./scripts/install_cron.sh
```

### 方式二：手动添加到 crontab

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每30分钟执行一次，覆盖 16:00-23:30 检测窗口）
0,30 16-23 * * * sleep $((RANDOM % 60)); /bin/bash /Users/berton/Github/qlib/scripts/auto_download_qlib_bin.sh
```

### 方式三：手动执行测试

```bash
# 赋予执行权限
chmod +x scripts/auto_download_qlib_bin.sh

# 手动运行（受时间窗/交易日限制）
./scripts/auto_download_qlib_bin.sh

# 手动补跑：跳过时间窗与交易日判定（幂等，已下载会自动跳过）
QDLIB_FORCE_CHECK=1 ./scripts/auto_download_qlib_bin.sh
```

## 配置选项

编辑脚本中的配置区域：

```bash
# 基础配置
REPO_OWNER="chenditc"
REPO_NAME="investment_data"
# 下载目录必须是 TCC 安全路径：~/Downloads 会被 macOS 拒绝后台进程访问
# （launchd/cron 下 rm/tar 报 "Operation not permitted"，2026-05~06 断更根因）
DOWNLOAD_DIR="${HOME}/.qlib/downloads"
QLIB_DATA_DIR="${HOME}/.qlib/qlib_data"
CN_DATA_DIR="${QLIB_DATA_DIR}/cn_data"
CN_DATA_BACKUP="${QLIB_DATA_DIR}/cn_data_backup"

# 日志和状态（macOS 标准日志目录，launchd 可写）
LOG_DIR="${HOME}/Library/Logs/qlib_data"
LOG_FILE="${LOG_DIR}/download.log"
STATE_FILE="${LOG_DIR}/.download_state"  # 记录最后成功的日期

# 下载配置
MAX_RETRIES=3
RETRY_DELAY=10
# 多连接并发 + 掐死停滞连接 + 坏连接快速重建（设计依据见脚本内注释）
ARIA2C_OPTIONS="-x 16 -s 16 -k 1M --lowest-speed-limit=10K --timeout=30 --connect-timeout=10 --retry-wait=2"

# GitHub 加速镜像前缀（按序探测，首个可用者胜出；全部失败回退直连）。
# 自建 Cloudflare Worker 反代后把地址加在首位（见下方"镜像加速"一节）。
MIRROR_PREFIXES=(
    "https://ghfast.top"
    "https://ghp.ci"
)

# 交易日配置
MAX_CHECK_DAYS=9  # 最多向前查找9个交易日（处理长假）

# 节假日配置（每年更新）
HOLIDAYS_2025=(
    "2025-01-01"  # 元旦
    "2025-01-28" "2025-01-29" "2025-01-30" "2025-01-31"  # 春节
    "2025-02-01" "2025-02-02" "2025-02-03" "2025-02-04"
    "2025-04-04" "2025-04-05" "2025-04-06"  # 清明节
    "2025-05-01" "2025-05-02" "2025-05-03" "2025-05-04" "2025-05-05"  # 劳动节
    "2025-05-31" "2025-06-02"  # 端午节（调休）
    "2025-10-01" "2025-10-02" "2025-10-03" "2025-10-04"  # 国庆节
    "2025-10-05" "2025-10-06" "2025-10-07" "2025-10-08"
)
```

## 镜像加速

直连 GitHub Releases 在无代理网络下实测仅 ~100KB/s（540MB 需 100+ 分钟），且存在
整包挂死风险。脚本通过 `MIRROR_PREFIXES` 镜像链解决：

- **下载选路**：每次下载尝试按序探测镜像（首字节 range 请求，`-L` 跟随跳转，
  200/206 为可用），首个可用者胜出；全部不可用回退直连。镜像只是反向代理，
  字节与直连一致，`gzip -t` 完整性校验保持不变。
- **探测救援**：直连探测失败（HTTP 000/5xx，无法区分"未发布"）时，任一镜像能
  探测到该 URL 即视为已发布并继续下载，避免把"直连拥塞"误判成"探测失败"告警。
- **镜像可用性变化频繁**（2026-09-22 实测 ghfast.top 可用、ghp.ci/gh-proxy.com/
  ghproxy.net/gh.llkk.cc 均不可用），列表按需增删即可，探测不通过自动跳过。
- **aria2c 侧**：`-x 16 -s 16 -k 1M` 并发分段（镜像实测可近似线性叠加）；
  `--lowest-speed-limit=10K` 掐死停滞连接（默认永不掐断会无限期挂死）；
  `--timeout=30 --connect-timeout=10 --retry-wait=2` 快速重建坏连接。

### 自建 Cloudflare Worker 反代（长期最稳，推荐有 CF 账号时部署）

公共镜像随时可能跑路或限流；自建 Worker 一行配置即可获得专属加速通道：

1. 参考 `scripts/cloudflare_worker_gh_proxy.js` 文件头注释，在 CF Dashboard
   创建 Worker 并粘贴部署（无需本地 CLI）。
2. 把 `https://<your-worker>.workers.dev` 加到 `MIRROR_PREFIXES` 首位。

Worker 内置 GitHub 系域名白名单（防开放代理滥用）、Range 透传（aria2c 分段可用）、
302 跳转改写（release-assets 链路保持加速）。

## 日志查看

```bash
# 查看完整日志
cat ~/Library/Logs/qlib_data/download.log

# 实时查看日志
tail -f ~/Library/Logs/qlib_data/download.log

# 查看最近10条
tail -n 10 ~/Library/Logs/qlib_data/download.log

# 查看特定时间的日志
grep "2025-12-30" ~/Library/Logs/qlib_data/download.log
```

## 状态管理

```bash
# 查看最后下载成功的日期
cat ~/Library/Logs/qlib_data/.download_state

# 强制重新下载（删除状态文件）
rm ~/Library/Logs/qlib_data/.download_state
```

## 典型场景

### 场景1：正常交易日

```
日期：2025-01-15（周三，交易日）
时间：16:30
流程：
  1. 检测到是交易日
  2. 检查 2025-01-15 数据是否已下载
  3. 未下载 → 检查 GitHub Release
  4. 存在 → 下载并安装
  5. 记录状态：2025-01-15
```

### 场景2：数据延迟发布

```
日期：2025-01-15（周三，交易日）
时间：16:30 - 数据未上线
     17:00 - 数据未上线
     17:30 - 数据上线并下载

流程：
  1. 16:30 检测 → 未上线 → 等待
  2. 17:00 检测 → 未上线 → 等待
  3. 17:30 检测 → 上线 → 下载并安装
  4. 后续时间点：已下载 → 跳过
```

### 场景3：节假日前延后发布

```
日期：2025-01-27（周一，春节前最后交易日）
时间：18:00 - 数据仍未上线

情况：数据可能延后到春节假期发布

流程：
  1. 1月27日晚检测 → 未上线 → 持续检测
  2. 1月28日（春节）→ 非交易日，但继续检测
  3. 1月29日（春节）→ 继续检测
  4. 1月30日（春节）→ 数据上线 → 下载并安装
  5. 后续日期：已下载 → 跳过
```

### 场景4：周末处理

```
日期：2025-01-18（周六）
时间：16:30

情况：上一个交易日（1月17日）数据已下载

流程：
  1. 检测到是周末
  2. 检查状态文件 → 最后成功：2025-01-17
  3. 下一个交易日：2025-01-20（周一）
  4. 今天（1月18日）< 2025-01-20 → 跳过检测

结果：周末不执行检测
```

## 数据更新流程

```
检测当日发布
    ↓
下载压缩包
    ↓
【数据更新开始】
    ↓
检查 cn_data_backup 是否存在
    ├─ 存在 → 删除
    └─ 不存在 → 继续
    ↓
备份 cn_data → cn_data_backup
    ↓
解压到 cn_data (--strip-components=1)
    ↓
验证数据完整性
    ├─ 成功 → 删除压缩包 → 记录状态 → 完成
    └─ 失败 → 恢复备份 → 报错退出
```

### 失败回滚机制

脚本在以下情况会自动回滚：
- 解压失败
- 数据验证失败（缺少 calendars 或 instruments 目录）
- 文件损坏

回滚操作：
1. 删除损坏的 cn_data 目录
2. 将 cn_data_backup 重命名回 cn_data
3. 记录错误日志

## 日志查看

```bash
# 查看完整日志
cat ~/Library/Logs/qlib_data/download.log

# 实时查看日志
tail -f ~/Library/Logs/qlib_data/download.log

# 查看最近10条
tail -n 10 ~/Library/Logs/qlib_data/download.log
```

## 工作流程

```
每30分钟触发（16:00-23:30）
    ↓
检查时间窗口和交易日
    ↓
不在窗口/非必要 → 跳过
    ↓
在窗口且必要 → 继续
    ↓
检查数据是否已下载
    ↓
已下载 → 跳过
未下载 → 继续
    ↓
检查 GitHub Release
    ↓
未上线 → 等待下次检测
    ↓
已上线 → 下载
    ↓
备份现有 cn_data
    ↓
解压新数据（--strip-components=1）
    ↓
验证数据
    ↓
┌───┴───┐
↓       ↓
成功    失败
↓       ↓
完成   恢复备份
```

## 故障排除

### 问题1：命令未找到

```bash
# 检查命令是否存在
which aria2c
which curl

# macOS 安装
brew install aria2

# Linux 安装
sudo apt-get install aria2 curl
```

### 问题2：脚本在非交易日也执行

**原因**：上一个交易日数据未成功下载

**解决**：
```bash
# 检查状态
cat ~/Library/Logs/qlib_data/.download_state

# 查看日志确认原因
tail -n 50 ~/Library/Logs/qlib_data/download.log

# 如果是网络问题，手动运行
./scripts/auto_download_qlib_bin.sh
```

### 问题3：数据下载后没有更新

**原因**：可能是数据验证失败或解压失败

**解决**：
```bash
# 查看错误日志
grep "ERROR" ~/Library/Logs/qlib_data/download.log

# 检查备份数据是否存在
ls -la ~/.qlib/qlib_data/cn_data_backup

# 手动恢复备份
rm -rf ~/.qlib/qlib_data/cn_data
mv ~/.qlib/qlib_data/cn_data_backup ~/.qlib/qlib_data/cn_data
```

### 问题4：节假日配置不准确

**解决**：更新节假日列表

```bash
# 编辑脚本
vim scripts/auto_download_qlib_bin.sh

# 找到 HOLIDAYS_2025 数组
# 添加或修改节假日日期
```

### 问题5：下载速度慢

调整 aria2c 参数：

```bash
# 编辑脚本
vim scripts/auto_download_qlib_bin.sh

# 修改配置
ARIA2C_OPTIONS="-x 32 -s 32"  # 增加连接数

# 或限制下载速度
ARIA2C_OPTIONS="-x 16 -s 16 --max-download-limit=5000K"
```

## 高级配置

### 调整检测频率

```bash
# 编辑 crontab
crontab -e

# 每15分钟检测一次
*/15 16-23 * * * sleep $((RANDOM % 60)); /bin/bash /Users/berton/Github/qlib/scripts/auto_download_qlib_bin.sh

# 每小时检测一次
0 16-23 * * * sleep $((RANDOM % 60)); /bin/bash /Users/berton/Github/qlib/scripts/auto_download_qlib_bin.sh
```

### 自定义节假日列表

```bash
# 从文件读取节假日
HOLIDAYS_FILE="${DOWNLOAD_DIR}/.holidays"

if [[ -f "${HOLIDAYS_FILE}" ]]; then
    mapfile -t HOLIDAYS < "${HOLIDAYS_FILE}"
fi
```

### 下载完成后通知

**macOS**：
```bash
# 在脚本最后添加
osascript -e 'display notification "Qlib 数据下载完成" with title "自动下载"'
```

**Linux**：
```bash
# 需要安装 libnotify-bin
sudo apt-get install libnotify-bin

# 在脚本最后添加
notify-send "Qlib 下载" "数据下载完成"
```

## 监控和维护

### 创建日志轮转（防止日志过大）

创建 `/etc/logrotate.d/qlib-download`：

```
/Users/your_username/Library/Logs/qlib_data/download.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
```

### 监控磁盘空间

```bash
# 添加到 crontab 检查磁盘空间
0 8 * * * df -h ~/.qlib/qlib_data | awk 'NR==2 {if ($5+0 > 80) print "警告：磁盘使用率超过80%"}'
```

### 清理旧备份

```bash
# 创建清理脚本
cat > ~/scripts/cleanup_qlib_backup.sh << 'EOF'
#!/bin/bash
# 删除超过7天的备份
find ~/.qlib/qlib_data/cn_data_backup -type d -mtime +7 -exec rm -rf {} \;
EOF

chmod +x ~/scripts/cleanup_qlib_backup.sh

# 添加到 crontab（每周日凌晨执行）
0 3 * * 0 ~/scripts/cleanup_qlib_backup.sh
```

## 安全建议

1. **不要在脚本中硬编码 Token**：使用公共 API 即可
2. **限制脚本权限**：`chmod 700 scripts/auto_download_qlib_bin.sh`
3. **使用专用用户**：创建专门的用户运行定时任务
4. **定期检查日志**：监控异常行为
5. **备份状态文件**：定期备份 `.download_state` 文件

## 性能优化

### aria2c 参数调优

```bash
# 高速连接（适合千兆以上网络）
ARIA2C_OPTIONS="-x 32 -s 32 --split=32 --min-split-size=1M"

# 稳定连接（适合不稳定网络）
ARIA2C_OPTIONS="-x 8 -s 8 --timeout=120 --connect-timeout=60"

# 节省资源（适合低配机器）
ARIA2C_OPTIONS="-x 4 -s 4 --lowest-speed-limit=10K"

# 限制带宽（避免影响其他应用）
ARIA2C_OPTIONS="-x 16 -s 16 --max-download-limit=5000K"
```

### 脚本优化

```bash
# 减少日志输出（仅记录重要事件）
LOG_LEVEL="WARN"  # DEBUG, INFO, WARN, ERROR

# 使用 rsync 替代 cp（更快）
rsync -av --delete "${CN_DATA_DIR}/" "${CN_DATA_BACKUP}/"
```

## 系统定时器（Linux 推荐）

创建服务文件 `/etc/systemd/system/qlib-download.service`：

```ini
[Unit]
Description=Qlib Data Auto Download
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=your_username
ExecStart=/bin/bash /Users/berton/Github/qlib/scripts/auto_download_qlib_bin.sh
Nice=10
IOSchedulingClass=idle
IOSchedulingPriority=7

[Install]
WantedBy=multi-user.target
```

创建定时器文件 `/etc/systemd/system/qlib-download.timer`：

```ini
[Unit]
Description=Qlib Data Auto Download Timer
Requires=qlib-download.service

[Timer]
OnCalendar=16:00-23:30/30min
RandomizedDelaySec=60
AccuracySec=1m
Persistent=true

[Install]
WantedBy=timers.target
```

启用定时器：

```bash
sudo systemctl daemon-reload
sudo systemctl enable qlib-download.timer
sudo systemctl start qlib-download.timer

# 查看状态
sudo systemctl list-timers
sudo systemctl status qlib-download.timer
```

## 相关链接

- [GitHub Releases](https://github.com/chenditc/investment_data/releases)
- [aria2 文档](https://aria2.github.io/manual/en/html/aria2c.html)
- [crontab.guru](https://crontab.guru/) - Cron 表达式生成器
- [中国节假日](http://www.gov.cn/xinwen/2024-12/23/content_6992277.htm) - 国务院节假日安排
