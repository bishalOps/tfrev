# Contributing to tfrev

Thanks for your interest in contributing to tfrev!

## Development Setup

```bash
git clone https://github.com/bishalOps/tfrev.git
cd tfrev
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/ -v
```

With coverage:

```bash
pytest tests/ -v --cov=tfrev --cov-report=term-missing
```

## Linting and Formatting

```bash
ruff check src/tfrev/ tests/
ruff format src/tfrev/ tests/
mypy src/tfrev/
```

## Project Structure

See [ARCHITECTURE.md](ARCHITECTURE.md) for design details and module responsibilities.

## Making Changes

1. Fork the repo and create a feature branch
2. Make your changes
3. Add or update tests as needed
4. Run the full test suite and linting
5. Open a pull request

## Code Style

- Python 3.9+ compatible (use `from __future__ import annotations`)
- Formatted with `ruff format`
- Type hints on all public functions
- Keep dependencies minimal

## Reporting Issues

Open an issue at [github.com/bishalOps/tfrev/issues](https://github.com/bishalOps/tfrev/issues).
