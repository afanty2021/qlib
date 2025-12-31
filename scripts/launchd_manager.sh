#!/bin/bash
#
# Qlib Auto Download Launchd 管理脚本
# 功能：简化 launchd 任务的安装、卸载和管理
#

set -euo pipefail

# ==================== 配置区域 ====================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_SOURCE="${SCRIPT_DIR}/com.qlib.autodownload.plist"
PLIST_TARGET="${HOME}/Library/LaunchAgents/com.qlib.autodownload.plist"
LABEL="com.qlib.autodownload"
SCRIPT_NAME="auto_download_qlib_bin.sh"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ==================== 工具函数 ====================
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}"
}

success() {
    echo -e "${GREEN}✓ $*${NC}"
}

error() {
    echo -e "${RED}✗ $*${NC}"
}

warn() {
    echo -e "${YELLOW}⚠ $*${NC}"
}

info() {
    echo -e "${BLUE}ℹ $*${NC}"
}

# 检查必要文件是否存在
check_files() {
    if [[ ! -f "${PLIST_SOURCE}" ]]; then
        error "plist 配置文件不存在：${PLIST_SOURCE}"
        return 1
    fi

    if [[ ! -f "${SCRIPT_DIR}/${SCRIPT_NAME}" ]]; then
        error "脚本文件不存在：${SCRIPT_DIR}/${SCRIPT_NAME}"
        return 1
    fi

    return 0
}

# 确保脚本可执行
ensure_executable() {
    local script="${SCRIPT_DIR}/${SCRIPT_NAME}"
    if [[ -f "${script}" ]]; then
        chmod +x "${script}"
        success "脚本已设置为可执行：${script}"
    fi
}

# 安装 launchd 任务
install() {
    log "INFO" "开始安装 launchd 任务"

    # 检查文件
    if ! check_files; then
        error "文件检查失败，安装终止"
        return 1
    fi

    # 确保脚本可执行
    ensure_executable

    # 更新 plist 文件中的路径（如果需要）
    local current_dir
    current_dir=$(pwd)
    log "INFO" "当前工作目录：${current_dir}"

    # 创建 LaunchAgents 目录（如果不存在）
    mkdir -p "${HOME}/Library/LaunchAgents"

    # 复制 plist 文件
    log "INFO" "复制 plist 文件到：${PLIST_TARGET}"
    cp "${PLIST_SOURCE}" "${PLIST_TARGET}"

    # 加载任务
    log "INFO" "加载 launchd 任务：${LABEL}"
    launchctl load "${PLIST_TARGET}"

    # 验证任务是否已加载
    if launchctl list | grep -q "${LABEL}"; then
        success "launchd 任务安装成功！"
        echo ""
        info "任务名称：${LABEL}"
        info "配置文件：${PLIST_TARGET}"
        info "执行脚本：${SCRIPT_DIR}/${SCRIPT_NAME}"
        echo ""
        info "使用以下命令管理任务："
        echo "  ./launchd_manager.sh status   # 查看状态"
        echo "  ./launchd_manager.sh start    # 启动任务"
        echo "  ./launchd_manager.sh stop     # 停止任务"
        echo "  ./launchd_manager.sh restart  # 重启任务"
        echo "  ./launchd_manager.sh logs     # 查看日志"
        echo "  ./launchd_manager.sh uninstall # 卸载任务"
        return 0
    else
        error "launchd 任务加载失败"
        return 1
    fi
}

# 卸载 launchd 任务
uninstall() {
    log "INFO" "开始卸载 launchd 任务"

    # 检查任务是否已加载
    if launchctl list | grep -q "${LABEL}"; then
        log "INFO" "卸载 launchd 任务：${LABEL}"
        launchctl unload "${PLIST_TARGET}"
        success "任务已卸载"
    else
        info "任务未加载，跳过卸载步骤"
    fi

    # 删除 plist 文件
    if [[ -f "${PLIST_TARGET}" ]]; then
        log "INFO" "删除 plist 文件：${PLIST_TARGET}"
        rm -f "${PLIST_TARGET}"
        success "plist 文件已删除"
    else
        info "plist 文件不存在，跳过删除步骤"
    fi

    success "launchd 任务卸载完成！"
    return 0
}

# 启动任务
start() {
    log "INFO" "启动任务：${LABEL}"

    # 检查是否已加载
    if ! launchctl list | grep -q "${LABEL}"; then
        error "任务未加载，请先运行 install 安装任务"
        return 1
    fi

    # 启动任务
    launchctl start "${LABEL}"
    success "任务已启动"

    return 0
}

# 停止任务
stop() {
    log "INFO" "停止任务：${LABEL}"

    # 检查是否已加载
    if ! launchctl list | grep -q "${LABEL}"; then
        error "任务未加载"
        return 1
    fi

    # 停止任务
    launchctl stop "${LABEL}"
    success "任务已停止"

    return 0
}

