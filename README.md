# GitBroom

Git branch cleanup tool — see which branches are merged, stale, or safe to delete.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -e ".[dev]"
```

## Usage

```bash
python -m gitbroom
```

## Development

```bash
pytest tests/ -v
ruff check src/
mypy src/
```
