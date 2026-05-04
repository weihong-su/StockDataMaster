@echo off
cd /d "%~dp0"

:: Detect Python (conda env first, then system PATH)
set PYTHON=

set CONDA_PY=C:\Users\PC\Anaconda3\envs\python38\python.exe
if exist "%CONDA_PY%" (
    set PYTHON=%CONDA_PY%
    goto :RUN
)

where python >nul 2>&1
if not errorlevel 1 (
    set PYTHON=python
    goto :RUN
)

where python3 >nul 2>&1
if not errorlevel 1 (
    set PYTHON=python3
    goto :RUN
)

echo Python not found. Please install Python 3.8+ or set up conda env python38.
pause
exit /b 1

:RUN
"%PYTHON%" -X utf8 menu.py
