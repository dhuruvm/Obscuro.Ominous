@echo off
call "%~dp0run.cmd" %*
exit /b %errorlevel%
setlocal
set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"

set "PYTHON="
if exist "%APP_DIR%\venv\Scripts\python.exe" set "PYTHON=%APP_DIR%\venv\Scripts\python.exe"
if not defined PYTHON (
    for %%P in (
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%ProgramFiles%\Python312\python.exe"
        "C:\Python312\python.exe"
        "C:\Python311\python.exe"
    ) do if exist "%%~P" set "PYTHON=%%~P"
)
if not defined PYTHON (
    where python >nul 2>nul
    if not errorlevel 1 for /f "delims=" %%P in ('where python 2^>nul') do set "PYTHON=%%P"
)
if not defined PYTHON (
    call powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_DIR%\ensure_env.ps1"
    if exist "%APP_DIR%\venv\Scripts\python.exe" set "PYTHON=%APP_DIR%\venv\Scripts\python.exe"
)
if not defined PYTHON (
    echo ERROR: Python was not found for Obscuro Ominous.
    exit /b 1
)

if not exist "%APP_DIR%\cli.py" (
    echo ERROR: cli.py was not found in "%APP_DIR%".
    exit /b 1
)

if "%1"=="" (
    "%PYTHON%" "%APP_DIR%\cli.py"
) else (
    "%PYTHON%" "%APP_DIR%\cli.py" %*
)
exit /b %errorlevel%