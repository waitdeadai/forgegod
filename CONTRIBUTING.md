# Contributing to ForgeGod

Thanks for your interest in ForgeGod. Here's how to contribute.

## Setup

```bash
git clone https://github.com/waitdeadai/forgegod.git
cd forgegod
pip install -e ".[dev]"
```

## Development

### Running Tests

```bash
pytest -x -v
```

Run a specific test file:

```bash
pytest tests/test_memory.py -v
```

### Linting

```bash
ruff check forgegod/ tests/
```

### Running the Loop

```bash
forgegod loop <path>
```

See `forgegod --help` for all CLI commands.

## Adding a New Tool

1. Create a new file in `forgegod/tools/` (e.g., `tools/mytool.py`)
2. Define a tool with `tool_def` and `tool_impl` functions
3. Register it in `forgegod/tools/_registry.py` via `register_tool()`
4. Add tests in `tests/test_tools.py`
5. Ensure `pytest` and `ruff` pass

Example:

```python
# forgegod/tools/mytool.py
from forgegod.tools import tool_def, tool_impl

@tool_def(name="mytool", description="My custom tool")
@tool_impl
async def mytool():
    return {"output": "Hello from mytool!"}
```

## Pull Request Guidelines

1. **Discuss first** — For large changes, open an issue before starting work.
2. **One PR per change** — Keep PRs focused. Don't mix features with refactors.
3. **Tests required** — New features need tests. Bug fixes need regression tests.
4. **Run the suite** — `pytest` must pass before submitting.
5. **No secrets** — Never commit API keys, tokens, or credentials.

## Code Style

- Python 3.11+
- Type hints on public functions
- Pydantic v2 for data models
- `async def` for I/O-bound operations
- Line length: 100 chars max

## License

By contributing, you agree that your contributions will be licensed under Apache 2.0.
