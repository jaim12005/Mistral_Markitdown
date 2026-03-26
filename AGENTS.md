# AGENTS.md

## Cursor Cloud specific instructions

### Overview
This is the **Enhanced Document Converter** (`mistral-markitdown` v3.0.0) — a Python CLI tool combining MarkItDown (local) with Mistral AI OCR (cloud) for document conversion. It is **not** a web application; there is no server to start.

### System dependencies
`poppler-utils` and `ghostscript` must be installed via apt. These are needed by `pdf2image` and `camelot-py` for PDF processing.

### Running common tasks
Standard commands are in the `Makefile`:
- **Lint:** `python3 -m flake8 .` (or `make lint` if inside the repo venv)
- **Tests:** `python3 -m pytest tests/` (593 tests, ~15s)
- **Format:** `python3 -m black . && python3 -m isort .`
- **Run app:** `python3 main.py --test` (self-test), `python3 main.py --mode markitdown --no-interactive` (convert files in `input/`)

### Gotchas
- The `Makefile` and `scripts/test-safe.sh` reference a local `env/` virtualenv. In Cloud Agent VMs, dependencies are installed system-wide, so run tools via `python3 -m <tool>` instead of bare commands (e.g., `python3 -m flake8` not `flake8`).
- `MISTRAL_API_KEY` is optional. Without it, only local MarkItDown conversion works; all Mistral OCR/QnA/Batch features are disabled. Tests mock API calls so they pass without a key.
- flake8 config is in `.flake8` (120 char line length, black-compatible ignores). pytest config is in `pyproject.toml`.
- Pre-existing lint warnings exist in test files (unused imports, unused variables); these are in the upstream code.
