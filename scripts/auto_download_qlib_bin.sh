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
QLIB_DATA_DIR="${HOME}/.qlib/qlib_data"     # Qlib数据目录
CN_DATA_DIR="${QLIB_DATA_DIR}/cn_data"      # 中国数据目录
CN_DATA_BACKUP="${QLIB_DATA_DIR}/cn_data_backup"  # 备份目录
# 注意：下载目录不能放 ~/Downloads —— macOS TCC 会拒绝后台进程（launchd/cron/agent）
# 访问 Downloads/Desktop/Documents，表现为 rm/tar "Operation not permitted"，导致
# 下载后的解压与清理全部失败（2026-05~06 断更的根因）。放 ~/.qlib 下无此限制。
DOWNLOAD_DIR="${HOME}/.qlib/downloads"      # 下载目录（TCC 安全路径）
LOG_DIR="${HOME}/Library/Logs/qlib_data"    # macOS 标准日志目录（launchd 可写）
LOG_FILE="${LOG_DIR}/download.log"          # 日志文件
STATE_FILE="${LOG_DIR}/.download_state"     # 状态文件（记录最后成功的日期）
MAX_RETRIES=3                               # 最大重试次数
RETRY_DELAY=10                              # 重试延迟（秒）
# GitHub 加速镜像前缀（按序探测，首个可用者胜出；全部失败回退直连）。
# 注意：镜像是第三方反向代理，内容一致是信任假设而非保证——下载后用直连元数据
# 大小交叉校验 + gzip 校验兜底（覆盖意外损坏与粗粒度陈旧）。可用性变化频繁
# （2026-09-22 实测：ghfast.top 可用且并发线性扩展；ghp.ci/gh-proxy.com/
# ghproxy.net/gh.llkk.cc 均不可用），探测不通过自动换下一个，勿写死依赖单一镜像。
# 自建 Cloudflare Worker 反代后把地址加在首位（见 scripts/cloudflare_worker_gh_proxy.js，
# 注意 *.workers.dev 在大陆被 DNS 污染，需绑定自定义域后再用）。
# 禁用镜像加速：把数组置空（MIRROR_PREFIXES=()），勿注释/删除整块声明。
MIRROR_PREFIXES=(
    "https://ghfast.top"
    "https://ghp.ci"
)
# -x 16 -s 16 -k 1M：镜像/CDN 对单连接限速，多连接并发近似线性叠加
#   （直连 GitHub 实测 ~100KB/s/连接，540MB 要 100+ 分钟；并发后 3-10 分钟）
# --lowest-speed-limit=10K：掐死停滞连接。默认 0 = 永不掐断，传输停滞后无限期挂死
#   （2026-09-22 曾在只差最后 512 字节处挂 15+ 分钟）
# --timeout/--connect-timeout/--retry-wait：坏连接快速重建，不占用下载重试次数
ARIA2C_OPTIONS="-x 16 -s 16 -k 1M --lowest-speed-limit=10K --timeout=30 --connect-timeout=10 --retry-wait=2"
MAX_CHECK_DAYS=9                           # 最多向前查找N个交易日（处理长假）
LOCK_FILE="${LOG_DIR}/.download_lock"       # 锁文件（防止并发执行）
# 待处理包文件名模式（日期为捕获组，BASH_REMATCH[1] 取日期）
PENDING_FILE_RE='qlib_bin_([0-9]{4}-[0-9]{2}-[0-9]{2})\.tar\.gz$'
# 下载后与直连元数据交叉校验的包大小基准（字节）。探测成功时由 fetch_expected_size
# 填充；为空表示基准缺失（直连不可用/解析失败），跳过比对。
RELEASE_EXPECTED_SIZE=""
# 救援路径探活的镜像前缀（probe_mirrors_available 写入，download_file 在父层
# 取走并清空后仅用于首次尝试）。必须在此声明：set -u 下未声明变量会让
# download_file 被 unbound 错误打断。
PREFERRED_MIRROR_PREFIX=""

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

        # PID 存活且确为本脚本进程 → 不偷锁。下载可持续 100+ 分钟（直连最坏情形），
        # 按锁龄强拆会让第二个实例并发写同一文件。锁龄不参与判定。
        # 注：kill -0 检查与下方写锁之间存在 TOCTOU 窗口（两个实例同时通过检查）；
        # 当前调度为单发串行（hermes 三档 + 锁跳过语义），无实害，记录在案。
        if [[ -n "${lock_pid}" ]] && kill -0 "${lock_pid}" 2>/dev/null \
            && ps -p "${lock_pid}" -o command= 2>/dev/null | grep -q "auto_download_qlib_bin"; then
            log "WARN" "另一个实例正在运行（PID: ${lock_pid}），跳过本次执行"
            return 1
        fi

        # 进程已不存在（或 PID 已被无关进程复用，command 不匹配）→ 失效锁，清理
        log "INFO" "清理失效的锁文件（PID: ${lock_pid} 已不存在或非本脚本进程）"
        rm -f "${LOCK_FILE}"
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
        ((++days_ago))

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
        ((++days_ahead))

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
    # QDLIB_FORCE_CHECK=1 时跳过时间窗与交易日判定（供定时任务/手动补跑使用）；
    # 幂等性由 is_data_downloaded（状态文件 + day.txt 日期）保证，不会重复下载。
    if [[ "${QDLIB_FORCE_CHECK:-0}" == "1" ]]; then
        log "INFO" "QDLIB_FORCE_CHECK=1，跳过时间窗与交易日判定"
        return 0
    fi

    local today
    today=$(date '+%Y-%m-%d')
    local current_hour
    current_hour=$(date '+%H')
    local current_minute
    current_minute=$(date '+%M')
    local current_time=$((10#$current_hour * 60 + 10#$current_minute)) # 转换为分钟

    # 时间窗口：16:00 - 23:30 (960分钟 - 1410分钟) - 考虑网络延迟，延长检测窗口
    local time_start=960   # 16:00
    local time_end=1410     # 23:30

    # 检查是否在检测时间窗口内
    if [[ ${current_time} -lt ${time_start} || ${current_time} -ge ${time_end} ]]; then
        log "INFO" "当前时间不在检测窗口内（16:00-23:30），跳过检测"
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

# 探测 release 是否已发布。
# 返回码：0 = 已发布（200/206）；1 = 确定未发布（404）；2 = 探测失败
# （000/超时/5xx 等网络或服务端异常，此时无法区分"未发布"）。
# 调用方必须把 2 当作失败退出，不能与 1 一样静默跳过——否则调度器每天
# 看到 exit 0 而数据持续陈旧（2026-04~06 断更的故障类别）。
# 注意：--retry-all-errors 需要 curl >= 7.71（macOS <= 12 自带 7.64 不支持，
# 旧系统上该选项会被拒绝，http_code 为空，同样落入 return 2 的失败分支）。
check_url_exists() {
    local url="$1"
    local http_code

    # -r 0-0 只取首字节探测：整包下载到 /dev/null 会撞上 --max-time 超时返回 000，
    # 被误判为"发布尚未上线"。GitHub release 链路存在分钟级间歇拥塞（000 可自愈），
    # curl 原生重试 3 次以穿透短拥塞窗口（404 也会被重试，多花 ~15s，可接受）。
    # 赋值必须挂兜底：curl 自身崩溃（无输出、退出码非零）时 set -e 会直接带崩脚本；
    # 兜底时保留已捕获的 4xx/5xx（如服务器明确回了 404/503）——它们有判定价值，
    # 只有空/000/2xx 截断才真正等价于"探测失败"。
    http_code=$(curl -L -s -o /dev/null -w "%{http_code}" --max-time 20 -r 0-0 \
        --retry 3 --retry-all-errors --retry-delay 5 "${url}") \
        || { [[ "${http_code}" =~ ^[45] ]] || http_code="000"; }

    case "${http_code}" in
        200|206)
            return 0
            ;;
        404)
            return 1
            ;;
        *)
            log "ERROR" "发布探测失败：HTTP ${http_code}（网络/服务端异常，非'未发布'）"
            return 2
            ;;
    esac
}

