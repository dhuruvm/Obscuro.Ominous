import time

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.status import Status

console = Console()

def start_chat(model_name, device="cpu"):
    from pipeline.model_manager import generate_text

    console.print(Panel(
        f"[bold magenta]Model Chat[/bold magenta]\n"
        f"Model: [bold cyan]{model_name}[/bold cyan]  |  Backend: [bold yellow]Ollama / {device.upper()}[/bold yellow]\n"
        "Type 'exit' or 'quit' to stop.",
        border_style="magenta",
    ))
    conversation = []

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]User[/bold green]")
            if user_input.lower() in ['exit', 'quit']:
                break
            if not user_input.strip():
                console.print("[dim]No message entered. Type a question or 'exit' to stop.[/dim]")
                continue

            conversation.append(f"User: {user_input}")
            prompt = (
                "You are a helpful local assistant. Answer the user's latest message directly. "
                "Use the conversation history for context and do not invent tool results.\n\n"
                + "\n".join(conversation[-12:])
                + "\nAssistant:"
            )
            started_at = time.perf_counter()
            console.print("[dim]Thinking... waiting for the first token[/dim]")
            response_stream = generate_text(
                model_name,
                prompt,
                stream=True,
                device=device,
                timeout=300,
                max_tokens=700,
            )
            if isinstance(response_stream, str):
                console.print(f"[bold red]Model error:[/bold red] {response_stream or 'Empty response'}")
                continue

            response_parts = []
            first_token_at = None
            with Status("[cyan]Thinking...[/cyan]", console=console, spinner="dots") as status:
                for chunk in response_stream:
                    if not chunk:
                        continue
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                        status.stop()
                        console.print("[bold blue]Model[/bold blue] [dim](streaming)[/dim]")
                    response_parts.append(chunk)
                    console.print(chunk, end="", markup=False, highlight=False)

            finished_at = time.perf_counter()
            response = "".join(response_parts).strip()
            console.print()
            if not response:
                console.print("[bold red]Model error:[/bold red] Empty response")
                continue
            conversation.append(f"Assistant: {response}")

            first_token_ms = ((first_token_at or finished_at) - started_at) * 1000
            total_seconds = max(finished_at - started_at, 0.001)
            word_count = len(response.split())
            approx_tokens = max(1, len(response) // 4)
            tokens_per_second = approx_tokens / total_seconds
            console.print(Panel(
                f"[dim]First token:[/dim] {first_token_ms:.0f} ms  "
                f"[dim]Total:[/dim] {total_seconds:.2f} s  "
                f"[dim]Words:[/dim] {word_count}  "
                f"[dim]Approx. speed:[/dim] {tokens_per_second:.1f} tok/s",
                border_style="dim",
                expand=False,
            ))
            
        except KeyboardInterrupt:
            break
        except Exception as error:
            console.print(f"\n[bold red]Chat error:[/bold red] {error}")
            
    console.print("\n[bold red]Chat ended.[/bold red]")
