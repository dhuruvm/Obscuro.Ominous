import re
import time
import json
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn,
    MofNCompleteColumn, TimeElapsedColumn
)
from rich.prompt import Prompt
from rich.table import Table
from pipeline.model_manager import generate_text
from pipeline.research_browser import research

console = Console()

# ─────────────────────────────────────────────
# Keyword Cleaning
# ─────────────────────────────────────────────

def _clean_keyword(line: str) -> str:
    """Strip numbering, quotes, asterisks, and extra whitespace from a keyword line."""
    # Remove leading number + dot/dash/paren: "1. ", "2) ", "- "
    line = re.sub(r"^\s*[\d]+[\.\)\-]\s*", "", line)
    # Remove markdown bold/italic markers
    line = re.sub(r"[*_`\"\']+", "", line)
    return line.strip()

def _parse_plan(plan_text: str, count: int) -> list[str]:
    """Parse AI plan response into a clean list of keywords."""
    keywords = []
    for line in plan_text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Only pick lines that look like list items
        if re.match(r"^\s*[\d\-\*\•]", line) or (len(keywords) < count and len(line) > 3):
            kw = _clean_keyword(line)
            if kw and len(kw) > 2:
                keywords.append(kw)
        if len(keywords) >= count:
            break
    # Fallback: use raw lines
    if not keywords:
        keywords = [_clean_keyword(l) for l in plan_text.splitlines() if l.strip()]
        keywords = [k for k in keywords if k][:count]
    return keywords[:count]

# ─────────────────────────────────────────────
# Main Autonomous Loop
# ─────────────────────────────────────────────

