#!/bin/bash
echo "========================================"
echo "  知名投资机构持仓追踪器"
echo "========================================"
echo
echo "正在检查Python环境..."
python3 --version 2>/dev/null || python --version 2>/dev/null

if [ $? -ne 0 ]; then
    echo "[错误] 未检测到Python，请先安装Python 3.8+"
    exit 1
fi

echo
echo "正在安装依赖..."
python3 -m pip install -r requirements.txt 2>/dev/null || python -m pip install -r requirements.txt

echo
echo "启动程序..."
python3 main.py 2>/dev/null || python main.py
