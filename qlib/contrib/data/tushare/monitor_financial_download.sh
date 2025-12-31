#!/bin/bash
# 财务数据下载监控脚本

echo "🔍 A股财务数据下载监控"
echo "======================================"

# 检查进程是否运行
if ps -p 8338 > /dev/null 2>&1; then
    echo "✅ 下载进程运行中 (PID: 8338)"
else
    echo "⚠️ 下载进程已结束"
fi

echo ""
echo "📊 最新进度:"
echo "======================================"

# 显示最新20行日志
tail -20 /tmp/financial_download.log | grep -E "\[[0-9]+/5466\]|💾|✅ 完成"

echo ""
echo "📁 已保存的批次文件:"
ls -lh ~/.qlib/qlib_data/cn_data/financial_data/batch_*.csv 2>/dev/null | tail -5

echo ""
echo "💾 使用以下命令实时监控:"
echo "   tail -f /tmp/financial_download.log"
