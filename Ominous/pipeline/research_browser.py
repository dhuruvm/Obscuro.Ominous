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
# URL Discovery via multiple public search engines
# ─────────────────────────────────────────────

def _extract_candidate_url(href: str) -> str:
    """Normalize redirected URLs from common search wrappers."""
    if not href:
        return ""

    if href.startswith("/l/?"):
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        href = parsed.get("uddg", [""])[0]

    if href.startswith("/url?"):
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        href = parsed.get("q", [""])[0]

    if href.startswith("http://") or href.startswith("https://"):
        return href

    return ""


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen = set()
    cleaned = []
    for url in urls:
        if not url:
            continue
        parsed = urllib.parse.urlsplit(url)
        if not parsed.scheme or not parsed.netloc:
            continue
        norm = url.rstrip("/")
        if norm in seen:
            continue
        seen.add(norm)
        cleaned.append(norm)
    return cleaned


def search_duckduckgo(query: str, max_results: int = 5) -> list[str]:
    """Search DuckDuckGo HTML and return a list of result URLs."""
    try:
        encoded = urllib.parse.quote_plus(query)
        sources = [
            ("https://html.duckduckgo.com/html/?q={encoded}", ["a.result__a", "a.result-link"]),
            ("https://lite.duckduckgo.com/lite/?q={encoded}", ["a.result-link", "a"]),
        ]

        for url_template, selectors in sources:
            url = url_template.format(encoded=encoded)
            resp = requests.get(url, headers=BROWSER_HEADERS, timeout=12)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            urls = []
            for selector in selectors:
                for a in soup.select(selector):
                    href = _extract_candidate_url(a.get("href", ""))
                    if href and "duckduckgo" not in href.lower():
                        urls.append(href)
                    if len(urls) >= max_results:
                        break
                if len(urls) >= max_results:
                    break

            if urls:
                return _dedupe_urls(urls)[:max_results]

            # Fallback: scan all links in page for any external destination
            for a in soup.find_all("a", href=True):
                href = _extract_candidate_url(a.get("href", ""))
                if href and "duckduckgo" not in href.lower():
                    urls.append(href)
                if len(urls) >= max_results:
                    break
            if urls:
                return _dedupe_urls(urls)[:max_results]

        return []

    except Exception as e:
        console.print(f"[red]DuckDuckGo search error: {e}[/red]")
        return []


def search_bing(query: str, max_results: int = 5) -> list[str]:
    """Search Bing as a fallback when DuckDuckGo is sparse or blocked."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.bing.com/search?q={encoded}"
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        urls = []
        for a in soup.select("li.b_algo a[href], a[href]"):
            href = _extract_candidate_url(a.get("href", ""))
            if href and "bing.com" not in href.lower():
                urls.append(href)
            if len(urls) >= max_results:
                break
        return _dedupe_urls(urls)[:max_results]
    except Exception:
        return []


def search_web_sources(query: str, max_results: int = 6) -> list[str]:
    """Collect URLs from multiple public search sources, preserving the highest-quality matches."""
    collected: list[str] = []
    for finder in (search_duckduckgo, search_bing):
        urls = finder(query, max_results=max_results)
        for url in urls:
            if url not in collected:
                collected.append(url)
        if len(collected) >= max_results:
            break
    return collected[:max_results]


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
    Researches a keyword across multiple sources and returns the combined text plus all visited URLs.
    This keeps the API stable while allowing richer source aggregation.
    """
    visited_urls = []
    collected_parts = []

    def _update(msg):
        if progress and browser_task is not None:
            progress.update(browser_task, description=f"[cyan]🌐 {msg[:70]}")

    _update(f"Wikipedia: {keyword}")
    wiki_url, wiki_text = fetch_wikipedia(keyword)
    if wiki_url:
        visited_urls.append(wiki_url)
    if wiki_text and len(wiki_text) > 80:
        collected_parts.append(wiki_text)
        _update(f"✓ Wikipedia hit ({len(wiki_text):,} chars)")

    _update(f"Searching web: {keyword}")
    urls = search_web_sources(keyword, max_results=6)
    for url in urls:
        if url in visited_urls:
            continue
        visited_urls.append(url)
        _update(f"Reading: {url[:65]}")
        text = scrape_page(url)
        if text and len(text.strip()) > 120:
            collected_parts.append(text.strip())
        time.sleep(0.2)

    combined_text = "\n\n".join(part.strip() for part in collected_parts if part and part.strip())
    if len(combined_text) < min_chars:
        return combined_text.strip(), visited_urls

    return combined_text.strip(), visited_urls
