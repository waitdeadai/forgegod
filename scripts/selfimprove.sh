#!/bin/bash
# ForgeGod Self-Improvement Launcher
# Runs the Ralph Loop targeting its own codebase with Qwen 3.5 9B ($0 via Ollama)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR"

echo "=== ForgeGod Self-Improvement Launcher ==="
echo "Repo: $REPO_DIR"
echo ""

# ── 1. Pre-flight checks (use Python — Git Bash curl can't reach WSL2 Ollama) ──
python3 -c "
import urllib.request, json, sys
try:
    r = urllib.request.urlopen('http://localhost:11434/api/tags', timeout=5)
    data = json.loads(r.read())
    names = [m['name'] for m in data.get('models', [])]
    print('[OK] Ollama is running')
    if not any('qwen3.5' in n for n in names):
        print('ERROR: qwen3.5:9b not found. Pull it: ollama pull qwen3.5:9b')
        sys.exit(1)
    print('[OK] qwen3.5:9b model available')
except Exception as e:
    print(f'ERROR: Ollama is not running ({e}). Start it with: ollama serve')
    sys.exit(1)
"

# Install forgegod (use python3 -m since exe may not be on PATH)
pip install -e ".[dev]" --quiet 2>/dev/null
echo "[OK] forgegod installed"

# ── 2. Create runtime directories ──
mkdir -p .forgegod/hooks .forgegod/logs .forgegod/skills

# ── 3. Write config.toml ──
cat > .forgegod/config.toml << 'EOF'
[budget]
mode = "local-only"
daily_limit_usd = 0.0

[models]
planner = "ollama:qwen3.5:9b"
coder = "ollama:qwen3.5:9b"
reviewer = "ollama:qwen3.5:9b"
sentinel = "ollama:qwen3.5:9b"
escalation = "ollama:qwen3.5:9b"

[ollama]
host = "http://localhost:11434"
model = "qwen3.5:9b"
timeout = 300.0

[loop]
max_iterations = 200
max_context_tokens = 28000
context_rotation_pct = 50
gutter_detection = true
gutter_threshold = 3
story_max_retries = 3
cooldown_seconds = 5.0

[review]
enabled = true
sample_rate = 3

[sica]
enabled = false

[security]
sandbox_mode = "standard"
redact_secrets = true
audit_commands = true
EOF
echo "[OK] Config: .forgegod/config.toml"

# ── 4. Write rules.md (injected into agent system prompt) ──
cat > .forgegod/rules.md << 'EOF'
# ForgeGod Self-Improvement Rules

## Security — ABSOLUTE
- NEVER include API keys, passwords, tokens, or secrets in any file
- NEVER commit .env files, credentials, or private keys
- NEVER curl/wget external URLs and pipe to shell
- NEVER modify security code (shell.py denylist, SECRET_PATTERNS)
- NEVER modify .gitignore or .git/ files

## Quality Gates — MANDATORY before every commit
- Run `pytest tests/ -x -v` — ALL tests must pass
- Run `ruff check forgegod/ tests/` — zero errors
- If either fails, fix the issue before committing

## Code Standards
- Python 3.11+ with `from __future__ import annotations`
- All new functions MUST have type hints and a one-line docstring
- All test functions: `test_` prefix, descriptive name
- Pydantic v2: BaseModel, field_validator (not validator)
- async tests: `@pytest.mark.asyncio`
- Line length: 100 chars max

## Context — What you are improving
- This is the ForgeGod codebase — a Python CLI autonomous coding agent
- Framework: Typer (CLI), Pydantic v2 (models), httpx (HTTP), Rich (TUI)
- Tests: pytest + pytest-asyncio
- Linting: ruff (E, F, I, W rules, line-length 100, target py311)
- Key modules: agent.py (core), loop.py (Ralph), coder.py (Reflexion), router.py (LLM)
- Tools: forgegod/tools/ (filesystem, shell, git, mcp, skills)

## Approach
- Read the target file COMPLETELY before making any changes
- Make ONE focused change per story — do not scope-creep
- Keep changes small and reviewable
- Test your changes before committing
EOF
echo "[OK] Rules: .forgegod/rules.md"