# bash 3.2 的 set -u 下，${#arr[@]} 对"未声明"数组直接 unbound 崩溃；崩溃若发生在
# if 条件上下文，退出码会被 EXIT trap 掩盖成 0（静默断更类事故）。
# ${arr[@]+x} 不能作守卫：bash 3.2.57 实测其展开依上下文而异——赋值/echo 处为空，
# 但 [ -n ... ] 判定中为真（顶层与函数内皆然）。最小复现：
#   /bin/bash -c 'set -u; if [ -n "${NOSUCH[@]+x}" ]; then echo TRUTHY; else echo EMPTY; fi'
# declare -p 判存在在所有上下文一致（未声明/置空/有值三态实测正确）。
# 用户"注释掉整块配置"是最自然的禁用方式，必须兜住。
mirrors_enabled() {
    declare -p MIRROR_PREFIXES >/dev/null 2>&1 || return 1
    [ "${#MIRROR_PREFIXES[@]}" -gt 0 ]
}

# 探测单个镜像前缀：对真实 release URL 经镜像发首字节 range 请求，echo HTTP 状态码。
# 这里挑选的是传输通道，状态码语义由调用方解释：200/206 = 镜像可用；404 = 镜像活
# 但无此资产（透传型镜像是"未发布"的强证据）；000/5xx = 镜像不可用。
# --max-filesize 64K：防个别镜像无视 Range 回全量包时，一次探测变成全带宽拉取。
# --retry 2：救援场景恰是网络抖动期，抗抖动等级与直连探测（--retry 3）对齐；
#   注意 --retry 不覆盖 connection-refused——DNS 已死的镜像每次探测仍固定多付
#   ~4s（如 ghp.ci 死亡期），可接受。
# 兜底保留 4xx/5xx 的理由同 check_url_exists：服务器明确应答的状态有判定价值。
probe_mirror() {
    local prefix="$1"
    local url="$2"
    local http_code

    # -L：部分镜像以 302 跳转应答，不跟随会误判为不可用
    http_code=$(curl -sL -o /dev/null -w "%{http_code}" --max-time 15 --max-filesize 65536 \
        --retry 2 --retry-delay 2 -r 0-0 "${prefix}/${url}" 2>/dev/null) \
        || { [[ "${http_code}" =~ ^[45] ]] || http_code="000"; }
    echo "${http_code}"
}