# 重启任务
restart() {
    log "INFO" "重启任务：${LABEL}"
    stop
    sleep 1
    start
    return 0
}

# 查看状态
status() {
    echo ""
    info "====== launchd 任务状态 ======"
    echo ""

    # 检查任务是否已加载
    if launchctl list | grep -q "${LABEL}"; then
        success "任务状态：已加载"
        echo ""

        # 显示详细信息
        info "任务详情："
        launchctl list | grep "${LABEL}" || true

        echo ""
        info "配置文件："
        if [[ -f "${PLIST_TARGET}" ]]; then
            echo "  ✓ ${PLIST_TARGET}"
        else
            echo "  ✗ ${PLIST_TARGET} (不存在)"
        fi

        echo ""
        info "下次执行时间："
        # 由于 launchd 不直接提供下次执行时间，这里只显示任务已配置
        echo "  • 执行间隔：每 30 分钟"
        echo "  • 时间窗口：16:00-22:00（由脚本内部控制）"

    else
        error "任务状态：未加载"
        echo ""
        warn "任务尚未安装或已卸载"
        echo "  请运行：./launchd_manager.sh install"
    fi

    echo ""
    info "============================="
    echo ""

    return 0
}

# 查看日志
logs() {
    local log_dir="${HOME}/Downloads/qlib_data"

    echo ""
    info "====== 日志文件 ======"
    echo ""

    # 检查脚本日志
    local script_log="${log_dir}/download.log"
    if [[ -f "${script_log}" ]]; then
        info "脚本日志（最近20行）："
        echo "  文件：${script_log}"
        tail -20 "${script_log}" | sed 's/^/  /'
    else
        warn "脚本日志不存在：${script_log}"
    fi

    echo ""

    # 检查 launchd 标准输出日志
    local stdout_log="${log_dir}/launchd_stdout.log"
    if [[ -f "${stdout_log}" ]]; then
        info "launchd 标准输出（最近20行）："
        echo "  文件：${stdout_log}"
        tail -20 "${stdout_log}" | sed 's/^/  /'
    else
        info "launchd 标准输出日志不存在：${stdout_log}"
    fi

    echo ""

    # 检查 launchd 错误日志
    local stderr_log="${log_dir}/launchd_stderr.log"
    if [[ -f "${stderr_log}" ]]; then
        warn "launchd 错误输出（最近20行）："
        echo "  文件：${stderr_log}"
        tail -20 "${stderr_log}" | sed 's/^/  /'
    else
        info "launchd 错误输出日志不存在：${stderr_log}"
    fi

    echo ""
    info "====================="
    echo ""

    return 0
}

# 测试运行（手动执行一次脚本，不通过 launchd）
test_run() {
    log "INFO" "测试运行脚本"

    local script="${SCRIPT_DIR}/${SCRIPT_NAME}"
    if [[ ! -f "${script}" ]]; then
        error "脚本文件不存在：${script}"
        return 1
    fi

    ensure_executable

    info "执行脚本：${script}"
    echo "----------------------------------------"
    bash "${script}"
    local exit_code=$?
    echo "----------------------------------------"

    if [[ ${exit_code} -eq 0 ]]; then
        success "测试运行成功"
        return 0
    else
        error "测试运行失败（退出码：${exit_code}）"
        return 1
    fi
}

# 显示帮助信息
show_help() {
    cat << EOF
${BLUE}Qlib Auto Download Launchd 管理脚本${NC}

${GREEN}用法：${NC}
  $0 <command> [options]

${GREEN}命令：${NC}
  ${YELLOW}install${NC}      安装 launchd 定时任务
  ${YELLOW}uninstall${NC}    卸载 launchd 定时任务
  ${YELLOW}start${NC}        启动任务（手动触发一次执行）
  ${YELLOW}stop${NC}         停止任务
  ${YELLOW}restart${NC}      重启任务
  ${YELLOW}status${NC}       查看任务状态
  ${YELLOW}logs${NC}         查看日志输出
  ${YELLOW}test${NC}         测试运行脚本（不通过 launchd）
  ${YELLOW}help${NC}         显示此帮助信息

${GREEN}示例：${NC}
  $0 install        # 安装定时任务
  $0 status         # 查看任务状态
  $0 logs           # 查看日志
  $0 uninstall      # 卸载任务

${GREEN}说明：${NC}
  • 安装后，脚本将每 30 分钟执行一次
  • 脚本内部有时间窗口检查（16:00-22:00）
  • 日志文件位于：~/Downloads/qlib_data/

EOF
}

# ==================== 主流程 ====================
main() {
    local command="${1:-help}"

    case "${command}" in
        install)
            install
            ;;
        uninstall)
            uninstall
            ;;
        start)
            start
            ;;
        stop)
            stop
            ;;
        restart)
            restart
            ;;
        status)
            status
            ;;
        logs)
            logs
            ;;
        test)
            test_run
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            error "未知命令：${command}"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# 执行主流程
main "$@"
