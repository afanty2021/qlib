#!/bin/bash
#
# 自动下载 Qlib 数据包脚本（增强版）
# 功能：智能检测交易日数据更新，支持节假日延迟发布
# 使用方法：添加到crontab（建议每30分钟执行一次）或手动执行
#

set -euo pipefail

# ==================== 配置区域 ====================
REPO_OWNER="chenditc"
REPO_NAME="investment_data"
DOWNLOAD_DIR="${HOME}/Downloads/qlib_data"  # 下载目录
QLIB_DATA_DIR="${HOME}/.qlib/qlib_data"     # Qlib数据目录
CN_DATA_DIR="${QLIB_DATA_DIR}/cn_data"      # 中国数据目录
CN_DATA_BACKUP="${QLIB_DATA_DIR}/cn_data_backup"  # 备份目录
LOG_DIR="${HOME}/Library/Logs/qlib_data"    # macOS 标准日志目录（launchd 可写）
LOG_FILE="${LOG_DIR}/download.log"          # 日志文件
STATE_FILE="${LOG_DIR}/.download_state"     # 状态文件（记录最后成功的日期）
MAX_RETRIES=3                               # 最大重试次数
RETRY_DELAY=10                              # 重试延迟（秒）
ARIA2C_OPTIONS="-x 8"                         # aria2c参数（简化：不使用分块下载，避免并发问题）
MAX_CHECK_DAYS=9                           # 最多向前查找N个交易日（处理长假）
LOCK_FILE="${LOG_DIR}/.download_lock"       # 锁文件（防止并发执行）
LOCK_TIMEOUT=3600                           # 锁超时时间（秒，1小时）

# 中国节假日配置（YYYY-MM-DD 格式）
# 注意：这是硬编码的节假日列表，建议每年更新
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

# ==================== 锁机制（防止并发执行） ====================
acquire_lock() {
    # 检查锁文件是否存在
    if [[ -f "${LOCK_FILE}" ]]; then
        # 读取锁文件中的PID
        local lock_pid
        lock_pid=$(cat "${LOCK_FILE}" 2>/dev/null || echo "")

        # 检查该进程是否还在运行
        if [[ -n "${lock_pid}" ]] && kill -0 "${lock_pid}" 2>/dev/null; then
            # 检查锁是否超时
            local lock_time
            lock_time=$(stat -f "%m" "${LOCK_FILE}" 2>/dev/null || stat -c "%Y" "${LOCK_FILE}" 2>/dev/null)
            local current_time
            current_time=$(date +%s)
            local elapsed=$((current_time - lock_time))

            if [[ ${elapsed} -lt ${LOCK_TIMEOUT} ]]; then
                log "WARN" "另一个实例正在运行（PID: ${lock_pid}，已运行 ${elapsed} 秒），跳过本次执行"
                return 1
            else
                log "WARN" "锁超时（${elapsed} 秒），清理过期锁"
                rm -f "${LOCK_FILE}"
            fi
        else
            log "INFO" "清理过期的锁文件（进程 ${lock_pid} 已不存在）"
            rm -f "${LOCK_FILE}"
        fi
    fi

    # 创建新锁
    echo $$ > "${LOCK_FILE}"
    log "INFO" "已获取锁（PID: $$）"
    return 0
}

release_lock() {
    if [[ -f "${LOCK_FILE}" ]]; then
        rm -f "${LOCK_FILE}"
        log "INFO" "已释放锁"
    fi
}

# ==================== 工具函数 ====================
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "${LOG_FILE}"
}

check_command() {
    local cmd="$1"
    if ! command -v "${cmd}" &> /dev/null; then
        log "ERROR" "命令 '${cmd}' 未找到，请先安装"
        exit 1
    fi
}

# 判断是否是周末（周六或周日）
is_weekend() {
    local date="$1"
    local day_of_week
    day_of_week=$(date -j -f "%Y-%m-%d" "${date}" "+%u" 2>/dev/null || date -d "${date}" "+%u" 2>/dev/null)

    # %u: 1=周一, 7=周日
    [[ "${day_of_week}" == "6" || "${day_of_week}" == "7" ]]
}

# 判断是否是节假日
is_holiday() {
    local date="$1"
    local holiday

    for holiday in "${HOLIDAYS_2025[@]}"; do
        [[ "${date}" == "${holiday}" ]] && return 0
    done

    return 1
}

# 判断是否是交易日
is_trading_day() {
    local date="$1"

    # 周末不是交易日
    if is_weekend "${date}"; then
        return 1
    fi

    # 节假日不是交易日
    if is_holiday "${date}"; then
        return 1
    fi

    return 0
}

