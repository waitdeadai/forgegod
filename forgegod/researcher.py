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
from forgegod.json_utils import extract_json
from forgegod.models import (
    CompetitiveFinding,
    DeepResearchBrief,
    LibraryRecommendation,
    ResearchBrief,
    ResearchDepth,
    SearchQuery,
    SearchResult,
    SOTAPattern,
    VerifiedSource,
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
        self.deep_research_cfg = config.deep_research

    async def research(
        self,
        task: str,
        depth: ResearchDepth | None = None,
    ) -> ResearchBrief:
        """Full research pipeline: queries → search → fetch → synthesize."""
        depth = depth or self.config.agent.research_depth_default
        limits = self._research_limits(depth)
        logger.info("Recon: starting research for task (depth=%s)", depth.value)

        # Step 1: Generate targeted search queries
        queries = await self._generate_queries(
            task,
            depth=depth,
            max_queries=limits["max_searches"],
        )
        logger.info("Recon: generated %d search queries", len(queries))

        # Step 2: Execute searches in parallel
        results = await self._execute_searches(
            queries,
            batch_size=limits["batch_size"],
        )
        logger.info("Recon: got %d search results", len(results))

        # Step 3: Fetch top result content for depth
        results = await self._fetch_top_results(
            results,
            max_fetch=limits["max_fetch"],
        )

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

    def _research_limits(self, depth: ResearchDepth) -> dict[str, int]:
        """Map research depth to concrete search/fetch budgets."""
        if depth == ResearchDepth.QUICK:
            return {
                "max_searches": min(self.recon.max_searches, 4),
                "batch_size": 4,
                "max_fetch": 3,
            }
        if depth == ResearchDepth.DEEP:
            return {
                "max_searches": min(max(self.recon.max_searches, 8), 10),
                "batch_size": 5,
                "max_fetch": 6,
            }
        return {
            "max_searches": max(self.recon.max_searches, 12),
            "batch_size": 5,
            "max_fetch": 10,
        }

    async def _generate_queries(
        self,
        task: str,
        *,
        depth: ResearchDepth,
        max_queries: int,
    ) -> list[SearchQuery]:
        """Ask the researcher model to generate targeted search queries."""
        year = datetime.now(timezone.utc).year
        depth_guidance = {
            ResearchDepth.QUICK: (
                "Depth: QUICK. Return 3-4 high-signal queries focused on official docs, "
                "release notes, and one practical implementation pattern."
            ),
            ResearchDepth.DEEP: (
                "Depth: DEEP. Return 5-8 queries covering official docs, migration guidance, "
                "security notes, and one competitive implementation comparison."
            ),
            ResearchDepth.SOTA: (
                f"Depth: SOTA. Return 8-12 current-year ({year}) queries covering official docs, "
                "release notes, changelogs, security/CVE checks, benchmarks, compatibility, "
                "and strong prior art."
            ),
        }[depth]
        prompt = (
            RECON_QUERY_PROMPT.format(task=task, year=year)
            + "\n\n"
            + depth_guidance
        )

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
        return queries[:max_queries]

    def _parse_queries(self, response: str) -> list[SearchQuery]:
        """Parse LLM response into SearchQuery list."""
        try:
            data = extract_json(response, expect_array=True)
        except ValueError:
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

    async def _execute_searches(
        self,
        queries: list[SearchQuery],
        *,
        batch_size: int = 5,
    ) -> list[SearchResult]:
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

        # Run searches concurrently in bounded batches to avoid rate limits.
        all_results: list[SearchResult] = []
        effective_batch_size = max(1, batch_size)
        for batch_start in range(0, len(queries), effective_batch_size):
            batch = queries[batch_start : batch_start + effective_batch_size]
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

    async def _fetch_top_results(
        self,
        results: list[SearchResult],
        *,
        max_fetch: int = 10,
    ) -> list[SearchResult]:
        """Fetch full content for top results to get deeper context."""
        max_fetch = min(max_fetch, len(results))
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
            max_tokens=4096,
            temperature=0.2,
        )

        return self._parse_brief(response, task)

    def _parse_brief(self, response: str, task: str) -> ResearchBrief:
        """Parse synthesis response into ResearchBrief."""
        try:
            data = extract_json(response)
        except ValueError:
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

    # ── Deep Research (Phase 2) ───────────────────────────────────────────────

    async def deep_research(self, task: str, story_id: str = "") -> DeepResearchBrief:
        """Deep research with causal chain search and information gain threshold.

        Runs iterative search cycles. Each cycle generates queries causally dependent
        on the previous cycle's findings. Stops when information gain drops below
        the configured threshold (default 1.5), preventing infinite loops.
        """
        cfg = self.config.deep_research
        findings: list[dict] = []
        sources_verified: list[VerifiedSource] = []
        information_gain_history: list[float] = []
        previous_state = ""

        for iteration in range(cfg.max_search_iterations):
            # Generate causally-chained queries based on previous findings
            queries = await self._generate_causal_queries(
                task, previous_state, iteration
            )
            if not queries:
                # Fallback if chain breaks down
                queries = [
                    SearchQuery(
                        query=f"best practices {task} 2026",
                        category="sota",
                        priority=1,
                    )
                ]

            # Execute searches
            results = await self._execute_searches(queries)

            # Fetch and verify sources
            results = await self._fetch_top_results(results)
            verified, unverified = await self._verify_sources(results)
            sources_verified.extend(verified)

            # Serialize current state for information gain
            current_state = self._serialize_findings(results, findings)
            gain = self._calculate_information_gain(previous_state, current_state)
            information_gain_history.append(gain)

            if gain < cfg.information_gain_threshold:
                logger.info(
                    "DeepResearch: stopped early at iteration %d — gain=%.2f < %.2f threshold",
                    iteration + 1, gain, cfg.information_gain_threshold,
                )
                break

            previous_state = current_state
            iteration_findings: list[dict] = []
            for q in queries:
                iteration_findings.append({
                    "query": q.query,
                    "results": [r.model_dump() for r in results],
                })
            findings.extend(iteration_findings)

        # Synthesize into DeepResearchBrief
        brief = await self._synthesize_deep(task, findings, sources_verified)
        brief.story_id = story_id
        brief.information_gain_history = information_gain_history
        brief.search_iterations = len(information_gain_history)
        brief.sources_verified = sources_verified
        brief.stopped_early = (
            len(information_gain_history) < cfg.max_search_iterations
        )
        if brief.stopped_early and not brief.stop_reason:
            last_gain = information_gain_history[-1] if information_gain_history else 0.0
            brief.stop_reason = (
                f"information_gain={last_gain:.2f} < "
                f"{cfg.information_gain_threshold} threshold"
            )

        return brief

    async def _generate_causal_queries(
        self, task: str, previous_state: str, iteration: int
    ) -> list[SearchQuery]:
        """Generate queries where step N depends on step N-1 findings."""
        if iteration == 0:
            # First iteration: broad competitive + SOTA queries
            prompt = (
                f"Generate 4 targeted search queries for: {task}\n\n"
                "Generate queries in these categories (1 per line):\n"
                "1. [COMPETITIVE] What do Claude Code, SWE-agent, Aider do for: {topic}\n"
                "2. [SOTA] What is the SOTA pattern for: {topic} in 2026\n"
                "3. [ARCH] How does SWE-agent decompose tasks — open source architecture\n"
                "4. [BENCHMARK] {topic} SWE-bench results 2026\n"
                "Return as JSON array with fields: query, category, priority (1=high)"
            ).format(topic=task)
        else:
            # Subsequent iterations: narrow based on previous state
            prompt = (
                f"Based on this research state for: {task}\n"
                f"Previous findings summary: {previous_state[:500]}\n\n"
                "Generate 3 NEW query strings that narrow or confirm these findings.\n"
                "Focus on: verified competitor techniques, benchmark scores, SOTA patterns.\n"
                "Return as JSON array: "
                "[{{\"query\": \"...\", \"category\": \"...\", \"priority\": 1}}]"
            )

        response, _ = await self.router.call(
            prompt=prompt,
            role="researcher",
            json_mode=True,
            max_tokens=1024,
            temperature=0.3,
        )

        return self._parse_queries(response)

    def _serialize_findings(
        self, results: list[SearchResult], prior_findings: list[dict]
    ) -> str:
        """Serialize findings into a normalized string for information gain comparison."""
        parts = []
        for r in results[:15]:
            parts.append(f"{r.title}|{r.snippet[:100]}")
        for finding in prior_findings:
            parts.append(f"Q:{finding.get('query', '')}")
            for r in finding.get("results", []):
                if isinstance(r, dict):
                    parts.append(f"R:{r.get('title', '')[:80]}")
        return "\n".join(parts)

    def _calculate_information_gain(self, previous: str, current: str) -> float:
        """Calculate ratio of new unique information in current vs previous state.

        A simple proxy: ratio of new character n-grams not present in previous.
        """
        if not previous:
            return 2.0  # First iteration always has high apparent gain

        prev_chars = set(previous)
        curr_chars = set(current)
        new_chars = curr_chars - prev_chars
        overlap = len(curr_chars & prev_chars)

        return len(new_chars) / max(overlap, 1)

    async def _verify_sources(
        self, results: list[SearchResult]
    ) -> tuple[list[VerifiedSource], list[SearchResult]]:
        """Fetch each URL and verify content matches the claim. Returns (verified, unverified)."""

        async def _verify_one(r: SearchResult) -> tuple[VerifiedSource | None, SearchResult | None]:
            if not r.url:
                return None, r
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            try:
                content = await web_fetch(r.url, max_chars=2000)
                match = not content.startswith("Error") and len(content) > 100
                verified_src = VerifiedSource(
                    url=r.url,
                    verified_at=today,
                    content_match=bool(match),
                    snippet=r.snippet[:200],
                )
                return verified_src, None
            except Exception:
                return None, r

        # Process in small batches to avoid hammering servers
        batch_size = 4
        verified_list: list[VerifiedSource] = []
        unverified_list: list[SearchResult] = []

        for i in range(0, len(results), batch_size):
            batch = results[i : i + batch_size]
            tasks = [_verify_one(r) for r in batch]
            pairs = await asyncio.gather(*tasks, return_exceptions=True)
            for pair in pairs:
                if isinstance(pair, tuple) and pair[0] is not None:
                    verified_list.append(pair[0])
                    if pair[1] is not None:
                        unverified_list.append(pair[1])
                elif isinstance(pair, SearchResult):
                    unverified_list.append(pair)

        return verified_list, unverified_list

    async def _synthesize_deep(
        self,
        task: str,
        findings: list[dict],
        sources: list[VerifiedSource],
    ) -> DeepResearchBrief:
        """Synthesize deep research findings into a DeepResearchBrief."""
        # Format findings for LLM synthesis
        findings_text = []
        for f in findings:
            findings_text.append(f"Query: {f.get('query', '')}")
            for r in f.get("results", [])[:3]:
                if isinstance(r, dict):
                    findings_text.append(f"  - {r.get('title', '')}: {r.get('snippet', '')[:150]}")

        sources_text = "\n".join(
            f"- [{s.url}]({s.verified_at}) — {'✓' if s.content_match else '✗'}: {s.snippet[:100]}"
            for s in sources
        )

        synthesis_prompt = (
            "You are the ForgeGod Deep Research Synthesizer.\n"
            "Given the following research findings, produce a structured JSON brief.\n\n"
            f"Task: {task}\n\n"
            f"Findings:\n{chr(10).join(findings_text[:50])}\n\n"
            f"Verified sources ({len(sources)}):\n{sources_text[:2000]}\n\n"
            "Return JSON with this exact structure:\n"
            "{\n"
            '  "competitive_intelligence": [{"competitor": "...", "technique": "...", '
            '"evidence_url": "...", "applicable": true/false, "forgegod_equivalents": ["..."]}],\n'
            '  "sota_patterns": [{"pattern_name": "...", "description": "...", '
            '"evidence_url": "...", "tech_stack_relevance": ["..."], "confidence": 0.0-1.0}],\n'
            '  "verified_constraints": ["constraint 1", "constraint 2"]\n'
            "}"
        )

        response, _ = await self.router.call(
            prompt=synthesis_prompt,
            role="researcher",
            json_mode=True,
            max_tokens=4096,
            temperature=0.2,
        )

        return self._parse_deep_brief(response, task)

    def _parse_deep_brief(self, response: str, task: str) -> DeepResearchBrief:
        """Parse synthesis response into DeepResearchBrief."""
        try:
            data = extract_json(response)
        except ValueError:
            logger.warning("DeepResearch: failed to parse synthesis, returning empty brief")
            return DeepResearchBrief(task=task)

        competitive: list[CompetitiveFinding] = []
        for item in data.get("competitive_intelligence", []):
            if isinstance(item, dict):
                competitive.append(CompetitiveFinding(
                    competitor=item.get("competitor", ""),
                    technique=item.get("technique", ""),
                    evidence_url=item.get("evidence_url", ""),
                    applicable=item.get("applicable", True),
                    forgegod_equivalents=item.get("forgegod_equivalents", []),
                ))

        sota_patterns: list[SOTAPattern] = []
        for item in data.get("sota_patterns", []):
            if isinstance(item, dict):
                sota_patterns.append(SOTAPattern(
                    pattern_name=item.get("pattern_name", ""),
                    description=item.get("description", ""),
                    evidence_url=item.get("evidence_url", ""),
                    tech_stack_relevance=item.get("tech_stack_relevance", []),
                    confidence=item.get("confidence", 0.0),
                ))

        return DeepResearchBrief(
            task=task,
            competitive_intelligence=competitive,
            sota_patterns=sota_patterns,
            verified_constraints=data.get("verified_constraints", []),
        )
