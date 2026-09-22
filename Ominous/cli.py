import argparse
import sys
import time

# Force UTF-8 encoding for Windows terminal to display rich spinners
sys.stdout.reconfigure(encoding='utf-8')

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.live import Live
from rich.table import Table

console = Console()

def parse_args():
    parser = argparse.ArgumentParser(description="Obscuro Ominous - Autonomous AI Data Pipeline & Training System")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Process Command
    process_parser = subparsers.add_parser("process", help="Re-tokenize a dataset from the store into .bin/.idx")
    process_parser.add_argument("--workers",    "-w", type=int, default=4,     help="Number of worker processes")
    process_parser.add_argument("--chunk-size", "-c", type=int, default=10000, help="Documents per chunk")
    
    # Train Command
    train_parser = subparsers.add_parser("train", help="Build a persistent model from a dataset")
    train_parser.add_argument("--dataset", "-d", type=str, required=True, help="Prefix of .bin and .idx files")
    train_parser.add_argument("--device", type=str, choices=['cpu', 'gpu', 'both'], default=None, help="Hardware device to use")
    train_parser.add_argument("--base-model", type=str, help="Ollama model used as the training base")
    train_parser.add_argument("--output-model", type=str, help="Name to save in the Model Store")
    
    # Chat Command
    chat_parser = subparsers.add_parser("chat", help="Interactive chat with the model")
    chat_parser.add_argument("--device", type=str, choices=['cpu', 'gpu', 'both'], default=None, help="Hardware device to use")
    chat_parser.add_argument("--model", type=str, help="Ollama model name from the Model Store")
    
    # Models Command
    models_parser = subparsers.add_parser("models", help="Manage local AI models via Ollama")
    models_parser.add_argument("--list", action="store_true", help="List available local models")
    models_parser.add_argument("--pull", type=str, help="Download a specific model (e.g. llama3.1)")
    models_parser.add_argument("--import-gguf", type=str, help="Import a local .gguf file into Ollama")
    models_parser.add_argument("--name", type=str, help="Ollama name for an imported GGUF model")

    # Datasets Command
    subparsers.add_parser("datasets", help="Browse and manage the Dataset Store")

    # Autonomous Command — fully interactive wizard, no pre-set args needed
    subparsers.add_parser("autonomous", help="Run AI Autonomous Data Collector (interactive wizard)")
    
    return parser.parse_args()

def generate_ui_table(workers_active, total_docs, junk_filtered):
    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Metric", style="dim", width=20)
    table.add_column("Value")
    
    table.add_row("Workers Active", str(workers_active))
    table.add_row("Documents Processed", str(total_docs))
    table.add_row("Junk Filtered", str(junk_filtered))
    table.add_row("Output Format", "Indexed Binary (.bin / .idx)")
    return table

def handle_process(args):
    from pipeline.dataset_store import pick_dataset_interactive, STORE_DIR
    import os

    console.print(Panel.fit("[bold green]Data Collector & Processor[/bold green]\nSelect a dataset from the store to (re)process into binary.", border_style="green"))

    ds = pick_dataset_interactive()
    if not ds:
        console.print("[red]No dataset selected or store is empty.[/red]")
        return

    jsonl_path  = os.path.join(STORE_DIR, ds["jsonl_file"])
    bin_prefix  = os.path.join(STORE_DIR, ds["bin_prefix"])

    from pipeline.collector import DataCollector
    from workers.job_manager import JobManager
    from io_module.binary_writer import BinaryWriter

    collector   = DataCollector(jsonl_path, chunk_size=args.chunk_size)
    job_manager = JobManager(args.workers)
    writer      = BinaryWriter(bin_prefix)

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )

    job_task = progress.add_task("Processing data chunks...", total=None)
    total_processed = 0
    total_junk = 0

    with Live(progress, console=console, refresh_per_second=4):
        try:
            for results, junk_count in job_manager.process_data(collector.iter_chunks()):
                for token_ids in results:
                    writer.write_document(token_ids)
                    total_processed += 1
                total_junk += junk_count
                progress.update(job_task, advance=1, description=f"Docs: {total_processed} | Junk: {total_junk}")
        except KeyboardInterrupt:
            pass
        finally:
            job_manager.close()
            writer.close()

    console.print("[bold green]Processing complete![/bold green]")
    console.print(generate_ui_table(args.workers, total_processed, total_junk))
    console.print(f"Binary saved: {bin_prefix}.bin  /  {bin_prefix}.idx")