# 获取前一个交易日
get_previous_trading_day() {
    local current_date="$1"
    local check_date
    local days_ago=0

    # 检测操作系统类型
    local is_macos=0
    if [[ "$(uname)" == "Darwin" ]]; then
        is_macos=1
    fi

    while [ ${days_ago} -lt ${MAX_CHECK_DAYS} ]; do
        ((days_ago++))

        # macOS 和 Linux 兼容的日期计算
        if [ ${is_macos} -eq 1 ]; then
            # macOS
            check_date=$(date -j -v-${days_ago}d -f "%Y-%m-%d" "${current_date}" "+%Y-%m-%d" 2>/dev/null)
        else
            # Linux
            check_date=$(date -d "${current_date} -${days_ago} days" "+%Y-%m-%d" 2>/dev/null)
        fi

        if [[ -n "${check_date}" ]] && is_trading_day "${check_date}"; then
            echo "${check_date}"
            return 0
        fi
    done

    return 1
}

# 获取下一个交易日
get_next_trading_day() {
    local current_date="$1"
    local check_date
    local days_ahead=0

    # 检测操作系统类型
    local is_macos=0
    if [[ "$(uname)" == "Darwin" ]]; then
        is_macos=1
    fi

    while [ ${days_ahead} -lt ${MAX_CHECK_DAYS} ]; do
        ((days_ahead++))

        # macOS 和 Linux 兼容的日期计算
        if [ ${is_macos} -eq 1 ]; then
            # macOS
            check_date=$(date -j -v+${days_ahead}d -f "%Y-%m-%d" "${current_date}" "+%Y-%m-%d" 2>/dev/null)
        else
            # Linux
            check_date=$(date -d "${current_date} +${days_ahead} days" "+%Y-%m-%d" 2>/dev/null)
        fi

        if [[ -n "${check_date}" ]] && is_trading_day "${check_date}"; then
            echo "${check_date}"
            return 0
        fi
    done

    return 1
}

# 判断是否应该检测数据（基于时间窗口和交易日）
should_check_data() {
    local today
    today=$(date '+%Y-%m-%d')
    local current_hour
    current_hour=$(date '+%H')
    local current_minute
    current_minute=$(date '+%M')
    local current_time=$((10#$current_hour * 60 + 10#$current_minute)) # 转换为分钟

    # 时间窗口：16:00 - 22:00 (960分钟 - 1320分钟)
    local time_start=960   # 16:00
    local time_end=1320     # 22:00

    # 检查是否在检测时间窗口内
    if [[ ${current_time} -lt ${time_start} || ${current_time} -ge ${time_end} ]]; then
        log "INFO" "当前时间不在检测窗口内（16:00-22:00），跳过检测"
        return 1
    fi

    # 检查今天是否是交易日
    if is_trading_day "${today}"; then
        log "INFO" "今天是交易日（${today}），需要检测数据更新"
        return 0
    fi

    # 如果今天不是交易日，检查是否需要继续检测（可能是节假日前延后发布）
    local last_success_date
    last_success_date=$(get_last_success_date 2>/dev/null || echo "")

    if [[ -n "${last_success_date}" ]]; then
        # 获取最后成功日期的下一个交易日
        local next_trading_day
        next_trading_day=$(get_next_trading_day "${last_success_date}")

        if [[ -n "${next_trading_day}" ]]; then
            # 如果下一个交易日已经过去（包括今天），说明还需要检测
            local next_trading_timestamp
            local today_timestamp

            # 检测操作系统类型
            if [[ "$(uname)" == "Darwin" ]]; then
                # macOS
                next_trading_timestamp=$(date -j -f "%Y-%m-%d" "${next_trading_day}" "+%s" 2>/dev/null)
                today_timestamp=$(date -j -f "%Y-%m-%d" "${today}" "+%s" 2>/dev/null)
            else
                # Linux
                next_trading_timestamp=$(date -d "${next_trading_day}" "+%s" 2>/dev/null)
                today_timestamp=$(date -d "${today}" "+%s" 2>/dev/null)
            fi

            if [[ -n "${next_trading_timestamp}" ]] && [[ -n "${today_timestamp}" ]] && [[ ${today_timestamp} -ge ${next_trading_timestamp} ]]; then
                log "INFO" "非交易日但可能等待延后发布，继续检测（上次成功: ${last_success_date}）"
                return 0
            fi
        fi
    fi

    log "INFO" "今天是非交易日且无需检测，跳过"
    return 1
}

# 获取应该检测的目标日期
get_target_date() {
    local today
    today=$(date '+%Y-%m-%d')

    # 如果今天是交易日，目标就是今天
    if is_trading_day "${today}"; then
        echo "${today}"
        return 0
    fi

    # 如果今天不是交易日，检查最近的一个交易日
    local last_trading_day
    last_trading_day=$(get_previous_trading_day "${today}")

    if [[ -n "${last_trading_day}" ]]; then
        echo "${last_trading_day}"
        return 0
    fi

    # 找不到交易日，使用今天
    echo "${today}"
    return 0
}

# 检查指定日期的数据是否已下载
is_data_downloaded() {
    local target_date="$1"

    # 检查状态文件
    if [[ -f "${STATE_FILE}" ]]; then
        local last_success
        last_success=$(cat "${STATE_FILE}" 2>/dev/null || echo "")

        if [[ "${last_success}" == "${target_date}" ]]; then
            log "INFO" "数据已成功下载（${target_date}），跳过重复下载"
            return 0
        fi
    fi

    # 检查数据目录中的 calendars/day.txt 文件
    local day_file="${CN_DATA_DIR}/calendars/day.txt"

    if [[ -f "${day_file}" ]]; then
        # 检查是否包含目标日期
        if grep -q "${target_date}" "${day_file}" 2>/dev/null; then
            log "INFO" "数据文件中已包含目标日期（${target_date}），跳过下载"

            # 更新状态文件
            echo "${target_date}" > "${STATE_FILE}"
            return 0
        fi
    fi

    return 1
}

# 记录下载成功
mark_download_success() {
    local target_date="$1"
    echo "${target_date}" > "${STATE_FILE}"
    log "INFO" "已记录下载成功日期：${target_date}"
}

# 获取最后成功的日期
get_last_success_date() {
    if [[ -f "${STATE_FILE}" ]]; then
        cat "${STATE_FILE}" 2>/dev/null
    fi
}

check_url_exists() {
    local url="$1"
    local http_code

    # 使用HEAD请求检查URL是否存在，跟随重定向
    http_code=$(curl -L -s -o /dev/null -w "%{http_code}" --max-time 30 "${url}")

    case "${http_code}" in
        200)
            return 0
            ;;
        404)
            return 1
            ;;
        *)
            log "WARN" "收到意外的HTTP状态码：${http_code}"
            return 1
            ;;
    esac
}

