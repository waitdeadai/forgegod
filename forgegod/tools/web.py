"""ForgeGod web tools — search, fetch, PyPI, GitHub for Recon pipeline.

Provides web intelligence capabilities for the research-enhanced planning
mode. Uses SearXNG (free, self-hosted) as primary, Brave/Exa as fallback.
"""

from __future__ import annotations

import html
import json
import logging
import re
from urllib.parse import quote_plus

import httpx

from forgegod.tools import register_tool

logger = logging.getLogger("forgegod.tools.web")

# ── Constants ──

_TIMEOUT = 15.0
_MAX_FETCH_BYTES = 50_000
_USER_AGENT = "ForgeGod/0.1 (autonomous coding agent; +https://forgegod.com)"


# ── HTML → Text ──


def _html_to_text(raw_html: str, max_chars: int = 3000) -> str:
    """Extract readable text from HTML. Simple heuristic, no dependencies."""
    # Remove script/style blocks
    text = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", "", raw_html, flags=re.S | re.I)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode entities
    text = html.unescape(text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


# ── Search Providers ──


async def _search_searxng(
    query: str, url: str, max_results: int = 5
) -> list[dict]:
    """Search via self-hosted SearXNG instance."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{url.rstrip('/')}/search",
                params={
                    "q": query,
                    "format": "json",
                    "engines": "google,duckduckgo,brave",
                    "language": "en",
                },
                headers={"User-Agent": _USER_AGENT},
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for r in data.get("results", [])[:max_results]:
                results.append({
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "snippet": r.get("content", "")[:500],
                })
            return results
    except Exception as e:
        logger.warning("SearXNG search failed: %s", e)
        return []


async def _search_brave(
    query: str, api_key: str, max_results: int = 5
) -> list[dict]:
    """Search via Brave Search API (free 2K/month)."""
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": max_results},
                headers={
                    "X-Subscription-Token": api_key,
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for r in data.get("web", {}).get("results", [])[:max_results]:
                results.append({
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "snippet": r.get("description", "")[:500],
                })
            return results
    except Exception as e:
        logger.warning("Brave search failed: %s", e)
        return []


async def _search_exa(
    query: str, api_key: str, max_results: int = 5
) -> list[dict]:
    """Search via Exa AI (semantic, best for technical docs)."""
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                "https://api.exa.ai/search",
                json={
                    "query": query,
                    "type": "auto",
                    "numResults": max_results,
                    "useAutoprompt": True,
                },
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for r in data.get("results", [])[:max_results]:
                results.append({
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "snippet": r.get("text", "")[:500],
                })
            return results
    except Exception as e:
        logger.warning("Exa search failed: %s", e)
        return []


# ── Tool Implementations ──


async def web_search(
    query: str, provider: str = "searxng", max_results: int = 5,
    searxng_url: str = "http://localhost:8888",
    brave_api_key: str = "", exa_api_key: str = "",
) -> str:
    """Search the web. Returns JSON array of {url, title, snippet}.

    Tries providers in order: requested → SearXNG → Brave → Exa.
    """
    results: list[dict] = []

    # Try requested provider first, then fallback chain
    providers = [provider, "searxng", "brave", "exa"]
    seen = set()

    for p in providers:
        if p in seen or results:
            continue
        seen.add(p)

        if p == "searxng":
            results = await _search_searxng(query, searxng_url, max_results)
        elif p == "brave":
            results = await _search_brave(query, brave_api_key, max_results)
        elif p == "exa":
            results = await _search_exa(query, exa_api_key, max_results)

    if not results:
        return json.dumps({"error": "All search providers failed", "query": query})

    return json.dumps(results, ensure_ascii=False)


async def web_fetch(url: str, max_chars: int = 3000) -> str:
    """Fetch a URL and extract readable text content."""
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            follow_redirects=True,
            max_redirects=3,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            raw = resp.text[:_MAX_FETCH_BYTES]

            if "json" in content_type:
                return raw[:max_chars]
            elif "html" in content_type or raw.strip().startswith("<"):
                return _html_to_text(raw, max_chars)
            else:
                return raw[:max_chars]
    except Exception as e:
        return f"Error fetching {url}: {e}"


async def pypi_info(package: str) -> str:
    """Get package info from PyPI — version, description, dependencies."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"https://pypi.org/pypi/{quote_plus(package)}/json",
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            info = data.get("info", {})
            releases = list(data.get("releases", {}).keys())
            return json.dumps({
                "name": info.get("name", package),
                "version": info.get("version", "unknown"),
                "summary": info.get("summary", ""),
                "requires_python": info.get("requires_python", ""),
                "requires_dist": (info.get("requires_dist") or [])[:20],
                "license": info.get("license", ""),
                "home_page": info.get("home_page", "") or info.get("project_url", ""),
                "last_releases": releases[-5:] if releases else [],
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"PyPI lookup failed for {package}: {e}"})


async def github_search(
    query: str, language: str = "python", max_results: int = 5
) -> str:
    """Search GitHub repositories. Returns JSON array of repos."""
    try:
        search_q = f"{query} language:{language}" if language else query
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": search_q,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": max_results,
                },
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": _USER_AGENT,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for repo in data.get("items", [])[:max_results]:
                results.append({
                    "name": repo.get("full_name", ""),
                    "url": repo.get("html_url", ""),
                    "description": (repo.get("description") or "")[:200],
                    "stars": repo.get("stargazers_count", 0),
                    "language": repo.get("language", ""),
                    "updated": repo.get("updated_at", ""),
                })
            return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"GitHub search failed: {e}"})


# ── Tool Registration ──


def register_web_tools():
    """Register all web tools in the global tool registry."""
    register_tool(
        name="web_search",
        description="Search the web for information. Returns JSON array of {url, title, snippet}.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {
                    "type": "integer", "description": "Max results", "default": 5,
                },
            },
            "required": ["query"],
        },
        handler=_web_search_tool,
    )

    register_tool(
        name="web_fetch",
        description="Fetch a URL and extract readable text content.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "max_chars": {
                    "type": "integer", "description": "Max chars", "default": 3000,
                },
            },
            "required": ["url"],
        },
        handler=web_fetch,
    )

    register_tool(
        name="pypi_info",
        description="Get Python package info from PyPI — version, deps, license.",
        parameters={
            "type": "object",
            "properties": {
                "package": {"type": "string", "description": "Package name"},
            },
            "required": ["package"],
        },
        handler=pypi_info,
    )

    register_tool(
        name="github_search",
        description="Search GitHub repositories by keyword. Returns JSON with stars, description.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "language": {
                    "type": "string", "description": "Filter by language", "default": "python",
                },
            },
            "required": ["query"],
        },
        handler=github_search,
    )


async def _web_search_tool(query: str, max_results: int = 5) -> str:
    """Tool wrapper that reads config for provider settings."""
    # When called as a tool, use default SearXNG. Config-aware search
    # is handled by Researcher class which calls web_search() directly.
    return await web_search(query, max_results=max_results)