def handle_train(args):
    from pipeline.training_loop import train_model
    from pipeline.dataset_store import pick_dataset_interactive, get_latest_binary_prefix, STORE_DIR
    from pipeline.model_store import pick_model_interactive
    import os

    device = getattr(args, 'device', None)
    if not device:
        device = pick_device_interactive("Training", "gpu")

    # Try to auto-use the dataset arg; if not set or missing, pick from store
    dataset_prefix = getattr(args, 'dataset', None)
    if not dataset_prefix or not os.path.exists(dataset_prefix + ".idx"):
        console.print(Panel.fit("[bold cyan]Select Dataset for Training[/bold cyan]", border_style="cyan"))
        ds = pick_dataset_interactive()
        if not ds:
            console.print("[red]No dataset available. Run the Autonomous AI Collector first.[/red]")
            return
        dataset_prefix = os.path.join(STORE_DIR, ds["bin_prefix"])

    base_model = getattr(args, 'base_model', None)
    if not base_model:
        model = pick_model_interactive()
        if not model or model.get("backend") != "ollama":
            console.print("[red]Select an Ollama model as the training base.[/red]")
            return
        base_model = model["name"]

    model_name = getattr(args, 'output_model', None) or f"obscuro-{os.path.basename(dataset_prefix)}"
    train_model(dataset_prefix, base_model, model_name, device)

def handle_chat(args):
    from pipeline.chat_interface import start_chat
    from pipeline.model_store import pick_model_interactive

    device = getattr(args, 'device', None)
    if not device:
        device = pick_device_interactive("Chat", "gpu")

    model_name = getattr(args, 'model', None)
    if not model_name:
        model = pick_model_interactive()
        if not model or model.get("backend") != "ollama":
            console.print("[red]Select an Ollama model from the Model Store.[/red]")
            return
        model_name = model["name"]
    start_chat(model_name, device)

def handle_models(args):
    from pipeline.model_manager import list_local_models, pull_model, import_gguf
    from pipeline.model_store import print_models_table
    if args.list:
        from pipeline.model_manager import sync_model_store
        sync_model_store()
        print_models_table()
    elif args.pull:
        pull_model(args.pull)
    elif getattr(args, 'import_gguf', None):
        import_gguf(args.import_gguf, getattr(args, 'name', None))
    else:
        console.print("[yellow]Please specify --list or --pull <model>[/yellow]")

def handle_autonomous(args):
    from pipeline.setup_wizard import run_setup
    from pipeline.autonomous_agent import run_autonomous_loop
    
    console.print(Panel.fit("[bold magenta]Autonomous AI Data Scientist[/bold magenta]\nInitializing setup wizard...", border_style="magenta"))
    
    result = run_setup()
    if result is None:
        console.print("[bold red]Setup failed. Please check Ollama installation and try again.[/bold red]")
        return
    
    model_name, avg_response_time = result
    out_file = getattr(args, 'output', 'autonomous_data.jsonl')
    run_autonomous_loop(model_name, avg_response_time, output_file=out_file)

def handle_datasets(args, pause=False):
    from pipeline.dataset_store import print_datasets_table
    print_datasets_table()
    if pause:
        try:
            input("\nPress Enter to return to menu...")
        except (KeyboardInterrupt, EOFError):
            pass

