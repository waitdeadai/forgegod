# Contributing to ForgeGod

Thanks for your interest in ForgeGod. Here's how to contribute.

## Getting Started

```bash
git clone https://github.com/waitdeadai/forgegod.git
cd forgegod
pip install -e ".[dev]"
pytest
```

## Ways to Contribute

- **Bug reports** — Open an issue with steps to reproduce, expected vs actual behavior, and your Python version + OS.
- **Feature requests** — Open an issue describing the use case and proposed solution.
- **Code** — Fork, branch, implement, test, PR. See guidelines below.
- **Documentation** — README improvements, docstrings, examples.

## Pull Request Guidelines

1. **Discuss first** — For large changes, open an issue before starting work.
2. **One PR per change** — Keep PRs focused. Don't mix features with refactors.
3. **Tests required** — New features need tests. Bug fixes need a regression test.
4. **Run the suite** — `pytest` must pass before submitting.
5. **No secrets** — Never commit API keys, tokens, or credentials.

## Code Style

- Python 3.11+
- Type hints on public functions
- `ruff check .` for linting
- Pydantic v2 for data models
- `async def` for I/O-bound operations

## Development

```bash
# Run tests
pytest -x -v

# Run a specific test file
pytest tests/test_memory.py -v

# Lint
ruff check .
```

## License

By contributing, you agree that your contributions will be licensed under Apache 2.0.
