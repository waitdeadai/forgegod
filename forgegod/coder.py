"""ForgeGod Reflexion Coder — multi-attempt code generation with escalating models.

Ported from forge/forge_coder.py (Phase 63-70).
Stripped: WAITDEAD-specific generators, component extraction, domain constitution.
Kept: Reflexion loop, AST validation, code extraction, memory spine.

The loop:
  Attempt 1: Local model (qwen3-coder-next) → validate → if fail:
  Attempt 2: Cloud model (gpt-4o-mini) → validate → if fail:
  Attempt 3: Frontier model (o4-mini/sonnet) → validate → accept best
"""

from __future__ import annotations

import ast
import logging
import re
from typing import Any

from forgegod.config import ForgeGodConfig
from forgegod.models import CodeFile, ReflexionAttempt
from forgegod.router import ModelRouter

logger = logging.getLogger("forgegod.coder")

# Role escalation per attempt
ATTEMPT_ROLES = {1: "coder", 2: "reviewer", 3: "sentinel"}

MAX_ATTEMPTS = 3

# Language detection
EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".sh": "bash",
    ".sql": "sql",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
}


class ReflexionCoder:
    """Multi-attempt code generation with Reflexion and model escalation."""

    def __init__(self, config: ForgeGodConfig, router: ModelRouter | None = None):
        self.config = config
        self.router = router or ModelRouter(config)
        self.max_attempts = MAX_ATTEMPTS

    async def generate(
        self,
        task: str,
        file_path: str,
        context: str = "",
        existing_code: str = "",
        learnings: list[str] | None = None,
    ) -> CodeFile:
        """Generate code for a file with Reflexion loop.

        Args:
            task: Description of what to generate/modify.
            file_path: Target file path.
            context: Additional context (project description, architecture, etc.).
            existing_code: Current file contents (for modifications).
            learnings: Past lessons from memory spine.

        Returns:
            CodeFile with generated code and validation metadata.
        """
        code_file = CodeFile(path=file_path)
        reflections: list[str] = []
        lang = self._detect_language(file_path)

        for attempt_num in range(1, self.max_attempts + 1):
            role = ATTEMPT_ROLES.get(attempt_num, "sentinel")

            # Build prompt
            prompt = self._build_prompt(
                task=task,
                file_path=file_path,
                lang=lang,
                context=context,
                existing_code=existing_code,
                reflections=reflections,
                attempt=attempt_num,
                learnings=learnings or [],
            )

            # Generate
            response, usage = await self.router.call(
                prompt=prompt,
                role=role,
                max_tokens=8192,
                temperature=0.3 if attempt_num < 3 else 0.2,
            )

            # Extract code from response
            code = self._extract_code(response, lang)

            # Validate
            ast_valid, ast_error = self._validate_syntax(code, file_path, lang)
            imports_valid, import_errors = self._validate_imports(code, lang)

            attempt = ReflexionAttempt(
                attempt_number=attempt_num,
                model_used=f"{usage.provider}:{usage.model}",
                code_generated=code,
                validation_result="PASS" if (ast_valid and imports_valid) else "FAIL",
                error_message=ast_error or "; ".join(import_errors),
                success=ast_valid and imports_valid,
            )

            if ast_valid and imports_valid:
                code_file.content = code
                code_file.ast_valid = True
                code_file.imports_valid = True
                code_file.reflexion_attempts.append(attempt)
                logger.info(
                    f"Generated {file_path}: PASS in {attempt_num} attempt(s) "
                    f"[{usage.provider}:{usage.model}]"
                )
                return code_file

            # Generate reflection for next attempt
            if attempt_num < self.max_attempts:
                reflection = await self._generate_reflection(
                    code, ast_error, import_errors, lang
                )
                attempt.reflection = reflection
                reflections.append(reflection)
                logger.info(
                    f"Attempt {attempt_num} for {file_path}: FAIL — "
                    f"{ast_error or '; '.join(import_errors)}"
                )

            code_file.reflexion_attempts.append(attempt)

        # All attempts failed — store best attempt
        if code_file.reflexion_attempts:
            best = max(
                code_file.reflexion_attempts,
                key=lambda a: (a.success, -a.attempt_number),
            )
            code_file.content = best.code_generated

        logger.warning(f"All {self.max_attempts} attempts failed for {file_path}")
        return code_file

    async def architect_edit(
        self,
        task: str,
        file_path: str,
        existing_code: str = "",
        context: str = "",
    ) -> CodeFile:
        """Architect/Editor two-pass generation (Aider pattern — 83% polyglot benchmark).

        Pass 1: Expensive reasoning model generates a plan (read-only, no code output).
        Pass 2: Cheap fast model receives the plan and generates actual code.

        This reduces cost while maintaining quality — the editor model doesn't
        need to "think", it just follows detailed instructions.
        """
        lang = self._detect_language(file_path)

        # Pass 1: Architect (reasoning model — planner role)
        architect_prompt = f"""You are a senior software architect. Analyze this task and create a detailed implementation plan.

## Task
{task}

## File: {file_path} ({lang})

{f'## Existing Code\n```{lang}\n{existing_code[:6000]}\n```' if existing_code else ''}

{f'## Context\n{context[:3000]}' if context else ''}

## Instructions
Create a DETAILED implementation plan. For each change:
1. Specify the EXACT location (function name, line range)
2. Describe WHAT to change and WHY
3. List new imports needed
4. Note edge cases to handle

Do NOT write any code. Only write the plan.
Output format: numbered steps with specific details."""

        plan, _ = await self.router.call(
            prompt=architect_prompt,
            role="planner",  # Uses reasoning model
            max_tokens=4096,
            temperature=0.3,
        )

        # Pass 2: Editor (fast cheap model — coder role)
        editor_prompt = f"""You are a code editor. Follow the implementation plan EXACTLY.

## Plan from Architect
{plan}

## File: {file_path} ({lang})

{f'## Existing Code (modify this)\n```{lang}\n{existing_code[:6000]}\n```' if existing_code else ''}

## Instructions
Implement the architect's plan precisely. Include ALL imports.
Output ONLY the {lang} code in ```{lang} fences. No explanations."""

        response, usage = await self.router.call(
            prompt=editor_prompt,
            role="coder",  # Uses cheap fast model
            max_tokens=8192,
            temperature=0.2,
        )

        code = self._extract_code(response, lang)
        ast_valid, ast_error = self._validate_syntax(code, file_path, lang)
        imports_valid, import_errors = self._validate_imports(code, lang)

        code_file = CodeFile(path=file_path)
        code_file.content = code
        code_file.ast_valid = ast_valid
        code_file.imports_valid = imports_valid
        code_file.reflexion_attempts.append(ReflexionAttempt(
            attempt_number=1,
            model_used=f"{usage.provider}:{usage.model}",
            code_generated=code,
            validation_result="PASS" if (ast_valid and imports_valid) else "FAIL",
            error_message=ast_error or "; ".join(import_errors),
            reflection=f"Architect/Editor two-pass. Plan: {plan[:200]}...",
            success=ast_valid and imports_valid,
        ))

        if not (ast_valid and imports_valid):
            # Fall back to standard Reflexion loop
            logger.info(f"Architect/Editor failed for {file_path}, falling back to Reflexion")
            return await self.generate(
                task=task,
                file_path=file_path,
                context=context,
                existing_code=existing_code,
            )

        logger.info(f"Architect/Editor: {file_path} generated successfully")
        return code_file

    async def generate_batch(
        self,
        tasks: list[dict[str, Any]],
        context: str = "",
        learnings: list[str] | None = None,
    ) -> list[CodeFile]:
        """Generate code for multiple files.

        Each task dict should have: task, file_path, existing_code (optional).
        """
        results = []
        for t in tasks:
            code_file = await self.generate(
                task=t["task"],
                file_path=t["file_path"],
                context=context,
                existing_code=t.get("existing_code", ""),
                learnings=learnings,
            )
            results.append(code_file)
        return results

    def _build_prompt(
        self,
        task: str,
        file_path: str,
        lang: str,
        context: str,
        existing_code: str,
        reflections: list[str],
        attempt: int,
        learnings: list[str],
    ) -> str:
        """Build generation prompt with escalating context."""
        # GOAP scratch pad (Hermes/Teknium pattern — Goal, Actions, Observation, Reflection)
        prompt = f"""You are ForgeGod Coder, an expert programmer.

<scratch_pad>
Goal: {task}
File: {file_path} ({lang})
Attempt: {attempt}/{self.max_attempts}
Actions needed: Analyze requirements → generate code → validate syntax
Observation: {"First attempt — generate clean, correct code" if attempt == 1 else f"Previous attempts failed — applying reflections"}
Reflection: {"N/A" if not reflections else reflections[-1][:200]}
</scratch_pad>

## Conventions
- Modern {lang} idioms, type hints where supported
- async/await for I/O-bound operations
- Complete, production-ready code with all imports
"""

        if context:
            prompt += f"\n## Project Context\n{context[:4000]}\n"

        if existing_code:
            prompt += f"\n## Existing Code (modify this)\n```{lang}\n{existing_code[:6000]}\n```\n"

        # Memory spine — past lessons
        if learnings:
            prompt += "\n## PAST LESSONS (avoid these patterns)\n"
            for lesson in learnings[:8]:
                prompt += f"- {lesson}\n"

        # Reflections from previous failed attempts
        if reflections:
            prompt += "\n## Previous Attempt Reflections\n"
            for i, r in enumerate(reflections, 1):
                prompt += f"\n### Attempt {i} reflection:\n{r}\n"
            prompt += "\nFix ALL issues mentioned above.\n"

        if attempt >= 3:
            prompt += "\n## CRITICAL: FINAL attempt. Be extremely careful. Double-check every import and syntax construct.\n"

        prompt += f"\nOutput ONLY the {lang} code in ```{lang} fences. No explanations."
        return prompt

    async def _generate_reflection(
        self,
        code: str,
        ast_error: str | None,
        import_errors: list[str],
        lang: str,
    ) -> str:
        """Generate reflection on why the code failed."""
        prompt = f"""The following {lang} code FAILED validation:

```{lang}
{code[:3000]}
```

Errors:
- Syntax Error: {ast_error or 'None'}
- Import Errors: {', '.join(import_errors) if import_errors else 'None'}

Analyze WHY this failed and provide specific, actionable fix instructions.
Be concise (max 200 words)."""

        result, _ = await self.router.call(
            prompt=prompt,
            role="reviewer",
            max_tokens=1000,
            temperature=0.3,
        )
        return result if result else f"Syntax error: {ast_error}"

    # ── Validation ──

    def _validate_syntax(
        self, code: str, file_path: str, lang: str
    ) -> tuple[bool, str | None]:
        """Validate code syntax."""
        if not code.strip():
            return False, "Empty code"

        if lang == "python":
            return self._validate_python_ast(code)

        if lang == "json":
            return self._validate_json(code)

        # For other languages, accept if non-empty (no local parser available)
        return True, None

    def _validate_python_ast(self, code: str) -> tuple[bool, str | None]:
        """AST-parse Python code."""
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, f"SyntaxError at line {e.lineno}: {e.msg}"

    def _validate_json(self, code: str) -> tuple[bool, str | None]:
        """Validate JSON."""
        import json
        try:
            json.loads(code)
            return True, None
        except json.JSONDecodeError as e:
            return False, f"JSONDecodeError: {e}"

    def _validate_imports(
        self, code: str, lang: str
    ) -> tuple[bool, list[str]]:
        """Validate imports are reasonable."""
        if lang != "python":
            return True, []

        errors: list[str] = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False, ["Code has syntax errors"]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if self._is_suspicious_import(alias.name):
                        errors.append(f"Suspicious import: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and self._is_suspicious_import(node.module):
                    errors.append(f"Suspicious import from: {node.module}")

        return len(errors) == 0, errors

    def _is_suspicious_import(self, module: str) -> bool:
        """Check if an import looks suspicious (e.g., placeholder modules)."""
        suspicious = ["nonexistent", "placeholder", "todo_module", "fixme"]
        return any(s in module.lower() for s in suspicious)

    # ── Code Extraction ──

    def _extract_code(self, response: str, lang: str) -> str:
        """Extract code from LLM response fences."""
        if not response:
            return ""

        # Try language-specific fences
        fence_langs = [lang]
        if lang == "python":
            fence_langs.extend(["py", "python3"])
        elif lang in ("typescript", "javascript"):
            fence_langs.extend(["ts", "tsx", "js", "jsx"])

        for fl in fence_langs:
            pattern = rf"```{fl}\n(.*?)```"
            match = re.search(pattern, response, re.DOTALL)
            if match:
                return match.group(1).strip()

        # Try generic fence
        match = re.search(r"```\n(.*?)```", response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # If no fences, check if the whole response looks like code
        lines = response.strip().split("\n")
        if lines and self._looks_like_code(lines[0], lang):
            return response.strip()

        return response.strip()

    def _looks_like_code(self, first_line: str, lang: str) -> bool:
        """Heuristic: does the first line look like code?"""
        code_starters = {
            "python": ["import ", "from ", '"""', "#!", "class ", "def ", "#"],
            "typescript": ["import ", "export ", "const ", "//", "/*"],
            "javascript": ["import ", "export ", "const ", "//", "/*"],
            "go": ["package ", "import ", "func ", "//"],
            "rust": ["use ", "fn ", "pub ", "mod ", "//"],
        }
        starters = code_starters.get(lang, ["//", "#", "import "])
        return any(first_line.strip().startswith(s) for s in starters)

    def _detect_language(self, file_path: str) -> str:
        """Detect language from file extension."""
        for ext, lang in EXT_TO_LANG.items():
            if file_path.endswith(ext):
                return lang
        return "python"