def pick_device_interactive(target_name="Chat", current_device="gpu") -> str:
    from pipeline.ui_menu import InteractiveMenu
    options = [
        ("GPU (High Performance)", "NVIDIA CUDA / GPU accelerated execution"),
        ("CPU (Standard)", "Standard multi-threaded CPU execution"),
        ("BOTH (Distributed Simulation)", "Heterogeneous CPU + GPU simulated execution"),
    ]
    initial = 0 if current_device == "gpu" else (1 if current_device == "cpu" else 2)
    idx = InteractiveMenu.select(
        options,
        title=f"Hardware Device for {target_name}",
        subtitle="Choose target execution hardware backend",
        footer="↑/↓ navigate • enter select • esc back",
        initial_index=initial
    )
    if idx == 0:
        return "gpu"
    elif idx == 1:
        return "cpu"
    elif idx == 2:
        return "both"
    return current_device

def configure_workers_interactive(current_workers=4, current_chunk=1000) -> tuple[int, int]:
    from pipeline.ui_menu import InteractiveMenu
    options = [
        ("4 Workers (Balanced)", "Standard quad-core worker pool (Recommended)"),
        ("2 Workers (Low Memory)", "Conservative pool for lower memory systems"),
        ("8 Workers (High Performance)", "High concurrency for multi-core CPUs"),
        ("16 Workers (Ultra Concurrency)", "Maximum throughput for workstation/server CPUs"),
    ]
    w_map = {0: 4, 1: 2, 2: 8, 3: 16}
    initial = 0
    for k, v in w_map.items():
        if v == current_workers:
            initial = k
            break
    idx = InteractiveMenu.select(
        options,
        title="Configure Worker Concurrency",
        subtitle="Set worker process allocation for tokenization",
        footer="↑/↓ navigate • enter select • esc back",
        initial_index=initial
    )
    if idx is not None:
        return w_map.get(idx, current_workers), current_chunk
    return current_workers, current_chunk

def handle_models_interactive():
    from pipeline.ui_menu import InteractiveMenu
    options = [
        ("Open Model Store", "Show Ollama models and imported GGUF files"),
        ("Download a model (pull)", "Pull a recommended or custom model (llama3.1, phi3, deepseek-r1)"),
        ("Import a GGUF model", "Register a local quantized .gguf file and import it into Ollama"),
    ]
    idx = InteractiveMenu.select(
        options,
        title="Manage Local AI Models",
        subtitle="Ollama model repository management",
        footer="↑/↓ navigate • enter select • esc back"
    )
    if idx == 0:
        from pipeline.model_store import print_models_table
        print_models_table()
        try:
            input("\nPress Enter to return to menu...")
        except (KeyboardInterrupt, EOFError):
            pass
    elif idx == 1:
        rec_models = [
            ("llama3.1", "Meta Llama 3.1 8B — Best general-purpose"),
            ("phi3", "Microsoft Phi-3 Mini — Fast & lightweight"),
            ("mistral", "Mistral 7B — High performance"),
            ("gemma2", "Google Gemma 2 9B — Strong reasoning"),
            ("deepseek-r1", "DeepSeek-R1 — Advanced reasoning"),
            ("Custom Model...", "Enter custom model tag or HuggingFace ID"),
        ]
        m_idx = InteractiveMenu.select(
            rec_models,
            title="Download Model",
            subtitle="Select a model to download into Ollama",
            footer="↑/↓ navigate • enter download • esc cancel"
        )
        if m_idx is not None:
            if m_idx == len(rec_models) - 1:
                try:
                    m_name = input("\nEnter model name to download: ").strip()
                except (KeyboardInterrupt, EOFError):
                    return
            else:
                m_name = rec_models[m_idx][0]
            if m_name:
                from pipeline.model_manager import pull_model
                pull_model(m_name)
                try:
                    input("\nPress Enter to return to menu...")
                except (KeyboardInterrupt, EOFError):
                    pass
    elif idx == 2:
        from pipeline.model_manager import import_gguf
        try:
            path = input("\nPath to .gguf file: ").strip().strip('"')
        except (KeyboardInterrupt, EOFError):
            return
        if path:
            import_gguf(path)
        try:
            input("\nPress Enter to return to menu...")
        except (KeyboardInterrupt, EOFError):
            pass