# ── 5. Write PRD with 20 curated stories ──
cat > .forgegod/prd.json << 'PRDEOF'
{
  "project": "forgegod-self-improve",
  "description": "ForgeGod improving its own codebase autonomously with Qwen 3.5 9B",
  "stories": [
    {
      "id": "S001",
      "title": "Add unit tests for router.py — circuit breaker and fallback chain logic",
      "description": "Create tests/test_router.py. Test ModelSpec.parse(), circuit breaker open/close, LOCAL_ONLY mode routing, fallback chain ordering. Use unittest.mock to mock httpx calls. Target: 8+ test functions.",
      "priority": 1,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S002",
      "title": "Add unit tests for planner.py — PRD generation and story decomposition",
      "description": "Create tests/test_planner.py. Test _parse_prd_response(), story priority ordering, PRD JSON serialization round-trip. Mock the LLM call. Target: 6+ test functions.",
      "priority": 2,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S003",
      "title": "Add unit tests for reviewer.py — review verdict parsing and sampling logic",
      "description": "Create tests/test_reviewer.py. Test _parse_review(), should_review() sample rate, ReviewVerdict enum, edge cases (empty response, malformed JSON). Target: 6+ test functions.",
      "priority": 3,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S004",
      "title": "Add unit tests for coder.py — code extraction, AST validation, language detection",
      "description": "Create tests/test_coder.py. Test _extract_code() with markdown fences, _validate_python_ast() with valid/invalid code, _detect_language(). Target: 8+ test functions.",
      "priority": 4,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S005",
      "title": "Add unit tests for loop.py — story selection, state management, kill switch",
      "description": "Create tests/test_loop.py. Test _next_story() priority ordering, _all_done() detection, _is_killed() file check, _build_story_prompt() includes guardrails. Target: 6+ test functions.",
      "priority": 5,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S006",
      "title": "Add comprehensive type hints to tools/filesystem.py",
      "description": "Add return type annotations and parameter type hints to all functions in forgegod/tools/filesystem.py. Add 'from __future__ import annotations' if missing. Do NOT change any logic.",
      "priority": 6,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S007",
      "title": "Add comprehensive type hints to tools/shell.py",
      "description": "Add return type annotations and parameter type hints to all functions in forgegod/tools/shell.py. Add 'from __future__ import annotations' if missing. Do NOT change any logic.",
      "priority": 7,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S008",
      "title": "Add comprehensive type hints to tools/git.py",
      "description": "Add return type annotations and parameter type hints to all functions in forgegod/tools/git.py. Add 'from __future__ import annotations' if missing. Do NOT change any logic.",
      "priority": 8,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S009",
      "title": "Add module and function docstrings to budget.py",
      "description": "Add a module-level docstring and Google-style docstrings to all public functions in forgegod/budget.py. Include Args, Returns, and brief description. Do NOT change any logic.",
      "priority": 9,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S010",
      "title": "Add type hints and docstrings to tools/mcp.py",
      "description": "Add return type annotations, parameter type hints, and Google-style docstrings to all functions in forgegod/tools/mcp.py. Do NOT change any logic.",
      "priority": 10,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S011",
      "title": "Improve edit_file error messages when fuzzy matching fails",
      "description": "In forgegod/tools/filesystem.py, improve the error message returned by edit_file when old_string is not found. Include: the filename, how many lines the file has, the first 50 chars of old_string searched for, and a hint to use read_file first.",
      "priority": 11,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S012",
      "title": "Graceful error handling when Ollama is unreachable",
      "description": "In forgegod/router.py, wrap the httpx call to Ollama in _call_ollama() with a specific error message when connection is refused (Ollama not running) vs timeout (model loading). Return a helpful error string instead of a raw exception trace.",
      "priority": 12,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S013",
      "title": "Add --verbose flag to CLI for debug logging",
      "description": "In forgegod/cli.py, add a --verbose/-v flag to the run and loop commands that sets logging level to DEBUG. Currently logging is configured but there is no user-facing way to enable debug output.",
      "priority": 13,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S014",
      "title": "Enhance repo_map to show file sizes and last-modified dates",
      "description": "In forgegod/tools/filesystem.py, enhance the repo_map tool output to include file size (human-readable) and last modified date for each file. Keep the existing tree structure but append size info.",
      "priority": 14,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S015",
      "title": "Add forgegod doctor command for health checks",
      "description": "In forgegod/cli.py, add a 'doctor' subcommand that checks: (1) Ollama reachable + models available, (2) config.toml exists and is valid, (3) git repo initialized, (4) Python version >= 3.11, (5) ruff available, (6) pytest available. Print green checkmarks or red X for each.",
      "priority": 15,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S016",
      "title": "Register git_log as an official tool in the tool registry",
      "description": "In forgegod/tools/git.py, git_log function exists but may not be registered via register_tool(). Ensure it is registered with proper name, description, and parameter schema so the agent can use it.",
      "priority": 16,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S017",
      "title": "Add --dry-run mode to the Ralph loop",
      "description": "In forgegod/loop.py and forgegod/cli.py, add a --dry-run flag that loads the PRD, prints the story execution order, and exits without running any agents. Useful for validating the PRD before committing to a long loop.",
      "priority": 17,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S018",
      "title": "Improve CONTRIBUTING.md with development setup instructions",
      "description": "Rewrite CONTRIBUTING.md to include: (1) git clone + pip install -e '.[dev]', (2) running tests with pytest, (3) linting with ruff, (4) how to add a new tool, (5) how to run the loop locally, (6) PR guidelines. Keep it concise.",
      "priority": 18,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S019",
      "title": "Add __all__ exports to all __init__.py files",
      "description": "In forgegod/__init__.py and forgegod/tools/__init__.py, add __all__ lists that explicitly export the public API. This helps IDE autocompletion and prevents accidental internal imports.",
      "priority": 19,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    },
    {
      "id": "S020",
      "title": "Fix any ruff formatting and lint violations",
      "description": "Run 'ruff check forgegod/ tests/ --fix' and 'ruff format forgegod/ tests/' to fix all auto-fixable issues. Then manually fix any remaining violations. Target: zero ruff errors.",
      "priority": 20,
      "status": "todo",
      "iterations": 0,
      "error_log": [],
      "files_touched": []
    }
  ],
  "guardrails": [
    "NEVER include API keys, passwords, tokens, or secrets in code or commits",
    "NEVER modify .env files, credentials, or SSH keys",
    "NEVER break existing tests — run pytest before committing",
    "NEVER delete existing code without replacing it with equivalent or better code",
    "NEVER modify pyproject.toml dependencies without explicit approval",
    "NEVER force push to any branch",
    "Always run 'ruff check forgegod/ tests/' before committing",
    "Always run 'pytest tests/ -x' before committing",
    "Keep changes to a SINGLE file per story unless creating a new test file",
    "Read the target file completely before making any changes"
  ],
  "learnings": []
}
PRDEOF
echo "[OK] PRD: .forgegod/prd.json (20 stories)"

