"""ForgeGod Researcher — web intelligence gathering for Recon pipeline.

Phase 1 of Recon: generates search queries, executes them across providers,
fetches top results, synthesizes findings into a structured ResearchBrief.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from forgegod.config import ForgeGodConfig
from forgegod.models import (
    LibraryRecommendation,
    ResearchBrief,
    SearchQuery,
    SearchResult,
)
from forgegod.router import ModelRouter
from forgegod.terse import RECON_QUERY_PROMPT, RECON_SYNTHESIS_PROMPT
from forgegod.tools.web import pypi_info, web_fetch, web_search

logger = logging.getLogger("forgegod.researcher")


class Researcher:
    """Web research orchestrator — searches, fetches, synthesizes."""

    def __init__(self, config: ForgeGodConfig, router: ModelRouter):
        self.config = config
        self.router = router
        self.recon = config.recon

    async def research(self, task: str) -> ResearchBrief:
        """Full research pipeline: queries → search → fetch → synthesize."""
        logger.info("Recon: starting research for task")

        # Step 1: Generate targeted search queries
        queries = await self._generate_queries(task)
        logger.info("Recon: generated %d search queries", len(queries))

        # Step 2: Execute searches in parallel
        results = await self._execute_searches(queries)
        logger.info("Recon: got %d search results", len(results))

        # Step 3: Fetch top result content for depth
        results = await self._fetch_top_results(results)

        # Step 4: Check PyPI for any Python packages mentioned
        results = await self._check_pypi(task, results)

        # Step 5: Synthesize everything into a ResearchBrief
        brief = await self._synthesize(task, results)
        brief.search_count = len(queries)
        brief.raw_results = results

        logger.info(
            "Recon: brief ready — %d libs, %d patterns, %d warnings",
            len(brief.libraries),
            len(brief.architecture_patterns),
            len(brief.security_warnings),
        )
        return brief

    async def _generate_queries(self, task: str) -> list[SearchQuery]:
        """Ask the researcher model to generate targeted search queries."""
        year = datetime.now(timezone.utc).year
        prompt = RECON_QUERY_PROMPT.format(task=task, year=year)

        response, _ = await self.router.call(
            prompt=prompt,
            role="researcher",
            json_mode=True,
            max_tokens=1024,
            temperature=0.3,
        )

        queries = self._parse_queries(response)

        # Cap at max_searches
        queries = sorted(queries, key=lambda q: q.priority)
        return queries[: self.recon.max_searches]

    def _parse_queries(self, response: str) -> list[SearchQuery]:
        """Parse LLM response into SearchQuery list."""
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON array from response
            import re

            match = re.search(r"\[.*\]", response, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                logger.warning("Failed to parse query response, using fallback queries")
                return [SearchQuery(query="best practices " + response[:50], category="patterns")]

        if isinstance(data, dict) and "queries" in data:
            data = data["queries"]

        queries = []
        for item in data:
            if isinstance(item, str):
                queries.append(SearchQuery(query=item))
            elif isinstance(item, dict):
                queries.append(SearchQuery(
                    query=item.get("query", ""),
                    category=item.get("category", ""),
                    priority=item.get("priority", 2),
                ))
        return [q for q in queries if q.query.strip()]

    async def _execute_searches(self, queries: list[SearchQuery]) -> list[SearchResult]:
        """Run all search queries in parallel across providers."""
        provider = self.recon.search_provider
        searxng_url = self.recon.searxng_url
        brave_key = self.recon.brave_api_key
        exa_key = self.recon.exa_api_key

        async def _search_one(q: SearchQuery) -> list[SearchResult]:
            raw = await web_search(
                query=q.query,
                provider=provider,
                max_results=3,
                searxng_url=searxng_url,
                brave_api_key=brave_key,
                exa_api_key=exa_key,
            )
            try:
                items = json.loads(raw)
            except json.JSONDecodeError:
                return []

            if isinstance(items, dict) and "error" in items:
                logger.warning("Search failed for '%s': %s", q.query, items["error"])
                return []

            return [
                SearchResult(
                    query=q.query,
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    snippet=item.get("snippet", ""),
                    source=provider,
                )
                for item in items
            ]

        # Run searches concurrently (batch of 5 to avoid rate limits)
        all_results: list[SearchResult] = []
        for batch_start in range(0, len(queries), 5):
            batch = queries[batch_start : batch_start + 5]
            tasks = [_search_one(q) for q in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in batch_results:
                if isinstance(result, list):
                    all_results.extend(result)

        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique: list[SearchResult] = []
        for r in all_results:
            if r.url and r.url not in seen_urls:
                seen_urls.add(r.url)
                unique.append(r)

        return unique

    async def _fetch_top_results(self, results: list[SearchResult]) -> list[SearchResult]:
        """Fetch full content for top results to get deeper context."""
        max_fetch = min(10, len(results))
        max_chars = self.recon.max_fetch_chars

        async def _fetch_one(r: SearchResult) -> SearchResult:
            if not r.url:
                return r
            content = await web_fetch(r.url, max_chars=max_chars)
            if not content.startswith("Error"):
                r.content = content
            return r

        tasks = [_fetch_one(r) for r in results[:max_fetch]]
        fetched = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge fetched content back
        for i, result in enumerate(fetched):
            if isinstance(result, SearchResult):
                results[i] = result

        return results

    async def _check_pypi(self, task: str, results: list[SearchResult]) -> list[SearchResult]:
        """Check PyPI for Python packages mentioned in results."""
        # Extract package names from snippets and content
        import re

        all_text = " ".join(r.snippet + " " + r.content for r in results)
        # Common patterns: `pip install X`, `import X`, package names in context
        candidates: set[str] = set()
        for match in re.finditer(r"pip install (\S+)", all_text):
            pkg = match.group(1).strip("'\"`).,;")
            if pkg and len(pkg) < 40:
                candidates.add(pkg)

        # Also try common packages from the task description
        task_lower = task.lower()
        common_pkgs = {
            "fastapi": "fastapi", "flask": "flask", "django": "django",
            "typer": "typer", "click": "click", "rich": "rich",
            "pydantic": "pydantic", "sqlalchemy": "sqlalchemy",
            "pytest": "pytest", "httpx": "httpx", "requests": "requests",
            "duckdb": "duckdb", "sqlite": "aiosqlite",
        }
        for keyword, pkg in common_pkgs.items():
            if keyword in task_lower or keyword in all_text.lower():
                candidates.add(pkg)

        # Fetch PyPI info for top candidates (max 8)
        for pkg in list(candidates)[:8]:
            info = await pypi_info(pkg)
            results.append(SearchResult(
                query=f"pypi:{pkg}",
                url=f"https://pypi.org/project/{pkg}/",
                title=f"PyPI: {pkg}",
                snippet=info[:500],
                content=info,
                source="pypi",
            ))

        return results

    async def _synthesize(self, task: str, results: list[SearchResult]) -> ResearchBrief:
        """Feed all results to LLM for synthesis into ResearchBrief."""
        # Format results for the prompt
        formatted_results = []
        for r in results[:30]:  # Cap to avoid prompt overflow
            entry = f"[{r.source}] {r.title}\nURL: {r.url}\n"
            if r.content:
                entry += f"Content: {r.content[:800]}\n"
            elif r.snippet:
                entry += f"Snippet: {r.snippet}\n"
            formatted_results.append(entry)

        results_text = "\n---\n".join(formatted_results)

        prompt = RECON_SYNTHESIS_PROMPT.format(
            task=task,
            results=results_text,
        )

        response, _ = await self.router.call(
            prompt=prompt,
            role="researcher",
            json_mode=True,
            max_tokens=2048,
            temperature=0.2,
        )

        return self._parse_brief(response, task)

    def _parse_brief(self, response: str, task: str) -> ResearchBrief:
        """Parse synthesis response into ResearchBrief."""
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            import re

            match = re.search(r"\{.*\}", response, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                logger.warning("Failed to parse synthesis, returning empty brief")
                return ResearchBrief(task=task)

        libraries = []
        for lib in data.get("libraries", []):
            if isinstance(lib, dict):
                libraries.append(LibraryRecommendation(
                    name=lib.get("name", ""),
                    version=lib.get("version", ""),
                    why=lib.get("why", ""),
                    alternatives=lib.get("alternatives", []),
                    caveats=lib.get("caveats", ""),
                ))

        return ResearchBrief(
            task=task,
            libraries=libraries,
            architecture_patterns=data.get("architecture_patterns", []),
            security_warnings=data.get("security_warnings", []),
            best_practices=data.get("best_practices", []),
            prior_art=data.get("prior_art", []),
        )
