# 从 Crontab 迁移到 Launchd 指南

> **作者**：Qlib 脚本工具集
> **更新日期**：2025-12-31
> **适用系统**：macOS

## 📋 目录

- [概述](#概述)
- [为什么选择 Launchd](#为什么选择-launchd)
- [快速开始](#快速开始)
- [详细配置说明](#详细配置说明)
- [从 Crontab 迁移](#从-crontab-迁移)
- [常见问题](#常见问题)

---

## 概述

本指南介绍如何将 Qlib 自动下载脚本从 crontab 迁移到 macOS 原生的 launchd 定时任务系统。

### 相关文件

```
scripts/
├── auto_download_qlib_bin.sh        # 主下载脚本
├── com.qlib.autodownload.plist      # launchd 配置文件
├── launchd_manager.sh               # 管理辅助脚本
└── LAUNCHD_MIGRATION_GUIDE.md       # 本指南
```

---

## 为什么选择 Launchd

### Launchd 相比 Crontab 的优势

| 特性 | Crontab | Launchd | 说明 |
|-----|---------|---------|------|
| **电源管理** | ❌ 不支持 | ✅ 完整支持 | 笔记本睡眠/唤醒后自动恢复 |
| **时区处理** | ⚠️ 手动处理 | ✅ 自动处理 | 系统时区变化无需修改 |
| **日志管理** | ⚠️ 需手动配置 | ✅ 内置支持 | 自动分离 stdout/stderr |
| **环境变量** | ⚠️ 有限支持 | ✅ 完整支持 | 可配置完整环境 |
| **负载控制** | ❌ 不支持 | ✅ 支持优先级 | Nice 值、后台 IO |
| **崩溃重启** | ❌ 不支持 | ✅ KeepAlive | 任务崩溃自动重启 |
| **用户界面** | ❌ 纯命令行 | ✅ 图形化管理 | launchctl 管理 |

### 技术优势

```
★ Insight ─────────────────────────────────────
launchd 的核心优势：
1. 电源管理：macOS 会在合适的时机执行任务，
   避免在电池供电时频繁唤醒
2. 系统集成：launchctl 提供统一的任务管理接口
3. 灵活调度：支持时间间隔、日历时间等多种调度方式
─────────────────────────────────────────────────
```

---

## 快速开始

### 前置条件

1. **macOS 系统**：launchd 是 macOS 特有的任务调度系统
2. **脚本文件**：确保 `auto_download_qlib_bin.sh` 存在且可执行
3. **必要工具**：curl, aria2c, tar 等命令行工具

### 安装步骤

#### 1. 使用管理脚本（推荐）

```bash
# 进入脚本目录
cd /Users/berton/Github/qlib/scripts

# 安装 launchd 任务
./launchd_manager.sh install
```

安装成功后，你会看到：

```
✓ launchd 任务安装成功！

任务名称：com.qlib.autodownload
配置文件：~/Library/LaunchAgents/com.qlib.autodownload.plist
执行脚本：/Users/berton/Github/qlib/scripts/auto_download_qlib_bin.sh

使用以下命令管理任务：
  ./launchd_manager.sh status   # 查看状态
  ./launchd_manager.sh start    # 启动任务
  ./launchd_manager.sh stop     # 停止任务
  ./launchd_manager.sh restart  # 重启任务
  ./launchd_manager.sh logs     # 查看日志
  ./launchd_manager.sh uninstall # 卸载任务
```

#### 2. 手动安装（可选）

如果你想手动安装，可以执行以下步骤：

```bash
# 1. 复制 plist 文件
cp com.qlib.autodownload.plist ~/Library/LaunchAgents/

# 2. 加载任务
launchctl load ~/Library/LaunchAgents/com.qlib.autodownload.plist

# 3. 验证任务已加载
launchctl list | grep com.qlib.autodownload
```

### 验证安装

```bash
# 查看任务状态
./launchd_manager.sh status

# 预期输出：
# ✓ 任务状态：已加载
# 任务详情：
# 12345 0 com.qlib.autodownload
```

---

## 详细配置说明

### plist 文件结构

`com.qlib.autodownload.plist` 是一个标准的 macOS 属性列表文件，定义了任务的所有配置。

### 核心配置项

#### 1. 任务标识（Label）

```xml
<key>Label</key>
<string>com.qlib.autodownload</string>
```

- **用途**：唯一标识任务
- **命名规范**：反向域名格式（如 `com.company.task`）

#### 2. 执行配置

```xml
<key>ProgramArguments</key>
<array>
    <string>/path/to/script.sh</string>
</array>

<key>WorkingDirectory</key>
<string>/path/to/working/directory</string>
```

#### 3. 调度方式

**方式一：时间间隔（当前配置）**

```xml
<key>StartInterval</key>
<integer>1800</integer>  <!-- 1800秒 = 30分钟 -->
```

**方式二：日历调度（备选方案）**

```xml
<key>StartCalendarInterval</key>
<array>
    <dict>
        <key>Hour</key>
        <integer>16</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <!-- 更多时间点... -->
</array>
```

#### 4. 环境变量

```xml
<key>EnvironmentVariables</key>
<dict>
    <key>PATH</key>
    <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>

    <!-- 如需 token，可在此添加 -->
    <!--
    <key>TUSHARE_TOKEN</key>
    <string>your_token_here</string>
    -->
</dict>
```

#### 5. 日志配置

```xml
<key>StandardOutPath</key>
<string>/Users/berton/Downloads/qlib_data/launchd_stdout.log</string>

<key>StandardErrorPath</key>
<string>/Users/berton/Downloads/qlib_data/launchd_stderr.log</string>
```

#### 6. 高级选项

```xml
<!-- 任务崩溃时自动重启 -->
<key>KeepAlive</key>
<false/>

<!-- 低优先级后台 IO -->
<key>LowPriorityBackgroundIO</key>
<true/>

<!-- 进程优先级 -->
<key>Nice</key>
<integer>10</integer>

<!-- 加载时立即执行 -->
<key>RunAtLoad</key>
<false/>
```

### 调度策略选择

#### 当前配置：时间间隔（StartInterval）

- **配置**：每 30 分钟执行一次
- **优点**：实现简单，执行频率固定
- **缺点**：在非窗口期也会执行（由脚本内部控制）

#### 备选方案：日历调度（StartCalendarInterval）

- **配置**：在指定时间点执行（如 16:00, 16:30, 17:00...）
- **优点**：精确控制执行时间，避免非窗口期执行
- **缺点**：配置较繁琐

**建议**：如果希望更精确的控制，可以切换到日历调度模式。

### 切换到日历调度

编辑 `com.qlib.autodownload.plist`：

```bash
# 1. 注释掉 StartInterval
# <key>StartInterval</key>
# <integer>1800</integer>

# 2. 取消注释 StartCalendarInterval 部分
# 3. 重新加载任务
./launchd_manager.sh restart
```

---

## 从 Crontab 迁移

### 检查现有 Crontab 配置

```bash
# 查看当前用户的 crontab
crontab -l
```

### 典型的 Crontab 配置

```cron
# 每30分钟执行一次（16:00-22:00）
*/30 16-22 * * 1-5 /Users/berton/Github/qlib/scripts/auto_download_qlib_bin.sh
```

### Crontab 到 Launchd 的映射

| Crontab | Launchd | 说明 |
|---------|---------|------|
| `*/30 * * * *` | `StartInterval: 1800` | 每30分钟 |
| `0 16 * * 1-5` | `StartCalendarInterval` + `Weekday` | 工作日16:00 |
| `@reboot` | `RunAtLoad: true` | 启动时执行 |
| `CRON_TZ=Asia/Shanghai` | 自动处理 | 时区 |

### 迁移步骤

#### 1. 备份现有 Crontab

```bash
# 导出当前 crontab
crontab -l > ~/crontab_backup_$(date +%Y%m%d).txt
```

#### 2. 禁用 Crontab 任务

```bash
# 编辑 crontab，注释掉相关任务
crontab -e

# 在任务前添加 # 号：
# */30 16-22 * * 1-5 /Users/berton/Github/qlib/scripts/auto_download_qlib_bin.sh
```

#### 3. 安装 Launchd 任务

```bash
./launchd_manager.sh install
```

#### 4. 测试验证

```bash
# 等待一个执行周期（30分钟），或手动触发
./launchd_manager.sh test

# 查看日志
./launchd_manager.sh logs
```

#### 5. 确认无误后移除 Crontab

```bash
# 完全删除 crontab 任务
crontab -e
# 删除相关行
```

---

## 管理和维护

### 常用命令

```bash
# 查看所有 launchd 任务
launchctl list

# 查看特定任务
launchctl list com.qlib.autodownload

# 启动任务（手动触发一次）
launchctl start com.qlib.autodownload

# 停止任务
launchctl stop com.qlib.autodownload

# 重启任务
launchctl unload ~/Library/LaunchAgents/com.qlib.autodownload.plist
launchctl load ~/Library/LaunchAgents/com.qlib.autodownload.plist

# 查看任务配置
plutil -p ~/Library/LaunchAgents/com.qlib.autodownload.plist
```

### 使用管理脚本

```bash
# 查看状态
./launchd_manager.sh status

# 启动/停止/重启
./launchd_manager.sh start
./launchd_manager.sh stop
./launchd_manager.sh restart

# 查看日志
./launchd_manager.sh logs

# 测试运行
./launchd_manager.sh test

# 卸载
./launchd_manager.sh uninstall
```

### 日志管理

#### 日志文件位置

```bash
# 脚本日志
~/Downloads/qlib_data/download.log

# launchd 标准输出
~/Downloads/qlib_data/launchd_stdout.log

# launchd 错误输出
~/Downloads/qlib_data/launchd_stderr.log
```

#### 查看日志

```bash
# 实时查看脚本日志
tail -f ~/Downloads/qlib_data/download.log

# 查看最近 50 行
tail -50 ~/Downloads/qlib_data/download.log

# 使用管理脚本
./launchd_manager.sh logs
```

#### 日志轮转（可选）

如需配置日志轮转，创建 `/etc/newsyslog.d/qlib.conf`：

```
# logfilename                 [owner:group]  mode  count  size  when  flags
/Users/berton/Downloads/qlib_data/*.log  berton:staff  640  7     1000  *     J
```

---

## 常见问题

### Q1: 任务没有执行怎么办？

**排查步骤：**

```bash
# 1. 检查任务是否已加载
./launchd_manager.sh status

# 2. 查看错误日志
./launchd_manager.sh logs

# 3. 手动测试脚本
./launchd_manager.sh test

# 4. 检查 launchd 日志
log show --predicate 'subsystem == "com.apple.launchd"' --last 1h | grep qlib
```

### Q2: 如何修改执行频率？

**方法一：修改时间间隔**

编辑 `com.qlib.autodownload.plist`：

```xml
<key>StartInterval</key>
<integer>3600</integer>  <!-- 改为 1 小时 -->
```

**方法二：切换到日历调度**

参考 [切换到日历调度](#切换到日历调度)。

**修改后重启任务：**

```bash
./launchd_manager.sh restart
```

### Q3: 如何添加环境变量？

编辑 `com.qlib.autodownload.plist`：

```xml
<key>EnvironmentVariables</key>
<dict>
    <key>PATH</key>
    <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>

    <!-- 添加新变量 -->
    <key>CUSTOM_VAR</key>
    <string>value</string>
</dict>
```

### Q4: 任务在笔记本睡眠后不执行？

**解决方案：**

launchd 会自动处理电源管理，但可以优化：

```xml
<!-- 即使在省电模式也运行 -->
<key>Disabled</key>
<false/>

<!-- 或使用低优先级 IO -->
<key>LowPriorityBackgroundIO</key>
<true/>
```

### Q5: 如何完全卸载？

```bash
# 1. 停止并卸载任务
./launchd_manager.sh uninstall

# 2. 删除 plist 文件
rm ~/Library/LaunchAgents/com.qlib.autodownload.plist

# 3. 确认已删除
launchctl list | grep qlib  # 应该没有输出
```

### Q6: 与 Crontab 可以共存吗？

**不建议**。两者都会执行脚本，可能导致重复下载。

建议使用一种方式：要么用 crontab，要么用 launchd。

### Q7: 如何调试任务？

```bash
# 1. 查看 launchd 调试信息
sudo log show --predicate 'eventMessage contains "qlib"' --last 1h

# 2. 启用 launchd 调试模式
sudo launchctl log level debug

# 3. 实时查看系统日志
log stream --predicate 'process == "launchd"'
```

### Q8: 权限问题？

```bash
# 确保脚本可执行
chmod +x auto_download_qlib_bin.sh

# 检查 plist 文件权限
chmod 644 com.qlib.autodownload.plist

# 确保在正确的目录
ls -la ~/Library/LaunchAgents/
```

---

## 参考资料

### 官方文档

- [Apple Developer: launchd.plist(5)](https://www.manpagez.com/man/5/launchd.plist/)
- [launchctl 手册](https://ss64.com/osx/launchctl.html)

### 相关工具

- [LaunchControl](https://www.soma-zone.com/LaunchControl/) - 图形化 launchd 管理工具
- [Lingon](https://www.peterborgapps.com/lingon/) - 另一个图形化管理工具

---

## 总结

```
★ Insight ─────────────────────────────────────
迁移最佳实践：
1. 测试先行：先用 test 命令测试脚本运行
2. 逐步迁移：保留 crontab 一段时间，观察 launchd 运行
3. 日志监控：定期检查日志，确保任务正常执行
4. 备份配置：保留备份文件，方便快速回滚
─────────────────────────────────────────────────
```

### 快速检查清单

- [ ] 备份现有 crontab
- [ ] 安装 launchd 任务
- [ ] 验证任务加载成功
- [ ] 测试脚本执行
- [ ] 检查日志输出
- [ ] 禁用/删除 crontab
- [ ] 设置日志轮转（可选）

---

**最后更新**：2025-12-31
**文档版本**：1.0
