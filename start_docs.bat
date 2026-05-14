@echo off
setlocal

rem ================================================================
rem  StockDataMaster - MkDocs local preview (hot reload)
rem  - Auto installs docs deps when mkdocs is missing
rem  - Starts `mkdocs serve` and opens browser
rem
rem  Note: keep this file ASCII-only.
rem  cmd.exe parses .bat files using the system ANSI codepage (GBK
rem  on CN Windows). UTF-8 (no BOM) inside .bat breaks parsing.
rem ================================================================

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "DOCS_PORT=8000"
rem URL contains /StockDataMaster/ sub-path, aligned with site_url in mkdocs.yml
set "DOCS_URL=http://127.0.0.1:%DOCS_PORT%/StockDataMaster/"

where mkdocs >nul 2>nul
if errorlevel 1 (
    echo [INFO] mkdocs not found, installing docs requirements...
    pip install -r requirements-docs.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install docs requirements. Check Python/pip/network.
        pause
        exit /b 1
    )
)

echo [INFO] Starting MkDocs hot-reload server at %DOCS_URL%
echo [INFO] Edits to docs\*.md or source-code docstrings reload automatically.
echo [INFO] Press Ctrl+C to stop.
echo.

rem Open browser after 3s so mkdocs has time to bind the port
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start %DOCS_URL%"

mkdocs serve --dev-addr=127.0.0.1:%DOCS_PORT%

endlocal
