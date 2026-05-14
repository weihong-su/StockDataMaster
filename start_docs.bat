@echo off
chcp 65001 > nul
setlocal

rem ================================================================
rem  StockDataMaster - MkDocs 本地预览(热重载)
rem  - 自动安装文档依赖(若 mkdocs 缺失)
rem  - 启动 mkdocs serve 并自动打开浏览器
rem ================================================================

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "DOCS_PORT=8000"
rem URL 含 /StockDataMaster/ 子路径,与 mkdocs.yml 中 site_url 对齐
set "DOCS_URL=http://127.0.0.1:%DOCS_PORT%/StockDataMaster/"

where mkdocs >nul 2>nul
if errorlevel 1 (
    echo [INFO] 未检测到 mkdocs,正在安装文档依赖...
    pip install -r requirements-docs.txt
    if errorlevel 1 (
        echo [ERROR] 安装文档依赖失败,请检查 Python / pip / 网络环境
        pause
        exit /b 1
    )
)

echo [INFO] 正在启动 MkDocs 热重载服务: %DOCS_URL%
echo [INFO] 修改 docs\ 下任意 markdown 或源码 docstring 都将自动刷新
echo [INFO] 按 Ctrl+C 停止服务
echo.

rem 延迟 3 秒后打开浏览器,确保 mkdocs 已经监听端口
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start %DOCS_URL%"

mkdocs serve --dev-addr=127.0.0.1:%DOCS_PORT%

endlocal
