@echo off
setlocal

rem ================================================================
rem  StockDataMaster - MkDocs local preview (hot reload)
rem  - Auto detects Python (conda env first, then system PATH)
rem  - Installs docs deps via `python -m pip` if missing
rem  - Starts `mkdocs serve` via `python -m mkdocs` (no PATH dep)
rem  - Opens browser after a short delay
rem
rem  Note: keep this file ASCII-only.
rem  cmd.exe parses .bat files using the system ANSI codepage
rem  (GBK on CN Windows). Non-ASCII bytes break parsing.
rem ================================================================

set "ROOT=%~dp0"
cd /d "%ROOT%"

rem ---- Detect Python ----------------------------------------------
set "PYTHON="
set "CONDA_PY=C:\Users\PC\Anaconda3\envs\python38\python.exe"
if exist "%CONDA_PY%" (
    set "PYTHON=%CONDA_PY%"
    goto :CHECK_DEPS
)

where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON=python"
    goto :CHECK_DEPS
)

where python3 >nul 2>nul
if not errorlevel 1 (
    set "PYTHON=python3"
    goto :CHECK_DEPS
)

echo [ERROR] Python not found. Install Python 3.8+ or set up conda env python38.
pause
exit /b 1

:CHECK_DEPS
echo [INFO] Using Python: %PYTHON%
"%PYTHON%" -m mkdocs --version >nul 2>nul
if not errorlevel 1 goto :SERVE

echo [INFO] mkdocs missing in this Python, installing docs requirements...
"%PYTHON%" -m pip install -r requirements-docs.txt
if errorlevel 1 (
    echo [ERROR] Failed to install docs requirements. Check pip/network.
    pause
    exit /b 1
)

:SERVE
set "DOCS_PORT=8000"
rem URL contains /StockDataMaster/ sub-path, aligned with site_url in mkdocs.yml
set "DOCS_URL=http://127.0.0.1:%DOCS_PORT%/StockDataMaster/"

echo [INFO] Starting MkDocs hot-reload server at %DOCS_URL%
echo [INFO] Edits to docs\*.md or source-code docstrings reload automatically.
echo [INFO] Press Ctrl+C to stop.
echo.

rem Open browser after 3s so mkdocs has time to bind the port
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start %DOCS_URL%"

"%PYTHON%" -m mkdocs serve --dev-addr=127.0.0.1:%DOCS_PORT%

endlocal