# 镜像面判定（供直连探测失败时降级）。返回码：0 = 任一镜像 200/206（胜出前缀写入
# 全局 PREFERRED_MIRROR_PREFIX，下载时直接采用，避免二次探测）；2 = 无镜像可用但有
# 404（透传型镜像证实"未发布"，按未发布静默等待，不告警）；1 = 镜像面全灭或未配置。
probe_mirrors_available() {
    local url="$1"
    local prefix code saw_404=0

    mirrors_enabled || return 1

    for prefix in "${MIRROR_PREFIXES[@]}"; do
        code=$(probe_mirror "${prefix}" "${url}")
        case "${code}" in
            200|206)
                PREFERRED_MIRROR_PREFIX="${prefix}"
                return 0
                ;;
            404)
                saw_404=1
                ;;
        esac
    done

    if [ "${saw_404}" -eq 1 ]; then
        return 2
    fi
    return 1
}

# 解析本次下载尝试的实际 URL：按序探测镜像前缀，首个可用者胜出；全部不可用回退直连。
# 每次下载尝试都重新解析——上一尝试选中的镜像此时可能已不可用（救援选定的前缀
# 由 download_file 在父层消费，不经过本函数）。
# 镜像内容与直连一致是信任假设，下载后另有大小交叉校验 + gzip 校验兜底。
# 注意：本函数在 $( ) 命令替换内执行，log 必须走 stderr——log 默认写 stdout，
# 会混进返回的 URL（2026-09-22 评审 Critical 1：污染的 URL 让真实 aria2c 全部拒识）。
resolve_download_url() {
    local url="$1"

    if mirrors_enabled; then
        local prefix code
        for prefix in "${MIRROR_PREFIXES[@]}"; do
            code=$(probe_mirror "${prefix}" "${url}")
            case "${code}" in
                200|206)
                    log "INFO" "使用镜像加速：${prefix}" >&2
                    echo "${prefix}/${url}"
                    return 0
                    ;;
            esac
        done
    fi

    log "INFO" "镜像均不可用，直连下载" >&2
    echo "${url}"
    return 0
}

