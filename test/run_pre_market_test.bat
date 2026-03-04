@echo off
REM StockDataMaster 盘前回归测试批处理脚本
REM 用途：一键运行盘前回归测试
REM 作者：YOLO Team
REM 最后更新：2025-12-10

echo ================================================================================
echo StockDataMaster 盘前回归测试
echo ================================================================================
echo.

REM 检查Python环境
set PYTHON_PATH=C:\Users\PC\Anaconda3\envs\python39\python.exe

if not exist "%PYTHON_PATH%" (
    echo [错误] 未找到Python环境: %PYTHON_PATH%
    echo 请检查Python安装路径是否正确
    pause
    exit /b 1
)

echo [信息] Python环境: %PYTHON_PATH%
echo.

REM 检查测试脚本
set TEST_SCRIPT=test\test_pre_market.py

if not exist "%TEST_SCRIPT%" (
    echo [错误] 未找到测试脚本: %TEST_SCRIPT%
    echo 请确保在项目根目录运行此脚本
    pause
    exit /b 1
)

echo [信息] 测试脚本: %TEST_SCRIPT%
echo.

REM 显示当前时间
echo [信息] 当前时间: %date% %time%
echo.

REM 运行测试
echo ================================================================================
echo 开始运行测试...
echo ================================================================================
echo.

"%PYTHON_PATH%" "%TEST_SCRIPT%"

set TEST_EXIT_CODE=%ERRORLEVEL%

echo.
echo ================================================================================
echo 测试完成
echo ================================================================================
echo.

if %TEST_EXIT_CODE% equ 0 (
    echo [成功] 测试执行成功
) else (
    echo [失败] 测试执行失败，退出码: %TEST_EXIT_CODE%
)

echo.
echo 测试报告已保存在 test\reports\ 目录
echo.

REM 询问是否查看报告
set /p OPEN_REPORT=是否打开测试报告目录? (Y/N):

if /i "%OPEN_REPORT%"=="Y" (
    start explorer test\reports
)

pause
exit /b %TEST_EXIT_CODE%
