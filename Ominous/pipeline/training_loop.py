import time
import struct
import json
import os
import numpy as np
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table

console = Console()


def train_model(prefix, base_model, model_name, device="gpu"):
    """Build a real Ollama model using dataset context and save it to Model Store."""
    from pipeline.model_manager import create_ollama_model
    from pipeline.dataset_store import list_datasets, STORE_DIR

    dataset_name = os.path.basename(prefix)
    metadata = next(
        (record for record in list_datasets() if record.get("bin_prefix") == dataset_name),
        None,
    )
    if not metadata:
        console.print(f"[bold red]Dataset metadata not found for {dataset_name}.[/bold red]")
        return False

    jsonl_path = os.path.join(STORE_DIR, metadata["jsonl_file"])
    excerpts = []
    try:
        with open(jsonl_path, "r", encoding="utf-8") as handle:
            for line in handle:
                document = json.loads(line)
                text = document.get("text", "").strip()
                if text:
                    excerpts.append(text[:1200])
                if len(excerpts) >= 12:
                    break
    except (OSError, json.JSONDecodeError) as error:
        console.print(f"[bold red]Could not read dataset context: {error}[/bold red]")
        return False

    if not excerpts:
        console.print("[bold red]The selected dataset contains no usable text.[/bold red]")
        return False

    context = "\n\n---\n\n".join(excerpts)
    system_prompt = (
        f"You are {model_name}, a local model built from the '{metadata['name']}' dataset. "
        "Answer using the subject matter and style represented below. Be accurate, concise, "
        "and say when the dataset does not contain enough information.\n\n"
        f"Training context:\n{context}"
    )
    console.print(Panel(
        f"[bold cyan]Building Model[/bold cyan]\n"
        f"Base: [bold]{base_model}[/bold]  |  Device: [bold yellow]{device.upper()}[/bold yellow]\n"
        "This creates a persistent Ollama model from the selected dataset context.",
        border_style="cyan",
    ))
    return create_ollama_model(model_name, base_model, system_prompt)

def simulate_training(prefix, device, epochs=3):
    console.print(Panel(f"[bold cyan]Industrial Training Simulation[/bold cyan]\nDevice: [bold yellow]{device.upper()}[/bold yellow] | Dataset: {prefix}.bin", border_style="cyan"))
    
    # Try to verify the dataset exists
    idx_path = f"{prefix}.idx"
    try:
        with open(idx_path, 'rb') as f:
            f.seek(0, 2)
            file_size = f.tell()
            total_docs = file_size // 12
    except FileNotFoundError:
        console.print(f"[bold red]Error: Dataset {prefix}.idx not found![/bold red]")
        return
        
    console.print(f"Loaded [bold green]{total_docs}[/bold green] documents from dataset.")
    
    # Adjust speed based on device
    speed_multiplier = 1.0 if device == 'cpu' else 5.0
    if device == 'both':
        speed_multiplier = 6.0
        
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("Loss: {task.fields[loss]:.4f}"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        
        for epoch in range(epochs):
            task = progress.add_task(f"[cyan]Epoch {epoch+1}/{epochs}...", total=total_docs, loss=5.0)
            
            current_loss = 5.0 - (epoch * 1.2)
            
            for i in range(total_docs):
                # Simulate processing time per batch
                if i % 100 == 0:
                    time.sleep(0.05 / speed_multiplier)
                    
                    # Add some noise to the loss
                    step_loss = current_loss + (np.random.random() * 0.2 - 0.1)
                    step_loss = max(0.01, step_loss - (i / total_docs))
                    
                    progress.update(task, advance=100, loss=step_loss)
                    
            progress.update(task, completed=total_docs)
            console.print(f"[bold green]Epoch {epoch+1} Complete![/bold green] Final Loss: {step_loss:.4f}")
            
    console.print(Panel("[bold magenta]Training Finished Successfully![/bold magenta]", border_style="magenta"))
