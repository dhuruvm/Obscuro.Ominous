import time
import json
import requests
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, TextColumn,
    DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
)
from rich.table import Table
from rich.live import Live
from rich.text import Text

console = Console()

OLLAMA_URL = "http://localhost:11434/api"


def ollama_executable():
    import os
    import shutil

    found = shutil.which("ollama")
    if found:
        return found
    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Ollama\ollama.exe"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None

def is_ollama_running():
    try:
        r = requests.get("http://localhost:11434/", timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False

def ensure_ollama_running():
    """Check if Ollama is running; if not, try to start it."""
    if is_ollama_running():
        return True
    import subprocess
    exe = ollama_executable()
    if exe:
        subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        return is_ollama_running()
    return False

def list_local_models():
    """Returns a list of locally installed Ollama model names."""
    if not ensure_ollama_running():
        console.print("[bold red]✗ Ollama is not running.[/bold red]")
        return []
    try:
        r = requests.get(f"{OLLAMA_URL}/tags", timeout=5)
        if r.status_code == 200:
            models = r.json().get("models", [])
            return [m["name"] for m in models]
    except Exception as e:
        console.print(f"[red]Error fetching models: {e}[/red]")
    return []


def sync_model_store():
    """Mirror Ollama's local models into the application's Model Store."""
    from pipeline.model_store import register_ollama_model

    if not ensure_ollama_running():
        return []
    try:
        response = requests.get(f"{OLLAMA_URL}/tags", timeout=5)
        response.raise_for_status()
        models = response.json().get("models", [])
        for model in models:
            register_ollama_model(model.get("name", ""), model)
        return models
    except (requests.RequestException, ValueError) as error:
        console.print(f"[red]Error syncing Model Store: {error}[/red]")
        return []


def create_ollama_model(model_name, base_model, system_prompt):
    """Create a persistent Ollama model through the local API."""
    from pipeline.model_store import register_ollama_model

    if not ensure_ollama_running():
        console.print("[bold red]Ollama is not running.[/bold red]")
        return False

    payload = {
        "model": model_name,
        "from": base_model,
        "system": system_prompt,
        "stream": False,
    }
    try:
        response = requests.post(f"{OLLAMA_URL}/create", json=payload, timeout=None)
        if response.status_code != 200:
            console.print(f"[red]Model build failed:[/red] {response.text.strip()}")
            return False
        register_ollama_model(model_name, {"source": f"Built from {base_model}"})
        console.print(f"[bold green]Model saved to Model Store:[/bold green] {model_name}")
        return True
    except requests.RequestException as error:
        console.print(f"[red]Model build failed:[/red] {error}")
        return False


def import_gguf(path, model_name=None):
    """Import a GGUF file into Ollama so it can produce real chat responses."""
    import os
    from pipeline.model_store import register_gguf

    record = register_gguf(path)
    name = model_name or os.path.splitext(record["name"])[0].lower().replace(" ", "-")
    if not ensure_ollama_running():
        console.print("[bold red]Ollama is not running.[/bold red]")
        return None
    if create_ollama_model(name, record["source"], "You are a helpful assistant."):
        return name
    return None

def pull_model(model_name):
    """
    Pulls a model from the Ollama registry with a rich multi-layer progress display.
    Tracks each individual layer download separately.
    """
    if not ensure_ollama_running():
        console.print("[bold red]✗ Ollama is not running.[/bold red]")
        return False

    console.print(Panel(
        f"[bold cyan]Pulling model:[/bold cyan] [bold white]{model_name}[/bold white]\n"
        "[dim]Layers will be downloaded in parallel. Large models may take several minutes.[/dim]",
        border_style="cyan", expand=False
    ))

    # layer_id -> {"status", "completed", "total"}
    layers = {}
    overall_status = ""

    try:
        response = requests.post(
            f"{OLLAMA_URL}/pull",
            json={"name": model_name},
            stream=True,
            timeout=None
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description:<40}"),
            BarColumn(bar_width=30),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
            transient=False,
        ) as progress:

            task_map = {}   # layer_id -> task_id
            status_task = progress.add_task("[cyan]Initializing...", total=None)

            for raw_line in response.iter_lines():
                if not raw_line:
                    continue
                try:
                    data = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                status  = data.get("status", "")
                digest  = data.get("digest", "")
                total   = data.get("total", 0)
                completed = data.get("completed", 0)

                # Non-layer status lines (manifest, verifying, writing, success)
                if not digest:
                    overall_status = status
                    progress.update(status_task, description=f"[cyan]{status[:60]}")
                    continue

                # Short layer ID for display
                short_id = digest[-12:] if len(digest) > 12 else digest

                if digest not in task_map:
                    # New layer → create a new progress task
                    tid = progress.add_task(
                        f"[yellow]Layer {short_id}",
                        total=total if total > 0 else None
                    )
                    task_map[digest] = tid
                    layers[digest] = {"completed": 0, "total": total}

                tid = task_map[digest]

                if "pull" in status or "downloading" in status.lower():
                    progress.update(tid,
                        completed=completed,
                        total=total if total > 0 else None,
                        description=f"[yellow]↓ {short_id}"
                    )
                elif status == "verifying sha256 digest":
                    progress.update(tid,
                        completed=total or completed,
                        description=f"[cyan]✔ verifying {short_id}"
                    )
                elif status == "already exists":
                    progress.update(tid,
                        completed=total or 1,
                        total=total or 1,
                        description=f"[green]✓ cached   {short_id}"
                    )
                else:
                    progress.update(tid, description=f"[dim]{status[:30]} {short_id}")

            # Mark all as done
            progress.update(status_task, description="[bold green]✓ Complete!", completed=1, total=1)

    except requests.RequestException as e:
        console.print(f"\n[red]Network error: {e}[/red]")
        return False
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        return False

    console.print(Panel(
        f"[bold green]✓ Model '{model_name}' downloaded and saved locally![/bold green]",
        border_style="green", expand=False
    ))
    return True


def generate_text(model_name, prompt, stream=False, timeout=180, max_tokens=None, device=None):
    """
    Generates text from the local model.
    If stream=True, yields chunks as they arrive.
    """
    if not ensure_ollama_running():
        return "Error: Ollama is not running."
    try:
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": stream
        }
        if max_tokens:
            payload["options"] = {"num_predict": max_tokens}
        if device == "cpu":
            payload.setdefault("options", {})["num_gpu"] = 0
        elif device == "gpu":
            payload.setdefault("options", {})["num_gpu"] = -1

        response = requests.post(
            f"{OLLAMA_URL}/generate",
            json=payload,
            stream=stream,
            timeout=timeout
        )
        if response.status_code == 200:
            if stream:
                # Return a generator of text chunks
                def _gen():
                    for line in response.iter_lines():
                        if line:
                            try:
                                chunk = json.loads(line)
                                yield chunk.get("response", "")
                                if chunk.get("done"):
                                    break
                            except json.JSONDecodeError:
                                pass
                return _gen()
            return response.json().get("response", "")
        else:
            return f"Error: {response.status_code} - {response.text}"
    except requests.exceptions.Timeout:
        return "Error: Model response timed out."
    except Exception as e:
        return f"Error connecting to Ollama: {e}"
