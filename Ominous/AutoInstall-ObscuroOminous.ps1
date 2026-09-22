param(
    [switch]$SkipDockerCheck
)

$ErrorActionPreference = "Stop"

function Require-Admin {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host "This installer requires administrative privileges to install Docker and set up the environment." -ForegroundColor Yellow
        Write-Host "Restarting with elevated privileges..." -ForegroundColor Cyan
        Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
        exit
    }
}

Require-Admin

$appDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$exePath = Join-Path $appDir "dist\obscuro\obscuro.exe"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Obscuro Ominous - Autonomous Auto-Install " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Check/Install Docker
if (-not $SkipDockerCheck) {
    Write-Host "Checking for Docker..." -ForegroundColor Cyan
    if (Get-Command "docker" -ErrorAction SilentlyContinue) {
        Write-Host "Docker is already installed." -ForegroundColor Green
    } else {
        Write-Host "Docker not found. Downloading Docker Desktop installer..." -ForegroundColor Yellow
        $installerPath = Join-Path $appDir "Docker Desktop Installer.exe"
        Invoke-WebRequest -Uri "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe" -OutFile $installerPath
        Write-Host "Installing Docker Desktop quietly... This may take a few minutes." -ForegroundColor Yellow
        Start-Process -FilePath $installerPath -ArgumentList "install", "--quiet", "--accept-license" -Wait -NoNewWindow
        Write-Host "Docker installation completed. You might need to restart your computer or start Docker Desktop manually." -ForegroundColor Green
    }
}

# 2. Check for built executable
if (-not (Test-Path $exePath)) {
    Write-Host "Executable not found at dist\obscuro\obscuro.exe. Building it now..." -ForegroundColor Yellow
    if (Test-Path (Join-Path $appDir "build_exe.ps1")) {
        & powershell.exe -ExecutionPolicy Bypass -File (Join-Path $appDir "build_exe.ps1")
    } else {
        throw "build_exe.ps1 not found. Cannot build executable."
    }
}

# 3. Setup local launchers
Write-Host "Setting up local command launchers..." -ForegroundColor Cyan
$launcherContent = @"
@echo off
"$exePath" %*
exit /b %errorlevel%
"@

foreach ($name in @("obscuro.cmd", "obscuro-ominous.cmd", "oo.cmd", "datacollector.cmd", "dc.cmd")) {
    $target = Join-Path $appDir $name
    [System.IO.File]::WriteAllText($target, $launcherContent)
}
Write-Host "Created local command launchers in application directory." -ForegroundColor Green

# 4. Create local shortcut instead of Desktop
Write-Host "Creating local shortcut..." -ForegroundColor Cyan
$shortcutPath = Join-Path $appDir "Obscuro Ominous.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $appDir
$shortcut.Description = "Launch Obscuro Ominous"
$shortcut.Save()
Write-Host "Created local shortcut in application directory." -ForegroundColor Green

Write-Host "Installation complete!" -ForegroundColor Green
Write-Host "Launching Obscuro Ominous..." -ForegroundColor Cyan
Start-Process -FilePath $exePath -NoNewWindow
