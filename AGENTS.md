# Repository Guidelines

## Project Structure & Module Organization
- main.py: interactive CLI entry; supports flags like `--mode`, `--test`, `--no-interactive`.
- local_converter.py: MarkItDown conversions, PDF table extraction, PDF→image utility.
- mistral_converter.py: Mistral OCR integration and response processing.
- utils.py: helpers (I/O, markdown/table utilities, concurrency, caching, metadata).
- config.py: env loader, constants, and directory setup.
- Directories: `input/`, `output_md/`, `output_txt/`, `output_images/`, `logs/` (incl. `logs/metadata/`), `cache/`.
- Setup scripts: `requirements.txt`, `run_converter.bat` (Windows), `quick_start.sh` (macOS/Linux), `.env.example`.

## Build, Test, and Development Commands
- Create env: `python -m venv env && source env/bin/activate` (Windows: `env\Scripts\activate`).
- Install deps: `pip install -r requirements.txt`.
- Configure: `cp .env.example .env` and set `MISTRAL_API_KEY` (Windows OCR images often require `POPPLER_PATH`).
- Smoke test: `python main.py --test` (checks environment and exits 0 on success).
- Run menu: `python main.py` or non-interactive: `python main.py --mode hybrid --no-interactive`.
- Quick start: `bash quick_start.sh` (macOS/Linux) or `./run_converter.bat` (Windows).

## Coding Style & Naming Conventions
- Python 3.10+, PEP 8, 4‑space indentation, type hints where practical.
- Names: `snake_case` for functions/vars, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants/env.
- Follow module responsibilities above; use `pathlib.Path`; write files via `utils.write_text`.
- No enforced formatter/linters in repo; keep diffs small and focused.

## Testing Guidelines
- No unit tests yet. Use `--test` and real files under `input/` for verification.
- Validate outputs in `output_md/`, `output_txt/`, `output_images/`; review `logs/metadata/*.json`.
- Include a minimal repro command in PRs (e.g., the exact `--mode` used).

## Commit & Pull Request Guidelines
- Conventional commits preferred: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`; scoped examples: `fix(local_converter): …`.
- PRs should include: purpose, summary of changes, sample command/output paths, any new env vars, and linked issues.

## Security & Configuration Tips
- Do not commit `.env`, API keys, or `logs/` with `SAVE_MISTRAL_JSON=true`.
- When adding config, update `.env.example` and `config.py` defaults.
- Respect `BATCH_SIZE`, cache TTL (`CACHE_DURATION_HOURS`), and keep writes inside project dirs.

