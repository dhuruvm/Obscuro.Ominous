@echo off
setlocal EnableExtensions
set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"

if not exist "%APP_DIR%\cli.py" (
    echo ERROR: cli.py was not found in "%APP_DIR%".
    exit /b 2
)

set "PYTHON=%APP_DIR%\venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    call powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_DIR%\ensure_env.ps1"
) else if not exist "%APP_DIR%\venv\pyvenv.cfg" (
    call powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_DIR%\ensure_env.ps1"
)
if not exist "%PYTHON%" (
    for /f "usebackq delims=" %%P in ("%APP_DIR%\.python_path") do if exist "%%P" set "PYTHON=%%P"
)
if not exist "%PYTHON%" (
    for /f "delims=" %%P in ('where python 2^>nul') do if not defined OO_FOUND_PYTHON set "PYTHON=%%P" & set "OO_FOUND_PYTHON=1"
)
if not exist "%PYTHON%" (
    call powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_DIR%\ensure_env.ps1"
    if exist "%APP_DIR%\venv\Scripts\python.exe" set "PYTHON=%APP_DIR%\venv\Scripts\python.exe"
)
if not exist "%PYTHON%" (
    echo ERROR: Python could not be found or installed.
    exit /b 1
)

"%PYTHON%" -c "import rich" >nul 2>nul
if errorlevel 1 (
    call powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_DIR%\ensure_env.ps1"
    if exist "%APP_DIR%\venv\Scripts\python.exe" set "PYTHON=%APP_DIR%\venv\Scripts\python.exe"
)

pushd "%APP_DIR%" >nul
"%PYTHON%" "%APP_DIR%\cli.py" %*
set "EXIT_CODE=%errorlevel%"
popd
exit /b %EXIT_CODE%