"""
Research Browser
~~~~~~~~~~~~~~~~
A dedicated multi-source web scraper powering the Autonomous AI Data Scientist.
Supports: DuckDuckGo search -> live page scraping, Wikipedia API, and direct URLs.
Shows a live 'Research Browser' panel in the terminal.
"""

import re
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ─────────────────────────────────────────────
# URL Discovery via DuckDuckGo
# ─────────────────────────────────────────────

def search_duckduckgo(query: str, max_results: int = 5) -> list[str]:
    """Search DuckDuckGo HTML and return a list of result URLs."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        urls = []
        for a in soup.select("a.result__a"):
            href = a.get("href", "")
            # Handle DuckDuckGo redirect wrapper
            if not href:
                continue
            if href.startswith("/l/?"):
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                href = parsed.get("uddg", [""])[0]
            if href.startswith("http") and "duckduckgo" not in href:
                urls.append(href)
            if len(urls) >= max_results:
                break

        # Fallback: grab any external links if above fails
        if not urls:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("http") and "duckduckgo" not in href:
                    urls.append(href)
                if len(urls) >= max_results:
                    break

        return urls

    except Exception as e:
        console.print(f"[red]DuckDuckGo search error: {e}[/red]")
        return []


# ─────────────────────────────────────────────
# Wikipedia API (fast, reliable for factual data)
# ─────────────────────────────────────────────

def fetch_wikipedia(query: str) -> tuple[str, str]:
    """Returns (page_url, text_content) for best Wikipedia match."""
    try:
        search_url = (
            "https://en.wikipedia.org/w/api.php"
            f"?action=query&list=search&srsearch={urllib.parse.quote(query)}"
            "&utf8=&format=json&srlimit=1"
        )
        resp = requests.get(search_url, headers=BROWSER_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("query", {}).get("search", [])
        if not results:
            return "", ""

        page_id = results[0]["pageid"]
        page_url = f"https://en.wikipedia.org/?curid={page_id}"
        extract_url = (
            "https://en.wikipedia.org/w/api.php"
            f"?action=query&prop=extracts&pageids={page_id}"
            "&format=json&explaintext=1&exsectionformat=plain"
        )
        resp2 = requests.get(extract_url, headers=BROWSER_HEADERS, timeout=10)
        resp2.raise_for_status()
        pages = resp2.json().get("query", {}).get("pages", {})
        text = pages.get(str(page_id), {}).get("extract", "")
        return page_url, text

    except Exception as e:
        return "", ""

# ─────────────────────────────────────────────
# Generic Page Scraper
# ─────────────────────────────────────────────

def scrape_page(url: str) -> str:
    """Fetches a URL and returns cleaned plain text."""
    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=12, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        # Remove noise tags
        for tag in soup(["script", "style", "nav", "footer", "header",
                         "aside", "form", "noscript", "iframe", "svg"]):
            tag.decompose()

        # Extract paragraphs
        paragraphs = [p.get_text(separator=" ").strip() for p in soup.find_all("p")]
        text = " ".join(p for p in paragraphs if len(p) > 60)

        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    except Exception as e:
        return ""

# ─────────────────────────────────────────────
# Research Session (orchestrates all sources)
# ─────────────────────────────────────────────

def research(keyword: str, progress=None, browser_task=None, min_chars: int = 300) -> tuple[str, list[str]]:
    """
    Researches a keyword using multiple sources in order of quality.
    Returns (best_text, list_of_urls_visited).
    Updates progress task with current URL being browsed.
    """
    visited_urls = []
    best_text = ""

    def _update(msg):
        if progress and browser_task is not None:
            progress.update(browser_task, description=f"[cyan]🌐 {msg[:70]}")

    # ── Source 1: Wikipedia (best for factual text) ──────────────
    _update(f"Wikipedia: {keyword}")
    wiki_url, wiki_text = fetch_wikipedia(keyword)
    if wiki_url:
        visited_urls.append(wiki_url)
    if wiki_text and len(wiki_text) > min_chars:
        best_text = wiki_text
        _update(f"✓ Wikipedia hit ({len(wiki_text):,} chars)")

    # ── Source 2: DuckDuckGo web search ─────────────────────────
    if len(best_text) < min_chars:
        _update(f"Searching web: {keyword}")
        urls = search_duckduckgo(keyword, max_results=5)
        for url in urls:
            visited_urls.append(url)
            _update(f"Reading: {url[:65]}")
            text = scrape_page(url)
            if len(text) > len(best_text):
                best_text = text
            if len(best_text) > 2000:
                break
            time.sleep(0.3)  # polite delay

    return best_text.strip(), visited_urls