# 获取直连响应头里的包大小基准（Content-Range 总长优先，Content-Length 兜底），
# 供下载完成后交叉校验镜像内容陈旧/损坏。基准取不到时不阻塞主流程（跳过比对）。
# 仅在直连探测成功后调用——直连拥塞的救援场景拿不到可靠基准，宁可跳过不误杀。
fetch_expected_size() {
    local url="$1"
    local headers total

    headers=$(curl -sL -D - -o /dev/null --max-time 20 -r 0-0 "${url}" 2>/dev/null | tr -d '\r') || headers=""
    # grep 无匹配时 pipeline 在 pipefail 下非零，必须就地兜底，否则会带崩整个脚本
    local final_code
    final_code=$(printf '%s\n' "${headers}" | grep -i '^HTTP/' | tail -1 | awk '{print $2}') || final_code=""
    total=$(printf '%s\n' "${headers}" | grep -i '^content-range:' | tail -1 | sed 's|.*/||') || total=""
    # Content-Length 兜底仅在最终应答为 200（无 range 语义）时启用：畸形 206
    # （无 Content-Range）的 Content-Length 是本次分段的长度（如 1），拿来当
    # 总长基准会让每次下载都"大小不符"三连败。
    if [[ ! "${total}" =~ ^[0-9]+$ && "${final_code}" == "200" ]]; then
        total=$(printf '%s\n' "${headers}" | grep -i '^content-length:' | tail -1 | awk '{print $2}') || total=""
    fi
    if [[ "${total}" =~ ^[0-9]+$ ]]; then
        RELEASE_EXPECTED_SIZE="${total}"
        log "INFO" "包大小基准：${RELEASE_EXPECTED_SIZE} 字节（下载后交叉校验）"
    fi
}