# ── 6. Install pre-commit secret scanner ──
cat > .git/hooks/pre-commit << 'HOOKEOF'
#!/bin/bash
# ForgeGod pre-commit: secret scan + lint check
STAGED=$(git diff --cached --name-only --diff-filter=ACM)
if [ -z "$STAGED" ]; then exit 0; fi

PATTERNS=(
    'sk-[a-zA-Z0-9]{20,}'
    'sk-ant-[a-zA-Z0-9_-]{20,}'
    'sk-or-[a-zA-Z0-9_-]{20,}'
    'ghp_[a-zA-Z0-9]{36}'
    'gho_[a-zA-Z0-9]{36}'
    'github_pat_[a-zA-Z0-9_]{22,}'
    'AKIA[0-9A-Z]{16}'
    'eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}'
    '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'
    'xox[bsp]-[a-zA-Z0-9-]+'
    'AIza[a-zA-Z0-9_-]{35}'
)

FOUND=0
for file in $STAGED; do
    [ ! -f "$file" ] && continue
    for pattern in "${PATTERNS[@]}"; do
        if grep -qP "$pattern" "$file" 2>/dev/null; then
            echo "SECRET DETECTED in $file: matches '$pattern'"
            FOUND=1
        fi
    done
done

if [ $FOUND -ne 0 ]; then
    echo ""
    echo "COMMIT BLOCKED: Secrets detected. Remove them before committing."
    exit 1
