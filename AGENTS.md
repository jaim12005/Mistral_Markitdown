# Mistral Markitdown

Stack: Python 3.10–3.12, MarkItDown, Mistral AI SDK, Pydantic, pdfplumber, camelot-py, pdf2image

## Commands

- Install: `pip install -r requirements.txt`
- Install dev: `pip install -r requirements.txt && pip install -r requirements-dev.txt`
- Test all: `python3 -m pytest tests/` (~593 tests, ~15s)
- Test single file: `python3 -m pytest tests/test_<name>.py -v`
- Lint: `python3 -m flake8 .`
- Format: `python3 -m black . && python3 -m isort .`
- Full check: `make check` (lint + test)
- Run app: `python3 main.py` (interactive) or `python3 main.py --mode markitdown --no-interactive`
- Self-test: `python3 main.py --test`
- Coverage: `python3 -m pytest tests/ --cov=. --cov-report=html --cov-report=term-missing`
- Security audit: `pip-audit --desc`

## Structure

- `main.py` -- CLI entry point and orchestration
- `config.py` -- configuration loading from .env and defaults
- `schemas.py` -- Pydantic data models and validation
- `mistral_converter.py` -- Mistral AI OCR/QnA/Batch conversion
- `local_converter.py` -- local MarkItDown-based conversion
- `utils.py` -- shared utilities
- `scripts/` -- helper scripts (test runner, etc.)
- `tests/` -- pytest test suite
- `input/` -- drop files here for conversion (gitignored)
- `output_md/`, `output_txt/`, `output_images/` -- conversion output (gitignored)
- `cache/` -- runtime cache (gitignored)
- `docs/` -- documentation

## Rules

- Make the smallest safe change.
- Preserve public APIs unless the task says otherwise.
- Reuse existing patterns/utilities before adding abstractions.
- Add/update tests for behavior changes.
- Ask first before changing schema, auth, CI, infra, or dependencies.
- Never commit secrets or edit generated/vendor files casually.
- Use `python3 -m <tool>` instead of bare commands when not in a virtualenv.

## Environment

- Python: 3.10, 3.11, or 3.12
- System deps: `poppler-utils` and `ghostscript` (needed by pdf2image and camelot-py)
- Setup: `pip install -r requirements.txt && pip install -r requirements-dev.txt`
- Config: copy `.env.example` to `.env`, set `MISTRAL_API_KEY` (optional — without it, only local MarkItDown works)

## Debugging

- Stale lint: `python3 -m flake8 .` (config is in `.flake8`, 120 char line length, black-compatible ignores)
- Failing tests: `python3 -m pytest tests/ -v --tb=long` — tests mock API calls so they pass without a key
- Type checking: `pyrightconfig.json` exists but typeCheckingMode is off

## Gotchas

- `MISTRAL_API_KEY` is optional. Without it, only local MarkItDown conversion works; all Mistral OCR/QnA/Batch features are disabled.
- The `Makefile` and `scripts/test-safe.sh` reference a local `env/` virtualenv. In cloud or CI environments, run tools via `python3 -m <tool>`.
- Pre-existing lint warnings exist in test files (unused imports, unused variables); these are in the upstream code.
- flake8 config is in `.flake8` (120 char line length, black-compatible ignores). pytest config is in `pyproject.toml`.
- Black is configured with `line-length = 120` and isort uses `profile = "black"` — both in `pyproject.toml`.

## PRs

- Before PR: `make check` (runs lint + tests)
- Include summary, risk, and validation steps.