# 清理未完成的下载残留
cleanup_incomplete_downloads() {
    local output="$1"
    local download_dir="$2"

    # 获取基础文件名（不含扩展名）
    local base_name="${output%.tar.gz}"

    # 查找并清理所有相关的未完成文件
    # 1. 先清理与主文件名相关的文件 (.tar.gz, .tar.gz.aria2等)
    local had_control=0
    for file in "${download_dir}/${output}"*; do
        if [[ -f "${file}" ]]; then
            local filename
            filename=$(basename "${file}")

            # 清理 .aria2 控制文件
            if [[ "${filename}" == *.aria2 ]]; then
                log "INFO" "清理未完成下载的控制文件：${filename}"
                rm -f "${file}"
                had_control=1
            fi
        fi
    done

    # 控制文件存在 = 上一次 aria2c 未正常收尾（正常完成时 aria2 会自行删除控制
    # 文件）。此时数据文件不可信：aria2 会预分配整尺寸文件，-c 在没有控制文件时
    # 按"本地长度 == 总长"直接判完成 → 3 秒假成功 → gzip 闸门拦截 → 白烧一次
    # 重试（2026-09-22 生产日志 23:42:45-48 实证）。控制文件一删，数据文件同删。
    if [ "${had_control}" -eq 1 ] && [[ -f "${download_dir}/${output}" ]]; then
        log "INFO" "同步删除未完成的数据文件：${output}"
        rm -f "${download_dir}/${output}"
    fi

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

# 检查是否有待处理的下载文件（用于时间窗口外继续处理）
check_pending_downloads() {
    local pending_files=0

    for file in "${DOWNLOAD_DIR}"/qlib_bin_*.tar.gz; do
        # glob 已限定 .tar.gz 结尾（.aria2 控制文件不可能命中），再校验日期格式
        if [[ -f "${file}" ]] && [[ "$(basename "${file}")" =~ ${PENDING_FILE_RE} ]]; then
            pending_files=$((pending_files + 1))
        fi
    done

    # 输出待处理文件数量，确保退出码为0
    echo "${pending_files}"
    return 0
}

# 验证gzip文件完整性。单次确定性校验：锁机制保证没有并发写入者，
# 静态文件重试必然得到相同结果，等待重试没有意义。
verify_gzip_file() {
    local file="$1"
    if gzip -t "${file}" 2>/dev/null; then
        return 0
    fi
    log "WARN" "文件完整性校验失败：${file}"
    return 1
}

download_file() {
    local url="$1"
    local output="$2"
    local attempt=1

    # 救援探活的前缀必须在父层取走并清空：download_file 里对 resolve 的调用在
    # $( ) 子 shell 内，子 shell 里的清空对父 shell 无效，前缀会被钉死在全部
    # 重试上，镜像中途死亡时尝试 2/3 不会切换通道（复审合并阻塞项）。
    # 它只作为首次尝试的选路；后续尝试由 resolve 重新探测选路。
    local first_mirror="${PREFERRED_MIRROR_PREFIX}"
    PREFERRED_MIRROR_PREFIX=""

    # 在开始下载前，清理可能存在的未完成下载
    cleanup_incomplete_downloads "${output}" "${DOWNLOAD_DIR}"

    while [ ${attempt} -le ${MAX_RETRIES} ]; do
        log "INFO" "开始下载（尝试 ${attempt}/${MAX_RETRIES}）"

        # 首次尝试用救援选定的镜像；后续尝试重新解析（首个可用者胜出，全部失败回退直连）
        local attempt_url
        if [ "${attempt}" -eq 1 ] && [ -n "${first_mirror}" ]; then
            log "INFO" "使用镜像加速（救援选定）：${first_mirror}" >&2
            attempt_url="${first_mirror}/${url}"
        else
            attempt_url=$(resolve_download_url "${url}")
        fi
        # 防御：解析产物必须是单行 https URL（命令替换曾把日志行混进返回值，
        # 真实 aria2c 对多行/非 https 参数直接拒识——评审 Critical 1 的兜底防线）
        if [[ "${attempt_url}" != https://* || "${attempt_url}" == *$'\n'* ]]; then
            log "ERROR" "下载地址解析异常，回退直连"
            attempt_url="${url}"
        fi

        # 使用 -c 参数支持续传，--allow-overwrite=true 覆盖已存在的文件
        # --auto-file-renaming=false 防止自动重命名（避免产生 .1, .2 等文件）
        if aria2c ${ARIA2C_OPTIONS} -c --allow-overwrite=true --auto-file-renaming=false -o "${output}" "${attempt_url}"; then
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
            ((++attempt))
            continue
            fi

            # 镜像内容交叉校验：大小与直连元数据不符 = 疑似内容陈旧/损坏，按损坏处理
            if [[ -n "${RELEASE_EXPECTED_SIZE}" ]]; then
                local actual_size
                actual_size=$(stat -f%z "${output}" 2>/dev/null || stat -c%s "${output}" 2>/dev/null || echo "")
                if [[ -n "${actual_size}" && "${actual_size}" != "${RELEASE_EXPECTED_SIZE}" ]]; then
                    log "ERROR" "文件大小 ${actual_size} 与直连元数据 ${RELEASE_EXPECTED_SIZE} 不符（疑似镜像内容陈旧），删除并重试"
                    rm -f "${output}"
                    if [ ${attempt} -lt ${MAX_RETRIES} ]; then
                        log "INFO" "等待 ${RETRY_DELAY} 秒后重试..."
                        sleep ${RETRY_DELAY}
                    fi
                    ((++attempt))
                    continue
                fi
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
            ((++attempt))
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
                        # 数据日期早于目标日期：正常发布延迟，或镜像内容陈旧。
                        # 仍标记成功（文件已正确解压），但升 WARN 提示留意。
                        log "WARN" "数据日期 ${latest_data_date} 早于目标日期 ${target_date}，数据可能有延迟"
                        log "WARN" "文件已正确解压，标记为成功（若反复出现请排查镜像内容陈旧）"
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
    # LOG_DIR 必须在获取锁之前存在：锁文件与日志都写在其中，新机器首次运行
    # 若目录缺失，锁写入/tee 会在 set -euo pipefail 下直接把脚本带崩
    mkdir -p "${LOG_DIR}"

    # 尝试获取锁，如果失败则退出
    if ! acquire_lock; then
        exit 0
    fi

    # 确保脚本退出时释放锁，且保留原始退出码：裸 release_lock 会让 set -e 隐式
    # 中止的非零退出被 trap 内最后命令的状态掩盖成 0（静默断更类事故的通用形态）
    trap 'rc=$?; release_lock; exit $rc' EXIT

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

    # 优化：检查是否有待处理的下载文件（允许在时间窗口外继续处理）
    local pending_count
    pending_count=$(check_pending_downloads)

    # 列出待处理文件
    if [ "${pending_count}" -gt 0 ]; then
        for file in "${DOWNLOAD_DIR}"/qlib_bin_*.tar.gz; do
            if [[ -f "${file}" ]] && [[ "$(basename "${file}")" =~ ${PENDING_FILE_RE} ]]; then
                log "INFO" "发现待处理文件：$(basename "${file}")"
            fi
        done
    fi

    local pending_mode=false

    if [ "${pending_count}" -gt 0 ]; then
        log "INFO" "发现 ${pending_count} 个待处理文件，将继续处理（忽略时间窗口限制）"
        pending_mode=true
    fi

    # 判断是否应该检测数据
    if [ "${pending_mode}" = false ] && ! should_check_data; then
        log "INFO" "无需检测，脚本结束"
        exit 0
    fi

    # 优化：如果有待处理文件，优先处理最新的待处理文件
    if [ "${pending_mode}" = true ]; then
        # 获取最新的待处理文件
        local latest_pending_file=""
        local latest_date=""

        for file in "${DOWNLOAD_DIR}"/qlib_bin_*.tar.gz; do
            if [[ -f "${file}" ]]; then
                local filename
                filename=$(basename "${file}")

                if [[ "${filename}" =~ ${PENDING_FILE_RE} ]]; then
                    local file_date="${BASH_REMATCH[1]}"

                    # 比较日期，找到最新的
                    if [[ "${file_date}" > "${latest_date}" ]] || [[ -z "${latest_date}" ]]; then
                        latest_date="${file_date}"
                        latest_pending_file="${file}"
                    fi
                fi
            fi
        done

        if [[ -n "${latest_pending_file}" ]]; then
            log "INFO" "优先处理最新的待处理文件：$(basename "${latest_pending_file}")"

            local tarball_path="${latest_pending_file}"
            local target_date="${latest_date}"

            # 半截包防御：待处理文件可能是上次中断下载的残留（部分文件没有
            # 完成标记），必须先通过 gzip 校验才能解压；损坏则删除并转入下方
            # 正常下载流程，避免把截断的 tar 包送进 备份→解压→回滚 的全量循环。
            if ! verify_gzip_file "${tarball_path}"; then
                log "WARN" "待处理文件未通过完整性校验（疑似未完成的下载），删除后走正常下载流程：$(basename "${tarball_path}")"
                rm -f "${tarball_path}"
            elif extract_tarball "${tarball_path}" "${target_date}"; then
                # 显示更新后的数据目录大小
                local new_data_size
                new_data_size=$(du -sh "${CN_DATA_DIR}" 2>/dev/null | cut -f1)
                log "INFO" "数据目录大小：${new_data_size}"

                log "INFO" "========================================"
                log "INFO" "待处理文件处理完成！"
                log "INFO" "========================================"

                # 退出脚本，避免重复处理
                exit 0
            else
                log "ERROR" "待处理文件解压失败，删除文件以便下次重新下载"
                rm -f "${tarball_path}"
                exit 1
            fi
        fi
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

    # 探测发布：404 = 未发布（正常等待，下次再试）；探测失败（rc=2）≠ 未发布，
    # 必须以非零退出，让 20:00 的调度任务能感知并告警，而不是静默断更。
    local probe_rc=0
    check_url_exists "${release_url}" || probe_rc=$?
    if [ "${probe_rc}" -eq 1 ]; then
        log "INFO" "发布尚未上线，将在下次检测"
        exit 0
    fi
    if [ "${probe_rc}" -ne 0 ]; then
        # 直连探测失败（000/5xx）≠ 未发布——GitHub 链路间歇拥塞时发布往往仍在线。
        # 用镜像面重新判定：任一镜像探到 → 继续下载；透传镜像 404 → 按未发布静默
        # 等待（与直连 404 同语义，避免把正常等待升级成告警）；直连与镜像全灭 →
        # 才是真故障，告警退出（rc=2 的告警语义保留给"全都连不上"）。
        local rescue_rc=0
        probe_mirrors_available "${release_url}" || rescue_rc=$?
        case "${rescue_rc}" in
            0)
                log "INFO" "直连探测失败（HTTP 000/5xx），镜像探测可用，继续通过镜像下载"
                ;;
            2)
                log "INFO" "直连探测失败，镜像返回 404，判定发布尚未上线，将在下次检测"
                exit 0
                ;;
            *)
                log "ERROR" "发布探测失败（rc=${probe_rc}，直连与镜像均不可用），以失败退出供调度器告警"
                exit 1
                ;;
        esac
    fi

    log "INFO" "找到发布：${release_url}"
    fetch_expected_size "${release_url}"

    # 下载文件
    local output_file="qlib_bin_${target_date}.tar.gz"
    local tarball_path="${DOWNLOAD_DIR}/${output_file}"

    if ! download_file "${release_url}" "${output_file}"; then
        log "ERROR" "下载任务失败"
        exit 1
    fi

    # 解压并更新 Qlib 数据
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
}

# 执行主流程
main
