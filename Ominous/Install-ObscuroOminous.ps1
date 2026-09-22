param(
    [switch]$SkipPath,
    [switch]$SkipShortcut
)

$ErrorActionPreference = "Stop"
$appDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $appDir "Run_ObscuroOminous.bat"

Write-Host "Installing Obscuro Ominous..." -ForegroundColor Cyan
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $appDir "ensure_env.ps1")
if ($LASTEXITCODE -ne 0) { throw "Environment setup failed." }

$globalLauncher = @"
@echo off
call "$appDir\run.cmd" %*
exit /b %errorlevel%
"@
$windowsApps = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"
foreach ($name in @("obscuro.cmd", "obscuro-ominous.cmd", "oo.cmd", "datacollector.cmd", "dc.cmd")) {
    $target = Join-Path $windowsApps $name
    if (Test-Path $windowsApps) {
        [System.IO.File]::WriteAllText($target, $globalLauncher)
    }
}
Write-Host "Updated global command launchers." -ForegroundColor Green

if (-not $SkipPath) {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @($userPath -split ';' | Where-Object { $_ -and $_ -ne $appDir })
    [Environment]::SetEnvironmentVariable("Path", (($parts + $appDir) -join ';'), "User")
    Write-Host "Added the application directory to the user PATH." -ForegroundColor Green
}

if (-not $SkipShortcut) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktop "Obscuro Ominous.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $launcher
    $shortcut.WorkingDirectory = $appDir
    $shortcut.Description = "Launch Obscuro Ominous"
    $shortcut.Save()
    Write-Host "Created a desktop shortcut." -ForegroundColor Green
}

Write-Host "Installation complete. Start the desktop shortcut or run: obscuro" -ForegroundColor Green
