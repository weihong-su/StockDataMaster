@echo off
REM ================================================================================
REM StockDataMaster 交易时段综合测试脚本
REM ================================================================================
REM
REM 用途: 一键运行完整的交易时段综合测试
REM 要求: 必须在交易时段运行 (09:30-15:00)
REM 输出: JSON报告 + Markdown报告
REM
REM ================================================================================

echo ================================================================================
echo StockDataMaster 交易时段综合测试
echo ================================================================================
echo.

REM 检查当前时间
echo [INFO] 检查当前时间...
for /f "tokens=1-2 delims=:" %%a in ('time /t') do set hour=%%a
echo [INFO] 当前时间: %time%
echo.

REM 检查是否在交易时段 (简化版,仅检查小时)
if %hour% GEQ 9 if %hour% LEQ 15 (
    echo [PASS] 当前可能在交易时段
) else (
    echo [WARN] 当前不在交易时段 ^(09:30-15:00^)
    echo [WARN] 部分测试可能无法完整执行
)
echo.

REM 检查Python环境
echo [INFO] 检查Python环境...
set PYTHON_ENV=C:\Users\PC\Anaconda3\envs\python38\python.exe

if not exist "%PYTHON_ENV%" (
    echo [FAIL] Python环境不存在: %PYTHON_ENV%
    echo.
    pause
    exit /b 1
)

echo [PASS] Python环境: %PYTHON_ENV%
echo.

REM 切换到项目目录
cd /d "%~dp0.."
echo [INFO] 工作目录: %CD%
echo.

REM 运行测试
echo ================================================================================
echo 开始运行综合测试...
echo ================================================================================
echo.

"%PYTHON_ENV%" test\test_trading_hours_comprehensive.py

REM 检查测试结果
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ================================================================================
    echo [PASS] 测试执行成功!
    echo ================================================================================
    echo.
    echo [INFO] 测试报告已生成:
    echo [INFO]   - JSON: test\test_trading_hours_comprehensive_report.json
    echo [INFO]   - Markdown: docs\test_trading_hours_comprehensive_report.md
    echo.
) else (
    echo.
    echo ================================================================================
    echo [FAIL] 测试执行失败! (错误代码: %ERRORLEVEL%)
    echo ================================================================================
    echo.
    echo [INFO] 请查看控制台输出和日志文件:
    echo [INFO]   - logs\data_master.log
    echo.
)

REM 询问是否查看报告
echo.
set /p choice="是否打开Markdown报告? (Y/N): "
if /i "%choice%"=="Y" (
    if exist "docs\test_trading_hours_comprehensive_report.md" (
        start "" "docs\test_trading_hours_comprehensive_report.md"
    ) else (
        echo [WARN] 报告文件不存在
    )
)

echo.
pause
