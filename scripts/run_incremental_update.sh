#!/bin/bash
# TuShare A股数据增量更新快速启动脚本
# 借鉴 investment_data 项目的增量更新思路

set -e

echo "=========================================="
echo "TuShare A股数据增量更新"
echo "=========================================="
echo ""

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 Python3"
    echo "请先安装 Python3: https://www.python.org/downloads/"
    exit 1
fi

echo "✅ Python3 环境检查通过"

# 检查 TUSHARE_TOKEN 环境变量
if [ -z "$TUSHARE_TOKEN" ]; then
    echo "❌ 错误: 未设置 TUSHARE_TOKEN 环境变量"
    echo ""
    echo "请设置 TuShare API Token:"
    echo "  export TUSHARE_TOKEN='your_token_here'"
    echo ""
    echo "或修改 ~/.bashrc 或 ~/.zshrc 添加:"
    echo "  echo 'export TUSHARE_TOKEN=\"your_token_here\"' >> ~/.bashrc"
    echo "  source ~/.bashrc"
    echo ""
    echo "💡 如何获取 Token: 访问 https://tushare.pro 注册账号并申请"
    exit 1
fi

echo "✅ TUSHARE_TOKEN 环境变量已设置"

# 检查依赖
echo ""
echo "检查依赖包..."

python3 -c "import qlib" 2>/dev/null || {
    echo "❌ Qlib 未安装"
    echo "正在安装 Qlib..."
    pip install qlib
}

python3 -c "import tushare" 2>/dev/null || {
    echo "❌ TuShare 未安装"
    echo "正在安装 TuShare..."
    pip install tushare
}

python3 -c "import yaml" 2>/dev/null || {
    echo "❌ PyYAML 未安装"
    echo "正在安装 PyYAML..."
    pip install pyyaml
}

echo "✅ 依赖包检查完成"

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo ""
echo "=========================================="
echo "开始增量更新..."
echo "=========================================="
echo ""

# 运行更新脚本
python3 "$SCRIPT_DIR/tushare_incremental_update.py"

echo ""
echo "=========================================="
echo "更新完成！"
echo "=========================================="
echo ""
echo "📊 数据文件位置: ~/.qlib/qlib_data/cn_data/"
echo "📝 日志文件位置: ~/.qlib/qlib_data/cn_data/incremental_update.log"
echo ""
echo "查看日志:"
echo "  tail -f ~/.qlib/qlib_data/cn_data/incremental_update.log"