# 清理未完成的下载残留
cleanup_incomplete_downloads() {
    local output="$1"
    local download_dir="$2"

    # 获取基础文件名（不含扩展名）
    local base_name="${output%.tar.gz}"

    # 查找并清理所有相关的未完成文件
    # 1. 先清理与主文件名相关的文件 (.tar.gz, .tar.gz.aria2等)
    for file in "${download_dir}/${output}"*; do
        if [[ -f "${file}" ]]; then
            local filename
            filename=$(basename "${file}")

            # 清理 .aria2 控制文件
            if [[ "${filename}" == *.aria2 ]]; then
                log "INFO" "清理未完成下载的控制文件：${filename}"
                rm -f "${file}"
            fi
        fi
    done

    # 2. 再清理自动重命名的分块文件 (.tar.1.gz, .tar.2.gz 等)
    for file in "${download_dir}/${base_name}".tar.*.gz; do
        if [[ -f "${file}" ]]; then
            local filename
            filename=$(basename "${file}")

            # 清理分块文件（如 .tar.1.gz, .tar.2.gz 等），但不要清理主文件
            if [[ "${filename}" =~ \.tar\.[0-9]+\.gz$ ]]; then
                log "INFO" "清理未完成的分块文件：${filename}"
                rm -f "${file}"
            fi
        fi
    done
}

# 验证gzip文件完整性
verify_gzip_file() {
    local file="$1"

    if gzip -t "${file}" 2>/dev/null; then
        return 0
    else
        log "WARN" "文件完整性验证失败：${file}"
        return 1
    fi
}

