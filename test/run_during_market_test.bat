@echo off
chcp 65001 >nul
echo ====================================
echo StockDataMaster 盘中回归测试
echo ====================================
echo.

echo 正在启动盘中测试...
echo Python环境: C:\Users\PC\Anaconda3\envs\python39
echo.

C:\Users\PC\Anaconda3\envs\python39\python.exe test_during_market.py

echo.
echo ====================================
echo 测试执行完成
echo ====================================
pause
