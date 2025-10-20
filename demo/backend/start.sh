#!/bin/bash

# StockDataMaster Demo 后端启动脚本

echo "========================================="
echo "StockDataMaster监控平台 - 后端服务"
echo "========================================="

# 检查Python环境
if ! command -v python &> /dev/null; then
    echo "错误: 未找到Python"
    exit 1
fi

# 检查依赖
echo "检查依赖..."
pip list | grep -q fastapi || {
    echo "正在安装依赖..."
    pip install -r requirements.txt
}

# 启动服务
echo ""
echo "正在启动API服务..."
echo "地址: http://localhost:8000"
echo "文档: http://localhost:8000/docs"
echo ""

python api_server.py
