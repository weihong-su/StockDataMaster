@echo off
REM 盘后回归测试启动脚本
REM 适用于Windows系统

echo ====================================
echo 盘后回归测试 - 启动脚本
echo ====================================
echo.

REM 设置Python环境路径
set PYTHON_EXE=C:\Users\PC\Anaconda3\envs\python39\python.exe

REM 检查Python环境是否存在
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python环境不存在: %PYTHON_EXE%
    echo 请检查Anaconda环境是否正确安装
    pause
    exit /b 1
)

echo [OK] Python环境: %PYTHON_EXE%
echo.

REM 检查当前时间是否为盘后时段 (>= 15:00)
"%PYTHON_EXE%" -c "import datetime; now = datetime.datetime.now(); print(f'当前时间: {now.strftime(\"%%Y-%%m-%%d %%H:%%M:%%S\")}'); exit(0 if now.hour >= 15 else 1)"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [WARNING] 当前不是盘后时段 ^(时间 ^< 15:00^)
    echo 建议在盘后时段 ^(15:00之后^) 运行此测试
    echo.
    choice /C YN /M "是否继续执行测试？"
    if errorlevel 2 (
        echo 测试已取消
        pause
        exit /b 1
    )
)

echo.
echo ====================================
echo 开始执行盘后回归测试
echo ====================================
echo.

REM 切换到测试目录
cd /d "%~dp0"

REM 执行测试脚本
"%PYTHON_EXE%" test_post_market.py

REM 显示测试结果
echo.
echo ====================================
echo 测试执行完成
echo ====================================
echo.

REM 检查报告文件
if exist "reports\post_market_test_*.md" (
    echo [OK] 测试报告已生成
    echo 报告位置: reports\
    echo.
    dir /b /o-d reports\post_market_test_*.md | findstr /r "post_market_test_.*\.md" | set /p LATEST_REPORT=
    echo 最新报告: %LATEST_REPORT%
) else (
    echo [WARN] 未找到测试报告
)

echo.
pause
