#!/bin/bash
#
# 自动安装定时任务脚本（增强版）
# 功能：将 auto_download_qlib_bin.sh 添加到 crontab
#       每30分钟执行一次，时间窗口：16:00-22:00
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_SCRIPT="${SCRIPT_DIR}/auto_download_qlib_bin.sh"

# Cron 表达式：每30分钟执行一次（16:00-22:00）
# 16:00, 16:30, 17:00, 17:30, 18:00, 18:30, 19:00, 19:30, 20:00, 20:30, 21:00, 21:30
CRON_ENTRIES=(
    "0,30 16-21 * * * sleep \$((RANDOM \% 60)); ${MAIN_SCRIPT}"
)

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# 检查主脚本是否存在
if [ ! -f "${MAIN_SCRIPT}" ]; then
    print_error "找不到主脚本：${MAIN_SCRIPT}"
    exit 1
fi

# 赋予执行权限
chmod +x "${MAIN_SCRIPT}"
print_success "已设置脚本执行权限"

# 检查是否已存在相同的 cron 任务
if crontab -l 2>/dev/null | grep -F "${MAIN_SCRIPT}" > /dev/null; then
    print_warning "定时任务已存在"
    echo ""
    echo "当前定时任务："
    crontab -l 2>/dev/null | grep -F "${MAIN_SCRIPT}" | while read -r line; do
        echo "  ${line}"
    done
    echo ""
    read -p "是否要重新安装？(y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "取消安装"
        exit 0
    fi

    # 删除旧的定时任务
    crontab -l 2>/dev/null | grep -v -F "${MAIN_SCRIPT}" | crontab -
    print_success "已删除旧的定时任务"
fi

# 添加新的定时任务
for cron_entry in "${CRON_ENTRIES[@]}"; do
    (crontab -l 2>/dev/null; echo "${cron_entry}") | crontab -
done

print_success "定时任务安装成功"
echo ""
print_info "定时任务详情："
echo "  执行时间：16:00-22:00，每30分钟一次"
echo "  执行时刻：16:00, 16:30, 17:00, 17:30, ..., 21:00, 21:30"
echo "  随机延迟：0-59 秒（避免高峰请求）"
echo "  脚本路径：${MAIN_SCRIPT}"
echo ""
echo "特性说明："
echo "  • 智能交易日检测：自动跳过周末和节假日"
echo "  • 持续检测：数据未上线会持续检测，直到成功"
echo "  • 节假日处理：节假日前可能延后发布，自动延长检测"
echo "  • 去重下载：已下载的数据不会重复下载"
echo ""
echo "常用命令："
echo "  查看所有定时任务："
echo "    crontab -l"
echo ""
echo "  查看实时日志："
echo "    tail -f ~/Downloads/qlib_data/download.log"
echo ""
echo "  手动测试运行："
echo "    ${MAIN_SCRIPT}"
echo ""
echo "  查看下载状态："
echo "    cat ~/Downloads/qlib_data/.download_state"
echo ""
echo "  删除状态文件（强制重新下载）："
echo "    rm ~/Downloads/qlib_data/.download_state"
echo ""
print_warning "注意：首次运行建议手动测试，确认脚本正常工作后再依赖定时任务"