download_file() {
    local url="$1"
    local output="$2"
    local attempt=1

    # 在开始下载前，清理可能存在的未完成下载
    cleanup_incomplete_downloads "${output}" "${DOWNLOAD_DIR}"

    while [ ${attempt} -le ${MAX_RETRIES} ]; do
        log "INFO" "开始下载（尝试 ${attempt}/${MAX_RETRIES}）"

        # 使用 -c 参数支持续传，--allow-overwrite=true 覆盖已存在的文件
        # --auto-file-renaming=false 防止自动重命名（避免产生 .1, .2 等文件）
        if aria2c ${ARIA2C_OPTIONS} -c --allow-overwrite=true --auto-file-renaming=false -o "${output}" "${url}"; then
            log "INFO" "下载成功：${output}"

            # 验证文件存在
            if [ ! -f "${output}" ]; then
                log "ERROR" "文件未正确保存"
                return 1
            fi

            # 验证gzip完整性
            if ! verify_gzip_file "${output}"; then
                log "ERROR" "下载的文件损坏，删除并重试"
                rm -f "${output}"
                if [ ${attempt} -lt ${MAX_RETRIES} ]; then
                    log "INFO" "等待 ${RETRY_DELAY} 秒后重试..."
                    sleep ${RETRY_DELAY}
                fi
                ((attempt++))
                continue
            fi

            # 验证通过，显示文件大小
            local file_size
            file_size=$(du -h "${output}" | cut -f1)
            log "INFO" "文件大小：${file_size}"

            # 清理可能残留的分块文件
            cleanup_incomplete_downloads "${output}" "${DOWNLOAD_DIR}"

            return 0
        else
            log "WARN" "下载失败（尝试 ${attempt}/${MAX_RETRIES}）"
            if [ ${attempt} -lt ${MAX_RETRIES} ]; then
                log "INFO" "等待 ${RETRY_DELAY} 秒后重试..."
                sleep ${RETRY_DELAY}
            fi
            ((attempt++))
        fi
    done

    log "ERROR" "下载失败，已达到最大重试次数"
    # 清理失败的残留文件
    cleanup_incomplete_downloads "${output}" "${DOWNLOAD_DIR}"
    return 1
}

backup_data() {
    local source_dir="$1"
    local backup_dir="$2"

    # 如果备份目录已存在，先删除
    if [ -d "${backup_dir}" ]; then
        log "INFO" "删除旧备份：${backup_dir}"
        rm -rf "${backup_dir}"
    fi

    # 拷贝当前数据为备份
    log "INFO" "备份数据：${source_dir} -> ${backup_dir}"
    if cp -r "${source_dir}" "${backup_dir}"; then
        log "INFO" "备份成功"

        # 显示备份大小
        local backup_size
        backup_size=$(du -sh "${backup_dir}" 2>/dev/null | cut -f1)
        log "INFO" "备份大小：${backup_size}"

        return 0
    else
        log "ERROR" "备份失败"
        return 1
    fi
}