def run_autonomous_loop(model_name: str, avg_response_time: float,
                        output_file: str = "autonomous_data.jsonl"):
    console.print(Panel(
        f"[bold magenta]Advanced Autonomous AI Data Scientist[/bold magenta]\n"
        f"Model: [bold cyan]{model_name}[/bold cyan]  |  "
        f"Output: [bold]{output_file}[/bold]",
        border_style="magenta"
    ))

    # ── User Inputs ──────────────────────────────────────────────
    console.print()
    dataset_desc = Prompt.ask(
        "[bold yellow]Describe the dataset you want to create[/bold yellow]\n"
        "[dim](e.g. 'Medical research papers on virology')[/dim]"
    )
    parameters = Prompt.ask(
        "[bold yellow]Any specific parameters?[/bold yellow]\n"
        "[dim](e.g. 'Keep documents over 500 words, use academic tone')[/dim]"
    )
    iterations = int(Prompt.ask(
        "[bold yellow]How many scraping iterations?[/bold yellow]",
        default="3"
    ))

    # ── AI Planning Phase ────────────────────────────────────────
    console.print()
    console.print(Rule("[cyan]AI Planning Phase[/cyan]"))
    console.print(f"[cyan]Generating research plan for:[/cyan] [bold]{dataset_desc}[/bold]\n")

    plan_prompt = (
        f"I want to build a dataset about: {dataset_desc}.\n"
        f"Constraints: {parameters}.\n"
        f"Give me exactly {iterations} unique, specific search keywords to find "
        f"high-quality data for this dataset.\n"
        f"Format: a simple numbered list. Each item on its own line. "
        f"No extra explanation, no quotes, no markdown."
    )

    t0 = time.time()
    plan_response = generate_text(model_name, plan_prompt)
    plan_time = time.time() - t0

    keywords = _parse_plan(plan_response, iterations)

    # Pad if needed
    while len(keywords) < iterations:
        keywords.append(f"{dataset_desc} {len(keywords)+1}")

    # ── ETA Calculation ──────────────────────────────────────────
    est_scrape   = 3.0          # seconds per iteration (search + scrape)
    est_ai       = plan_time * 2.5   # AI cleaning ~ 2.5x plan time
    est_per_iter = est_scrape + est_ai
    est_total    = est_per_iter * iterations

    # ── Display Plan ─────────────────────────────────────────────
    plan_table = Table(show_header=True, header_style="bold green", expand=True)
    plan_table.add_column("#",     style="dim", width=4)
    plan_table.add_column("Search Keyword", style="bold white")
    for i, kw in enumerate(keywords, 1):
        plan_table.add_row(str(i), kw)

    console.print(Panel(plan_table, title="[bold green]Master Research Plan[/bold green]",
                        border_style="green"))
    console.print(f"[bold yellow]⏱  Estimated time to complete: "
                  f"{est_total:.0f} seconds (~{est_total/60:.1f} min)[/bold yellow]\n")

    proceed = Prompt.ask("Proceed with execution?", choices=["y", "n"], default="y")
    if proceed != "y":
        return

    # ── Research & Collect Loop ──────────────────────────────────
    console.print()
    console.print(Rule("[magenta]Autonomous Research Loop[/magenta]"))

    collected_docs = []
    failed_count   = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        expand=True,
    ) as progress:

        overall  = progress.add_task("[bold cyan]Overall Progress", total=iterations)
        browser  = progress.add_task("[cyan]🌐 Research Browser: Idle", total=None)
        ai_clean = progress.add_task("[magenta]🤖 AI Cleaner: Waiting", total=None)

        for i, keyword in enumerate(keywords):
            loop_start = time.time()

            # ── PHASE 1: Research ─────────────────────────────────
            progress.update(browser,
                description=f"[cyan]🌐 [{i+1}/{iterations}] Researching: {keyword[:55]}")
            progress.update(ai_clean,
                description=f"[dim]🤖 AI Cleaner: waiting for data...")

            raw_text, visited = research(keyword, progress=progress,
                                         browser_task=browser, min_chars=300)

            if not raw_text or len(raw_text) < 100:
                progress.update(browser,
                    description=f"[red]✗ No data found for '{keyword[:40]}'")
                failed_count += 1
                progress.advance(overall)
                continue

            progress.update(browser,
                description=f"[green]✓ Got {len(raw_text):,} chars  "
                            f"({len(visited)} URL{'s' if len(visited)!=1 else ''} visited)")

            # ── PHASE 2: AI Cleaning & Labeling ──────────────────
            progress.update(ai_clean,
                description=f"[magenta]🤖 Cleaning & labeling '{keyword[:40]}'...")

            chunk = raw_text[:2500]
            clean_prompt = (
                f"Clean and format the following text into a high-quality dataset document on '{keyword}'.\n"
                f"Remove noise, boilerplate, and duplicate text. Retain informative facts and clear structure.\n"
                f"Text:\n{chunk}\n\n"
                f"Cleaned Text:"
            )

            try:
                cleaned = generate_text(model_name, clean_prompt, timeout=90, max_tokens=600)
            except Exception as e:
                cleaned = f"Error: {e}"

            # If AI cleaner timed out, failed, or produced an empty response,
            # use our deterministic DataCleaner to preserve the scraped data!
            if not cleaned or "Error" in str(cleaned) or len(str(cleaned).strip()) < 50:
                from pipeline.cleaner import DataCleaner
                cleaner = DataCleaner(min_length=100)
                rule_cleaned = cleaner.clean(raw_text)
                if rule_cleaned and len(rule_cleaned) >= 100:
                    cleaned = rule_cleaned
                    progress.update(ai_clean,
                        description=f"[yellow]⚡ AI timeout, preserved via rule cleaner ({len(cleaned):,} chars)")
                else:
                    progress.update(ai_clean,
                        description=f"[red]✗ AI & rule cleaning failed for '{keyword[:40]}'")
                    failed_count += 1
                    progress.advance(overall)
                    continue

            # ── PHASE 3: Stage document (do NOT save yet) ─────────
            collected_docs.append({
                "keyword":   keyword,
                "topic":     dataset_desc,
                "sources":   visited,
                "raw_chars": len(raw_text),
                "text":      cleaned,
            })

            elapsed = time.time() - loop_start
            progress.update(ai_clean,
                description=f"[bold green]✓ Collected doc #{len(collected_docs)} "
                            f"({len(cleaned):,} chars, {elapsed:.1f}s)")
            progress.advance(overall)

    # ── Dataset Verification & Commit to Store ───────────────────
    if not collected_docs:
        console.print("\n[bold red]No documents collected. Dataset NOT saved.[/bold red]")
        return

    console.print()
    console.print(Rule("[bold green]Dataset Store Verification & Commit[/bold green]"))

    dataset_name = Prompt.ask(
        "\n[bold yellow]Enter a name for this dataset[/bold yellow]",
        default=dataset_desc[:40]
    )

    from pipeline.dataset_store import verify_and_commit
    summary = verify_and_commit(
        documents=collected_docs,
        dataset_name=dataset_name,
        topic=dataset_desc,
        model_name=model_name
    )

    # ── Final Summary ─────────────────────────────────────────────
    console.print()
    summary_table = Table(show_header=False, expand=False, box=None)
    summary_table.add_column("Key",   style="bold")
    summary_table.add_column("Value", style="cyan")
    summary_table.add_row("Collected",        str(len(collected_docs)))
    summary_table.add_row("Passed & Saved",   str(summary.get("saved", 0)))
    summary_table.add_row("Failed Rule Check",str(summary.get("failed_rule", 0)))
    summary_table.add_row("Failed AI Check",  str(summary.get("failed_ai", 0)))
    summary_table.add_row("Failed Scraping",  str(failed_count))

    console.print(Panel(
        summary_table,
        title="[bold green]✓ Autonomous Loop Complete[/bold green]",
        border_style="green"
    ))

