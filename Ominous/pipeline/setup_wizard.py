import os
import json
import shutil
import urllib.request
import subprocess
import time
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from pipeline.model_manager import list_local_models, pull_model, generate_text

console = Console()

OLLAMA_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "ollama_config.json")

# ─────────────────────────────────────────────
# Config helpers
# ─────────────────────────────────────────────

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ─────────────────────────────────────────────
# Folder Browser (native Windows dialog via PowerShell)
# ─────────────────────────────────────────────


def open_folder_browser(description="Select Installation Folder", start_path=None):
    """
    Opens a native Windows folder browser using Python's built-in tkinter.
    Returns the selected path string, or None if cancelled.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
        
        # Build a root window but keep it hidden
        root = tk.Tk()
        root.withdraw()           # hide the empty root window
        root.attributes("-topmost", True)   # make dialog appear on top
        
        start = start_path or os.path.expandvars("%LOCALAPPDATA%")
        
        # Show the folder chooser
        chosen = filedialog.askdirectory(
            parent=root,
            title=description,
            initialdir=start,
            mustexist=False
        )
        root.destroy()
        return chosen if chosen else None
        
    except Exception as e:
        console.print(f"[red]Folder browser error: {e}[/red]")
        return None


# ─────────────────────────────────────────────
# Ollama Installation
# ─────────────────────────────────────────────

def find_ollama_exe(install_dir=None):
    """Return path to ollama.exe if found anywhere."""
    if shutil.which("ollama"):
        return shutil.which("ollama")
    if install_dir:
        candidate = os.path.join(install_dir, "ollama.exe")
        if os.path.exists(candidate):
            return candidate
    default = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
    if os.path.exists(default):
        return default
    return None

def check_and_install_ollama():
    """
    1. Checks if Ollama is already installed.
    2. If not, opens a native folder browser for the user to pick an install location.
    3. Downloads OllamaSetup.exe with progress and installs to the chosen folder.
    4. Verifies installation and saves config.
    """
    import sys
    config = load_config()
    saved_dir = config.get("install_path", "")

    # ── Already installed? ──────────────────────────────
    existing_exe = find_ollama_exe(saved_dir)
    if existing_exe:
        console.print(f"[green]✓ Ollama is already installed.[/green]  [dim]({existing_exe})[/dim]")
        return True

    # ── Not installed ───────────────────────────────────
    console.print(Panel(
        "[bold yellow]Ollama Not Found[/bold yellow]\n"
        "Ollama is required to run local AI models.\n\n"
        "You can either install Ollama now, or provide the path if it's already installed.",
        border_style="yellow"
    ))

    choice = Prompt.ask("Proceed to install? (y) / Provide path manually (m) / Cancel (n)", choices=["y", "m", "n"], default="y")
    if choice == "n":
        return False
    elif choice == "m":
        manual_path = Prompt.ask("Enter the full path to ollama.exe")
        if os.path.exists(manual_path) and manual_path.lower().endswith("ollama.exe"):
            config["exe_path"] = manual_path
            save_config(config)
            console.print(f"[bold green]✓ Ollama path saved:[/bold green] {manual_path}")
            return True
        else:
            console.print("[bold red]Invalid path or file does not exist.[/bold red]")
            return False

    # ── Step 1 · Choose install folder ─────────────────
    console.print("\n[bold cyan]Step 1/3 — Choose Install Folder[/bold cyan]")
    console.print("A folder browser window is opening. Select your install folder and click OK.\n")
    sys.stdout.flush()

    base_dir = open_folder_browser(
        description="Select where to install Ollama",
        start_path=os.path.expandvars("%LOCALAPPDATA%")
    )

    if not base_dir:
        console.print("[yellow]No folder selected → using default location.[/yellow]")
        base_dir = os.path.expandvars(r"%LOCALAPPDATA%\Programs")

    install_dir = os.path.join(base_dir, "Ollama")
    os.makedirs(install_dir, exist_ok=True)

    console.print(f"\n[green]✓ Install folder confirmed:[/green] [bold]{install_dir}[/bold]")
    sys.stdout.flush()

    # Save chosen dir right away
    config["install_path"] = install_dir
    save_config(config)

    # ── Step 2 · Download installer ────────────────────
    console.print("\n[bold cyan]Step 2/3 — Downloading Ollama Installer[/bold cyan]")
    console.print("[dim]This may take a minute depending on your connection speed...[/dim]")
    sys.stdout.flush()

    installer_path = os.path.join(install_dir, "OllamaSetup.exe")

    try:
        def _progress(block, block_size, total):
            done = min(block * block_size, total)
            if total > 0:
                pct = done * 100 / total
                mb_done = done / 1024 / 1024
                mb_total = total / 1024 / 1024
                print(f"\r  Downloading: {pct:5.1f}%  ({mb_done:.1f} / {mb_total:.1f} MB)  ", end="", flush=True)

        urllib.request.urlretrieve(OLLAMA_INSTALLER_URL, installer_path, _progress)
        print()
        console.print("[green]✓ Download complete![/green]")
        sys.stdout.flush()
    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red]")
        return False

    # ── Step 3 · Run installer ─────────────────────────
    console.print(f"\n[bold cyan]Step 3/3 — Running Installer[/bold cyan]")
    console.print(f"Installing Ollama to: [bold]{install_dir}[/bold]")
    console.print("[yellow]Please complete the installer window that appears...[/yellow]\n")
    sys.stdout.flush()

    try:
        subprocess.run([installer_path, f"/DIR={install_dir}"])
    except Exception as e:
        console.print(f"[red]Installer error: {e}[/red]")
        return False

    # ── Verify ─────────────────────────────────────────
    console.print("\n[cyan]Verifying installation...[/cyan]")
    sys.stdout.flush()
    time.sleep(4)

    exe = find_ollama_exe(install_dir)
    if exe:
        console.print(f"[bold green]✓ Ollama installed successfully![/bold green]  ([dim]{exe}[/dim])")
        config["exe_path"] = exe
        save_config(config)
        return True
    else:
        console.print("[bold yellow]Installation may still be in progress.[/bold yellow]")
        console.print("If the installer window is still open, please wait for it to finish.")
        console.print("Then re-launch the Data Collector tool.\n")
        return False


# ─────────────────────────────────────────────
# Model Setup
# ─────────────────────────────────────────────

RECOMMENDED_MODELS = [
    {"name": "qwen2.5:0.5b", "desc": "Qwen 2.5 0.5B      — Ultra lightweight (500M)"},
    {"name": "llama3.2:1b",  "desc": "Meta Llama 3.2 1B  — Fast & lightweight (1B)"},
    {"name": "llama3.1",     "desc": "Meta Llama 3.1 8B  — Best general-purpose"},
    {"name": "phi3",         "desc": "Microsoft Phi-3 Mini — Fast & lightweight"},
    {"name": "mistral",      "desc": "Mistral 7B          — High performance"},
    {"name": "gemma2",       "desc": "Google Gemma 2 9B   — Strong reasoning"},
    {"name": "deepseek-r1",  "desc": "DeepSeek-R1         — Advanced reasoning"},
]

def interactive_model_setup():
    """Shows a numbered model menu, downloads the model, and runs a diagnostic."""
    console.print(Panel("[bold cyan]AI Model Setup Wizard[/bold cyan]", border_style="cyan"))

    console.print("\n[bold]Available Models:[/bold]\n")
    for i, m in enumerate(RECOMMENDED_MODELS, 1):
        console.print(f"  [bold yellow]{i}.[/bold yellow] [bold]{m['name']}[/bold]  — [dim]{m['desc']}[/dim]")
    console.print(f"  [bold yellow]{len(RECOMMENDED_MODELS)+1}.[/bold yellow] [bold]Custom URL/Name[/bold]  — Enter any Ollama registry name or HuggingFace ID")
    console.print(f"  [bold yellow]{len(RECOMMENDED_MODELS)+2}.[/bold yellow] [bold]Custom by Parameter Size[/bold]  — Choose specific B or M size")
    console.print()

    all_choices = [str(i) for i in range(1, len(RECOMMENDED_MODELS) + 3)]
    choice = IntPrompt.ask("Select model number", choices=all_choices)

    if choice == len(RECOMMENDED_MODELS) + 1:
        model_name = Prompt.ask("Enter model name (e.g. gemma2:27b) or custom URL")
    elif choice == len(RECOMMENDED_MODELS) + 2:
        unit = Prompt.ask("Select parameter unit", choices=["M", "B"], default="B")
        val = Prompt.ask(f"Enter the number of {unit} (e.g. 500 for M, 1 for B)")
        family = Prompt.ask("Enter base model family (e.g. qwen2.5, llama3.2)", default="qwen2.5")
        
        if unit == "M":
            size_tag = f"{float(val)/1000:g}b"
        else:
            size_tag = f"{val}b"
            
        model_name = f"{family}:{size_tag}"
        console.print(f"[dim]Constructed model target: {model_name}[/dim]")
    else:
        model_name = RECOMMENDED_MODELS[choice - 1]["name"]

    # Download if not already local
    installed = list_local_models()
    if any(model_name in m for m in installed):
        console.print(f"[green]✓ '{model_name}' is already downloaded.[/green]")
    else:
        pull_model(model_name)

    # Diagnostic test
    console.print(f"\n[cyan]Running diagnostic test on '{model_name}'...[/cyan]")
    t0 = time.time()
    response = generate_text(model_name, "Reply with only: Hello, I am ready.")
    elapsed = time.time() - t0

    if "Error" in response or not response.strip():
        console.print(f"[bold red]Diagnostic failed![/bold red]\n{response}")
        return None

    console.print(f"[bold green]✓ Diagnostic passed![/bold green]  Response time: {elapsed:.2f}s")
    console.print(f"[dim]Model replied: {response.strip()[:120]}[/dim]\n")

    return model_name, elapsed


def run_setup():
    if not check_and_install_ollama():
        return None
    return interactive_model_setup()