def interactive_menu():
    from pipeline.ui_menu import InteractiveMenu, MenuItem

    state = {
        "chat_device": "cpu",
        "train_device": "gpu",
        "workers": 4,
        "chunk_size": 1000,
        "last_index": 0
    }

    while True:
        def configure_chat():
            state["chat_device"] = pick_device_interactive("Chat", state["chat_device"])

        def configure_train():
            state["train_device"] = pick_device_interactive("Training", state["train_device"])

        def configure_process():
            state["workers"], state["chunk_size"] = configure_workers_interactive(state["workers"], state["chunk_size"])

        def configure_models():
            handle_models_interactive()

        items = [
            MenuItem(
                title="Chat with a model",
                description="Start an interactive chat with local AI models (CPU/GPU)",
                badge=f"({state['chat_device'].upper()})",
                key="chat",
                on_configure=configure_chat
            ),
            MenuItem(
                title="Autonomous AI Data Scientist",
                description="Autonomous web research, extraction, cleaning & labeling",
                key="autonomous"
            ),
            MenuItem(
                title="Dataset Store",
                description="Browse, inspect, and verify binary datasets",
                key="datasets"
            ),
            MenuItem(
                title="Process & Tokenize Data",
                description="Re-tokenize raw datasets into high-performance binary (.bin / .idx)",
                badge=f"({state['workers']} workers)",
                key="process",
                on_configure=configure_process
            ),
            MenuItem(
                title="Train / Build Model",
                description="Build a persistent Ollama model from a dataset and base model",
                badge=f"({state['train_device'].upper()})",
                key="train",
                on_configure=configure_train
            ),
            MenuItem(
                title="Manage Local Models",
                description="List installed Ollama models or pull new ones",
                key="models",
                on_configure=configure_models
            ),
            MenuItem(
                title="Exit",
                description="Quit Obscuro Ominous",
                key="exit"
            )
        ]

        menu = InteractiveMenu(
            items=items,
            title="Obscuro Ominous 2.0.0",
            subtitle="",
            footer="↑/↓ navigate • enter launch • -> configure • esc quit",
            initial_index=state["last_index"],
            clear_screen=True
        )

        selected_idx, action = menu.run()

        if action == 'quit' or selected_idx is None:
            console.print("\n[green]Goodbye![/green]")
            break

        state["last_index"] = selected_idx
        selected_item = items[selected_idx]

        if action == 'configure':
            if selected_item.on_configure:
                selected_item.on_configure()
            continue

        # action == 'launch'
        key = selected_item.key

        if key == "chat":
            class DummyChatArgs:
                device = state["chat_device"]
            handle_chat(DummyChatArgs())
            try:
                input("\nPress Enter to return to menu...")
            except (KeyboardInterrupt, EOFError):
                pass

        elif key == "autonomous":
            class DummyAutoArgs:
                output = "autonomous_data.jsonl"
            handle_autonomous(DummyAutoArgs())
            try:
                input("\nPress Enter to return to menu...")
            except (KeyboardInterrupt, EOFError):
                pass

        elif key == "datasets":
            handle_datasets(None, pause=True)

        elif key == "process":
            class DummyProcessArgs:
                workers = state["workers"]
                chunk_size = state["chunk_size"]
            handle_process(DummyProcessArgs())
            try:
                input("\nPress Enter to return to menu...")
            except (KeyboardInterrupt, EOFError):
                pass

        elif key == "train":
            class DummyTrainArgs:
                device = None
                dataset = None
            handle_train(DummyTrainArgs())
            try:
                input("\nPress Enter to return to menu...")
            except (KeyboardInterrupt, EOFError):
                pass

        elif key == "models":
            handle_models_interactive()

        elif key == "exit":
            console.print("\n[green]Goodbye![/green]")
            break

def main():
    if len(sys.argv) == 1:
        interactive_menu()
        return

    args = parse_args()
    if args.command == 'process':
        handle_process(args)
    elif args.command == 'train':
        handle_train(args)
    elif args.command == 'chat':
        handle_chat(args)
    elif args.command == 'models':
        handle_models(args)
    elif args.command == 'datasets':
        handle_datasets(args)
    elif args.command == 'autonomous':
        handle_autonomous(args)

if __name__ == "__main__":
    main()

