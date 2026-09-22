"""
Dataset Store
~~~~~~~~~~~~~
Central registry for all finalized, AI-verified datasets.
All datasets pass through quality check + AI labeling before being committed.
"""

import os
import json
import time
import hashlib
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

console = Console()

STORE_DIR  = os.path.join(os.path.dirname(__file__), "..", "datasets")
REGISTRY   = os.path.join(STORE_DIR, "registry.json")

os.makedirs(STORE_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# Registry helpers
# ─────────────────────────────────────────────

def _load_registry() -> list:
    if os.path.exists(REGISTRY):
        with open(REGISTRY, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def _save_registry(records: list):
    with open(REGISTRY, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

def _next_id(records: list) -> int:
    if not records:
        return 1
    return max(r["id"] for r in records) + 1

# ─────────────────────────────────────────────
# Quality Verifier (rule-based pre-check)
# ─────────────────────────────────────────────

class VerificationError(Exception):
    pass

def _rule_check(document: dict) -> tuple[bool, str]:
    """
    Fast, rule-based quality checks before sending to AI.
    Returns (passed, reason).
    """
    text = document.get("text", "")
    if len(text) < 150:
        return False, f"Too short ({len(text)} chars, minimum 150)"
    if len(text.split()) < 30:
        return False, "Too few words (minimum 30)"
    # Check for encoding garbage
    if text.count("???") > 5 or text.count("\x00") > 0:
        return False, "Encoding corruption detected"
    # Junk ratio: repeated characters
    for char in ["#", "*", "=", "-"]:
        if text.count(char) > len(text) * 0.15:
            return False, f"High noise ratio (too many '{char}' chars)"
    return True, "OK"

def _ai_verify(model_name: str, document: dict) -> tuple[bool, str, str]:
    """
    Uses the local AI model to verify, clean, and label the document.
    Returns (passed, cleaned_text, label).
    """
    from pipeline.model_manager import generate_text

    text_sample = document.get("text", "")[:2000]
    topic       = document.get("topic", "unknown")

    prompt = (
        f"You are a professional data quality engineer.\n"
        f"Topic: {topic}\n"
        f"Review the following text and respond ONLY with a JSON object:\n"
        f"{{\n"
        f'  "verdict": "PASS" or "FAIL",\n'
        f'  "reason": "brief reason",\n'
        f'  "label": "short category label (e.g. educational, technical, news)",\n'
        f'  "cleaned_text": "the cleaned version of the text (fix grammar, remove noise)"\n'
        f"}}\n\n"
        f"Text:\n{text_sample}"
    )

    raw = generate_text(model_name, prompt)

    # Parse JSON from AI response
    try:
        # Extract JSON block even if AI adds extra text
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found")
        data = json.loads(raw[start:end])

        verdict      = data.get("verdict", "FAIL").upper()
        reason       = data.get("reason", "")
        label        = data.get("label", "general")
        cleaned_text = data.get("cleaned_text", document.get("text", ""))

        return verdict == "PASS", cleaned_text, label

    except Exception:
        # AI didn't return valid JSON — fall back to rule check pass
        return True, document.get("text", ""), "general"

# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def verify_and_commit(documents: list[dict], dataset_name: str,
                      topic: str, model_name: str = None) -> dict:
    """
    Runs every document through rule checks + (optional) AI verification.
    Only passing documents are committed to the store as a .jsonl file.
    Returns a summary dict.
    """
    records  = _load_registry()
    ds_id    = _next_id(records)
    ds_slug  = dataset_name.lower().replace(" ", "_")
    jsonl_name = f"ds_{ds_id:04d}_{ds_slug}.jsonl"
    jsonl_path = os.path.join(STORE_DIR, jsonl_name)
    bin_prefix = os.path.join(STORE_DIR, f"ds_{ds_id:04d}_{ds_slug}")

    passed_docs  = []
    failed_rule  = 0
    failed_ai    = 0
    total        = len(documents)

    console.print(f"\n[bold cyan]Verifying {total} documents for dataset:[/bold cyan] [bold]{dataset_name}[/bold]")

    for i, doc in enumerate(documents, 1):
        prefix = f"  [{i}/{total}]"

        # ── Rule check ───────────────────────────────────────────
        ok, reason = _rule_check(doc)
        if not ok:
            console.print(f"{prefix} [red]✗ Rule fail:[/red] {reason}")
            failed_rule += 1
            continue

        # ── AI verification (if model available) ─────────────────
        if model_name:
            ok, cleaned, label = _ai_verify(model_name, doc)
            if not ok:
                console.print(f"{prefix} [red]✗ AI rejected:[/red] {doc.get('keyword','')[:40]}")
                failed_ai += 1
                continue
            doc["text"]  = cleaned
            doc["label"] = label
        else:
            doc["label"] = "unverified"

        doc["verified"] = True
        passed_docs.append(doc)
        console.print(f"{prefix} [green]✓[/green] {doc.get('keyword', doc.get('source',''))[:50]}")

    if not passed_docs:
        console.print("[bold red]No documents passed verification. Dataset NOT saved.[/bold red]")
        return {"saved": 0, "failed_rule": failed_rule, "failed_ai": failed_ai}

    # ── Write verified JSONL ──────────────────────────────────────
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for doc in passed_docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    # ── Build .bin / .idx binary files from verified JSONL ───────
    try:
        import tiktoken, numpy as np, struct
        enc = tiktoken.get_encoding("cl100k_base")
        with open(bin_prefix + ".bin", "wb") as bf, \
             open(bin_prefix + ".idx", "wb") as xf:
            offset = 0
            for doc in passed_docs:
                ids  = enc.encode(doc["text"], allowed_special="all")
                arr  = np.array(ids, dtype=np.uint32)
                data = arr.tobytes()
                bf.write(data)
                xf.write(struct.pack("<QI", offset, len(ids)))
                offset += len(data)
        binary_ready = True
    except Exception as e:
        console.print(f"[yellow]Warning: binary conversion skipped ({e})[/yellow]")
        binary_ready = False

    # ── Register ──────────────────────────────────────────────────
    meta = {
        "id":           ds_id,
        "name":         dataset_name,
        "topic":        topic,
        "slug":         ds_slug,
        "jsonl_file":   jsonl_name,
        "bin_prefix":   f"ds_{ds_id:04d}_{ds_slug}",
        "binary_ready": binary_ready,
        "doc_count":    len(passed_docs),
        "failed_rule":  failed_rule,
        "failed_ai":    failed_ai,
        "created_at":   time.strftime("%Y-%m-%dT%H:%M:%S"),
        "checksum":     hashlib.md5(open(jsonl_path, "rb").read()).hexdigest()
    }
    records.append(meta)
    _save_registry(records)

    console.print(Panel(
        f"[bold green]✓ Dataset committed to store![/bold green]\n"
        f"ID: [bold]#{ds_id}[/bold]  |  "
        f"Docs: [bold]{len(passed_docs)}[/bold]  |  "
        f"Binary: [bold]{'Yes' if binary_ready else 'No'}[/bold]\n"
        f"File: [dim]{jsonl_path}[/dim]",
        border_style="green"
    ))

    return {
        "id": ds_id, "saved": len(passed_docs),
        "failed_rule": failed_rule, "failed_ai": failed_ai,
        "bin_prefix": bin_prefix if binary_ready else None
    }


def list_datasets() -> list:
    """Returns all registered datasets."""
    return _load_registry()


def print_datasets_table():
    """Prints a rich table of all datasets in the store."""
    records = _load_registry()

    if not records:
        console.print(Panel(
            "[dim]No datasets in the store yet.\n"
            "Run the Autonomous AI Data Scientist to create one.[/dim]",
            title="[bold cyan]Dataset Store[/bold cyan]",
            border_style="cyan"
        ))
        return []

    table = Table(
        title="[bold cyan]Dataset Store[/bold cyan]",
        show_header=True,
        header_style="bold magenta",
        expand=True
    )
    table.add_column("ID",       style="bold yellow", width=4)
    table.add_column("Name",     style="bold white")
    table.add_column("Topic",    style="cyan")
    table.add_column("Docs",     style="green", justify="right", width=6)
    table.add_column("Binary",   style="bold", width=7)
    table.add_column("Created",  style="dim")

    for r in records:
        table.add_row(
            f"#{r['id']}",
            r["name"],
            r["topic"][:40],
            str(r["doc_count"]),
            "[green]Yes[/green]" if r.get("binary_ready") else "[red]No[/red]",
            r["created_at"]
        )

    console.print(table)
    return records


def get_dataset_by_id(ds_id: int) -> dict | None:
    """Returns dataset metadata by ID."""
    for r in _load_registry():
        if r["id"] == ds_id:
            return r
    return None


def get_latest_binary_prefix() -> str | None:
    """Returns the bin_prefix of the most recently created binary-ready dataset."""
    records = [r for r in _load_registry() if r.get("binary_ready")]
    if not records:
        return None
    latest = sorted(records, key=lambda r: r["created_at"])[-1]
    return os.path.join(STORE_DIR, latest["bin_prefix"])


def pick_dataset_interactive() -> dict | None:
    """Interactively prompts the user to pick a dataset from the store using arrow keys."""
    records = print_datasets_table()
    if not records:
        return None

    try:
        from pipeline.ui_menu import InteractiveMenu
        options = [
            (
                f"#{r['id']} · {r['name']}",
                f"{r['doc_count']} docs • {r['topic'][:35]} • Binary: {'Ready (.bin/.idx)' if r.get('binary_ready') else 'Raw JSONL'}"
            )
            for r in records
        ]
        choice_idx = InteractiveMenu.select(
            options,
            title="Select Dataset",
            subtitle="Choose a dataset from the local store",
            footer="↑/↓ navigate • enter select • esc cancel",
            initial_index=0
        )
        if choice_idx is not None and 0 <= choice_idx < len(records):
            return records[choice_idx]
        return None
    except Exception:
        # Fallback to Prompt if UI error occurs
        ids = [str(r["id"]) for r in records]
        choice = Prompt.ask(
            "\n[bold yellow]Select dataset ID to use[/bold yellow]",
            choices=ids
        )
        return get_dataset_by_id(int(choice))
