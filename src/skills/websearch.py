"""
Built-in skill: websearch
Combines Tavily Search API (query -> top results) with Jina Reader (url -> markdown text).
Results are truncated to a configurable max length to stay within LLM context limits.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (env-based with sane defaults)
# ---------------------------------------------------------------------------
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "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")
TAVILY_BASE_URL = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com")

JINA_API_KEY = os.getenv("JINA_API_KEY", "")
JINA_BASE_URL = os.getenv("JINA_BASE_URL", "https://r.jina.ai")

# Truncation defaults
DEFAULT_MAX_RESULTS = 5  # max search hits to return
DEFAULT_MAX_CONTENT_CHARS = 4000  # per-page content truncation
DEFAULT_MAX_TOTAL_CHARS = 20000  # total output truncation
DEFAULT_TIMEOUT = 20.0  # seconds per HTTP call


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class SearchResult:
    """One search hit."""
    title: str = ""
    url: str = ""
    snippet: str = ""
    content: str = ""  # full / truncated page content from Jina
    score: float = 0.0


@dataclass
class WebSearchResponse:
    """Aggregated response returned to the LLM / caller."""
    query: str = ""
    results: List[Dict[str, Any]] = field(default_factory=list)
    answer: str = ""  # Tavily's optional AI answer
    truncated: bool = False
    error: str = ""


# ---------------------------------------------------------------------------
# Tavily search
# ---------------------------------------------------------------------------
async def _tavily_search(
    query: str,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
    search_depth: str = "basic",
    include_answer: bool = True,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    Call Tavily Search API.
    Docs: https://docs.tavily.com/docs/tavily-api/rest_api

    Returns raw JSON dict from Tavily.
    """
    if not TAVILY_API_KEY:
        return {"error": "TAVILY_API_KEY is not set"}

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_answer": include_answer,
        "include_raw_content": False,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(f"{TAVILY_BASE_URL}/search", json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Tavily HTTP error: %s – %s", exc.response.status_code, exc.response.text)
            return {"error": f"Tavily HTTP {exc.response.status_code}: {exc.response.text[:200]}"}
        except Exception as exc:
            logger.error("Tavily request failed: %s", exc)
            return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Jina Reader
# ---------------------------------------------------------------------------
async def _jina_read(
    url: str,
    *,
    max_chars: int = DEFAULT_MAX_CONTENT_CHARS,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """
    Use Jina Reader (https://r.jina.ai/<url>) to fetch a clean markdown
    representation of a webpage. The output is truncated to *max_chars*.
    """
    reader_url = f"{JINA_BASE_URL}/{url}"

    headers: Dict[str, str] = {
        "Accept": "text/plain",
    }
    if JINA_API_KEY:
        headers["Authorization"] = f"Bearer {JINA_API_KEY}"
    # Ask Jina to return concise content
    headers["X-Return-Format"] = "markdown"

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            resp = await client.get(reader_url, headers=headers)
            resp.raise_for_status()
            text = resp.text
        except httpx.HTTPStatusError as exc:
            logger.warning("Jina reader HTTP error for %s: %s", url, exc.response.status_code)
            return f"[Jina error: HTTP {exc.response.status_code}]"
        except Exception as exc:
            logger.warning("Jina reader failed for %s: %s", url, exc)
            return f"[Jina error: {exc}]"

    # Truncate
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n... [truncated at {max_chars} chars]"
    return text


# ---------------------------------------------------------------------------
# Parallel Jina fetch for multiple URLs
# ---------------------------------------------------------------------------
async def _batch_jina_read(
    urls: List[str],
    *,
    max_chars_per_page: int = DEFAULT_MAX_CONTENT_CHARS,
    timeout: float = DEFAULT_TIMEOUT,
    concurrency: int = 5,
) -> Dict[str, str]:
    """
    Fetch multiple URLs via Jina in parallel (bounded concurrency).
    Returns {url: content_text}.
    """
    sem = asyncio.Semaphore(concurrency)
    results: Dict[str, str] = {}

    async def _fetch(u: str):
        async with sem:
            results[u] = await _jina_read(u, max_chars=max_chars_per_page, timeout=timeout)

    await asyncio.gather(*[_fetch(u) for u in urls], return_exceptions=True)
    return results


# ---------------------------------------------------------------------------
# Public API — the tool function
# ---------------------------------------------------------------------------
async def websearch(
    query: str,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
    search_depth: str = "basic",
    fetch_content: bool = True,
    max_content_chars: int = DEFAULT_MAX_CONTENT_CHARS,
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    Perform a web search and optionally fetch full page content.

    Parameters
    ----------
    query : str
        The search query.
    max_results : int
        Number of search results to return (default 5).
    search_depth : str
        Tavily search depth — "basic" or "advanced".
    fetch_content : bool
        Whether to use Jina to fetch full page content for each result.
    max_content_chars : int
        Maximum characters to keep per page (truncation boundary).
    max_total_chars : int
        Maximum total characters in the final output (hard cap).
    timeout : float
        HTTP timeout in seconds.

    Returns
    -------
    dict with keys: query, answer, results[], truncated, error
    """
    response = WebSearchResponse(query=query)

    # Step 1: Tavily search
    raw = await _tavily_search(
        query,
        max_results=max_results,
        search_depth=search_depth,
        timeout=timeout,
    )

    if "error" in raw:
        response.error = raw["error"]
        return _to_dict(response)

    response.answer = raw.get("answer", "") or ""
    tavily_results: List[Dict[str, Any]] = raw.get("results", [])

    if not tavily_results:
        return _to_dict(response)

    # Build search result objects
    hits: List[SearchResult] = []
    for item in tavily_results[:max_results]:
        hits.append(SearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("content", ""),
            score=item.get("score", 0.0),
        ))

    # Step 2 (optional): Jina Reader — fetch full content
    if fetch_content:
        urls = [h.url for h in hits if h.url]
        contents = await _batch_jina_read(
            urls,
            max_chars_per_page=max_content_chars,
            timeout=timeout,
        )
        for h in hits:
            h.content = contents.get(h.url, "")

    # Step 3: Assemble & apply total truncation
    total_len = 0
    for h in hits:
        entry = {
            "title": h.title,
            "url": h.url,
            "snippet": h.snippet,
            "score": h.score,
        }
        if fetch_content and h.content:
            entry["content"] = h.content

        entry_len = sum(len(str(v)) for v in entry.values())
        if total_len + entry_len > max_total_chars:
            # truncate the content of this entry to fit
            remaining = max(0, max_total_chars - total_len - (entry_len - len(entry.get("content", ""))))
            if remaining > 200 and entry.get("content"):
                entry["content"] = entry["content"][:remaining] + "\n... [total limit reached]"
            else:
                entry.pop("content", None)
            response.results.append(entry)
            response.truncated = True
            break

        response.results.append(entry)
        total_len += entry_len

    return _to_dict(response)


def _to_dict(resp: WebSearchResponse) -> Dict[str, Any]:
    return {
        "query": resp.query,
        "answer": resp.answer,
        "results": resp.results,
        "truncated": resp.truncated,
        "error": resp.error,
    }


# ---------------------------------------------------------------------------
# Tool schema (OpenAI function-calling compatible)
# ---------------------------------------------------------------------------
TOOL_SCHEMA: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "websearch",
        "description": (
            "Search the web using Tavily and fetch full page content using Jina Reader. "
            "Returns search results with optional full-text content, all truncated to "
            "fit within LLM context limits. Use for current events, fact-checking, "
            "real-time information lookups, and general knowledge queries."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of search results (1-10). Default: 5.",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 10,
                },
                "search_depth": {
                    "type": "string",
                    "description": "Search depth: 'basic' (fast) or 'advanced' (thorough). Default: 'basic'.",
                    "enum": ["basic", "advanced"],
                    "default": "basic",
                },
                "fetch_content": {
                    "type": "boolean",
                    "description": "Whether to fetch full page content via Jina Reader. Default: true.",
                    "default": True,
                },
                "max_content_chars": {
                    "type": "integer",
                    "description": "Max characters per page content. Default: 4000.",
                    "default": 4000,
                    "minimum": 500,
                    "maximum": 20000,
                },
            },
            "required": ["query"],
        },
    },
}
