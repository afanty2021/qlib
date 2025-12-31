#!/bin/bash
#
# ETF数据自动更新定时任务安装脚本
#
# 功能：设置每天16:00自动执行ETF数据更新
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 日志文件
LOG_DIR="$HOME/.qlib/qlib_data/cn_data/etf"
mkdir -p "$LOG_DIR"

# Python解释器
PYTHON="${PYTHON_CMD:-python3}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}ETF数据自动更新定时任务安装${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查TUSHARE_TOKEN
if [ -z "$TUSHARE_TOKEN" ]; then
    echo -e "${RED}❌ 未设置TUSHARE_TOKEN环境变量${NC}"
    echo -e "${YELLOW}请先设置: export TUSHARE_TOKEN='your_token_here'${NC}"
    exit 1
fi

echo -e "${GREEN}✅ TUSHARE_TOKEN已设置${NC}"
echo ""

# 检查Python
if ! command -v $PYTHON &> /dev/null; then
    echo -e "${RED}❌ 未找到python3命令${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python解释器: $PYTHON${NC}"
echo ""

# 检查脚本文件
UPDATE_SCRIPT="$SCRIPT_DIR/etf_auto_download.py"

if [ ! -f "$UPDATE_SCRIPT" ]; then
    echo -e "${RED}❌ 未找到更新脚本: $UPDATE_SCRIPT${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 更新脚本: $UPDATE_SCRIPT${NC}"
echo ""

# 创建包装脚本
WRAPPER_SCRIPT="$SCRIPT_DIR/etf_update_wrapper.sh"
cat > "$WRAPPER_SCRIPT" << 'EOF'
#!/bin/bash
#
# ETF数据更新包装脚本
# 用于cron定时调用
#

# 设置环境变量
export TUSHARE_TOKEN="{{TUSHARE_TOKEN}}"
export PYTHONPATH="{{PROJECT_ROOT}}:$PYTHONPATH"

# 日志文件
LOG_DIR="$HOME/.qlib/qlib_data/cn_data/etf"
LOG_FILE="$LOG_DIR/cron_$(date +\%Y\%m\%d).log"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 执行更新
echo "========================================" >> "$LOG_FILE"
echo "ETF数据更新开始: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

cd {{PROJECT_ROOT}}
# 使用配置文件中的ETF列表
{{PYTHON}} {{UPDATE_SCRIPT}} --convert-qlib >> "$LOG_FILE" 2>&1

echo "========================================" >> "$LOG_FILE"
echo "ETF数据更新完成: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
EOF

# 替换占位符
sed -i.bak "s|{{TUSHARE_TOKEN}}|$TUSHARE_TOKEN|g" "$WRAPPER_SCRIPT"
sed -i.bak "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" "$WRAPPER_SCRIPT"
sed -i.bak "s|{{PYTHON}}|$PYTHON|g" "$WRAPPER_SCRIPT"
sed -i.bak "s|{{UPDATE_SCRIPT}}|$UPDATE_SCRIPT|g" "$WRAPPER_SCRIPT"
rm -f "$WRAPPER_SCRIPT.bak"

# 添加执行权限
chmod +x "$WRAPPER_SCRIPT"

echo -e "${GREEN}✅ 包装脚本: $WRAPPER_SCRIPT${NC}"
echo ""

# 安装cron任务
CRON_JOB="0 16 * * 1-5 $WRAPPER_SCRIPT"

# 检查是否已存在
if crontab -l 2>/dev/null | grep -q "etf_update_wrapper"; then
    echo -e "${YELLOW}⚠️  检测到已存在的ETF更新任务${NC}"

    read -p "是否要替换现有的定时任务? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # 删除旧任务
        crontab -l | grep -v "etf_update_wrapper" | crontab -
        # 添加新任务
        (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
        echo -e "${GREEN}✅ 定时任务已更新${NC}"
    else
        echo -e "${YELLOW}⚠️  保留现有定时任务${NC}"
        exit 0
    fi
else
    # 添加新任务
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo -e "${GREEN}✅ 定时任务已安装${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}安装完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "定时任务将在每个工作日16:00执行"
echo ""
echo -e "日志目录: $LOG_DIR"
echo -e "包装脚本: $WRAPPER_SCRIPT"
echo ""
echo -e "查看当前定时任务:"
echo -e "  ${YELLOW}crontab -l${NC}"
echo ""
echo -e "查看日志:"
echo -e "  ${YELLOW}tail -f $LOG_DIR/cron_\$(date +%Y%m%d).log${NC}"
echo ""
echo -e "手动测试运行:"
echo -e "  ${YELLOW}$WRAPPER_SCRIPT${NC}"
echo ""
echo -e "${YELLOW}提示: 如需修改执行时间，请使用 'crontab -e' 编辑${NC}"
echo ""
