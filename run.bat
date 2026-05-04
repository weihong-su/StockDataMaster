@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"

:: ============================================================
::  StockDataMaster  run.bat
::  用途: 一键安装 / 配置 / 启动各类任务
:: ============================================================

:MENU
cls
echo.
echo  ================================================================
echo   StockDataMaster  v1.2.0
echo  ================================================================
echo.
echo   安装 / 配置
echo   [1] 安装核心依赖
echo   [2] 安装内置库 (lib/)
echo   [3] 编辑配置文件 (config.json)
echo.
echo   开发 / 测试
echo   [4] 运行单元测试  (无需网络)
echo   [5] 运行全量测试  (需网络)
echo   [6] 启动交互式测试 GUI
echo   [7] 发布前质量检查
echo.
echo   服务 / 工具
echo   [8] 启动文档服务器
echo   [9] 查看运行日志
echo.
echo   [0] 退出
echo.
echo  ================================================================
set /p CHOICE="  请输入选项 [0-9]: "

if "%CHOICE%"=="1" goto INSTALL_DEPS
if "%CHOICE%"=="2" goto INSTALL_LIBS
if "%CHOICE%"=="3" goto EDIT_CONFIG
if "%CHOICE%"=="4" goto RUN_UNIT_TESTS
if "%CHOICE%"=="5" goto RUN_ALL_TESTS
if "%CHOICE%"=="6" goto RUN_GUI
if "%CHOICE%"=="7" goto PRE_RELEASE
if "%CHOICE%"=="8" goto SERVE_DOCS
if "%CHOICE%"=="9" goto VIEW_LOG
if "%CHOICE%"=="0" goto EXIT
echo   [!] 无效选项，请重试
timeout /t 1 >nul
goto MENU


:: ============================================================
::  公共: 检测 Python 环境
:: ============================================================
:FIND_PYTHON
set PYTHON=

:: 优先使用项目指定的 conda 环境
set CONDA_PYTHON=C:\Users\PC\Anaconda3\envs\python38\python.exe
if exist "%CONDA_PYTHON%" (
    set PYTHON=%CONDA_PYTHON%
    goto :eof
)

:: 尝试 conda activate python38
where conda >nul 2>&1
if %errorlevel%==0 (
    for /f "delims=" %%i in ('conda run -n python38 python -c "import sys; print(sys.executable)" 2^>nul') do set PYTHON=%%i
    if defined PYTHON goto :eof
)

:: 回退到系统 PATH
where python >nul 2>&1
if %errorlevel%==0 (
    set PYTHON=python
    goto :eof
)

where python3 >nul 2>&1
if %errorlevel%==0 (
    set PYTHON=python3
    goto :eof
)

echo   [FAIL] 未找到 Python 环境，请安装 Python 3.8+ 或配置 conda 环境 python38
goto :eof


:: ============================================================
::  [1] 安装核心依赖
:: ============================================================
:INSTALL_DEPS
cls
echo.
echo  ================================================================
echo   [1] 安装核心依赖
echo  ================================================================
echo.
call :FIND_PYTHON
if not defined PYTHON goto PAUSE_RETURN

echo   Python: %PYTHON%
echo.
echo   正在安装 pandas numpy mootdx baostock tushare ...
echo.
"%PYTHON%" -m pip install pandas numpy mootdx baostock tushare
echo.
if %errorlevel%==0 (
    echo   [OK] 安装完成
) else (
    echo   [WARN] 部分安装失败，请查看上方错误信息
)
goto PAUSE_RETURN


:: ============================================================
::  [2] 安装内置库
:: ============================================================
:INSTALL_LIBS
cls
echo.
echo  ================================================================
echo   [2] 安装内置库到 lib/ 目录
echo  ================================================================
echo.
call :FIND_PYTHON
if not defined PYTHON goto PAUSE_RETURN

if not exist "lib\install_libs.py" (
    echo   [FAIL] 未找到 lib\install_libs.py
    goto PAUSE_RETURN
)

echo   Python: %PYTHON%
echo.
"%PYTHON%" lib\install_libs.py
goto PAUSE_RETURN


:: ============================================================
::  [3] 编辑配置文件
:: ============================================================
:EDIT_CONFIG
if not exist "config.json" (
    echo   [FAIL] 未找到 config.json
    goto PAUSE_RETURN
)
:: 优先用 VS Code，回退到记事本
where code >nul 2>&1
if %errorlevel%==0 (
    start "" code config.json
) else (
    start "" notepad config.json
)
goto MENU


