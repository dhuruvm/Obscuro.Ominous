"""Persistent model catalog for chat, Ollama models, and local GGUF files."""

import json
import os
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL_DIR = os.path.join(ROOT_DIR, "models")
REGISTRY = os.path.join(MODEL_DIR, "registry.json")
os.makedirs(MODEL_DIR, exist_ok=True)


def _load() -> list[dict]:
    if not os.path.exists(REGISTRY):
        return []
    try:
        with open(REGISTRY, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []


def _save(records: list[dict]) -> None:
    with open(REGISTRY, "w", encoding="utf-8") as handle:
        json.dump(records, handle, indent=2, ensure_ascii=False)


def _upsert(record: dict) -> dict:
    records = _load()
    key = (record.get("backend"), record.get("name"))
    records = [item for item in records if (item.get("backend"), item.get("name")) != key]
    records.append(record)
    _save(sorted(records, key=lambda item: item.get("name", "").lower()))
    return record


def register_ollama_model(name: str, details: dict | None = None) -> dict:
    details = details or {}
    return _upsert({
        "name": name,
        "backend": "ollama",
        "format": "ollama",
        "source": "Ollama local model store",
        "size": details.get("size", 0),
        "updated_at": details.get("modified_at", time.strftime("%Y-%m-%dT%H:%M:%S")),
    })


def register_gguf(path: str) -> dict:
    absolute_path = os.path.abspath(path)
    if not os.path.isfile(absolute_path) or not absolute_path.lower().endswith(".gguf"):
        raise ValueError("A readable .gguf file is required.")
    return _upsert({
        "name": os.path.basename(absolute_path),
        "backend": "gguf",
        "format": "gguf",
        "source": absolute_path,
        "size": os.path.getsize(absolute_path),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })


def list_models() -> list[dict]:
    return _load()


def print_models_table() -> list[dict]:
    records = list_models()
    if not records:
        console.print(Panel(
            "[dim]No models in the store yet. Pull an Ollama model or import a .gguf file.[/dim]",
            title="[bold cyan]Model Store[/bold cyan]",
            border_style="cyan",
        ))
        return []

    table = Table(title="[bold cyan]Model Store[/bold cyan]", header_style="bold magenta")
    table.add_column("Name", style="bold white")
    table.add_column("Backend", style="cyan")
    table.add_column("Format", style="green")
    table.add_column("Source", style="dim")
    for record in records:
        source = record.get("source", "")
        if len(source) > 48:
            source = "..." + source[-45:]
        table.add_row(record["name"], record["backend"], record["format"], source)
    console.print(table)
    return records


def pick_model_interactive() -> dict | None:
    from pipeline.model_manager import sync_model_store

    sync_model_store()
    records = print_models_table()
    if not records:
        return None

    from pipeline.ui_menu import InteractiveMenu
    options = [
        (record["name"], f"{record['backend']} • {record['format']} • {record.get('source', '')[:42]}")
        for record in records
    ]
    choice = InteractiveMenu.select(
        options,
        title="Select Model",
        subtitle="Choose a model from the Model Store",
        footer="↑/↓ navigate • enter select • esc cancel",
    )
    return records[choice] if choice is not None and 0 <= choice < len(records) else None