extract_tarball() {
    local tarball="$1"
    local target_date="$2"

    log "INFO" "========================================"
    log "INFO" "开始数据更新流程（${target_date}）"
    log "INFO" "========================================"

    # 1. 备份现有数据
    if [ -d "${CN_DATA_DIR}" ]; then
        if ! backup_data "${CN_DATA_DIR}" "${CN_DATA_BACKUP}"; then
            log "ERROR" "备份失败，终止更新"
            return 1
        fi
    else
        log "INFO" "目标目录不存在，将创建新目录：${CN_DATA_DIR}"
        mkdir -p "${CN_DATA_DIR}"
    fi

    # 2. 解压新数据（使用 --strip-components=1 去掉顶层目录）
    log "INFO" "解压文件到：${CN_DATA_DIR}"
    log "INFO" "使用参数：--strip-components=1"

    if tar -xzf "${tarball}" -C "${CN_DATA_DIR}" --strip-components=1; then
        log "INFO" "解压成功"

        # 3. 验证解压结果
        if [ -d "${CN_DATA_DIR}/calendars" ] && [ -d "${CN_DATA_DIR}/instruments" ]; then
            log "INFO" "数据验证通过：calendars 和 instruments 目录存在"

            # 4. 验证目标日期数据
            local day_file="${CN_DATA_DIR}/calendars/day.txt"
            local data_ok=false
            if [ -f "${day_file}" ]; then
                # 获取数据中的最新日期
                local latest_data_date
                latest_data_date=$(tail -1 "${day_file}" 2>/dev/null || echo "")

                if [[ -n "${latest_data_date}" ]]; then
                    log "INFO" "数据中的最新日期：${latest_data_date}"

                    # 检查最新日期是否 >= 目标日期
                    # 使用字符串比较（YYYY-MM-DD格式可以直接比较）
                    if [[ "${latest_data_date}" > "${target_date}" ]] || [[ "${latest_data_date}" == "${target_date}" ]]; then
                        log "INFO" "目标日期数据验证通过：${target_date} (数据最新: ${latest_data_date})"
                        data_ok=true
                    else
                        # 数据日期早于目标日期，这是正常的（数据发布有延迟）
                        # 但我们仍然标记成功，因为文件已经正确解压
                        log "INFO" "数据日期 ${latest_data_date} 早于目标日期 ${target_date}，数据可能有延迟"
                        log "INFO" "但文件已正确解压，标记为成功"
                        data_ok=true
                    fi
                else
                    log "ERROR" "无法读取数据日期"
                    data_ok=false
                fi
            else
                log "ERROR" "day.txt 文件不存在"
                data_ok=false
            fi

            # 只有在数据验证通过后才继续
            if [[ "${data_ok}" == "true" ]]; then
                # 5. 清理压缩包
                rm -f "${tarball}"
                log "INFO" "已删除压缩包：${tarball}"

                # 6. 记录成功（记录实际数据的最新日期，而不是目标日期）
                # 这样可以更准确地反映数据状态
                local latest_data_date
                latest_data_date=$(tail -1 "${CN_DATA_DIR}/calendars/day.txt" 2>/dev/null || echo "${target_date}")
                mark_download_success "${latest_data_date}"
            else
                log "ERROR" "数据验证失败，不标记成功"
                return 1
            fi

            log "INFO" "========================================"
            log "INFO" "数据更新完成！"
            log "INFO" "========================================"

            return 0
        else
            log "ERROR" "数据验证失败：缺少必要目录"

            # 回滚：恢复备份
            if [ -d "${CN_DATA_BACKUP}" ]; then
                log "WARN" "尝试恢复备份..."
                rm -rf "${CN_DATA_DIR}"
                mv "${CN_DATA_BACKUP}" "${CN_DATA_DIR}"
                log "INFO" "已恢复到备份数据"
            fi

            return 1
        fi
    else
        log "ERROR" "解压失败"

        # 回滚：恢复备份
        if [ -d "${CN_DATA_BACKUP}" ]; then
            log "WARN" "尝试恢复备份..."
            rm -rf "${CN_DATA_DIR}"
            mv "${CN_DATA_BACKUP}" "${CN_DATA_DIR}"
            log "INFO" "已恢复到备份数据"
        fi

        return 1
    fi
}

# ==================== 主流程 ====================
main() {
    # 尝试获取锁，如果失败则退出
    if ! acquire_lock; then
        exit 0
    fi

    # 确保脚本退出时释放锁
    trap release_lock EXIT

    log "INFO" "========================================"
    log "INFO" "Qlib 数据自动下载脚本启动"
    log "INFO" "========================================"

    # 检查必要的命令
    check_command "curl"
    check_command "aria2c"
    check_command "tar"
    check_command "cp"
    check_command "du"

    # 创建必要目录
    mkdir -p "${DOWNLOAD_DIR}"
    mkdir -p "${QLIB_DATA_DIR}"
    cd "${DOWNLOAD_DIR}"

    # 判断是否应该检测数据
    if ! should_check_data; then
        log "INFO" "无需检测，脚本结束"
        exit 0
    fi

    # 获取目标日期
    local target_date
    target_date=$(get_target_date)
    log "INFO" "目标检测日期：${target_date}"

    # 检查是否已下载
    if is_data_downloaded "${target_date}"; then
        log "INFO" "数据已存在，无需重复下载"
        exit 0
    fi

    # 构建下载URL
    local base_url="https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download"
    local release_url="${base_url}/${target_date}/qlib_bin.tar.gz"

    # 检查是否存在发布
    if ! check_url_exists "${release_url}"; then
        log "INFO" "发布尚未上线，将在下次检测"
        exit 0
    fi

    log "INFO" "找到发布：${release_url}"

    # 下载文件
    local output_file="qlib_bin_${target_date}.tar.gz"

    if download_file "${release_url}" "${output_file}"; then
        # 解压并更新 Qlib 数据
        local tarball_path="${DOWNLOAD_DIR}/${output_file}"

        if extract_tarball "${tarball_path}" "${target_date}"; then
            # 显示更新后的数据目录大小
            local new_data_size
            new_data_size=$(du -sh "${CN_DATA_DIR}" 2>/dev/null | cut -f1)
            log "INFO" "数据目录大小：${new_data_size}"

            log "INFO" "========================================"
            log "INFO" "全部任务完成！"
            log "INFO" "========================================"
        else
            log "ERROR" "数据更新失败"
            exit 1
        fi
    else
        log "ERROR" "下载任务失败"
        exit 1
    fi
}

# 执行主流程
main