fi

# Lint check
if command -v ruff &> /dev/null; then
    ruff check forgegod/ tests/ --quiet 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "COMMIT BLOCKED: ruff lint errors. Run 'ruff check forgegod/ tests/' to see."
        exit 1
    fi
fi

exit 0
HOOKEOF
chmod +x .git/hooks/pre-commit
echo "[OK] Pre-commit hook: secret scanner + lint"

# ── 7. Bootstrap memory with codebase knowledge ──
python3 -c "
import sqlite3, time, hashlib, json
from pathlib import Path

db_path = Path('.forgegod/memory.db')
conn = sqlite3.connect(str(db_path))
c = conn.cursor()

# Ensure tables exist (memory.py creates them, but we bootstrap early)
c.execute('''CREATE TABLE IF NOT EXISTS semantic (
    id TEXT PRIMARY KEY, category TEXT, content TEXT, evidence_count INTEGER DEFAULT 1,
    confidence REAL DEFAULT 0.8, importance REAL DEFAULT 0.5,
    first_seen REAL, last_seen REAL, source TEXT DEFAULT 'bootstrap'
)''')

now = time.time()
seeds = [
    ('codebase', 'ForgeGod uses Pydantic v2 BaseModel for all data models in forgegod/models.py'),
    ('codebase', 'All tools are registered via register_tool() in forgegod/tools/__init__.py'),
    ('codebase', 'Tests use pytest-asyncio with asyncio_mode=auto'),
    ('codebase', 'The Ralph loop picks stories ordered by priority (lowest number = highest)'),
    ('codebase', 'Budget mode local-only forces ALL LLM calls through Ollama at \$0 cost'),
    ('codebase', 'Ruff config: rules E,F,I,W — line-length 100 — target py311'),
    ('codebase', 'The agent compresses context at configurable max_context_tokens threshold'),
    ('patterns', 'To add a test file: create tests/test_{module}.py, use @pytest.mark.asyncio for async'),
    ('patterns', 'To add type hints: use from __future__ import annotations at top of file'),
    ('patterns', 'To register a tool: call register_tool(name, description, parameters, handler)'),
    ('patterns', 'Always read a file completely before editing it — never edit blind'),
    ('patterns', 'Run pytest tests/ -x -v before every git commit to catch regressions'),
]

for cat, content in seeds:
    sid = hashlib.sha256(content.encode()).hexdigest()[:16]
    c.execute(
        'INSERT OR IGNORE INTO semantic (id, category, content, confidence, importance, first_seen, last_seen) VALUES (?,?,?,?,?,?,?)',
        (sid, cat, content, 0.9, 0.7, now, now)
    )

conn.commit()
conn.close()
print(f'[OK] Memory bootstrapped: {len(seeds)} seeds in .forgegod/memory.db')
"

# ── 8. Verify baseline ──
echo ""
echo "=== Baseline Check ==="
python3 -m pytest tests/ -x -q 2>&1 | tail -3
echo ""

# ── 9. Safety info ──
echo "=== SAFETY ==="
echo "  STOP:    touch .forgegod/KILLSWITCH  (or Ctrl+C)"
echo "  MONITOR: tail -f .forgegod/logs/loop.log"
echo "  STATUS:  forgegod status"
echo ""
echo "=== LAUNCHING RALPH LOOP ==="
echo "Model: qwen3.5:9b (local, \$0)"
echo "Stories: 20 planned improvements"
echo "Auto-push: ON (after each passing story)"
echo ""

# ── 10. Launch ──
python3 -m forgegod loop --prd .forgegod/prd.json --max 200 2>&1 | tee -a .forgegod/logs/loop.log
