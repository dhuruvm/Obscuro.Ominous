# Environment and dependency bootstrap for Obscuro Ominous.
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvDir = Join-Path $scriptDir "venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$requirements = Join-Path $scriptDir "requirements.txt"

function Find-Python {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        (Join-Path $env:ProgramFiles "Python312\python.exe"),
        "C:\Python312\python.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python -and $python.Source -notlike "*WindowsApps*") { return $python.Source }
    return $null
}

try {
    $pythonExe = Find-Python
    if (-not $pythonExe) {
        $installer = Join-Path $env:TEMP "obscuro-python-3.12.exe"
        Write-Host "Python 3.12 was not found. Downloading the official installer..." -ForegroundColor Cyan
        Invoke-WebRequest "https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe" -OutFile $installer
        $process = Start-Process $installer -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1 SimpleInstall=1" -Wait -PassThru
        Remove-Item $installer -Force -ErrorAction SilentlyContinue
        if ($process.ExitCode -ne 0) { throw "Python installer exited with code $($process.ExitCode)." }
        $pythonExe = Find-Python
    }
    if (-not $pythonExe) { throw "Python 3.12 could not be located after installation." }
    $venvConfig = Join-Path $venvDir "pyvenv.cfg"
    if ((Test-Path $venvDir) -and (-not (Test-Path $venvPython) -or -not (Test-Path $venvConfig))) {
        Write-Host "Removing incomplete virtual environment..." -ForegroundColor Yellow
        Remove-Item $venvDir -Recurse -Force
    }
    if (-not (Test-Path $venvPython) -or -not (Test-Path $venvConfig)) {
        Write-Host "Creating virtual environment..." -ForegroundColor Cyan
        & $pythonExe -m venv $venvDir
        if ($LASTEXITCODE -ne 0) { throw "Could not create the Python virtual environment." }
    }
    Push-Location $scriptDir
    try {
        & $venvPython -m pip install --upgrade pip --disable-pip-version-check --quiet
        if ($LASTEXITCODE -ne 0) { throw "pip could not be upgraded." }
        & $venvPython -m pip install -r $requirements --disable-pip-version-check
        if ($LASTEXITCODE -ne 0) { throw "Python dependencies could not be installed." }
        & $venvPython -c "import rich, requests, httpx, bs4, tiktoken, numpy"
        if ($LASTEXITCODE -ne 0) { throw "Dependency verification failed. Re-run the installer and inspect the package error above." }
    } finally {
        Pop-Location
    }
    [System.IO.File]::WriteAllText((Join-Path $scriptDir ".python_path"), $venvPython)
    Write-Host "Obscuro Ominous is ready: $venvPython" -ForegroundColor Green
    exit 0
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}


