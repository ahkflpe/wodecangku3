@echo off
chcp 65001 >nul
echo ========================================
echo   知名投资机构持仓追踪器
echo ========================================
echo.
echo 正在检查Python环境...
python --version 2>nul
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo 正在安装依赖...
python -m pip install -r requirements.txt

echo.
echo 启动程序...
python main.py

pause
