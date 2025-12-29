@echo off
REM TuShare A股数据增量更新快速启动脚本 (Windows)
REM 借鉴 investment_data 项目的增量更新思路

echo ==========================================
echo TuShare A股数据增量更新
echo ==========================================
echo.

REM 检查 Python 环境
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ 错误: 未找到 Python
    echo 请先安装 Python: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Python 环境检查通过

REM 检查 TUSHARE_TOKEN 环境变量
if "%TUSHARE_TOKEN%"=="" (
    echo ❌ 错误: 未设置 TUSHARE_TOKEN 环境变量
    echo.
    echo 请设置 TuShare API Token:
    echo   set TUSHARE_TOKEN=your_token_here
    echo.
    echo 或在系统环境变量中添加:
    echo   TUSHARE_TOKEN=your_token_here
    echo.
    echo 💡 如何获取 Token: 访问 https://tushare.pro 注册账号并申请
    pause
    exit /b 1
)

echo ✅ TUSHARE_TOKEN 环境变量已设置

REM 检查依赖
echo.
echo 检查依赖包...

python -c "import qlib" 2>nul || (
    echo ❌ Qlib 未安装
    echo 正在安装 Qlib...
    pip install qlib
)

python -c "import tushare" 2>nul || (
    echo ❌ TuShare 未安装
    echo 正在安装 TuShare...
    pip install tushare
)

python -c "import yaml" 2>nul || (
    echo ❌ PyYAML 未安装
    echo 正在安装 PyYAML...
    pip install pyyaml
)

echo ✅ 依赖包检查完成

REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0

echo.
echo ==========================================
echo 开始增量更新...
echo ==========================================
echo.

REM 运行更新脚本
python "%SCRIPT_DIR%tushare_incremental_update.py"

echo.
echo ==========================================
echo 更新完成！
echo ==========================================
echo.
echo 📊 数据文件位置: %%USERPROFILE%%\.qlib\qlib_data\cn_data\
echo 📝 日志文件位置: %%USERPROFILE%%\.qlib\qlib_data\cn_data\incremental_update.log
echo.
echo 查看日志:
echo   type %%USERPROFILE%%\.qlib\qlib_data\cn_data\incremental_update.log
echo.

pause
