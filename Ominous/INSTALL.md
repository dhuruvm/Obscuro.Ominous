# Obscuro Ominous installation

## Windows desktop

1. Open PowerShell in this folder.
2. Run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Install-ObscuroOminous.ps1
```

The installer creates `venv`, installs all dependencies, adds the folder to the user PATH, and creates a desktop shortcut. Close and reopen terminals after installation so the updated PATH is loaded.

To launch directly, double-click `Run_ObscuroOminous.bat`. The window stays open after exit and displays the error code if startup fails. From a new terminal, run `obscuro`, `oo`, or `datacollector`.

## Docker

Build and start the interactive CLI:

```powershell
docker compose up --build
```

Or run a command directly:

```powershell
docker build -t obscuro-ominous .
docker run --rm -it -v "${PWD}\datasets:/app/datasets" obscuro-ominous datasets
```

Docker Desktop is required on Windows. The container keeps datasets on the host through the mounted `datasets` folder.