:: ============================================================
::  [4] 运行单元测试（无需网络）
:: ============================================================
:RUN_UNIT_TESTS
cls
echo.
echo  ================================================================
echo   [4] 运行单元测试 (marker: unit)
echo  ================================================================
echo.
call :FIND_PYTHON
if not defined PYTHON goto PAUSE_RETURN

echo   Python: %PYTHON%
echo.
"%PYTHON%" -X utf8 -m pytest test/suite/ -v -m unit
echo.
if %errorlevel%==0 (
    echo   [OK] 所有单元测试通过
) else (
    echo   [FAIL] 存在失败用例，请查看上方输出
)
goto PAUSE_RETURN


:: ============================================================
::  [5] 运行全量测试（需网络）
:: ============================================================
:RUN_ALL_TESTS
cls
echo.
echo  ================================================================
echo   [5] 运行全量测试 (包含集成测试，需网络)
echo  ================================================================
echo.
call :FIND_PYTHON
if not defined PYTHON goto PAUSE_RETURN

echo   Python: %PYTHON%
echo.
"%PYTHON%" -X utf8 -m pytest test/suite/ -v
echo.
if %errorlevel%==0 (
    echo   [OK] 全量测试通过
) else (
    echo   [FAIL] 存在失败用例，请查看上方输出
)
goto PAUSE_RETURN


:: ============================================================
::  [6] 启动交互式测试 GUI
:: ============================================================
:RUN_GUI
cls
echo.
echo  ================================================================
echo   [6] 启动交互式测试 GUI
echo  ================================================================
echo.
call :FIND_PYTHON
if not defined PYTHON goto PAUSE_RETURN

if not exist "test\interactive_test_gui.py" (
    echo   [FAIL] 未找到 test\interactive_test_gui.py
    goto PAUSE_RETURN
)

echo   Python: %PYTHON%
echo   正在启动 GUI，窗口关闭后返回菜单...
echo.
"%PYTHON%" test\interactive_test_gui.py
goto MENU


:: ============================================================
::  [7] 发布前质量检查
:: ============================================================
:PRE_RELEASE
cls
echo.
echo  ================================================================
echo   [7] 发布前质量检查
echo  ================================================================
echo.
call :FIND_PYTHON
if not defined PYTHON goto PAUSE_RETURN

if not exist "scripts\pre_release_check.py" (
    echo   [FAIL] 未找到 scripts\pre_release_check.py
    goto PAUSE_RETURN
)

echo   Python: %PYTHON%
echo.
"%PYTHON%" -X utf8 scripts\pre_release_check.py
echo.
if %errorlevel%==0 (
    echo   [OK] 所有检查通过，可以发布
) else (
    echo   [FAIL] 检查未通过，禁止发布
)
goto PAUSE_RETURN


:: ============================================================
::  [8] 启动文档服务器
:: ============================================================
:SERVE_DOCS
cls
echo.
echo  ================================================================
echo   [8] 启动本地文档服务器
echo  ================================================================
echo.
call :FIND_PYTHON
if not defined PYTHON goto PAUSE_RETURN

if not exist "serve_docs.py" (
    echo   [FAIL] 未找到 serve_docs.py
    goto PAUSE_RETURN
)

echo   Python: %PYTHON%
echo   文档地址: http://localhost:8080
echo   关闭此窗口可停止服务
echo.
start "StockDataMaster Docs" /min "%PYTHON%" serve_docs.py
echo   [OK] 文档服务已在后台启动，浏览器将自动打开
goto PAUSE_RETURN


:: ============================================================
::  [9] 查看运行日志
:: ============================================================
:VIEW_LOG
cls
echo.
echo  ================================================================
echo   [9] 查看运行日志
echo  ================================================================
echo.
set LOG_FILE=logs\data_master.log
if not exist "%LOG_FILE%" (
    echo   [INFO] 日志文件不存在: %LOG_FILE%
    echo   请先运行一次数据获取操作以生成日志
    goto PAUSE_RETURN
)

:: 显示最后 50 行
echo   文件: %LOG_FILE%
echo   ----------------------------------------------------------------
echo.
powershell -Command "Get-Content '%LOG_FILE%' -Tail 50"
echo.
echo   ----------------------------------------------------------------
echo   [提示] 按 T 用记事本打开完整日志，其他键返回菜单
choice /c TN /n /m "  选择 [T=记事本 / N=返回]: "
if %errorlevel%==1 start "" notepad "%LOG_FILE%"
goto MENU


:: ============================================================
::  公共: 暂停后返回菜单
:: ============================================================
:PAUSE_RETURN
echo.
pause
goto MENU


:: ============================================================
::  退出
:: ============================================================
:EXIT
echo.
echo   再见！
echo.
endlocal
exit /b 0
