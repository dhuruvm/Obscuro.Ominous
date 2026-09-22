$ErrorActionPreference = "Stop"

Write-Host "Installing dependencies..." -ForegroundColor Cyan
pip install -r requirements.txt
pip install pyinstaller

Write-Host "Building standalone executable for Obscuro Ominous..." -ForegroundColor Cyan
# Collect all submodules explicitly and apply optimizations
pyinstaller --clean --noconfirm --onefile --name obscuro `
    --optimize 2 `
    --uac-admin `
    --collect-all pipeline `
    --collect-all io_module `
    --collect-all workers `
    --exclude-module PIL `
    --exclude-module tkinter `
    --exclude-module matplotlib `
    --exclude-module scipy `
    cli.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "Build completed successfully! Executable is located at dist/obscuro/obscuro.exe" -ForegroundColor Green
} else {
    Write-Host "Build failed with exit code $LASTEXITCODE" -ForegroundColor Red
}
