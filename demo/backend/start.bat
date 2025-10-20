@echo off
REM StockDataMaster Demo 后端启动脚本 (Windows)

echo =========================================
echo StockDataMaster监控平台 - 后端服务
echo =========================================

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python
    pause
    exit /b 1
)

REM 检查并安装依赖
echo 检查依赖...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo 正在安装依赖...
    pip install -r requirements.txt
)

REM 启动服务
echo.
echo 正在启动API服务...
echo 地址: http://localhost:8000
echo 文档: http://localhost:8000/docs
echo.

python api_server.py

pause
