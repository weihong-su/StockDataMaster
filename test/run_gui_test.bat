@echo off
REM ===================================================
REM StockDataMaster 交互式测试GUI启动脚本
REM ===================================================

echo.
echo ====================================
echo StockDataMaster 交互式测试GUI
echo ====================================
echo.

REM 切换到test目录
cd /d c:\github-repo\StockDataMaster\test

REM 检查Python环境是否存在
if not exist "C:\Users\PC\Anaconda3\envs\python38\python.exe" (
    echo [ERROR] Python环境不存在: C:\Users\PC\Anaconda3\envs\python38\python.exe
    echo 请检查Anaconda安装路径
    pause
    exit /b 1
)

REM 检查GUI文件是否存在
if not exist "interactive_test_gui.py" (
    echo [ERROR] GUI文件不存在: interactive_test_gui.py
    echo 当前目录: %CD%
    pause
    exit /b 1
)

echo [INFO] 启动GUI...
echo [INFO] Python: C:\Users\PC\Anaconda3\envs\python38\python.exe
echo [INFO] 脚本: interactive_test_gui.py
echo.

REM 启动GUI
C:\Users\PC\Anaconda3\envs\python38\python.exe interactive_test_gui.py

REM 检查退出码
if errorlevel 1 (
    echo.
    echo [ERROR] GUI启动失败，错误码: %errorlevel%
    pause
    exit /b %errorlevel%
)

echo.
echo [INFO] GUI已关闭
pause
